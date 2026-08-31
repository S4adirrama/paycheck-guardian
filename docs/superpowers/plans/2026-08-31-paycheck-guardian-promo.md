# Paycheck Guardian Promo Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible 60-second Remotion product film for the native Paycheck Guardian iOS application with real Simulator screens, English narration, original music, and verified H.264/AAC delivery artifacts.

**Architecture:** A standalone TypeScript/Remotion project owns timing, copy, reusable motion components, and eight scene components. Committed native screenshots are copied into Remotion’s public assets; deterministic shell scripts generate narration/music and validate the rendered MP4 with FFmpeg tools.

**Tech Stack:** Node.js 22, TypeScript 5, React 19, Remotion 4.0.518, Vitest, macOS `say`, FFmpeg/ffprobe 8.0.1.

**Spec:** `docs/superpowers/specs/2026-08-31-paycheck-guardian-promo-design.md`

## Global Constraints

- The final composition is exactly 1,800 frames at 30 fps and renders at 1920×1080.
- The delivered video is approximately 60.0 seconds, H.264 video with AAC audio.
- Narration is English, calm, and confident; key claims are duplicated visibly.
- Music is generated locally for this project and does not use a third-party copyrighted track.
- Product imagery comes only from `artifacts/ios/screenshots/`.
- Claims never imply guaranteed savings, bank connectivity, merchant access, or real cancellation.
- The closing disclosure reads `Educational prototype. No real financial actions.` for the full final scene.
- Retained source, assets, metadata, and frames expose no personal path, credential, account value, or environment secret.

---

## File Structure

```text
promo/
├── package.json
├── package-lock.json
├── tsconfig.json
├── remotion.config.ts
├── README.md
├── public/
│   ├── screens/01-welcome.png ... 05-agent-trace.png
│   └── audio/narration.wav, soundtrack.wav
├── scripts/
│   ├── prepare-assets.sh
│   ├── generate-audio.sh
│   └── verify-render.sh
└── src/
    ├── index.ts
    ├── Root.tsx
    ├── Promo.tsx
    ├── content.ts
    ├── timing.ts
    ├── content.test.ts
    ├── timing.test.ts
    ├── components/
    │   ├── BrandMark.tsx
    │   ├── Caption.tsx
    │   ├── PhoneFrame.tsx
    │   ├── SceneBackground.tsx
    │   └── Typography.tsx
    └── scenes/
        ├── HookScene.tsx
        ├── ProblemScene.tsx
        ├── PromiseScene.tsx
        ├── PlanScene.tsx
        ├── EvidenceScene.tsx
        ├── ApprovalScene.tsx
        ├── TraceScene.tsx
        └── FinaleScene.tsx
artifacts/ios/promo/
├── paycheck-guardian-promo.mp4
├── poster.png
├── contact-sheet.png
└── media-report.txt
```

---

### Task 1: Remotion Foundation and Exact Timeline

**Files:**
- Create: `promo/package.json`
- Create: `promo/tsconfig.json`
- Create: `promo/remotion.config.ts`
- Create: `promo/src/index.ts`
- Create: `promo/src/Root.tsx`
- Create: `promo/src/timing.ts`
- Create: `promo/src/timing.test.ts`

**Interfaces:**
- Produces: `FPS`, `WIDTH`, `HEIGHT`, `TOTAL_FRAMES`, `SceneKey`, `SceneTiming`, `SCENES`, `scene(key)`, and the registered `PaycheckGuardianPromo` composition.
- Consumes: no earlier task output.

- [ ] **Step 1: Add the pinned package manifest and TypeScript configuration**

Use exact runtime versions and scripts:

```json
{
  "name": "paycheck-guardian-promo",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "studio": "remotion studio src/index.ts",
    "render": "remotion render src/index.ts PaycheckGuardianPromo ../artifacts/ios/promo/paycheck-guardian-promo.mp4 --codec=h264 --audio-codec=aac --crf=18",
    "still": "remotion still src/index.ts PaycheckGuardianPromo ../artifacts/ios/promo/poster.png --frame=1665"
  },
  "dependencies": {
    "@remotion/cli": "4.0.518",
    "@remotion/media-utils": "4.0.518",
    "react": "19.1.1",
    "react-dom": "19.1.1",
    "remotion": "4.0.518"
  },
  "devDependencies": {
    "@types/react": "19.1.10",
    "@types/react-dom": "19.1.7",
    "typescript": "5.9.2",
    "vitest": "3.2.4"
  }
}
```

