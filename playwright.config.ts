import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: 'tests/desktop', testMatch: '**/*.spec.ts', workers: 1, timeout: 30_000 });
