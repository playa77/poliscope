import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
const base = resolve(`out/Poliscope-${process.platform}-${process.arch}`);
const executablePath = process.platform === 'darwin' ? join(base, 'Poliscope.app/Contents/MacOS/poliscope') : join(base, `poliscope${process.platform === 'win32' ? '.exe' : ''}`);
const args = ['--no-sandbox'];
function environment(data: string) {
  const env: Record<string, string | undefined> = { ...process.env, POLISCOPE_USER_DATA: data }; delete env.ELECTRON_RUN_AS_NODE;
  return env as Record<string, string>;
}

test('packaged production creation preserves unanswered choices, explicit editable references and cold reopen', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-creation-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  let app = await electron.launch({ executablePath, args, env: environment(join(directory, 'app')) });
  try {
    let page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    const choose = async () => {
      await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
      await page.getByRole('button', { name: 'Choose sandbox folder' }).click();
    };
    await choose();
    await page.getByLabel('Civilization name', { exact: true }).fill('An open society');
    await expect(page.getByLabel('Starting setup')).toHaveValue('blank');
    await page.getByLabel('Purpose (optional, stays in this session)').fill('Private session purpose');
    await page.getByRole('button', { name: 'Create sandbox', exact: true }).click();
    await expect(page.getByText('0 declared goals · 0 selected policies · 0 registered mechanisms')).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Unknown', exact: true })).toHaveCount(2);
    await expect(page.getByRole('combobox', { name: 'Scope', exact: true })).toBeEnabled();
    const domains = page.locator('.domain-grid button');
    await expect(domains).toHaveCount(12);
    for (let i = 0; i < 12; i++) {
      await domains.nth(i).focus(); await page.keyboard.press('Enter');
      await expect(domains.nth(i)).toHaveAttribute('aria-pressed', 'true');
      await expect(page.getByRole('region', { name: 'Selected domain' })).toContainText('Open for exploration');
    }
    await page.getByRole('button', { name: 'State inspector', exact: true }).click();
    await expect(page.getByRole('complementary', { name: 'State inspector' })).toContainText('workspace:unmodeled');
    await page.screenshot({ path: '/tmp/poliscope-workspace.png', fullPage: true });
    await page.getByText('Create a civilization', { exact: true }).click();
    await page.getByLabel('Civilization name', { exact: true }).fill('Edited reference');
    await page.getByLabel('Starting setup').selectOption('reference:small-settlement');
    await expect(page.getByLabel('Starting population (people, optional)')).toHaveValue('100');
    await page.getByLabel('Starting population (people, optional)').fill('125');
    await page.getByRole('button', { name: 'Create sandbox', exact: true }).click();
    await expect(page.getByRole('cell', { name: '125 people', exact: true })).toBeVisible();
    await expect(page.getByRole('cell', { name: '10 km2', exact: true })).toBeVisible();
    const catalogue = await page.evaluate(() => window.poliscope.workspaceCatalogue());
    expect(catalogue.branches).toHaveLength(2);
    const ordinary = catalogue.branches.find(b => b.name === 'An open society')!;
    // A cold app reopens the confirmed production store, rather than a renderer cache.
    await app.close();
    app = await electron.launch({ executablePath, args, env: environment(join(directory, 'app')) });
    page = await app.firstWindow(); await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await choose();
    await page.getByLabel('Open civilization and branch').selectOption(`${ordinary.context.civilization_id}/main`);
    await expect(page.getByRole('cell', { name: 'Unknown', exact: true })).toHaveCount(2);
    await expect(page.getByRole('cell', { name: '125 people', exact: true })).toHaveCount(0);
    const check = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', `
import sys
from pathlib import Path
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
with Store(Path(sys.argv[1])) as store:
 service=Revisions(store, registry=None)
 for branch in service.catalogue():
  record=service.read(branch.context)
  assert record.inputs.goals == [] and record.inputs.design.policies == []
  assert 'Private session purpose' not in record.model_dump_json()
`, worlds], { encoding: 'utf8' });
    expect(check.status, check.stderr).toBe(0);
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});

test('packaged navigation binds branch, retained revision and scope to the production world', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-context-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  const seed = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', `
import sys
from pathlib import Path
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.workspace import dispatch, registry
from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest, BranchRequest
with Store(Path(sys.argv[1])) as store:
 service=Revisions(store, registry=registry())
 state=dispatch(service,'create',dict(name='Two scopes',setup='blank',scope_name='Home',population='10',land_area=None),'one')
 data=service.read(state.context).inputs.model_dump(mode='json')
 data['scopes'].append(dict(data['scopes'][0],id='other',label='Other'))
 population=next(v for v in data['values'] if v['id']=='population:value')
 data['values'].append(dict(population,id='other:population',property_id='other:people',scope_id='other',value=dict(population['value'],value='20')))
 data['owners'].append(dict(entity_id='population',property_id='other:people',partition='conditions',writer_id='player'))
 request=PreviewRequest.model_validate(dict(revision_contract=1,context=state.context.model_dump(),changes=[dict(kind='replace_inputs',inputs=data)],decision=dict(alternatives=[],selected_id=None,rationale_ref=None)))
 candidate=service.preview(request)
 applied=service.apply(ApplyRequest(revision_contract=1,operation_id='edit',preview=request,candidate_digest=candidate.candidate_digest))
 service.change_branch(BranchRequest(revision_contract=1,operation_id='fork',context=applied.context,expected_sequence=applied.branch_sequence,action='fork',new_branch_id='alternative',name='Alternative'))
 print(state.context.revision_id)
`, worlds], { encoding: 'utf8' });
  expect(seed.status, seed.stderr).toBe(0);
  const app = await electron.launch({ executablePath, args, env: environment(join(directory, 'app')) });
  try {
    const page = await app.firstWindow(); await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
    await page.getByRole('button', { name: 'Choose sandbox folder' }).click();
    await page.getByLabel('Open civilization and branch').selectOption('civ:one/main');
    await expect(page.getByRole('cell', { name: '10 people', exact: true })).toBeVisible();
    await page.getByRole('combobox', { name: 'Scope', exact: true }).selectOption('other');
    await expect(page.getByRole('cell', { name: '20 people', exact: true })).toBeVisible();
    await expect(page.getByRole('cell', { name: '10 people', exact: true })).toHaveCount(0);
    await page.getByLabel('Open civilization and branch').selectOption('civ:one/alternative');
    await expect(page.getByRole('cell', { name: '10 people', exact: true })).toBeVisible();
    const revision = page.getByLabel('Read a retained revision', { exact: false });
    await revision.fill(seed.stdout.trim()); await revision.press('Enter');
    await expect(page.getByText('Historical revision — read only', { exact: false })).toBeVisible();
    await expect(page.getByRole('cell', { name: '10 people', exact: true })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Scope', exact: true }).locator('option')).toHaveCount(1);
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});
