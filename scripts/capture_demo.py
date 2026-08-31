#!/usr/bin/env python3
"""Capture the local Streamlit demo and package a captioned submission MP4.

The app is the source of every visual.  This script only adds an accessibility
caption band whose numerical claims are loaded from retained evaluation data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from textwrap import wrap
from urllib.error import URLError
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Locator, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "artifacts" / "video"
FRAMES_DIR = VIDEO_DIR / "frames"
METRICS_PATH = ROOT / "artifacts" / "evaluation" / "metrics.json"
PORT = 8501
VIEWPORT = {"width": 1920, "height": 1080}
FONT_PATHS = (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a legible system font, with Pillow's default as a last resort."""
    candidates = FONT_PATHS[::-1] if bold else FONT_PATHS
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _metrics() -> dict[str, object]:
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def _captions(metrics: dict[str, object]) -> list[dict[str, object]]:
    """Build the narrated sequence directly from the retained metric record."""
    baseline = metrics["baseline"]
    final = metrics["final"]
    unverified = metrics["unverified_agent"]
    unsafe = metrics["removed_unsafe_recurrence"]
    case_count = len(metrics["case_fingerprints"])
    return [
        {
            "frame": "problem-card",
            "duration": 28,
            "caption": "Alex needs a clear, private way to spot savings opportunities before the next paycheck. This local prototype uses only a synthetic demo.",
        },
        {
            "frame": "baseline-result",
            "duration": 24,
            "caption": f"The retained baseline missed too much: F1 {baseline['f1']} with {baseline['unsupported_claims']} unsupported claims across {case_count} synthetic cases.",
        },
        {
            "frame": "demo-input",
            "duration": 20,
            "caption": "Start with Alex's synthetic local demo. Uploads remain in the app session, and no bank, merchant, or receipt image is contacted.",
        },
        {
            "frame": "verified-plan",
            "duration": 51,
            "caption": "One click produces a verified savings plan. The app offers suggestions and estimates; it does not alter accounts or subscriptions.",
        },
        {
            "frame": "evidence",
            "duration": 33,
            "caption": "Open each recommendation to inspect the exact synthetic transaction evidence. This makes the recommendation reviewable before anyone acts.",
        },
        {
            "frame": "approval-simulation",
            "duration": 28,
            "caption": "A human checkpoint is explicit: choose a verified subscription, acknowledge the simulation, then simulate locally. No merchant is contacted; the human checkpoint is not prediction-scored.",
        },
        {
            "frame": "comparison",
            "duration": 38,
            "caption": f"Measured comparison: final precision {final['precision']}, recall {final['recall']}, F1 {final['f1']}; baseline F1 {baseline['f1']}. Final unsupported claims: {final['unsupported_claims']}.",
        },
        {
            "frame": "changelog",
            "duration": 26,
            "caption": f"Candidate tools drive opportunity F1 ({unverified['f1']} before verification). The verifier reduces unsupported claims from {unverified['unsupported_claims']} to {final['unsupported_claims']}; the human checkpoint is not prediction-scored.",
        },
        {
            "frame": "hot-take",
            "duration": 23,
            "caption": f"We removed the unsafe 26–35-day recurrence-only experiment: it reached F1 {unsafe['f1']} but left {unsafe['unsupported_claims']} unsupported claims. Recurrence is not proof of cancellability.",
        },
        {
            "frame": "closing",
            "duration": 9,
            "caption": f"Paycheck Guardian is offline, local-only, and evaluated on {case_count} synthetic cases at model cost ${metrics['model_cost_usd']}. Review evidence first; decide second.",
        },
    ]


