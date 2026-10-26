import { test, expect as baseExpect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
const expect = baseExpect.configure({ timeout: 20_000 });
const base = resolve(`out/Poliscope-${process.platform}-${process.arch}`);
const executablePath = process.platform === 'darwin' ? join(base, 'Poliscope.app/Contents/MacOS/poliscope') : join(base, `poliscope${process.platform === 'win32' ? '.exe' : ''}`);
function environment(data: string) {
  const env: Record<string, string | undefined> = { ...process.env, POLISCOPE_USER_DATA: data }; delete env.ELECTRON_RUN_AS_NODE;
  return env as Record<string, string>;
}

test('E2E-005 packaged interview cancel apply stale rejection qualitative proposal and reopen', async () => {
  test.setTimeout(240_000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-interview-ui-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  let app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: environment(join(directory, 'app')) });
  try {
    let page = await app.firstWindow();
    const choose = async () => {
      await app.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, worlds);
      await page.getByRole('button', { name: 'Choose sandbox folder' }).click();
    };
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await choose();
    await page.getByLabel('Civilization name', { exact: true }).fill('Interview society');
    await page.getByRole('button', { name: 'Create sandbox', exact: true }).click();
    await expect(page.getByRole('cell', { name: 'Unknown', exact: true })).toHaveCount(2);
    const catalogue = await page.evaluate(() => window.poliscope.workspaceCatalogue());
    const branch = catalogue.branches[0];
    const materials = page.locator('.domain-grid button').nth(0);
    await materials.focus(); await page.keyboard.press('Enter');
    const interview = page.getByRole('region', { name: 'Domain interview' });
    await expect(interview.getByRole('radio')).toHaveCount(4);
    await interview.getByText('Original wording and source', { exact: true }).focus(); await page.keyboard.press('Enter');
    await expect(interview).toContainText('Source adoption is historical context');
    await interview.getByRole('radio').first().focus(); await page.keyboard.press('Space');
    await expect(page.getByLabel('Open civilization and branch')).toBeDisabled();
    await interview.getByLabel('Preview population (people)').fill('125');
    await interview.getByLabel('Preview land area (km²)').fill('2.50');
    await interview.getByLabel('Private rationale (optional)').fill('Private UI rationale canary');
    await interview.getByRole('button', { name: 'Preview draft', exact: true }).focus(); await page.keyboard.press('Enter');
    const preview = page.getByRole('region', { name: 'Noncommitting preview' });
    await expect(preview).toContainText('None; numerical mechanisms are not supplied');
    await expect(preview.getByRole('cell', { name: '125 people', exact: true })).toBeVisible();
    // Actual production catalogue still points at the original head.
    expect((await page.evaluate(() => window.poliscope.workspaceCatalogue())).branches[0].context.revision_id).toBe(branch.context.revision_id);
    await interview.getByRole('button', { name: 'Cancel draft', exact: true }).focus(); await page.keyboard.press('Enter');
    await expect(preview).toHaveCount(0);
    await expect(page.getByLabel('Open civilization and branch')).toBeEnabled();
    await expect(page.getByRole('cell', { name: 'Unknown', exact: true })).toHaveCount(2);
    // Preview/apply uses a fresh draft after cancellation.
    await interview.getByRole('radio').nth(1).check();
    await interview.getByLabel('Preview population (people)').fill('125');
    await interview.getByLabel('Private rationale (optional)').fill('Private UI rationale canary');
    await interview.getByRole('button', { name: 'Preview draft', exact: true }).click();
    await preview.getByRole('button', { name: 'Apply draft', exact: true }).focus(); await page.keyboard.press('Enter');
    await expect(page.getByText('Applied one design revision.', { exact: false })).toBeVisible();
    await expect(page.getByRole('table', { name: 'Authored conditions for the selected revision and scope' }).getByRole('cell', { name: '125 people', exact: true })).toBeVisible();
    await expect(page.getByLabel('Open civilization and branch')).toBeEnabled();
    await page.locator('.domain-grid button').nth(2).focus(); await page.keyboard.press('Enter');
    await expect(interview.getByRole('radio')).toHaveCount(4);
    await interview.getByRole('radio', { name: 'Propose a qualitative alternative', exact: true }).check();
    const hostile = '<img src="https://untrusted.invalid/leak" onerror="alert(1)"> Unmodeled council';
    await interview.getByLabel('Proposed arrangement').fill(hostile);
    await interview.getByRole('button', { name: 'Preview draft', exact: true }).click();
    await expect(preview).toContainText('Qualitative model gap');
    await preview.getByRole('button', { name: 'Apply draft', exact: true }).click();
    await expect(interview.getByText('Current qualitative commitment', { exact: true })).toBeVisible();
    await interview.getByText('Current qualitative commitment', { exact: true }).click();
    await expect(interview.locator('.current-commitment')).toContainText('Unmodeled council');
    await expect(interview.locator('img')).toHaveCount(0);
    await interview.getByRole('button', { name: 'Defer this question', exact: true }).click();
    await expect(interview.getByRole('status')).toContainText('Deferred');
    await page.locator('.domain-grid button').nth(6).click();
    await expect(interview).toContainText('Health and wellbeing');
    // Optional clarification is a local, explicit public draft, usable without a key.
    await interview.getByRole('button',{name:'Review this question with optional assistance',exact:true}).press('Enter');
    const assistant=page.getByRole('region',{name:'Optional text assistance'});
    await expect(assistant.getByText('Authored interview question for optional review',{exact:true})).toBeVisible();
    await assistant.getByRole('button',{name:'Use this public question as the editable draft',exact:true}).press('Enter');
    const draft=await assistant.getByLabel('Text to share',{exact:true}).inputValue();expect(draft).toContain('Clarify this authored interview question');expect(draft).not.toContain('Private UI rationale canary');
    await expect(assistant.getByRole('button',{name:'Review request',exact:true})).toBeDisabled();
    await page.screenshot({ path: '/tmp/poliscope-interview.png', fullPage: true });
    await app.close();
    app = await electron.launch({ executablePath, args: ['--no-sandbox'], env: environment(join(directory, 'app')) });
    page = await app.firstWindow(); await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await choose();
    await page.getByLabel('Open civilization and branch').selectOption(`${branch.context.civilization_id}/main`);
    await expect(page.getByRole('cell', { name: '125 people', exact: true })).toBeVisible();
    await page.locator('.domain-grid button').nth(2).click();
    await page.getByText('Current qualitative commitment', { exact: true }).click();
    await expect(page.getByRole('region', { name: 'Domain interview' }).locator('.current-commitment')).toContainText('Unmodeled council');
    // Move the actual branch through a second production host after UI preview.
    const reopenedInterview = page.getByRole('region', { name: 'Domain interview' });
    await reopenedInterview.getByRole('radio').first().check();
    await reopenedInterview.getByRole('button', { name: 'Preview draft', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Noncommitting preview' })).toBeVisible();
    const concurrent = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', `
import sys
from pathlib import Path
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.workspace import registry
from poliscope_engine import interviews
with Store(Path(sys.argv[1])) as store:
 service=Revisions(store,registry=registry())
 branch=service.catalogue()[0]
 edit=dict(query=dict(context=branch.context.model_dump(),scope_id='home',domain_id='domain:3'),choice_id='interview:domain-3/option-3',proposal=None,population=None,land_area=None,rationale='')
 preview=interviews.stage(service,edit,'concurrent')[3]
 assert interviews.apply(service,dict(edit=edit,candidate_digest=preview.candidate_digest),'concurrent').status=='applied'
`, worlds], { encoding: 'utf8' });
    expect(concurrent.status, concurrent.stderr).toBe(0);
    await page.getByRole('button', { name: 'Apply draft', exact: true }).click();
    await expect(page.getByText('The branch changed. Nothing from this draft was applied.', { exact: false })).toBeVisible();
    await page.getByText('Current qualitative commitment', { exact: true }).click();
    await expect(reopenedInterview.locator('.current-commitment')).toContainText('Nested deliberation');
    const check = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', `
import sys
from pathlib import Path
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import HistoryQuery
with Store(Path(sys.argv[1])) as store:
 service=Revisions(store,registry=None)
 branch=service.catalogue()[0]
 history=service.history(HistoryQuery(context=branch.context,cursor=None,limit=100)).items
 assert len(history)==4
 records=[service.read(row.context) for row in history]
 assert [len(row.decision.alternatives) for row in records]==[0,3,4,3]
 assert all('Private UI rationale canary' not in row.model_dump_json() for row in records)
 assert all(not row.inputs.design.policies and not row.inputs.goals for row in records)
 private=list((Path(sys.argv[1])/'private-interviews').glob('*.json'))
 assert len(private)==1 and 'Private UI rationale canary' in private[0].read_text()
`, worlds], { encoding: 'utf8' });
    expect(check.status, check.stderr).toBe(0);
  } catch (error) {
    try {
      const failed = await app.firstWindow();
      await test.info().attach('interview-state', { body: await failed.locator('body').innerText(), contentType: 'text/plain' });
      await test.info().attach('interview-screen', { body: await failed.screenshot({ fullPage: true }), contentType: 'image/png' });
    } catch { /* Preserve the original failure if the app exited. */ }
    throw error;
  } finally { await app.close(); await rm(directory, { recursive: true, force: true }); }
});
