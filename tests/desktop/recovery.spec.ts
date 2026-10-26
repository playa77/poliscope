import { test, expect as baseExpect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const expect = baseExpect.configure({ timeout: 20000 });
const executablePath = resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform === 'win32' ? '.exe' : ''}`);

test('WP-041 cold discovery, comparison, backup restore, cancellation and safe diagnostics', async () => {
  test.setTimeout(120000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-recovery-ui-'));
  const source = join(directory, 'source'); await mkdir(source);
  const env: Record<string, string | undefined> = { ...process.env, POLISCOPE_USER_DATA: join(directory, 'app') }; delete env.ELECTRON_RUN_AS_NODE;
  let app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: env as Record<string,string> });
  try {
    let page = await app.firstWindow();
    await app.evaluate(({ dialog }, path) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] }); }, source);
    await page.getByRole('button', { name: 'Choose sandbox folder' }).press('Enter');
    await page.getByLabel('Civilization name').fill('Recovery society');
    await page.getByLabel('Settlement name').fill('Home');
    await page.getByLabel('Starting population (people, optional)').fill('17');
    await page.getByRole('button', { name: 'Create sandbox', exact: true }).press('Enter');
    await expect(page.getByText('Confirmed design revision')).toBeVisible();
    await app.close();
    // Cold start: no selected workspace or cached IDs in this renderer.
    app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: env as Record<string,string> });
    page = await app.firstWindow();
    const region = page.getByRole('region', { name: 'Recovery and historical inspection' });
    const database = join(source, 'poliscope.sqlite3');
    await app.evaluate(({ dialog }, path) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] }); }, database);
    await region.getByRole('button', { name: 'Inspect database without model' }).press('Enter');
    await expect(region.getByRole('status').last()).toContainText('read only');
    await region.getByLabel('Historical branch').selectOption('0');
    await region.getByRole('button', { name: 'Read retained revision' }).press('Enter');
    await expect(region.getByRole('status').last()).toContainText('not freshly reproduced');
    await expect(region.getByRole('table')).toContainText('17');
    const backup = join(directory, 'backup.sqlite3');
    await app.evaluate(({ dialog }, path) => { dialog.showSaveDialog = async () => ({ canceled: false, filePath: path }); }, backup);
    await region.getByRole('button', { name: 'Back up selected database' }).press('Enter');
    await expect(region.getByRole('status').last()).toContainText('Confirmed');
    const bytes = await readFile(backup);
    await region.getByRole('button', { name: 'Back up selected database' }).press('Enter');
    await expect(region.getByRole('alert')).toContainText('save_failed');
    expect(await readFile(backup)).toEqual(bytes);
    await region.getByRole('button', { name: 'Create compatible model comparison' }).press('Enter');
    await expect(region.getByRole('status').last()).toContainText('New comparison branch saved');
    await app.evaluate(({ dialog }, path) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] }); }, database);
    await region.getByRole('button', { name: 'Inspect database without model' }).press('Enter');
    await expect(region.getByLabel('Historical branch').locator('option')).toHaveCount(3);
    // Choose the pre-migration backup explicitly before restoring it.
    await app.evaluate(({ dialog }, path) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] }); }, backup);
    await region.getByRole('button', { name: 'Inspect database without model' }).press('Enter');
    await expect(region.getByLabel('Historical branch').locator('option')).toHaveCount(2);
    const restored = join(directory, 'restored'); await mkdir(restored);
    await app.evaluate(({ dialog }, path) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] }); }, restored);
    await region.getByRole('button', { name: 'Restore selected backup into new folder' }).press('Enter');
    await expect(region.getByRole('status').last()).toContainText('Confirmed');
    expect((await readFile(join(restored, 'poliscope.sqlite3'))).length).toBeGreaterThan(0);
    await app.evaluate(({ dialog }) => { dialog.showOpenDialog = async () => ({ canceled: true, filePaths: [] }); });
    await region.getByRole('button', { name: 'Inspect archive without model' }).press('Enter');
    await expect(region.getByRole('status').last()).toContainText('cancelled');
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});
