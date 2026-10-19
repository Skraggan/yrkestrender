// Trends relative to the average.
//
// Ads get longer and mention more things over time, and the job market grows
// and shrinks as a whole. So the main comparison is always against the average:
//  - for a share (how often something is mentioned): the change beyond what the
//    average item of the same kind changed, in percentage points;
//  - for a volume (number of ads): the change beyond the whole market's change.
// The total (raw) change is shown as a secondary number.

export interface ShareItem {
  sh: number | null;
  sh3: number | null;
}

/** How much shares of a group of items grew on average: Σ now / Σ three years ago. */
export function baseline(items: ShareItem[]): number {
  let now = 0;
  let before = 0;
  for (const i of items) {
    if (i.sh != null && i.sh3 != null) {
      now += i.sh;
      before += i.sh3;
    }
  }
  return before > 0 ? now / before : 1;
}

/** Change in share beyond the average change (percentage points as a fraction). */
export function excess(sh: number | null, sh3: number | null, base: number): number | null {
  if (sh == null || sh3 == null) return null;
  return sh - sh3 * base;
}

/** Volume change relative to a reference change: +0.12 means 12 % better than the market. */
export function volumeVsMarket(now: number, before: number, refNow: number, refBefore: number): number | null {
  if (!before || !refBefore || !refNow) return null;
  return now / before / (refNow / refBefore) - 1;
}
