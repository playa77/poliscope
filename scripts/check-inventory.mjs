import { readdir, readFile } from 'node:fs/promises';
import { resolve, relative } from 'node:path';
const area = process.argv[2];
if (!['content', 'contracts'].includes(area)) throw new Error('Expected content or contracts');
const root = resolve(import.meta.dirname, '..', area);
const manifest = JSON.parse(await readFile(resolve(root, 'inventory.json'), 'utf8'));
if (manifest.version !== 1 || manifest.status !== 'bootstrap-empty' || !Array.isArray(manifest.files) || manifest.files.length !== 0) {
  throw new Error('Bootstrap inventory must be empty; implement production validation with the first artifacts');
}
const entries = await readdir(root, { recursive: true, withFileTypes: true });
const files = entries.filter((entry) => entry.isFile()).map((entry) => relative(root, resolve(entry.parentPath, entry.name)));
if (files.some((file) => !['README.md', 'inventory.json'].includes(file))) throw new Error(`Unregistered ${area} artifacts`);
console.log(`${area}: empty bootstrap inventory validated; production validation pending`);
