import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import fixtures from '../../contracts/fixtures.json';

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
    const second = spawn(executablePath, ['--no-sandbox'], { env, stdio: 'ignore' });
    await expect(new Promise<number | null>((resolve, reject) => {
      const timer = setTimeout(() => { second.kill('SIGKILL'); reject(new Error('Second instance did not exit')); }, 10000);
      second.once('error', error => { clearTimeout(timer); reject(error); });
      second.once('exit', code => { clearTimeout(timer); resolve(code); });
    })).resolves.toBe(0);

    expect(await page.evaluate(() => ({ require: typeof (window as unknown as {require?: unknown}).require, methods: Object.keys(window.poliscope) }))).toEqual({ require: 'undefined', methods: ['archive', 'uncertainty', 'sensitivity', 'capacity', 'timeline', 'workbench', 'previewWorkbench', 'applyWorkbench', 'cancelWorkbench', 'deleteNote', 'exploration', 'previewWorld', 'applyWorld', 'cancelWorld', 'matrixModel', 'matrix', 'atlas', 'atlasSource', 'rationale', 'lineage', 'compare', 'historyAction', 'overview', 'target', 'chart', 'interview', 'previewInterview', 'applyInterview', 'cancelInterview', 'chooseWorkspace', 'workspaceCatalogue', 'createWorld', 'selectWorld', 'worldPage', 'openHistory', 'historyPage', 'reconnect', 'bootstrapStatus'] });
    expect(await app.evaluate(({ BrowserWindow }) => {
      const prefs = (BrowserWindow.getAllWindows()[0].webContents as unknown as { getLastWebPreferences(): {nodeIntegration: boolean; contextIsolation: boolean; sandbox: boolean} }).getLastWebPreferences();
      return [prefs.nodeIntegration, prefs.contextIsolation, prefs.sandbox];
    })).toEqual([false, true, true]);
    const summary = JSON.parse(fixtures.find(f => f.name === 'evidence:incomplete')!.frame).result;
    summary.coverage.explanation = '<img src="https://untrusted.invalid/leak" onerror="alert(1)"> ![remote](https://untrusted.invalid/markdown) <svg onload="alert(2)">';
    const saved = { history_schema: 1, summary, outputs: [], findings: [], sources: [], assumptions: [], traces: [] };
    const setup = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', `import sys\nfrom pathlib import Path\nfrom poliscope_engine.storage.store import Store\nwith Store(Path(sys.argv[1])) as s:\n with s.transaction():\n  s.add_context('selected', '{}')\n  s.retain_evidence('selected', sys.argv[2], sys.argv[3])`, data, summary.result_id, JSON.stringify(saved)], { encoding: 'utf8', timeout: 5000 });
    expect(setup.status, setup.stderr).toBe(0);
    await app.evaluate(({ dialog }, database) => {
      dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [database] });
    }, join(data, 'poliscope.sqlite3'));
    for (const [name, value] of Object.entries({ storage_context_id: 'selected', ...summary.context, result_id: summary.result_id })) {
      await page.locator(`input[name="${name}"]`).fill(String(value));
    }
    await page.getByRole('button', { name: 'Choose store and read' }).click();
    await expect(page.getByRole('heading', { name: 'Stored historical evidence — read only' })).toBeVisible();
    await expect(page.getByRole('status')).toContainText('Stored historical evidence');
    await expect(page.getByText(`Coverage: ${summary.coverage.status}`, { exact: false })).toBeVisible();
    await expect(page.getByText(summary.coverage.explanation, { exact: false })).toBeVisible();
    await expect(page.locator('main img, main svg')).toHaveCount(0);
    await page.getByRole('button', { name: 'Read collection' }).click();
    await expect(page.getByText('Collection: outputs', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Reconnect local engine' }).click();
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await expect(page.getByRole('heading', { name: 'Stored historical evidence — read only' })).toHaveCount(0);
  } finally {
    await app.close();
    await rm(data, { recursive: true, force: true });
  }
});
