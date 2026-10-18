import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

test('packaged shell launches its bundled engine with an isolated secure renderer', async () => {
  const data = await mkdtemp(join(tmpdir(), 'poliscope-smoke-'));
  const base = resolve(`out/Poliscope-${process.platform}-${process.arch}`);
  const executablePath = process.platform === 'darwin' ? join(base, 'Poliscope.app/Contents/MacOS/poliscope') : join(base, `poliscope${process.platform === 'win32' ? '.exe' : ''}`);
  const env: Record<string, string> = Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
  env.POLISCOPE_USER_DATA = data;
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath, args: ['--no-sandbox'], env });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    expect(await page.evaluate(() => ({ require: typeof (window as unknown as {require?: unknown}).require, methods: Object.keys(window.poliscope) }))).toEqual({ require: 'undefined', methods: ['bootstrapStatus'] });
    expect(await app.evaluate(({ BrowserWindow }) => {
      const prefs = (BrowserWindow.getAllWindows()[0].webContents as unknown as { getLastWebPreferences(): {nodeIntegration: boolean; contextIsolation: boolean; sandbox: boolean} }).getLastWebPreferences();
      return [prefs.nodeIntegration, prefs.contextIsolation, prefs.sandbox];
    })).toEqual([false, true, true]);
  } finally {
    await app.close();
    await rm(data, { recursive: true, force: true });
  }
});
