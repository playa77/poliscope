/** Explicit live-only entry point; ordinary test scripts never call this. */
import { build } from 'vite';
import { builtinModules } from 'node:module';
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { mkdir } from 'node:fs/promises';
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
const child = spawn(executable, ['--no-sandbox', '--user-data-dir=' + directory + '/chromium', directory + '/runner/main.cjs', ...(preflight ? ['--preflight'] : [])], { env, stdio: 'inherit', shell: false });
child.on('error', () => { console.error('Live runner could not start.'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => child.kill(signal));
