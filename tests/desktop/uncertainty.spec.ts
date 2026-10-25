import { test, expect as baseExpect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const expect = baseExpect.configure({ timeout: 20000 });
const executablePath = resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform === 'win32' ? '.exe' : ''}`);

test('WP-038 keyboard uncertainty, explicit probability and sensitivity keep saved inputs intact', async () => {
  test.setTimeout(120000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-uncertainty-ui-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  const env: Record<string, string | undefined> = { ...process.env, POLISCOPE_USER_DATA: join(directory, 'app') }; delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: env as Record<string, string> });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
    await page.getByRole('button', { name: 'Choose sandbox folder' }).press('Enter');
    await page.getByLabel('Civilization name').fill('Hypothetical bounds');
    await page.getByLabel('Starting population').fill('10');
    await page.getByRole('button', { name: 'Create sandbox', exact: true }).press('Enter');
    await page.getByRole('button', { name: 'Uncertainty and sensitivity', exact: true }).press('Enter');
    const view = page.getByRole('region', { name: 'Uncertainty inspector' });
    await expect(view.getByLabel('Lower bound')).toBeEnabled();
    await view.getByLabel('Lower bound').fill('2'); await view.getByLabel('Upper bound', { exact: true }).fill('5');
    await view.getByLabel('Threshold: report values below').fill('4');
    await view.getByLabel('Method assumption and rationale').fill('Player-selected hypothetical range, with no probability assumption.');
    await view.getByRole('button', { name: 'Inspect uncertainty', exact: true }).press('Enter');
    const report = view.getByRole('region', { name: 'Uncertainty report' });
    await expect(report).toContainText('2 to 5'); await expect(report).toContainText('overlap');
    await expect(report).toContainText('No probability model');
    await view.getByLabel('Explicit variant A').fill('2'); await view.getByLabel('Explicit variant B').fill('5');
    await view.getByRole('button', { name: 'Preview selected variants' }).press('Enter');
    await expect(view.getByRole('region', { name: 'Sensitivity report' })).toContainText('Variant A: parameter = 2');
    await expect(view.getByRole('region', { name: 'Sensitivity report' })).toContainText('Variant B: parameter = 5');
    await view.getByRole('combobox', { name: /^Form/ }).selectOption('distribution');
    await view.getByLabel('Outcome A value').fill('0'); await view.getByLabel('Outcome B value').fill('1');
    await view.getByLabel('Outcome A numerator').fill('1'); await view.getByLabel('Outcome A denominator').fill('4');
    await view.getByLabel('Outcome B numerator').fill('3'); await view.getByLabel('Outcome B denominator').fill('4');
    await view.getByLabel('Threshold: report values below').fill('0.5');
    await view.getByRole('button', { name: 'Inspect uncertainty', exact: true }).press('Enter');
    await expect(report).toContainText('1/4');
    await page.getByRole('button', { name: 'Civilization overview', exact: true }).press('Enter');
    const selected = await page.evaluate(async () => {
      const catalogue = await window.poliscope.workspaceCatalogue();
      const state = await window.poliscope.selectWorld({ civilization_id: catalogue.branches[0].context.civilization_id, branch_id: 'main', revision_id: null });
      return window.poliscope.worldPage({ context: state.context, scope_id: 'home', collection: 'values', cursor: null });
    });
    expect(selected.result.page.items.find(v => 'id' in v && v.id === 'population:value')).toMatchObject({ value: { value: '10' } });
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});
