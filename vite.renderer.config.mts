import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
import { contentPolicy } from './desktop/main/security';
export default defineConfig({ root: 'desktop/renderer', plugins: [react(), {
  name: 'packaged-content-policy', apply: 'build',
  transformIndexHtml: () => [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: contentPolicy() }, injectTo: 'head-prepend' }],
}], base: './', build: { outDir: resolve(import.meta.dirname, '.vite/renderer/main_window'), emptyOutDir: true } });
