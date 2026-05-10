// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// When the HUJI subdomain CNAME is live, change `site` to the HUJI URL
// (e.g. https://ai-hub.cs.huji.ac.il) and rebuild — that's the only edit needed.
export default defineConfig({
  site: 'https://huji-ai-hub.pages.dev',
  integrations: [sitemap()],
});
