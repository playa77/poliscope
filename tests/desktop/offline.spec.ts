import { test, expect, _electron as electron, type Page, type Locator } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { spawn, spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const base = resolve(`out/Poliscope-${process.platform}-${process.arch}`);
const executablePath = process.platform === 'darwin' ? join(base, 'Poliscope.app/Contents/MacOS/poliscope') : join(base, `poliscope${process.platform === 'win32' ? '.exe' : ''}`);
function environment(data: string) {
  const env: Record<string, string | undefined> = { ...process.env, POLISCOPE_USER_DATA: data };
  delete env.ELECTRON_RUN_AS_NODE;
  for (const key of Object.keys(env)) if (/API_KEY|OPENROUTER|OPENAI|ANTHROPIC/.test(key)) delete env[key];
  return env as Record<string, string>;
}
async function press(page: Page, target: Locator, key = 'Enter') {
  await expect(target).toBeEnabled(); await target.focus(); await expect(target).toBeFocused(); await page.keyboard.press(key);
}
async function type(page: Page, target: Locator, value: string) {
  await expect(target).toBeEnabled(); await target.focus(); await expect(target).toBeFocused();
  await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.insertText(value); await expect(target).toHaveValue(value);
}
async function select(page: Page, target: Locator, value: string) {
  await expect.poll(() => target.locator('option').evaluateAll((options, value) => options.some(o => (o as HTMLOptionElement).value === value), value)).toBe(true);
  const index = await target.locator('option').evaluateAll((options, value) => options.findIndex(o => (o as HTMLOptionElement).value === value), value);
  expect(index).toBeGreaterThanOrEqual(0);
  await expect(target).toBeEnabled(); await target.focus(); await page.keyboard.press('Space');
  await page.keyboard.press('Home');
  // The disabled placeholder is skipped by the native menu. Commit once.
  for (let i = 1; i < index; i++) await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter'); await expect(target).toHaveValue(value);
}
function python(source: string, directory: string) {
  const result = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', source, directory], { encoding: 'utf8' });
  expect(result.status, result.stderr).toBe(0); return result.stdout.trim();
}

for (const id of ['E2E-001', 'E2E-016.a']) test(id + ' offline keyboard production create preview cancel apply fork compare trace and reopen', async () => {
  test.setTimeout(240_000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-offline-'));
  const worlds = join(directory, 'worlds'); const numeric = join(directory, 'numeric');
  await mkdir(worlds); await mkdir(numeric);
  const seed = spawnSync(resolve('.venv/bin/python'), ['tests/engine/overview_fixture.py', numeric], { encoding: 'utf8' });
  expect(seed.status, seed.stderr).toBe(0);
  let app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: environment(join(directory, 'app')) });
  let blocked = 0;
  const offline = async () => app.evaluate(({ session }) => {
    // Every HTTP destination fails, including future provider endpoints. No UI/IPC replacement.
    session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*'] }, (_details, callback) => callback({ cancel: true }));
  });
  try {
    let page = await app.firstWindow(); await expect(page.getByRole('status').filter({ hasText: /^Local engine ready$/ })).toHaveText('Local engine ready'); await offline();
    blocked = await app.evaluate(async ({ session }) => { try { await session.defaultSession.fetch('https://api.openai.com/v1/models'); return 0; } catch { return 1; } });
    expect(blocked).toBe(1);
    const choose = async (folder: string) => {
      await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, folder);
      await press(page, page.getByRole('button', { name: 'Choose sandbox folder' }));
    };
    await choose(worlds);
    await type(page, page.getByLabel('Civilization name', { exact: true }), 'Offline keyboard society');
    await press(page, page.getByRole('button', { name: 'Create sandbox', exact: true }));
    await expect(page.getByRole('cell', { name: 'Unknown', exact: true })).toHaveCount(2);
    const root = (await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context;
    await press(page, page.locator('.domain-grid button').first());
    let interview = page.getByRole('region', { name: 'Domain interview' });
    await press(page, interview.getByText('Original wording and source', { exact: true }));
    await expect(interview).toContainText('Source adoption is historical context; only Apply records a player choice');
    await expect(interview).toContainText('These are original synthetic exploration templates.');
    await press(page, interview.getByRole('radio').first(), 'Space');
    await type(page, interview.getByLabel('Preview population (people)'), '125');
    await press(page, interview.getByRole('button', { name: 'Preview draft', exact: true }));
    await expect(page.getByRole('region', { name: 'Noncommitting preview' })).toContainText('125 people');
    expect((await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context).toEqual(root);
    await press(page, interview.getByRole('button', { name: 'Cancel draft', exact: true }));
    await expect(page.getByRole('region', { name: 'Noncommitting preview' })).toHaveCount(0);
    await press(page, interview.getByRole('radio').first(), 'Space');
    await type(page, interview.getByLabel('Preview population (people)'), '125');
    await press(page, interview.getByRole('button', { name: 'Preview draft', exact: true }));
    await press(page, page.getByRole('button', { name: 'Apply draft', exact: true }));
    await expect(page.getByRole('table', { name: 'Authored conditions for the selected revision and scope' })).toContainText('125 people');
    const saved = (await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context;
    python(`import sys\nfrom pathlib import Path\nfrom poliscope_engine.storage import Store\nfrom poliscope_engine.revisions import Revisions\nfrom poliscope_engine.contracts.revisions import HistoryQuery\nwith Store(Path(sys.argv[1])) as store:\n s=Revisions(store,registry=None)\n b=s.catalogue()[0]\n h=s.history(HistoryQuery(context=b.context,cursor=None,limit=100))\n assert len(h.items)==2\n r=s.read(b.context)\n assert len(r.decision.alternatives)==3\n assert not r.inputs.goals and not r.inputs.design.policies\n assert next(v.value.value for v in r.inputs.values if v.id=='population:value')=='125'\n print(b.context.revision_id)`, worlds);
    await press(page, page.getByRole('button', { name: 'History and comparison', exact: true }));
    let history = page.getByRole('region', { name: 'Design history', exact: true });
    await type(page, history.getByLabel('Branch name', { exact: true }), 'Keyboard fork');
    await type(page, history.getByLabel('Revision to fork or restore'), root.revision_id);
    await press(page, history.getByRole('button', { name: 'Fork revision', exact: true }));
    await expect(page.getByLabel('Selected state')).toContainText('Keyboard fork');
    await press(page, history.getByRole('button', { name: 'Compare with ' + saved.revision_id, exact: true }));
    await expect(history.getByRole('region', { name: 'Retained comparison' })).toContainText('125');
    // Inspect separately authored numerical evidence using the same real UI/engine/store path.
    await choose(numeric);
    await select(page, page.getByLabel('Open civilization and branch'), 'civ/main');
    await press(page, page.getByRole('button', { name: 'Civilization overview', exact: true }));
    const overview = page.getByRole('region', { name: 'Diagnostic overview', exact: true });
    await press(page, overview.getByRole('button', { name: 'Inspect Reserve', exact: true }));
    const inspector = page.getByRole('complementary', { name: 'Evidence inspector' });
    await expect(inspector).toContainText('account_result → stock → available');
    await press(page, inspector.getByRole('button', { name: 'Open calculation', exact: false }));
    await expect(inspector.getByRole('table', { name: 'Typed inputs and calculated results' })).toContainText('0 kg');
    await press(page, inspector.getByRole('button', { name: 'Evidence synthetic:source', exact: true }).first());
    await expect(inspector).toContainText('MIT');
    await press(page, inspector.getByRole('button', { name: 'Close evidence inspector' }));
    await expect(overview.getByRole('button', { name: 'Inspect Reserve', exact: true })).toBeFocused();
    await press(page, overview.getByText('Distributions, accounts and commitments', { exact: true }));
    const account = overview.getByRole('table', { name: 'Exact retained values across local and group scopes' }).getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'stock', exact: true }) }).getByRole('button');
    await press(page, account);
    await expect(inspector.getByRole('table', { name: 'Exact reconciled account' })).toContainText('0 kg');
    await press(page, inspector.getByRole('button', { name: 'Close evidence inspector' }));
    await expect(account).toBeFocused();
    await page.screenshot({ path: '/tmp/poliscope-offline.png', fullPage: true });
    await app.close();
    app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: environment(join(directory, 'app')) });
    page = await app.firstWindow(); await expect(page.getByRole('status').filter({ hasText: /^Local engine ready$/ })).toHaveText('Local engine ready'); await offline();
    await choose(worlds);
    await select(page, page.getByLabel('Open civilization and branch'), root.civilization_id + '/main');
    await expect(page.getByRole('cell', { name: '125 people', exact: true })).toBeVisible();
    expect((await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches.find(b => b.context.branch_id === 'main')!.context).toEqual(saved);
    await press(page, page.getByRole('button', { name: 'History and comparison', exact: true }));
    history = page.getByRole('region', { name: 'Design history', exact: true });
    await expect(history.getByRole('button', { name: 'Inspect revision ' + root.revision_id, exact: true })).toBeEnabled();
    await test.info().attach('saved-identities', { body: JSON.stringify({ root, saved, numeric_root: seed.stdout.trim(), provider_network: 'blocked', key: 'absent' }), contentType: 'application/json' });
  } catch (error) { const page = await app.firstWindow(); await test.info().attach('offline-state', { body: await page.locator('body').innerText(), contentType: 'text/plain' }); throw error; }
  finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});

