# Paycheck Guardian Promo

This directory contains the reproducible Remotion source for the 60-second English product film. The film targets a US hackathon audience and combines real iOS Simulator captures with motion graphics, on-screen captions, English narration, and an original generated soundtrack.

## Deliverables

- `../artifacts/ios/promo/paycheck-guardian-promo.mp4` — final 1920×1080 H.264/AAC film.
- `../artifacts/ios/promo/poster.png` — poster frame.
- `../artifacts/ios/promo/contact-sheet.png` — eight-scene visual review sheet.
- `../artifacts/ios/promo/media-report.md` — retained technical verification.

## Reproduce

From `promo/`:

```bash
npm ci
./scripts/prepare-assets.sh
./scripts/generate-audio.sh
./scripts/verify-audio.sh
npm test
npm run typecheck
mkdir -p ../artifacts/ios/promo
npm run render
npm run still
./scripts/verify-render.sh
```

Use `npm run studio` to open the editable composition. The timing contract is 1,800 frames at 30 fps. Audio is generated locally: macOS `say` provides the English voice, while FFmpeg synthesizes the music from tonal and noise sources. No stock media, cloud voice service, API key, or network runtime is required after dependencies are installed.

The values shown are synthetic hackathon fixtures. The app and film are educational prototypes, not financial advice, and no real cancellation or merchant contact occurs.
