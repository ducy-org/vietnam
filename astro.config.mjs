// @ts-check
import { defineConfig } from 'astro/config';

import preact from '@astrojs/preact';
import sitemap from '@astrojs/sitemap';

import mdx from '@astrojs/mdx';

// https://astro.build/config
export default defineConfig({
  site: 'https://vietnam.ducy.org',
  integrations: [preact(), sitemap(), mdx()],
  vite: {
    optimizeDeps: {
      include: ['leaflet'],
    },
    define: {
      'import.meta.env.PUBLIC_MEDIA_URL': JSON.stringify(
        process.env.MEDIA_URL || ''
      ),
    },
  },
});