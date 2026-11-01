import { test, expect, _electron as electron } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

test('WP-054 packaged runtime without interpreter PATH preserves data across cold restart', async () => {
  test.setTimeout(90000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-native space-'));
  const base = resolve(process.env.POLISCOPE_NATIVE_APP ?? `out/Poliscope-${process.platform}-x64`);
  const extension = process.platform === 'win32' ? '.exe' : '';
  const env: Record<string, string> = Object.fromEntries(Object.entries({ ...process.env, PATH: '', POLISCOPE_USER_DATA: join(directory, 'user-data') }).filter((entry): entry is [string, string] => entry[1] !== undefined));
  delete env.ELECTRON_RUN_AS_NODE;
  const engine = join(base, 'resources/poliscope-engine/poliscope-engine' + extension);
  const probe = JSON.parse(execFileSync(engine, ['--self-test'], { env, cwd: directory, timeout: 60000, encoding: 'utf8' }));
  expect(probe.status).toBe('passed');
  expect(probe.checks).toContain('sqlite-cold-replay');
  const executablePath = join(base, 'poliscope' + extension);
  let app: Awaited<ReturnType<typeof electron.launch>> | undefined;
  try {
    app = await electron.launch({ executablePath, args: ['--no-sandbox'], env });
    let page = await app.firstWindow();
    await expect(page.getByRole('status').first()).toHaveText('Local engine ready');
    await app.evaluate(({ dialog }, path) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] }); }, join(directory, 'store'));
    await page.getByRole('button', { name: 'Choose sandbox folder' }).click();
    await page.getByLabel('Civilization name').fill('Native retained canary');
    await page.getByLabel('Settlement name').fill('Home');
    await page.getByLabel('Starting population (people, optional)').fill('17');
    await page.getByRole('button', { name: 'Create sandbox', exact: true }).click();
    await expect(page.getByText('Confirmed design revision')).toBeVisible();
    const state = await page.evaluate(() => window.poliscope.workspaceCatalogue());
    await app.close(); app = undefined;
    app = await electron.launch({ executablePath, args: ['--no-sandbox'], env });
    page = await app.firstWindow();
    await expect(page.getByRole('status').first()).toHaveText('Local engine ready');
    await app.evaluate(({ dialog }, path) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] }); }, join(directory, 'store'));
    await page.getByRole('button', { name: 'Choose sandbox folder' }).click();
    expect(await page.evaluate(() => window.poliscope.workspaceCatalogue())).toEqual(state);
    await page.getByRole('button', { name: 'Reconnect local engine' }).click();
    await expect(page.getByRole('status').first()).toHaveText('Local engine ready');
  } finally { await app?.close(); await rm(directory, { recursive: true, force: true }); }
});
