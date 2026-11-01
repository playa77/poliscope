/** Same source identity as scripts/evidence.py; never includes ignored runtime data. */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync, readlinkSync } from 'node:fs';
import { join } from 'node:path';
export function sourceCandidate(root = process.cwd()) {
  const env = { ...process.env }; delete env.OPENROUTER_API_KEY;
  const raw = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], { cwd: root, env });
  const paths = [...new Set(raw.toString('utf8').split('\0').filter(Boolean))].sort((a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b)));
  const result = createHash('sha256');
  for (const name of paths) {
    const path = join(root, name);
    let bytes;
    try {
      const stat = lstatSync(path);
      bytes = stat.isSymbolicLink() ? Buffer.from(readlinkSync(path)) : stat.isFile() ? readFileSync(path) : Buffer.from('DELETED');
    } catch (error) { if (error.code !== 'ENOENT') throw error; bytes = Buffer.from('DELETED'); }
    result.update(Buffer.from(name)); result.update(Buffer.from([0]));
    result.update(createHash('sha256').update(bytes).digest());
  }
  return result.digest('hex');
}
