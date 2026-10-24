import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const executablePath = resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform === 'win32' ? '.exe' : ''}`);

test('E2E-008 all-domain education retained quantities atlas matrix world and source share one revision', async () => {
  test.setTimeout(240000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-static-system-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  const seed = spawnSync(resolve('.venv/bin/python'), ['tests/engine/static_system_fixture.py', worlds], { encoding: 'utf8' });
  expect(seed.status, seed.stderr).toBe(0);
  const env: Record<string,string | undefined> = { ...process.env, POLISCOPE_USER_DATA: join(directory, 'app') };
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: env as Record<string,string> });
  try {
    const page = await app.firstWindow(); await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
    await page.getByRole('button', { name: 'Choose sandbox folder' }).press('Enter');
    await page.getByLabel('Open civilization and branch').selectOption('civ/main');
    await page.getByLabel('Scope', { exact: true }).selectOption('local');
    const catalogue = await page.evaluate(() => window.poliscope.workspaceCatalogue());
    const context = catalogue.branches[0].context;
    expect(context.revision_id).toBe(seed.stdout.trim());
    const overview = page.getByRole('region', { name: 'Diagnostic overview', exact: true });
    await expect(overview.getByRole('region', { name: 'Shared participant time', exact: true })).toContainText('0 hours');
    await expect(overview).toContainText('no delivered service');
    await overview.getByRole('button', { name: 'Inspect Shared participant time', exact: true }).press('Enter');
    const inspector = page.getByRole('complementary', { name: 'Evidence inspector' });
    await inspector.getByRole('button', { name: 'Evidence synthetic:whole-system', exact: true }).first().press('Enter');
    await expect(inspector.getByRole('region', { name: 'Source or assumption' })).toContainText('MIT');
    await inspector.getByRole('button', { name: 'Close evidence inspector' }).press('Enter');
    const domains = page.locator('.domain-grid button');
    await expect(domains).toHaveCount(12);
    for (let i = 0; i < 12; i++) {
      await domains.nth(i).press('Enter');
      const interview = page.getByRole('region', { name: 'Domain interview' });
      await expect(interview).toBeVisible();
      await expect.poll(() => interview.getByRole('radio').count()).toBeGreaterThan(1);
      await expect(interview.locator('input[type="radio"]:checked')).toHaveCount(0);
    }
    await page.getByRole('button', { name: 'Decision atlas', exact: true }).press('Enter');
    const atlas = page.getByRole('region', { name: 'Decision discovery' });
    await expect(atlas).toContainText('matching questions');
    await page.getByRole('button', { name: 'Dependency matrix', exact: true }).press('Enter');
    const matrix = page.getByRole('region', { name: 'Sparse relationship matrix' });
    await matrix.getByLabel('Relationship provenance', { exact: true }).selectOption('retained_execution');
    await expect(matrix.getByRole('table')).toContainText('partial');
    await page.getByRole('button', { name: 'World and institutions', exact: true }).press('Enter');
    // These are real public IPC readers and selected-context grants. No model
    // callbacks remain available in the packaged historical reader.
    const account = await page.evaluate(context => window.poliscope.overview({ context, scope_id: 'local',
      collection: 'accounts', all_scopes: true, item_id: 'time:a', cursor: null }), context);
    expect(account.items[0].kind).toBe('account');
    const source = await page.evaluate(context => window.poliscope.overview({ context, scope_id: 'local',
      collection: 'references', all_scopes: true, item_id: 'synthetic:whole-system', cursor: null }), context);
    expect(JSON.stringify(source)).toContain('static-system-v1.json');
    expect(JSON.stringify(source)).toContain('MIT');
    expect((await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context).toEqual(context);
    await test.info().attach('whole-system-context', { body: JSON.stringify(context), contentType: 'application/json' });
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});
