import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
const base = resolve(`out/Poliscope-${process.platform}-${process.arch}`);
const executablePath = process.platform === 'darwin' ? join(base, 'Poliscope.app/Contents/MacOS/poliscope') : join(base, `poliscope${process.platform === 'win32' ? '.exe' : ''}`);
function environment(data: string) {
  const env: Record<string, string | undefined> = { ...process.env, POLISCOPE_USER_DATA: data }; delete env.ELECTRON_RUN_AS_NODE;
  return env as Record<string, string>;
}

test('packaged retained diagnostics, local shortage, exact traces, configuration and isolated targets', async () => {
  test.setTimeout(240000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-overview-ui-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  const seed = spawnSync(resolve('.venv/bin/python'), ['tests/engine/overview_fixture.py', worlds], { encoding: 'utf8' });
  expect(seed.status, seed.stderr).toBe(0);
  const app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: environment(join(directory, 'app')) });
  try {
    const page = await app.firstWindow(); await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
    await page.getByRole('button', { name: 'Choose sandbox folder' }).click();
    await page.getByLabel('Open civilization and branch').selectOption('civ/main');
    const overview = page.getByRole('region', { name: 'Diagnostic overview', exact: true });
    await expect(overview.getByText('Retained evidence: complete', { exact: false })).toBeVisible();
    // Reads run against a workspace registry that cannot execute this saved model.
    await expect(overview.getByRole('region', { name: 'Reserve', exact: true }).getByRole('button', { name: '0 kg', exact: true })).toBeVisible();
    const catalogue = await page.evaluate(() => window.poliscope.workspaceCatalogue());
    const context = catalogue.branches[0].context;
    const before = await page.evaluate(context => window.poliscope.overview({ context, scope_id: 'east', collection: 'accounts', all_scopes: true, item_id: null, cursor: null }), context);
    await overview.getByText('Try a session target for Reserve', { exact: true }).click();
    const target = overview.getByRole('region', { name: 'Reserve', exact: true });
    await target.getByLabel('Target value (kg)').fill('1');
    await target.getByRole('button', { name: 'Compare session target' }).click();
    await expect(target.getByText('Outside your target', { exact: false })).toBeVisible();
    await target.getByLabel('Target value (kg)').fill('0');
    await target.getByRole('button', { name: 'Compare session target' }).click();
    await expect(target.getByText('Within your target', { exact: false })).toBeVisible();
    const after = await page.evaluate(context => window.poliscope.overview({ context, scope_id: 'east', collection: 'accounts', all_scopes: true, item_id: null, cursor: null }), context);
    expect(after).toEqual(before);
    expect((await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context).toEqual(context);
    // Keyboard-only definition and selected calculation opening.
    await target.getByRole('button', { name: 'Inspect Reserve', exact: true }).focus(); await page.keyboard.press('Enter');
    const inspector = page.getByRole('complementary', { name: 'Evidence inspector' });
    await expect(inspector).toContainText('account_result → stock → available');
    await inspector.getByRole('button', { name: 'Open calculation', exact: false }).focus(); await page.keyboard.press('Enter');
    await expect(inspector.getByRole('table', { name: 'Typed inputs and calculated results' })).toBeVisible();
    await expect(inspector).toContainText('0 kg');
    await inspector.getByRole('button', { name: 'Evidence synthetic:source', exact: true }).first().click();
    await expect(inspector.getByRole('region', { name: 'Source or assumption' })).toContainText('MIT');
    await expect(inspector.getByRole('region', { name: 'Source or assumption' })).toContainText('<img src="https://sink.invalid/private">');
    await expect(inspector.locator('img')).toHaveCount(0);
    await inspector.getByRole('button', { name: 'Evidence synthetic:assumption', exact: true }).first().click();
    await expect(inspector.getByRole('region', { name: 'Source or assumption' })).toContainText('No inter-scope transfer mechanism is declared.');
    await inspector.getByRole('button', { name: 'Next trace page', exact: true }).click();
    await expect(inspector.getByRole('button', { name: 'First trace page' })).toBeVisible();
    await inspector.getByRole('button', { name: 'Close evidence inspector' }).focus();
    await page.keyboard.press('Escape');
    await expect(inspector).toHaveCount(0);
    await expect(target.getByRole('button', { name: 'Inspect Reserve', exact: true })).toBeFocused();
    await target.getByRole('button', { name: 'Show local/group distribution' }).click();
    await expect(overview.getByRole('table', { name: 'Exact retained values across local and group scopes' })).toContainText('200 kg');
    await expect(overview.getByRole('region', { name: 'Indicator distribution chart' })).toBeVisible();
    // Configurable small set and all seven distinct text meanings.
    await overview.locator('summary').filter({ hasText: 'Choose overview indicators' }).click();
    const choices = overview.getByRole('group', { name: 'Small indicator set' });
    for (const box of await choices.getByRole('checkbox').all()) if (await box.isChecked()) await box.uncheck();
    for (const status of ['known', 'partial', 'missing_input', 'unmodeled', 'conflict', 'solver_failure', 'not_applicable']) await choices.getByRole('checkbox', { name: `Synthetic ${status}`, exact: true }).check();
    const cards = overview.locator('.indicator-grid');
    for (const label of ['Known', 'Partial coverage', 'Missing input', 'Unmodeled', 'Conflict', 'Solver failure', 'Not applicable']) await expect(cards).toContainText(label);
    await choices.getByRole('checkbox', { name: 'green', exact: true }).check();
    await expect(choices.getByRole('checkbox', { name: 'orange', exact: true })).toBeDisabled();
    await page.getByRole('combobox', { name: 'Scope', exact: true }).selectOption('region');
    await expect(overview.getByRole('region', { name: 'Reserve', exact: true }).getByRole('button', { name: '200 kg', exact: true })).toBeVisible();
    const allFindings = overview.getByRole('region', { name: 'Findings across scopes' });
    await expect(allFindings.getByRole('button', { name: 'physical shortage · east · Known', exact: true })).toHaveCount(2);
    await allFindings.getByRole('listitem').filter({ hasText: 'A declared claim has an unmet amount' }).getByRole('button').click();
    // Local unmet demand remains visible beside the regional reserve of 200 kg.
    await expect(page.getByRole('complementary', { name: 'Evidence inspector' })).toContainText('80 kg');
    await page.screenshot({ path: '/tmp/poliscope-overview.png', fullPage: true });
    // Invalid context and injected execution fields fail through packaged IPC.
    expect(await page.evaluate(async context => {
      try { await window.poliscope.overview({ context: { ...context, revision_id: 'foreign' }, scope_id: 'region', collection: 'indicators', all_scopes: true, item_id: null, cursor: null }); return false; } catch { return true; }
    }, context)).toBe(true);
    const revision = page.getByLabel('Read a retained revision', { exact: false });
    await revision.fill(seed.stdout.trim()); await revision.press('Enter');
    await expect(overview.getByRole('region', { name: 'Reserve', exact: true }).getByRole('button', { name: '0 kg', exact: true })).toBeVisible();
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});
