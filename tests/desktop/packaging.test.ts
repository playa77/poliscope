import { createRequire } from 'node:module';
import { expect, it } from 'vitest';
import { createPackage } from '@electron/asar';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
const config = createRequire(import.meta.url)('../../forge.config.cjs');
it('refuses cross-target packages that would embed the host Python runtime', async () => {
  const foreign = process.platform === 'win32' ? 'linux' : 'win32';
  await expect(config.hooks.prePackage({}, foreign, 'x64')).rejects.toThrow('Build natively');
  await expect(config.hooks.prePackage({}, process.platform, 'arm64')).rejects.toThrow('Build natively');
  await expect(config.hooks.prePackage({}, process.platform, 'x64')).resolves.toBeUndefined();
});

it('rejects private ASAR files and mismatched packaged identity', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-asar-'));
  try {
    const source = join(directory, 'source');
    await mkdir(source);
    const packageText = await readFile(resolve('package.json'), 'utf8');
    await writeFile(join(source, 'package.json'), packageText);
    for (const name of ['.vite/build/main.cjs', '.vite/build/preload.cjs', '.vite/renderer/main_window/index.html']) {
      const path = join(source, name);
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, 'synthetic fixture');
    }
    const archive = join(directory, 'app.asar');
    const inspect = () => spawnSync(process.execPath, [resolve('scripts/check_bundle.mjs'), archive], { encoding: 'utf8', timeout: 10000 });
    await createPackage(source, archive);
    const valid = inspect();
    expect(valid.status, valid.stderr).toBe(0);
    expect(JSON.parse(valid.stdout).version).toBe(JSON.parse(packageText).version);
    await writeFile(join(source, '.env'), 'SYNTHETIC_PRIVATE_CANARY');
    await createPackage(source, archive);
    const denied = inspect();
    expect(denied.status).toBe(1);
    expect(denied.stderr).toContain('Unexpected source/dependency/private content');
    expect(denied.stderr).not.toContain('SYNTHETIC_PRIVATE_CANARY');
    await rm(join(source, '.env'));
    await writeFile(join(source, 'package.json'), JSON.stringify({ ...JSON.parse(packageText), version: '999.0.0' }));
    await createPackage(source, archive);
    const mismatch = inspect();
    expect(mismatch.status).toBe(1);
    expect(mismatch.stderr).toContain('Packaged application identity mismatch');
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30000);

it('accepts host-form ASAR paths on Windows and Linux without admitting private or prefix-lookalike entries', () => {
  const { bundlePathsAreSafe } = createRequire(import.meta.url)('../../scripts/bundle_paths.mjs');
  for (const separator of ['/', String.fromCharCode(92)]) {
    const paths = ['/package.json', '/.vite', '/.vite/build/main.cjs'].map(p => p.replaceAll('/', separator));
    expect(bundlePathsAreSafe(paths, separator)).toBe(true);
    for (const denied of ['/.env', '/node_modules/private', '/.vite-private/key', '/desktop/main.ts']) {
      expect(bundlePathsAreSafe([...paths, denied.replaceAll('/', separator)], separator)).toBe(false);
    }
  }
  expect(bundlePathsAreSafe(['/package.json'], ':')).toBe(false);
});
