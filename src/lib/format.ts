// Swedish number and date formatting.

const intFmt = new Intl.NumberFormat('sv-SE');
const MONTHS = ['januari', 'februari', 'mars', 'april', 'maj', 'juni', 'juli', 'augusti', 'september', 'oktober', 'november', 'december'];
const MONTHS_SHORT = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];

export const int = (n: number) => intFmt.format(Math.round(n));

/** 0.1234 -> "12 %" (one decimal under 10 %). */
export function pct(x: number | null | undefined, digits?: number): string {
  if (x == null || Number.isNaN(x)) return '–';
  if (x > 0 && x < 0.001) return 'under 0,1 %';
  const v = x * 100;
  const d = digits ?? (v < 10 && v > 0 ? 1 : 0);
  return `${v.toLocaleString('sv-SE', { minimumFractionDigits: d, maximumFractionDigits: d })} %`;
}

/** Change in percentage points, signed: "+4,2 p.e." */
export function pp(a: number | null | undefined, b: number | null | undefined): string {
  if (a == null || b == null) return '–';
  const v = (a - b) * 100;
  const s = Math.abs(v).toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${v > 0.05 ? '+' : v < -0.05 ? '−' : '±'}${s} p.e.`;
}

/** A single percentage-point value (fraction in), signed: "+1,4 p.e." */
export function ppValue(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return '–';
  const v = x * 100;
  const s = Math.abs(v).toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${v > 0.05 ? '+' : v < -0.05 ? '−' : '±'}${s} p.e.`;
}

/** A relative value (fraction in), signed: "+12 %". */
export function relValue(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return '–';
  const v = x * 100;
  const s = Math.abs(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 });
  return `${v >= 0.5 ? '+' : v <= -0.5 ? '−' : '±'}${s} %`;
}

/** Up/down class for a signed value. */
export function signClass(x: number | null | undefined, threshold = 0.002): string {
  if (x == null) return '';
  return x > threshold ? 'up' : x < -threshold ? 'down' : '';
}

/** Relative change: "+12 %" / "−8 %". */
export function rel(now: number, before: number): string {
  if (!before) return '–';
  const v = (now / before - 1) * 100;
  const s = Math.abs(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 });
  return `${v >= 0.5 ? '+' : v <= -0.5 ? '−' : '±'}${s} %`;
}

export function trendClass(a: number | null | undefined, b: number | null | undefined, threshold = 0.002): string {
  if (a == null || b == null) return '';
  if (a - b > threshold) return 'up';
  if (b - a > threshold) return 'down';
  return '';
}

export function monthName(ym: string, short = false): string {
  const [y, m] = ym.split('-').map(Number);
  return `${(short ? MONTHS_SHORT : MONTHS)[m - 1]} ${y}`;
}

/** "okt 2025 – sep 2026" */
export function windowLabel(w: [string, string]): string {
  return `${monthName(w[0], true)} – ${monthName(w[1], true)}`;
}

/** Swedish indefinite article for the hero sentence ("en sjuksköterska", "ett ..."). */
export function lower(s: string) {
  return s.charAt(0).toLowerCase() + s.slice(1);
}
