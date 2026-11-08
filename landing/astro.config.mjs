// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://transfiereme.asware.com.mx',
  trailingSlash: 'never',
  build: {
    format: 'file',
  },
  server: {
    port: 4330,
    host: true,
  },
});
