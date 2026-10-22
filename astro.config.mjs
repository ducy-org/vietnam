// @ts-check
import { defineConfig } from 'astro/config';

import preact from '@astrojs/preact';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://vietnam.ducy.org',
  integrations: [preact(), sitemap()],
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