Set `jsx` to `react-jsx`, `module` to `ESNext`, `moduleResolution` to `Bundler`, `strict` to `true`, and include `src/**/*.ts` plus `src/**/*.tsx`.

- [ ] **Step 2: Install dependencies and retain the lockfile**

Run: `cd promo && npm install`

Expected: `package-lock.json` is created and `npm ls --depth=0` exits zero with the pinned packages.

- [ ] **Step 3: Write the failing timeline tests**

```ts
import {describe, expect, it} from 'vitest';
import {FPS, HEIGHT, SCENES, TOTAL_FRAMES, WIDTH} from './timing';

describe('promo timeline', () => {
  it('is exactly sixty seconds at 30 fps in full HD', () => {
    expect(FPS).toBe(30);
    expect(TOTAL_FRAMES).toBe(1800);
    expect(WIDTH).toBe(1920);
    expect(HEIGHT).toBe(1080);
  });

  it('covers the timeline contiguously', () => {
    expect(SCENES[0].from).toBe(0);
    SCENES.slice(1).forEach((item, index) => {
      expect(item.from).toBe(SCENES[index].from + SCENES[index].duration);
    });
    const last = SCENES.at(-1)!;
    expect(last.from + last.duration).toBe(TOTAL_FRAMES);
  });
});
```

- [ ] **Step 4: Run the focused test and observe the missing-module failure**

Run: `cd promo && npm test -- src/timing.test.ts`

Expected: FAIL because `src/timing.ts` does not exist.

- [ ] **Step 5: Implement the exact storyboard timing**

```ts
export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const TOTAL_FRAMES = 1800;

export type SceneKey = 'hook' | 'problem' | 'promise' | 'plan' | 'evidence' | 'approval' | 'trace' | 'finale';
export type SceneTiming = {key: SceneKey; from: number; duration: number};

export const SCENES: SceneTiming[] = [
  {key: 'hook', from: 0, duration: 180},
  {key: 'problem', from: 180, duration: 210},
  {key: 'promise', from: 390, duration: 210},
  {key: 'plan', from: 600, duration: 330},
  {key: 'evidence', from: 930, duration: 300},
  {key: 'approval', from: 1230, duration: 240},
  {key: 'trace', from: 1470, duration: 180},
  {key: 'finale', from: 1650, duration: 150},
];

export const scene = (key: SceneKey): SceneTiming => SCENES.find((item) => item.key === key)!;
```

Register `PaycheckGuardianPromo` with the exact timing constants in `Root.tsx`, and call `registerRoot(RemotionRoot)` in `index.ts`.

- [ ] **Step 6: Verify the timeline and scaffold**

Run: `cd promo && npm test -- src/timing.test.ts && npm run typecheck`

Expected: 2 timeline tests pass; TypeScript exits zero.

- [ ] **Step 7: Commit the foundation**

```bash
git add promo/package.json promo/package-lock.json promo/tsconfig.json promo/remotion.config.ts promo/src/index.ts promo/src/Root.tsx promo/src/timing.ts promo/src/timing.test.ts
git commit -m "feat(promo): scaffold exact Remotion timeline"
```

---

### Task 2: Claims, Assets, and Reusable Visual System

**Files:**
- Create: `promo/src/content.ts`
- Create: `promo/src/content.test.ts`
- Create: `promo/src/components/BrandMark.tsx`
- Create: `promo/src/components/Caption.tsx`
- Create: `promo/src/components/PhoneFrame.tsx`
- Create: `promo/src/components/SceneBackground.tsx`
- Create: `promo/src/components/Typography.tsx`
- Create: `promo/scripts/prepare-assets.sh`
- Create: `promo/public/screens/01-welcome.png` through `05-agent-trace.png`

**Interfaces:**
- Consumes: `FPS` from `src/timing.ts` and committed iOS screenshots.
- Produces: `NARRATION`, `CAPTIONS`, `DISCLOSURE`, `METRICS`, reusable scene primitives, and deterministic public screen assets.

- [ ] **Step 1: Write failing safety-copy tests**

