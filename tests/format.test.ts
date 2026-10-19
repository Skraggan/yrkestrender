import { describe, expect, it } from 'vitest';
import { pct, pp, rel, trendClass, windowLabel } from '../src/lib/format';
import { linePath, monthRange, niceMax, smooth } from '../src/lib/chart';

describe('format', () => {
  it('formats shares in Swedish', () => {
    expect(pct(0.1234)).toBe('12 %');
    expect(pct(0.0456)).toBe('4,6 %');
    expect(pct(null)).toBe('–');
  });
  it('formats percentage point changes with sign', () => {
    expect(pp(0.15, 0.1)).toBe('+5,0 p.e.');
    expect(pp(0.1, 0.15)).toBe('−5,0 p.e.');
    expect(pp(0.1, 0.1)).toBe('±0,0 p.e.');
  });
  it('formats relative change', () => {
    expect(rel(120, 100)).toBe('+20 %');
    expect(rel(80, 100)).toBe('−20 %');
    expect(rel(5, 0)).toBe('–');
  });
  it('classifies trends', () => {
    expect(trendClass(0.2, 0.1)).toBe('up');
    expect(trendClass(0.1, 0.2)).toBe('down');
    expect(trendClass(0.1, 0.1)).toBe('');
  });
  it('labels windows', () => {
    expect(windowLabel(['2025-10', '2026-09'])).toBe('okt 2025 – sep 2026');
  });
});

describe('chart helpers', () => {
  it('rounds axis maxima to nice numbers', () => {
    expect(niceMax(0.37)).toBe(0.4);
    expect(niceMax(73000)).toBe(80000);
  });
  it('lists months inclusively across years', () => {
    expect(monthRange('2025-11', '2026-02')).toEqual(['2025-11', '2025-12', '2026-01', '2026-02']);
  });
  it('breaks lines at missing values', () => {
    const d = linePath([1, null, 2], (i) => i, (v) => v);
    expect(d).toBe('M0.0 1.0M2.0 2.0');
  });
  it('smooths with a moving average', () => {
    expect(smooth([0, 3, 0], 1)).toEqual([1.5, 1, 1.5]);
  });
});
