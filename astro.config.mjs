// @ts-check
import { defineConfig } from 'astro/config';

import preact from '@astrojs/preact';

// https://astro.build/config
export default defineConfig({
  site: 'https://vietnam.ducy.org',
  integrations: [preact()],
  vite: {
    define: {
      'import.meta.env.PUBLIC_MEDIA_URL': JSON.stringify(
        process.env.MEDIA_URL || ''
      ),
    },
  },
});