```ts
import {describe, expect, it} from 'vitest';
import {CAPTIONS, DISCLOSURE, METRICS, NARRATION} from './content';

describe('promo claims', () => {
  it('retains exact verified product values', () => {
    expect(METRICS).toEqual({beforePaycheck: '$44.87', monthly: '$97.49', evidenceMonthly: '$63.00', evidencePaycheck: '$29.00'});
  });

  it('states every safety boundary', () => {
    const copy = [NARRATION, DISCLOSURE, ...CAPTIONS.map((item) => item.text)].join(' ').toLowerCase();
    expect(copy).toContain('without connecting to your bank');
    expect(copy).toContain('no merchant is contacted');
    expect(copy).toContain('no real cancellation');
    expect(DISCLOSURE).toBe('Educational prototype. No real financial actions.');
    expect(copy).not.toContain('guaranteed savings');
  });
});
```

- [ ] **Step 2: Run the focused copy test and observe failure**

Run: `cd promo && npm test -- src/content.test.ts`

Expected: FAIL because `src/content.ts` does not exist.

- [ ] **Step 3: Implement centralized narration, captions, and metrics**

Define the approved 113-word narration verbatim from the spec. Define timed caption records as `{from: number; duration: number; text: string; accent?: string}` and ensure the closing disclosure begins at frame 1650 and lasts 150 frames.

- [ ] **Step 4: Implement reusable motion components**

`SceneBackground` renders navy/blue radial gradients, a subtle grid, deterministic particles based on frame number, and a 120 px safe area. `PhoneFrame` renders a 430×932 rounded device shell, masks a screenshot with `Img`, and supports `scale`, `rotate`, and `glow` props. `Caption` uses `spring()` and `interpolate()` for entry/exit opacity. `BrandMark` recreates the mint shield as inline SVG so no external logo asset is needed.

- [ ] **Step 5: Add deterministic asset preparation**

```bash
#!/bin/bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
source_dir="$repo_root/artifacts/ios/screenshots"
target_dir="$repo_root/promo/public/screens"
mkdir -p "$target_dir"
for name in 01-welcome 02-verified-plan 03-evidence 04-simulated-approval 05-agent-trace; do
  test -f "$source_dir/$name.png"
  cp "$source_dir/$name.png" "$target_dir/$name.png"
done
```

- [ ] **Step 6: Prepare assets and verify copy/components**

Run: `chmod +x promo/scripts/prepare-assets.sh && promo/scripts/prepare-assets.sh && cd promo && npm test -- src/content.test.ts && npm run typecheck`

Expected: 2 copy tests pass, all five images exist in `public/screens`, and TypeScript exits zero.

- [ ] **Step 7: Commit content and visual primitives**

```bash
git add promo/src/content.ts promo/src/content.test.ts promo/src/components promo/scripts/prepare-assets.sh promo/public/screens
git commit -m "feat(promo): add safe copy and visual system"
```

---

### Task 3: Eight Animated Product Scenes

**Files:**
- Create: `promo/src/Promo.tsx`
- Create: `promo/src/scenes/HookScene.tsx`
- Create: `promo/src/scenes/ProblemScene.tsx`
- Create: `promo/src/scenes/PromiseScene.tsx`
- Create: `promo/src/scenes/PlanScene.tsx`
- Create: `promo/src/scenes/EvidenceScene.tsx`
- Create: `promo/src/scenes/ApprovalScene.tsx`
- Create: `promo/src/scenes/TraceScene.tsx`
- Create: `promo/src/scenes/FinaleScene.tsx`
- Modify: `promo/src/Root.tsx`

**Interfaces:**
- Consumes: `SCENES`, `scene()`, `CAPTIONS`, `METRICS`, and all reusable visual components.
- Produces: `Promo` — the complete silent visual composition used by audio and render tasks.

- [ ] **Step 1: Add a failing composition bundle check**

Run: `cd promo && npx remotion compositions src/index.ts`

Expected: FAIL because `Root.tsx` imports the not-yet-created `Promo` component.

- [ ] **Step 2: Implement Hook, Problem, and Promise scenes**

