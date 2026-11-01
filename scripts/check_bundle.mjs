// Inspect actual ASAR bytes; no application code is executed by this check.
import { extractFile, listPackage } from '@electron/asar';
import { readFileSync } from 'node:fs';
import { resolve, sep, normalize } from 'node:path';
import { bundlePathsAreSafe } from './bundle_paths.mjs';
const archive = process.argv[2];
const expected = JSON.parse(readFileSync(resolve('package.json'), 'utf8'));
const actual = JSON.parse(extractFile(archive, 'package.json').toString('utf8'));
if (actual.name !== expected.name || actual.version !== expected.version || actual.productName !== expected.productName || actual.main !== '.vite/build/main.cjs') {
  throw new Error('Packaged application identity mismatch');
}
const entries = listPackage(archive);
if (!bundlePathsAreSafe(entries, sep)) {
  throw new Error('Unexpected source/dependency/private content inside ASAR');
}
for (const name of ['.vite/build/main.cjs', '.vite/build/preload.cjs', '.vite/renderer/main_window/index.html']) {
  if (!extractFile(archive, normalize(name)).length) throw new Error('Missing production bundle entry');
}
process.stdout.write(JSON.stringify({ name: actual.name, version: actual.version, main: actual.main, entries: entries.length }));
