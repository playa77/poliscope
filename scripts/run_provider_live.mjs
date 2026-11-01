/** Explicit live-only entry point; ordinary test scripts never call this. */
import { build } from 'vite';
import { builtinModules } from 'node:module';
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { sourceCandidate } from './source_candidate.mjs';
const preflight = process.argv.includes('--preflight');
if (!preflight && (process.env.POLISCOPE_LIVE_OPENROUTER !== '1' || !process.env.OPENROUTER_API_KEY)) {
  console.error('Live test requires explicit opt-in and securely configured OPENROUTER_API_KEY. No request sent.');
  process.exit(2);
}
const directory = resolve('artifacts/wp-055-live');
await mkdir(directory, { recursive: true });
await build({ configFile: false, logLevel: 'error', build: {
  outDir: directory + '/runner', target: 'node24', minify: false,
  lib: { entry: resolve('tests/live/openrouter.ts'), formats: ['cjs'], fileName: () => 'main.cjs' },
  rolldownOptions: { external: ['electron', ...builtinModules, ...builtinModules.map(x => 'node:' + x)] },
} });
const executable = resolve('node_modules/electron/dist/' + (process.platform === 'win32' ? 'electron.exe' : 'electron'));
const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE;
const before = sourceCandidate();
const started = new Date().toISOString();
const child = spawn(executable, ['--no-sandbox', '--user-data-dir=' + directory + '/chromium', directory + '/runner/main.cjs', ...(preflight ? ['--preflight'] : [])], { env, stdio: 'inherit', shell: false });
child.on('error', () => { console.error('Live runner could not start.'); process.exitCode = 1; });
child.on('exit', async code => {
  process.exitCode = code ?? 1;
  if (preflight) return;
  try {
    const report = await readFile(directory + '/junit.xml');
    const passed = code === 0 && sourceCandidate() === before;
    if (!passed) process.exitCode = 1;
    const target = 'E2E-013 authenticated exact-model metadata generation streaming schema tools reasoning usage and cancellation';
    const results = { tests: 1, failed: passed ? 0 : 1, skipped: 0, skip_reasons: [], cases: [{ file: null, class: 'tests.live.openrouter', name: target }] };
    const record = { version: 1, suite: 'live', candidate: before, started_at: started, finished_at: new Date().toISOString(), exit_code: code, status: passed ? 'passed' : 'failed', readiness: false, results, report_sha256: createHash('sha256').update(report).digest('hex') };
    await mkdir(directory + '/check', { recursive: true });
    await writeFile(directory + '/check/junit.xml', report);
    await writeFile(directory + '/check/evidence.json', JSON.stringify(record, null, 2) + '\n');
  } catch { process.exitCode = 1; console.error('Live evidence could not be retained.'); }
});
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => child.kill(signal));