Use `useCurrentFrame`, `spring`, `interpolate`, and `Easing` only; do not use CSS keyframes or wall-clock time. Hook animates expense fragments into the headline. Problem presents three signal cards (`Recurring`, `Duplicate`, `Discretionary`). Promise introduces the shield and `LOCAL • SYNTHETIC DEMO`, then flies in `01-welcome.png` inside `PhoneFrame`.

- [ ] **Step 3: Implement Plan and Evidence scenes**

Plan morphs the welcome device into `02-verified-plan.png`, enlarges `$44.87`, and labels it `Potential before next paycheck` plus `not guaranteed`. Evidence uses `03-evidence.png` and calls out `$63.00 monthly`, `$29.00 before paycheck`, `Transactions`, and `Calculation` without inventing additional values.

- [ ] **Step 4: Implement Approval, Trace, and Finale scenes**

Approval transitions to `04-simulated-approval.png` and draws a mint confirmation ring around `Local simulation confirmed`, with `No merchant contacted` beside it. Trace pans through `05-agent-trace.png` and animates paired `Tool Called → Tool Result → Verified` labels. Finale holds the shield, product name, `Verified. Explainable. In your control.`, and the disclosure for all 150 frames.

- [ ] **Step 5: Assemble scenes with exact sequences and global captions**

In `Promo.tsx`, render each scene in a `Sequence` using its central timing record. Add the global `Caption` overlay after scene sequences so captions stay above device frames. Use `premountFor={FPS}` for screenshot-heavy scenes to avoid first-frame flashes.

- [ ] **Step 6: Verify the composition bundles and exposes one exact render target**

Run: `cd promo && npm run typecheck && npx remotion compositions src/index.ts`

Expected: TypeScript exits zero and Remotion lists exactly `PaycheckGuardianPromo`, 1920×1080, 30 fps, 1800 frames.

- [ ] **Step 7: Commit the visual film**

```bash
git add promo/src/Promo.tsx promo/src/scenes promo/src/Root.tsx
git commit -m "feat(promo): animate complete product story"
```

---

### Task 4: Local Narration and Original Soundtrack

**Files:**
- Create: `promo/scripts/generate-audio.sh`
- Create: `promo/scripts/verify-audio.sh`
- Create: `promo/public/audio/narration.wav`
- Create: `promo/public/audio/soundtrack.wav`
- Modify: `promo/src/Promo.tsx`

**Interfaces:**
- Consumes: approved narration from `src/content.ts` and the 60-second timeline.
- Produces: two deterministic 48 kHz stereo WAV assets and audio-backed `Promo` composition.

- [ ] **Step 1: Write the failing audio verifier**

```bash
#!/bin/bash
set -euo pipefail
audio_dir="$(cd "$(dirname "$0")/../public" && pwd)/audio"
for name in narration soundtrack; do
  file="$audio_dir/$name.wav"
  test -s "$file"
  codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$file")"
  rate="$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of default=nw=1:nk=1 "$file")"
  test "$codec" = "pcm_s16le"
  test "$rate" = "48000"
done
```

- [ ] **Step 2: Run the verifier and observe missing-asset failure**

Run: `chmod +x promo/scripts/verify-audio.sh && promo/scripts/verify-audio.sh`

Expected: FAIL because `promo/public/audio/narration.wav` is absent.

- [ ] **Step 3: Implement narration generation with voice fallback**

`generate-audio.sh` selects `Samantha` when `say -v '?'` lists it, otherwise the first `en_US` voice. It writes the approved narration with explicit `[[slnc N]]` pauses to a temporary AIFF at 145 words per minute, then converts it with FFmpeg to stereo PCM 48 kHz, applies loudness normalization near `-16 LUFS`, pads with silence, and trims to exactly 60 seconds.

- [ ] **Step 4: Implement an original electronic soundtrack**

Use only FFmpeg `lavfi` sources: layer low-volume 110 Hz and 220 Hz sine beds, a filtered 440/554 Hz pulse, and a short noise-based percussion transient. Apply fade-in, fade-out, and `loudnorm` near `-27 LUFS`; mix to stereo PCM 48 kHz for exactly 60 seconds. No downloaded audio enters the project.

- [ ] **Step 5: Add audio to Remotion**

Render `narration.wav` and `soundtrack.wav` from frame 0 with Remotion `Audio` and `staticFile()`. Set narration volume to `1`, soundtrack volume to `0.30`, and fade soundtrack below `0.12` during the final spoken product name.