def write_recording_materials(metrics: dict[str, object], sequence: list[dict[str, object]]) -> None:
    """Create recording-ready materials, generated from the same metric input."""
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    timing = [
        ("0:00–0:28", "user and bottleneck"),
        ("0:28–0:52", "baseline failure"),
        ("0:52–1:12", "Alex demo input"),
        ("1:12–2:03", "verified plan"),
        ("2:03–2:36", "expanded evidence"),
        ("2:36–3:04", "human checkpoint"),
        ("3:04–3:42", "measured comparison"),
        ("3:42–4:08", "changelog and biggest contribution"),
        ("4:08–4:31", "removed unsafe experiment and hot take"),
        ("4:31–4:40", "close"),
    ]
    script = [
        "# Paycheck Guardian — five-minute solution video script",
        "",
        "This script is generated by `scripts/capture_demo.py` from `artifacts/evaluation/metrics.json`. It describes a local-only synthetic demo; no real financial data, credential, bank, merchant, or account is shown.",
        "",
        f"Retained evaluation: offline mode, {len(metrics['case_fingerprints'])} synthetic cases, final F1 {metrics['final']['f1']}, baseline F1 {metrics['baseline']['f1']}, model cost ${metrics['model_cost_usd']}.",
        "",
    ]
    storyboard = [
        "# Paycheck Guardian — capture storyboard",
        "",
        "Every visual below is captured from the local Streamlit UI at 1920×1080. Caption figures are generated from `artifacts/evaluation/metrics.json`; captions are overlaid on those real UI captures.",
        "",
        "| Time | Captured UI frame | Purpose |",
        "| --- | --- | --- |",
    ]
    cursor = 0
    for item, (window, purpose) in zip(sequence, timing, strict=True):
        minutes, seconds = divmod(cursor, 60)
        script.extend([f"## {minutes}:{seconds:02d} — {item['frame'].replace('-', ' ').title()}", "", str(item["caption"]), ""])
        storyboard.append(f"| {window} | `{item['frame']}.png` | {purpose} |")
        cursor += int(item["duration"])
    (VIDEO_DIR / "script.md").write_text("\n".join(script).rstrip() + "\n", encoding="utf-8")
    (VIDEO_DIR / "storyboard.md").write_text("\n".join(storyboard).rstrip() + "\n", encoding="utf-8")


def _wait_for_health(process: subprocess.Popen[bytes]) -> None:
    """Wait for Streamlit's health endpoint, failing early if the server exits."""
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Streamlit exited before it became ready.")
        try:
            with urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=1) as response:
                if response.read().decode("utf-8").strip() == "ok":
                    return
        except URLError:
            time.sleep(0.4)
    raise TimeoutError("Timed out waiting for the local Streamlit health endpoint.")


def _settle(page: Page) -> None:
    page.wait_for_timeout(700)
    page.locator("[data-testid='stAppViewContainer']").wait_for(state="visible")


def _capture(
    page: Page,
    name: str,
    required_text: str | None = None,
    required_locator: Locator | None = None,
) -> None:
    """Assert the expected Streamlit state is visible before taking a frame."""
    assert (required_text is None) != (required_locator is None)
    locator = required_locator or page.get_by_text(required_text or "", exact=False).first
    locator.wait_for(state="visible")
    path = FRAMES_DIR / f"{name}.png"
    page.screenshot(path=str(path))


def _scroll_to_text(page: Page, text: str) -> None:
    page.get_by_text(text, exact=False).first.scroll_into_view_if_needed()
    _settle(page)


def _place_text_near_top(page: Page, text: str) -> None:
    """Position a visible heading so its associated card is in the frame too."""
    locator = page.get_by_text(text, exact=False).first
    locator.evaluate(
        "element => element.scrollIntoView({block: 'start', inline: 'nearest', behavior: 'instant'})"
    )
    _settle(page)


