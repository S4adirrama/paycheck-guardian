# Paycheck Guardian Promo Video — Design Specification

**Date:** 2026-08-31
**Status:** Approved for implementation
**Format:** 60 seconds, 1920×1080, 30 fps, H.264 video with AAC audio
**Audience:** US hackathon judges and demo viewers

## Objective

Create a polished product-cinematic promo for the native Paycheck Guardian iOS application. The video must quickly explain the problem, demonstrate the working product with real Simulator screens, communicate its evidence-first safety model, and end with a memorable product promise. It must be understandable with or without sound.

## Creative Direction

The visual language follows the application: deep navy backgrounds, electric blue gradients, mint verification accents, white typography, soft glows, and restrained particle motion. Real app screenshots appear inside a custom animated iPhone frame. Motion uses smooth camera moves, spring easing, staggered typography, and subtle depth without distracting from the product.

English narration uses a calm, confident fintech tone. Every important spoken phrase is reinforced by visible text. The soundtrack is an original light electronic pulse produced specifically for the video and mixed below the voice-over. No third-party copyrighted media is required.

## Storyboard

| Time | Scene | Visual | Narration intent |
| --- | --- | --- | --- |
| 0–6 s | Hook | Fast-moving expense fragments resolve into a single paycheck line | “Your paycheck shouldn’t disappear without answers.” |
| 6–13 s | Problem | Recurring payment, duplicate charge, and discretionary-spend signals orbit a phone silhouette | Explain that hidden patterns are difficult to review safely |
| 13–20 s | Promise | Paycheck Guardian mark, local/synthetic badges, and welcome screen | Introduce a local-first evidence-backed assistant with no bank connection |
| 20–31 s | Verified plan | Welcome screen transitions to the real Verified Plan; `$44.87` receives visual emphasis | Show that the app finds and independently verifies opportunities before payday |
| 31–41 s | Evidence | Real evidence sheet with `$63.00` monthly and `$29.00` before-paycheck calculation | Explain that every estimate is traceable to transactions and arithmetic |
| 41–49 s | Human checkpoint | Approval interaction resolves into `Local simulation confirmed` | State that the person remains in control and no real cancellation occurs |
| 49–55 s | Agent trace | Real privacy-safe trace screen with tool-call/result rhythm | Show transparent orchestration and opaque identifiers |
| 55–60 s | Finale | Product mark, three-value lockup, and safety disclosure | “Verified. Explainable. In your control.” |

## Narration

The final script targets approximately 110–125 English words so it remains intelligible within 60 seconds with natural pauses:

> Your paycheck shouldn’t disappear without answers. Recurring charges, duplicates, and everyday spending patterns can hide in plain sight. Paycheck Guardian reviews local transaction evidence and turns it into a short, verified plan — without connecting to your bank. Run the demo and see what could stay in your account before the next paycheck. Every recommendation is independently checked. Open the evidence to inspect the transactions, the calculation, the confidence, and the caveat. Then you decide: approve a local simulation, or dismiss it instantly. No merchant is contacted. No real cancellation happens. And the privacy-safe agent trace shows how every tool call and verification decision was made. Paycheck Guardian. Verified. Explainable. In your control.

The on-screen closing disclosure is: `Educational prototype. No real financial actions.`

## Technical Architecture

The source lives in `promo/` as an independent Remotion + TypeScript project. It has no runtime dependency on the iOS app and consumes committed screenshots from `artifacts/ios/screenshots/`.

- `src/Root.tsx` registers the 60-second composition.
- `src/Promo.tsx` sequences the eight storyboard scenes.
- `src/scenes/` contains one focused component per scene.
- `src/components/` contains reusable typography, phone frame, badges, background, captions, and transition primitives.
- `public/` contains the narration, original soundtrack, and copies of required visual assets.
- `scripts/` contains deterministic local audio generation and render verification.

The composition is exactly 1,800 frames at 30 fps. Scene timing is defined centrally so visuals, captions, narration, and transitions remain synchronized.

## Audio Production

Narration is generated locally with an installed English macOS system voice and normalized for consistent loudness. The soundtrack is synthesized locally from original tones and percussion, then mixed beneath narration with fades and conservative headroom. The final AAC track must remain intelligible on laptop speakers and contain no clipping.

If the preferred system voice is unavailable, the audio script selects a documented English fallback instead of silently omitting narration.

## Accuracy and Safety Rules

- All product screens must come from the verified native Simulator capture.
- `$44.87`, `$97.49`, `$63.00`, and `$29.00` may appear only in the contexts shown by the application.
- The video must never imply guaranteed savings, bank connectivity, merchant access, or real cancellation.
- The local/synthetic nature of the demo appears before the product claim.
- No personal path, account value, credential, or environment secret may appear in visible frames, metadata, captions, or logs retained as artifacts.
- The final disclosure remains readable for the entire closing shot.

## Deliverables

- `artifacts/ios/promo/paycheck-guardian-promo.mp4` — final 60-second promo.
- `artifacts/ios/promo/poster.png` — representative poster frame.
- `artifacts/ios/promo/contact-sheet.png` — visual QA sheet spanning all scenes.
- `promo/` — reproducible Remotion source and exact render instructions.

## Verification

- Install and type-check the pinned Node dependencies.
- Render the complete composition through Remotion.
- Confirm with `ffprobe`: 1920×1080, 30 fps, H.264, AAC, and 60.0-second target duration.
- Decode the complete file to detect corrupted frames or audio.
- Inspect the poster, contact sheet, and representative frames from every scene.
- Confirm text remains inside safe margins and is readable at 1280×720 playback size.
- Scan source, retained assets, captions, and media metadata for local paths and secret-shaped values.

## Definition of Done

The promo is complete when it plays end-to-end as a coherent 60-second product story, uses real iOS evidence, includes English narration and original music, makes the local-only safety boundary unambiguous, passes media validation, and can be reproduced from the documented Remotion commands.