- [ ] **Step 6: Generate and validate both tracks**

Run: `chmod +x promo/scripts/generate-audio.sh && promo/scripts/generate-audio.sh && promo/scripts/verify-audio.sh && cd promo && npm run typecheck`

Expected: both files are PCM 48 kHz stereo, approximately 60 seconds, non-silent, and TypeScript exits zero.

- [ ] **Step 7: Commit audio production**

```bash
git add promo/scripts/generate-audio.sh promo/scripts/verify-audio.sh promo/public/audio promo/src/Promo.tsx
git commit -m "feat(promo): add narration and original soundtrack"
```

---

### Task 5: Final Render, Contact Sheet, and Reproduction Guide

**Files:**
- Create: `promo/scripts/verify-render.sh`
- Create: `promo/README.md`
- Create: `artifacts/ios/promo/paycheck-guardian-promo.mp4`
- Create: `artifacts/ios/promo/poster.png`
- Create: `artifacts/ios/promo/contact-sheet.png`
- Create: `artifacts/ios/promo/media-report.txt`
- Modify: `README-IOS.md`

**Interfaces:**
- Consumes: complete `PaycheckGuardianPromo`, public screens, and generated audio.
- Produces: hackathon-ready MP4, poster, contact sheet, media evidence, and exact reproduction commands.

- [ ] **Step 1: Write the failing render verifier**

The script must fail unless the MP4 exists, contains H.264 video and AAC audio, is 1920×1080, reports 30 fps, and has a duration between 59.95 and 60.05 seconds. Use `ffprobe -of json`, `jq -e`, and a full decode with `ffmpeg -v error -i "$video" -f null -`.

- [ ] **Step 2: Run the verifier and observe missing-video failure**

Run: `chmod +x promo/scripts/verify-render.sh && promo/scripts/verify-render.sh`

Expected: FAIL because `artifacts/ios/promo/paycheck-guardian-promo.mp4` does not exist.

- [ ] **Step 3: Render the final composition and poster**

Run:

```bash
cd promo
npm test
npm run typecheck
npm run render
npm run still
```

Expected: tests/typecheck pass; MP4 and poster are produced.

- [ ] **Step 4: Create a representative contact sheet**

Extract frames at seconds `2, 8, 16, 25, 35, 45, 52, 57` and tile them into a 4×2 PNG with FFmpeg `tile=4x2`, scaled to 480×270 per cell. Save `artifacts/ios/promo/contact-sheet.png`.

- [ ] **Step 5: Validate the complete media file and retain the report**

Run: `promo/scripts/verify-render.sh | tee artifacts/ios/promo/media-report.txt`

Expected: H.264, AAC, 1920×1080, 30 fps, ~60.000 seconds, full decode clean.

- [ ] **Step 6: Inspect the poster, contact sheet, and scene frames**

Use `view_image` on the poster/contact sheet and individually inspect at least one original-resolution frame from each scene. If any title, caption, screenshot, metric, or disclosure clips, create a focused regression check, fix the responsible component, rerender, and repeat media validation.

- [ ] **Step 7: Add exact reproduction documentation**

Document prerequisites, `npm install`, asset/audio generation, `npm test`, typecheck, render, still, and verification commands in `promo/README.md`. Link the MP4, poster, contact sheet, and source instructions from `README-IOS.md`. State that narration uses the local system voice and may sound slightly different if the fallback is selected.

- [ ] **Step 8: Run privacy and repository checks**

Scan `promo/` and `artifacts/ios/promo/` for `/Users/`, the user name, secret-shaped strings, authorization values, and values from sensitive environment-key names without printing the values. Run `git diff --check` and confirm no build/cache directory is tracked.

- [ ] **Step 9: Commit final promo deliverables**

```bash
git add promo/README.md promo/scripts/verify-render.sh artifacts/ios/promo README-IOS.md
git commit -m "docs(promo): deliver verified hackathon product film"
```

- [ ] **Step 10: Run the complete final audit**

Run: `cd promo && npm test && npm run typecheck && cd .. && promo/scripts/verify-audio.sh && promo/scripts/verify-render.sh && git diff --check && git status --short`

Expected: all tests and media checks pass; status is empty.