test('E2E-006.a actual child crash failed save confirmed identity and restart', async () => {
  test.setTimeout(180_000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-fault-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  const app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: environment(join(directory, 'app')) });
  let lockOwner: ReturnType<typeof spawn> | undefined;
  try {
    const page = await app.firstWindow(); await expect(page.getByRole('status').filter({ hasText: /^Local engine ready$/ })).toHaveText('Local engine ready');
    const choose = async () => {
      await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
      await press(page, page.getByRole('button', { name: 'Choose sandbox folder' }));
    };
    await choose(); await type(page, page.getByLabel('Civilization name', { exact: true }), 'Fault society');
    await press(page, page.getByRole('button', { name: 'Create sandbox', exact: true }));
    await expect(page.getByRole('cell', { name: 'Unknown', exact: true })).toHaveCount(2);
    const root = (await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context;
    await press(page, page.locator('.domain-grid button').first());
    const interview = page.getByRole('region', { name: 'Domain interview' });
    await press(page, interview.getByRole('radio').first(), 'Space');
    await type(page, interview.getByLabel('Preview population (people)'), '125');
    await press(page, interview.getByRole('button', { name: 'Preview draft', exact: true }));
    await expect(page.getByRole('region', { name: 'Noncommitting preview' })).toBeVisible();
    // Hold a real SQLite write lock: the save must fail without accepting a revision.
    const writer = lockOwner = spawn(resolve('.venv/bin/python'), ['-I', '-c', "import sys,sqlite3; from pathlib import Path; c=sqlite3.connect(Path(sys.argv[1])/'poliscope.sqlite3'); c.execute('BEGIN IMMEDIATE'); print('locked',flush=True); sys.stdin.readline(); c.rollback(); c.close()", worlds]);
    await new Promise<void>((resolve, reject) => { writer.stdout.once('data', () => resolve()); writer.once('error', reject); });
    await press(page, page.getByRole('button', { name: 'Apply draft', exact: true }));
    await expect(interview.getByRole('alert')).toContainText('Apply confirmation unavailable');
    await expect(page.getByLabel('Selected state')).toContainText(root.revision_id);
    await expect(page.getByText('Unsaved revision draft:', { exact: false })).toBeVisible();
    await new Promise<void>((resolve, reject) => { writer.once('exit', code => code === 0 ? resolve() : reject(new Error('Lock owner failed'))); writer.stdin.end('release\n'); });
    expect((await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context).toEqual(root);
    await press(page, page.getByRole('button', { name: 'Retry Apply', exact: true }));
    await expect(page.getByRole('cell', { name: '125 people', exact: true })).toBeVisible();
    const saved = (await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context;
    await press(page, page.getByRole('button', { name: 'World and institutions', exact: true }));
    await expect(page.getByLabel('Open civilization and branch')).toBeEnabled();
    // Kill the real page-query child, rather than an unrelated background observation.
    const mainPid = app.process().pid!;
    let killed = false;
    const timer = setInterval(() => {
      const ps = spawnSync('ps', ['--ppid', String(mainPid), '-o', 'pid=,args='], { encoding: 'utf8' });
      const row = ps.stdout.split('\n').find(row => row.includes('poliscope-engine') && row.includes('--workspace') && row.includes('--operation page'));
      if (row) { try { process.kill(Number(row.trim().split(/\s+/)[0]), 'SIGKILL'); killed = true; } catch {} clearInterval(timer); }
    }, 10);
    try {
      const outcome = await page.evaluate(async context => {
        try { await window.poliscope.worldPage({ context, scope_id: 'home', collection: 'values', cursor: null }); return 'returned'; }
        catch { return 'rejected'; }
      }, saved);
      expect(killed).toBe(true); expect(outcome).toBe('rejected');
    } finally { clearInterval(timer); }
    await expect(page.getByLabel('Selected state')).toContainText(saved.revision_id);
    await expect(page.getByLabel('Selected state')).toContainText('Confirmed design revision');
    await press(page, page.getByRole('button', { name: 'Reconnect local engine' }));
    await expect(page.getByRole('status').filter({ hasText: /^Local engine ready$/ })).toHaveText('Local engine ready');
    await choose(); await select(page, page.getByLabel('Open civilization and branch'), root.civilization_id + '/main');
    await expect(page.getByRole('cell', { name: '125 people', exact: true })).toBeVisible();
    expect((await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context).toEqual(saved);
    python(`import sys\nfrom pathlib import Path\nfrom poliscope_engine.storage import Store\nfrom poliscope_engine.revisions import Revisions\nfrom poliscope_engine.contracts.revisions import HistoryQuery\nwith Store(Path(sys.argv[1])) as store:\n s=Revisions(store,registry=None)\n b=s.catalogue()[0]\n assert len(s.history(HistoryQuery(context=b.context,cursor=None,limit=100)).items)==2`, worlds);
    await test.info().attach('fault-identities', { body: JSON.stringify({ root, saved, killed }), contentType: 'application/json' });
  } catch (error) { const page = await app.firstWindow(); await test.info().attach('offline-state', { body: await page.locator('body').innerText(), contentType: 'text/plain' }); throw error; }
  finally { lockOwner?.kill(); await app.close(); await rm(directory, { recursive: true, force: true }); }
});
