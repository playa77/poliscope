import { defineConfig } from 'vitest/config';
import matrix from './tests/fixtures/providers/acceptance-matrix.json' with { type: 'json' };
// Exact synthetic suites, shared by the public matrix and the offline command.
// No live test files or runtime provider credentials are selected.
export default defineConfig({ test: {
  allowOnly: false,
  maxWorkers: 2,
  testTimeout: 20000,
  include: [...new Set(matrix.capabilities.flatMap(row => row.unit_suites))].sort(),
} });
