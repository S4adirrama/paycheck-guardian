import {describe, expect, it} from 'vitest';
import {CAPTIONS, DISCLOSURE, METRICS, NARRATION} from './content';

describe('promo claims', () => {
  it('retains exact verified product values', () => {
    expect(METRICS).toEqual({
      beforePaycheck: '$44.87',
      monthly: '$97.49',
      evidenceMonthly: '$63.00',
      evidencePaycheck: '$29.00',
    });
  });

  it('states every safety boundary', () => {
    const copy = [NARRATION, DISCLOSURE, ...CAPTIONS.map((item) => item.text)]
      .join(' ')
      .toLowerCase();
    expect(copy).toContain('without connecting to your bank');
    expect(copy).toContain('no merchant is contacted');
    expect(copy).toContain('no real cancellation');
    expect(DISCLOSURE).toBe('Educational prototype. No real financial actions.');
    expect(copy).not.toContain('guaranteed savings');
  });

  it('keeps every caption inside the sixty-second timeline', () => {
    expect(CAPTIONS.every((item) => item.from >= 0 && item.duration > 0)).toBe(true);
    expect(CAPTIONS.every((item) => item.from + item.duration <= 1800)).toBe(true);
  });
});
