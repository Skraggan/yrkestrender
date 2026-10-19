// @ts-check
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';
import { BASE_PATH, SITE_URL } from './site.config.mjs';

export default defineConfig({
  output: 'static',
  site: SITE_URL,
  base: BASE_PATH,
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith('.json') && !/\/404\/?$/.test(page),
    }),
  ],
});
