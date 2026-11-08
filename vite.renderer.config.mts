import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'node:path';
import { contentPolicy } from './desktop/main/security';
const root = import.meta.dirname;
export default defineConfig({ root: 'desktop/renderer', resolve: { alias: { '@': root } }, plugins: [react(), tailwindcss(), {
  name: 'packaged-content-policy', apply: 'build',
  transformIndexHtml: () => [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: contentPolicy() }, injectTo: 'head-prepend' }],
}], base: './', build: { outDir: resolve(import.meta.dirname, '.vite/renderer/main_window'), emptyOutDir: true } });
