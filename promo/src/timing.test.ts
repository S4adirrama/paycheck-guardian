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
