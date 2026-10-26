import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: 'tests/desktop', testMatch: '**/*.spec.ts', outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? 'test-results', forbidOnly: Boolean(process.env.CI), workers: 1, expect: { timeout: 20_000 }, timeout: 30_000 });
