// Compatibility entry point; semantic validation belongs to canonical Python.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const area = process.argv[2];
if (!['content', 'contracts'].includes(area)) throw new Error('Expected content or contracts');
const script = area === 'content' ? 'build_content.py' : 'generate_contracts.py';
const result = spawnSync('uv', ['run', '--frozen', 'python', `scripts/${script}`, '--check'], {
  cwd: fileURLToPath(new URL('..', import.meta.url)), stdio: 'inherit', shell: false,
});
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
