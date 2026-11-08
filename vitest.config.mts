import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';
const root = import.meta.dirname;
export default defineConfig({ resolve: { alias: { '@': root } }, test: { allowOnly: !process.env.CI, include: ['tests/desktop/**/*.test.ts'] } });
