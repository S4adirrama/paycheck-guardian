"""Generate stable synthetic receipt PNG/text pairs without network access."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


RECEIPTS = (
    ("receipt-01", "2026-05-02", "DoorDash", "28.40"),
    ("receipt-02", "2026-05-03", "Netflix", "15.49"),
    ("receipt-03", "2026-05-04", "Planet Fitness", "24.99"),
)
CANVAS = (720, 900)


def _font() -> ImageFont.ImageFont:
    """Use a local, system-provided monospaced font when present."""
    for path in (
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, 28)
    return ImageFont.load_default()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "data" / "demo" / "receipts"
    output.mkdir(parents=True, exist_ok=True)
    font = _font()
    for name, date, merchant, total in RECEIPTS:
        text = f"DATE: {date}\nMERCHANT: {merchant}\nTOTAL: {total}\n"
        (output / f"{name}.txt").write_text(text, encoding="utf-8", newline="\n")
        image = Image.new("RGB", CANVAS, "white")
        draw = ImageDraw.Draw(image)
        draw.multiline_text((64, 80), "PAYCHECK GUARDIAN\n\n" + text, fill="black", font=font, spacing=18)
        image.save(output / f"{name}.png", format="PNG", optimize=False)


if __name__ == "__main__":
    main()
