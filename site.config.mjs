// Public address of the site and the path it is served from.
// Cloudflare Pages (custom domain or *.pages.dev): SITE_URL=https://…, BASE_PATH=/ (default).
// GitHub Pages project site: SITE_URL=https://skraggan.github.io, BASE_PATH=/yrkestrender (set in pages.yml).
export const SITE_URL = process.env.SITE_URL || 'https://yrkestrender.pages.dev';
export const BASE_PATH = process.env.BASE_PATH || '/';
