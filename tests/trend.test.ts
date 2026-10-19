import { describe, expect, it } from 'vitest';
import { baseline, excess, volumeVsMarket } from '../src/lib/trend';
import { ppValue, relValue } from '../src/lib/format';

describe('trend against the average', () => {
  it('computes the average growth of a group of shares', () => {
    expect(baseline([{ sh: 0.2, sh3: 0.1 }, { sh: 0.4, sh3: 0.2 }])).toBeCloseTo(2);
    expect(baseline([{ sh: null, sh3: 0.1 }])).toBe(1);
  });
  it('measures change beyond the average', () => {
    // Everything doubled: an item that also doubled is exactly average.
    expect(excess(0.2, 0.1, 2)).toBeCloseTo(0);
    // Grew less than average: negative even though the total change is positive.
    expect(excess(0.15, 0.1, 2)).toBeCloseTo(-0.05);
    expect(excess(null, 0.1, 2)).toBeNull();
  });
  it('compares volume with the market', () => {
    // Occupation fell 20 %, market fell 50 %: 60 % better than the market.
    expect(volumeVsMarket(80, 100, 50, 100)).toBeCloseTo(0.6);
    expect(volumeVsMarket(80, 0, 50, 100)).toBeNull();
  });
  it('formats signed values', () => {
    expect(ppValue(0.054)).toBe('+5,4 p.e.');
    expect(ppValue(-0.01)).toBe('−1,0 p.e.');
    expect(relValue(0.6)).toBe('+60 %');
  });
});
