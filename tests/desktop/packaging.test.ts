import { createRequire } from 'node:module';
import { expect, it } from 'vitest';
const config = createRequire(import.meta.url)('../../forge.config.cjs');
it('refuses cross-target packages that would embed the host Python runtime', async () => {
  const foreign = process.platform === 'win32' ? 'linux' : 'win32';
  await expect(config.hooks.prePackage({}, foreign, 'x64')).rejects.toThrow('Build natively');
  await expect(config.hooks.prePackage({}, process.platform, 'arm64')).rejects.toThrow('Build natively');
  await expect(config.hooks.prePackage({}, process.platform, 'x64')).resolves.toBeUndefined();
});
