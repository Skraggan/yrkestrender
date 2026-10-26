// @ts-check
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';
import { readFileSync } from 'node:fs';
import { BASE_PATH, SITE_URL } from './site.config.mjs';

// Every page is rebuilt from the same data, so they all change when the data does.
const { generated } = JSON.parse(readFileSync('./data/site/meta.json', 'utf8'));

export default defineConfig({
  output: 'static',
  site: SITE_URL,
  base: BASE_PATH,
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith('.json') && !/\/404\/?$/.test(page),
      lastmod: new Date(generated),
    }),
  ],
});