def capture_ui_frames() -> None:
    """Drive the demo with Chromium and save only authentic Streamlit screens."""
    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)
    FRAMES_DIR.mkdir(parents=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        page.goto(f"http://127.0.0.1:{PORT}", wait_until="networkidle")
        _settle(page)
        _capture(page, "problem-card", "Privacy and demo notice")
        print("captured problem-card", flush=True)

        page.get_by_role("button", name="Load Alex's synthetic demo").click()
        _settle(page)
        baseline_expander = page.get_by_text("Retained baseline comparison", exact=True).first
        baseline_expander.click()
        _settle(page)
        _place_text_near_top(page, "Baseline F1")
        _capture(page, "baseline-result", "Baseline F1")
        baseline_expander.click()
        _settle(page)
        _capture(page, "demo-input", "Parsed 8 transactions")
        print("captured demo-input", flush=True)

        page.get_by_role("button", name="Analyze verified savings options").click()
        _settle(page)
        _place_text_near_top(page, "Verified savings plan")
        _capture(page, "verified-plan", "Verified savings plan")
        print("captured verified-plan", flush=True)

        _scroll_to_text(page, "Set a spending limit for DoorDash")
        print("located DoorDash recommendation", flush=True)
        evidence_expander = page.locator("details").filter(has_text="Evidence (3 transactions)").first
        evidence_expander.locator("summary").scroll_into_view_if_needed()
        evidence_expander.locator("summary").click()
        _settle(page)
        _capture(
            page,
            "evidence",
            required_locator=evidence_expander.get_by_text("ccbf9f1b47c7", exact=False).first,
        )
        print("captured evidence", flush=True)

        _scroll_to_text(page, "Local cancellation simulation")
        subscription_picker = page.get_by_label("Choose a verified subscription to simulate cancelling")
        subscription_picker.click()
        subscription_picker.press("ArrowDown")
        subscription_picker.press("ArrowDown")
        subscription_picker.press("Enter")
        print("selected cancellation simulation", flush=True)
        acknowledgement = page.locator("label").filter(has_text="I understand this is only a simulation")
        acknowledgement.click()
        page.get_by_role("button", name="Simulate cancellation locally").click()
        _settle(page)
        confirmation = page.get_by_text("Cancellation simulated locally", exact=False).first
        confirmation.evaluate(
            "element => element.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'})"
        )
        _settle(page)
        acknowledgement.wait_for(state="visible")
        _capture(page, "approval-simulation", required_locator=confirmation)
        print("captured approval-simulation", flush=True)

        baseline_expander = page.get_by_text("Retained baseline comparison", exact=True).first
        baseline_expander.scroll_into_view_if_needed()
        baseline_expander.click()
        _settle(page)
        _capture(page, "comparison", "Verified workflow F1")
        print("captured comparison", flush=True)

        _scroll_to_text(page, "Verified savings plan")
        _capture(page, "changelog", "Verified savings plan")
        print("captured changelog", flush=True)

        _scroll_to_text(page, "Privacy and demo notice")
        _capture(page, "hot-take", "Privacy and demo notice")
        _capture(page, "closing", "Privacy and demo notice")
        print("captured hot-take and closing", flush=True)
        browser.close()


def _caption_frame(source: Path, destination: Path, caption: str) -> None:
    """Overlay a readable caption while preserving the underlying UI capture."""
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    checkpoint_frame = source.stem == "approval-simulation"
    caption_top = 135 if checkpoint_frame else height - 260
    caption_bottom = 390 if checkpoint_frame else height
    draw.rectangle((0, caption_top, width, caption_bottom), fill=(5, 14, 31, 222))
    draw.rounded_rectangle((55, 10, 900, 66), radius=18, fill=(18, 69, 89, 224))
    draw.text((80, 24), "PAYCHECK GUARDIAN  •  OFFLINE SYNTHETIC DEMO", font=_font(27, bold=True), fill=(236, 253, 245, 255))
    caption_font = _font(42)
    lines = wrap(caption, width=76)
    y = caption_top + 50
    for line in lines:
        draw.text((75, y), line, font=caption_font, fill=(255, 255, 255, 255))
        y += 53
    draw.text((75, caption_bottom - 42), "Local-only prototype · estimates require review · no bank or merchant contact", font=_font(24), fill=(188, 211, 235, 255))
    image.save(destination, quality=95)


def build_video(sequence: list[dict[str, object]]) -> Path:
    """Encode all captioned UI captures as H.264/yuv420p with a silent audio track."""
    captioned_dir = FRAMES_DIR / "captioned"
    captioned_dir.mkdir()
    concat = FRAMES_DIR / "concat.txt"
    entries: list[str] = []
    for index, item in enumerate(sequence, start=1):
        source = FRAMES_DIR / f"{item['frame']}.png"
        target = captioned_dir / f"{index:02d}-{item['frame']}.png"
        _caption_frame(source, target, str(item["caption"]))
        # A still-image concat input contributes one extra second at its native
        # image-demuxer rate. Compensate at each transition so the written
        # storyboard timestamps match the encoded MP4.
        encoded_hold = int(item["duration"]) - (0 if index == len(sequence) else 1)
        entries.extend((f"file '{target.relative_to(FRAMES_DIR).as_posix()}'", f"duration {encoded_hold}"))
    entries.append("file 'captioned/10-closing.png'")
    concat.write_text("\n".join(entries) + "\n", encoding="utf-8")
    output = VIDEO_DIR / "paycheck-guardian-demo.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-movflags", "+faststart", str(output),
        ],
        check=True,
    )
    return output


def main() -> None:
    metrics = _metrics()
    sequence = _captions(metrics)
    write_recording_materials(metrics, sequence)
    command = [
        sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
        "--server.address", "127.0.0.1", "--server.port", str(PORT), "--browser.gatherUsageStats", "false",
    ]
    process = subprocess.Popen(command, cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        _wait_for_health(process)
        capture_ui_frames()
        output = build_video(sequence)
        print(f"Wrote {output.relative_to(ROOT)}")
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
