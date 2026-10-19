// Geometry helpers for the server-rendered SVG charts.

export interface Series {
  label: string;
  color?: string;
  values: (number | null)[];
  dashed?: boolean;
}

export function niceMax(max: number): number {
  if (max <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(max)));
  const f = max / exp;
  const nice = f <= 1 ? 1 : f <= 1.5 ? 1.5 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 3 ? 3 : f <= 4 ? 4 : f <= 5 ? 5 : f <= 6 ? 6 : f <= 8 ? 8 : 10;
  return nice * exp;
}

/** Round step for about `count` gridlines up to `max`. */
export function niceStep(max: number, count = 4): number {
  const raw = max / count;
  const exp = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / exp;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * exp;
}

/** Axis maximum and gridline values with a round step. */
export function axis(dataMax: number, count = 4): { max: number; ticks: number[] } {
  const step = niceStep(Math.max(dataMax, 1e-9), count);
  const max = Math.ceil(dataMax / step - 1e-9) * step || step;
  const ticks: number[] = [];
  for (let v = 0; v <= max + step / 2; v += step) ticks.push(v);
  return { max, ticks };
}

export function ticks(max: number, count = 4): number[] {
  return Array.from({ length: count + 1 }, (_, i) => (max / count) * i);
}

/** Path for a series, breaking the line at missing values. */
export function linePath(values: (number | null)[], x: (i: number) => number, y: (v: number) => number): string {
  let d = '';
  let pen = false;
  values.forEach((v, i) => {
    if (v == null || Number.isNaN(v)) {
      pen = false;
      return;
    }
    d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

/** Centered moving average, used to calm noisy monthly series. */
export function smooth(values: (number | null)[], radius = 1): (number | null)[] {
  return values.map((_, i) => {
    let s = 0;
    let n = 0;
    for (let j = i - radius; j <= i + radius; j++) {
      const v = values[j];
      if (v != null) {
        s += v;
        n++;
      }
    }
    return n ? s / n : null;
  });
}

/** All months between two "YYYY-MM" strings, inclusive. */
export function monthRange(from: string, to: string): string[] {
  const out: string[] = [];
  let [y, m] = from.split('-').map(Number);
  const [ty, tm] = to.split('-').map(Number);
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m++;
    if (m > 12) {
      m = 1;
      y++;
    }
  }
  return out;
}

/**
 * Rolling 12-month totals for each month in `months`, indexed so that the
 * 12 months ending in December of `baseYear` = 100. Null until 12 months exist
 * or when the base is zero. Rolling sums remove the summer dip and other
 * seasonality, so occupation and market can be compared month by month.
 */
export function rollingIndex(counts: Record<string, number>, months: string[], baseYear: number): (number | null)[] {
  const roll: (number | null)[] = months.map((_, i) => {
    if (i < 11) return null;
    let s = 0;
    for (let j = i - 11; j <= i; j++) s += counts[months[j]] ?? 0;
    return s;
  });
  const bi = months.indexOf(`${baseYear}-12`);
  const base = bi >= 0 ? roll[bi] : null;
  if (!base) return months.map(() => null);
  return roll.map((v) => (v == null ? null : (v / base) * 100));
}
