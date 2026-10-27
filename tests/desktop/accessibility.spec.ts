import { test, expect, _electron as electron, type Locator } from '@playwright/test';
import { mkdtemp, mkdir, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

async function activate(control: Locator) { await expect(control).toBeEnabled(); await control.press('Enter'); }

// Real packaged UI and production engine; no provider or network is required.
test('WP-052 keyboard focus, state meaning, preview, navigation and zoom', async () => {
  test.setTimeout(120000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-accessibility-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  const env: Record<string, string | undefined> = { ...process.env, POLISCOPE_USER_DATA: join(directory, 'app') };
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath: resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform === 'win32' ? '.exe' : ''}`), args: ['--no-sandbox'], env: env as Record<string, string> });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to society workspace' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Design a society. Begin anywhere.' })).toBeFocused();
    expect(new URL(page.url()).hash).toBe('');
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    const providers = page.getByRole('button', { name: 'Open provider settings', exact: true });
    await providers.focus(); await page.keyboard.press('Enter');
    await expect(page.getByRole('region', { name: 'Provider settings', exact: true })).toBeFocused();
    await activate(page.getByRole('button', { name: 'Close provider settings' }));
    await expect(providers).toBeFocused();
    await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
    await expect(page.getByRole('button', { name: 'Choose sandbox folder' })).toBeEnabled();
    await activate(page.getByRole('button', { name: 'Choose sandbox folder' }));
    await expect(page.getByLabel('Civilization name', { exact: true })).toBeVisible();
    await page.getByText('Explore a question without AI', { exact: true }).press('Enter');
    await expect(page.locator('.inquiry-guide')).toContainText('a total can conceal exclusion');
    await expect(page.locator('.inquiry-guide')).toContainText('not an engine judgment');
    await page.getByLabel('Civilization name', { exact: true }).fill('Keyboard inquiry');
    await activate(page.getByRole('button', { name: 'Create sandbox', exact: true }));
    await expect(page.getByRole('region', { name: 'Selected state', exact: true })).toContainText('Confirmed design revision');
    const initial = (await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context;
    await activate(page.getByRole('button', { name: 'Evidence and models', exact: true }));
    const evidence = page.getByRole('region', { name: 'Evidence and models workspace' });
    await evidence.getByLabel('Inspect evidence').selectOption('notes');
    await activate(evidence.getByRole('button', { name: 'Add private inquiry or note' }));
    await expect(evidence.getByRole('heading', { name: 'Edit evidence · unsaved' })).toBeFocused();
    await activate(evidence.getByRole('button', { name: 'Cancel evidence edit' }));
    await expect(evidence.getByRole('button', { name: 'Add private inquiry or note' })).toBeFocused();
    await activate(evidence.getByRole('button', { name: 'Add private inquiry or note' }));
    await evidence.getByLabel('Private note kind').selectOption('expectation');
    await evidence.getByLabel('Private note text').fill('I predict an authored population change, with no calculated social benefit.');
    await activate(evidence.getByRole('button', { name: 'Preview evidence edit' }));
    await expect(evidence.getByRole('heading', { name: 'Preview · not applied' })).toBeFocused();
    await activate(evidence.getByRole('button', { name: 'Apply evidence edit' }));
    await expect(evidence.getByRole('table')).toContainText('I predict an authored population change');
    await activate(page.getByRole('button', { name: 'Civilization overview', exact: true }));
    await page.locator('.domain-grid button').first().press('Enter');
    await expect(page.getByRole('region', { name: 'Selected domain', exact: true })).toBeFocused();
    const interview = page.getByRole('region', { name: 'Domain interview', exact: true });
    await interview.getByRole('radio').first().press('Space');
    await interview.getByLabel('Preview population (people)').fill('125');
    await activate(interview.getByRole('button', { name: 'Preview draft', exact: true }));
    await expect(page.getByRole('heading', { name: 'Preview · not applied', exact: true })).toBeFocused();
    const preview = page.getByRole('region', { name: 'Noncommitting preview' });
    await expect(preview).toContainText('numerical mechanisms are not supplied');
    await expect(preview.getByRole('columnheader')).toHaveCount(3);
    await activate(preview.getByRole('button', { name: 'Apply draft', exact: true }));
    await expect(page.getByText('Applied one design revision.', { exact: false })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Selected state', exact: true })).toBeFocused();
    for (const name of ['World and institutions', 'Decision atlas', 'Dependency matrix', 'Uncertainty and sensitivity', 'Timeline and experiments', 'History and comparison', 'Evidence and models', 'Civilization overview']) {
      await activate(page.getByRole('navigation', { name: 'Workspaces' }).getByRole('button', { name, exact: true }));
      await expect(page.locator('#workspace-view-heading')).toBeFocused();
      await expect(page.locator('#workspace-view-heading')).toHaveText(name);
      if (name === 'World and institutions') {
        const world = page.getByRole('region', { name: 'Canonical world and institutions' });
        const add = world.getByRole('button', { name: 'Add entity or relationship' });
        await activate(add);
        await expect(world.getByRole('heading', { name: 'Canonical world edit' })).toBeFocused();
        await activate(world.getByRole('button', { name: 'Cancel world edit' }));
        await expect(add).toBeFocused();
      }
      if (name === 'Dependency matrix') {
        await expect(page.getByRole('region', { name: 'Sparse relationship matrix' }).getByRole('table')).toBeVisible();
      }
    }
    await activate(interview.getByRole('button', { name: 'Defer this question', exact: true }));
    await expect(interview.getByRole('status')).toContainText('Deferred');
    await interview.getByText('Original wording and source', { exact: true }).press('Enter');
    await expect(interview).toContainText('Source adoption is historical context');
    await activate(page.getByRole('button', { name: 'History and comparison', exact: true }));
    const history = page.getByRole('region', { name: 'Design history', exact: true });
    await activate(history.getByRole('button', { name: 'Compare with ' + initial.revision_id, exact: true }));
    await expect(history.getByRole('region', { name: 'Retained comparison' })).toContainText('population:value');
    await history.getByLabel('Branch name', { exact: true }).fill('Inquiry alternative');
    await activate(history.getByRole('button', { name: 'Fork revision', exact: true }));
    await expect(page.getByRole('region', { name: 'Selected state', exact: true })).toContainText('Inquiry alternative');
    await activate(page.getByRole('button', { name: 'Evidence and models', exact: true }));
    await evidence.getByLabel('Inspect evidence').selectOption('notes');
    await activate(evidence.getByRole('button', { name: 'Add private inquiry or note' }));
    await evidence.getByLabel('Private note kind').selectOption('observation');
    await evidence.getByLabel('Private note text').fill('The authored condition changed; social effects remain unmodeled.');
    await activate(evidence.getByRole('button', { name: 'Preview evidence edit' }));
    await activate(evidence.getByRole('button', { name: 'Apply evidence edit' }));
    await expect(evidence.getByRole('table')).toContainText('social effects remain unmodeled');
    await activate(page.getByRole('button', { name: 'Portable archives', exact: true }));
    const archives = page.getByRole('region', { name: 'Portable archives', exact: true });
    await archives.getByLabel('Include active private notes from all revisions').press('Space');
    const reportPath = join(directory, 'inquiry.md');
    await app.evaluate(({ dialog }, path) => { dialog.showSaveDialog = async () => ({ canceled: false, filePath: path }); }, reportPath);
    await activate(archives.getByRole('button', { name: 'Export Markdown inquiry report', exact: true }));
    await expect(archives.getByRole('status')).toContainText('Inquiry report exported');
    expect(await readFile(reportPath, 'utf8')).toContain('social effects remain unmodeled');
    await activate(page.getByRole('button', { name: 'Civilization overview', exact: true }));
    // Browser zoom uses the same Electron webContents path as desktop zoom.
    await app.evaluate(({ BrowserWindow }) => { BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2); });
    await expect(page.locator('.workspace-layout')).toHaveCSS('grid-template-columns', /\d/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    const focusColor = await page.locator('#workspace-view-heading').evaluate(el => getComputedStyle(el).outlineColor);
    expect(focusColor).toBe('rgb(255, 213, 137)');
    await page.screenshot({ path: '/tmp/poliscope-accessibility-zoom.png', fullPage: true });
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});
