// Public address of the site and the path it is served from.
// Production is https://yrkestrender.se served from the domain root (GitHub Pages, custom domain).
// Serving from a subpath (e.g. a GitHub Pages project site) needs BASE_PATH=/subpath.
export const SITE_URL = process.env.SITE_URL || 'https://yrkestrender.se';
export const BASE_PATH = process.env.BASE_PATH || '/';
