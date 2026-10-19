// Internal links respect Astro's base path, so the site works both at the root of
// a domain (Cloudflare Pages) and under /yrkestrender/ (GitHub Pages).
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

export function url(path: string): string {
  return `${BASE}${path}`;
}
