import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
if (Number(process.versions.node.split('.')[0]) !== 24) {
  console.error('Node 24 LTS is required. See .nvmrc.');
  process.exit(1);
}
if (!['start', 'package'].includes(process.argv[2])) process.exit(2);
const cli = resolve(root, 'node_modules/@electron-forge/cli/dist/electron-forge.js');
const child = spawn(process.execPath, [cli, process.argv[2], ...process.argv.slice(3)], {
  cwd: root, stdio: 'inherit', shell: false,
  env: { ...process.env, POLISCOPE_PROJECT_ROOT: root },
});
child.on('error', (error) => { console.error(error.message); process.exitCode = 1; });
child.on('exit', (code) => { process.exitCode = code ?? 1; });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
