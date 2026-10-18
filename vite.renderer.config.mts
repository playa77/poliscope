import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
export default defineConfig({ root: 'desktop/renderer', plugins: [react()], base: './', build: { outDir: resolve(import.meta.dirname, '.vite/renderer/main_window'), emptyOutDir: true } });
