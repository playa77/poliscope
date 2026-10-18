import { defineConfig } from 'vite';
export default defineConfig({ build: { lib: { entry: 'desktop/main/index.ts', formats: ['cjs'], fileName: () => 'main.cjs' } } });
