import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const base = resolve(`out/Poliscope-${process.platform}-${process.arch}`);
const executablePath = process.platform === 'darwin' ? join(base, 'Poliscope.app/Contents/MacOS/poliscope') : join(base, `poliscope${process.platform === 'win32' ? '.exe' : ''}`);
function environment(data: string) {
  const env: Record<string,string|undefined> = {...process.env,POLISCOPE_USER_DATA:data}; delete env.ELECTRON_RUN_AS_NODE;
  return env as Record<string,string>;
}
test('packaged history preserves old futures, historical inspection, exact context and cold reopen', async () => {
  test.setTimeout(240000);
  const directory = await mkdtemp(join(tmpdir(),'poliscope-history-ui-'));
  const worlds = join(directory,'worlds'); await mkdir(worlds);
  let app = await electron.launch({executablePath,args:['--no-sandbox'],env:environment(join(directory,'app'))});
  try {
    let page = await app.firstWindow();
    const choose = async () => {
      await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},worlds);
      await page.getByRole('button',{name:'Choose sandbox folder'}).click();
    };
    await expect(page.getByRole('status')).toHaveText('Local engine ready'); await choose();
    await page.getByLabel('Civilization name',{exact:true}).fill('History society');
    await page.getByRole('button',{name:'Create sandbox',exact:true}).click();
    await expect(page.getByRole('cell',{name:'Unknown',exact:true})).toHaveCount(2);
    const root = (await page.evaluate(()=>window.poliscope.workspaceCatalogue())).branches[0].context;
    async function commit(population:string) {
      await page.locator('.domain-grid button').first().click();
      const interview = page.getByRole('region',{name:'Domain interview'});
      await interview.getByRole('radio').first().check();
      await interview.getByLabel('Preview population (people)').fill(population);
      await interview.getByLabel('Private rationale (optional)').fill('Private history UI canary');
      await interview.getByRole('button',{name:'Preview draft',exact:true}).click();
      await page.getByRole('button',{name:'Apply draft',exact:true}).click();
      await expect(page.getByRole('table',{name:'Authored conditions for the selected revision and scope'})).toContainText(population+' people');
    }
    await commit('125');
    const first = (await page.evaluate(()=>window.poliscope.workspaceCatalogue())).branches.find(b=>b.context.branch_id==='main')!.context;
    await page.getByRole('button',{name:'History and comparison',exact:true}).click();
    let history = page.getByRole('region',{name:'Design history',exact:true});
    await expect(history.getByRole('table',{name:'Retained design lineage · all futures in this civilization'}).getByRole('row')).toHaveCount(3);
    const undoButton = history.getByRole('button',{name:'Undo design change',exact:true});
    await expect(undoButton).toBeEnabled();
    await undoButton.focus(); await expect(undoButton).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(history.getByRole('button',{name:'Redo design change',exact:true})).toBeEnabled();
    await history.getByRole('button',{name:'Redo design change',exact:true}).click();
    await expect(history.getByRole('button',{name:'Redo design change',exact:true})).toBeDisabled();
    await history.getByRole('button',{name:'Undo design change',exact:true}).click();
    await expect(history.getByRole('button',{name:'Redo design change',exact:true})).toBeEnabled();
    await commit('150');
    // Reopen the selected folder to refresh the branch directory after apply.
    await choose(); await page.getByLabel('Open civilization and branch').selectOption(root.civilization_id+'/main');
    await expect(page.getByLabel('Open civilization and branch')).toContainText('Retained future');
    const second = (await page.evaluate(()=>window.poliscope.workspaceCatalogue())).branches.find(b=>b.context.branch_id==='main')!.context;
    await page.getByRole('button',{name:'History and comparison',exact:true}).click();
    history = page.getByRole('region',{name:'Design history',exact:true});
    await expect(history.getByRole('button',{name:'Compare with '+first.revision_id,exact:true})).toBeEnabled();
    await history.getByRole('button',{name:'Compare with '+first.revision_id,exact:true}).click();
    const comparison = history.getByRole('region',{name:'Retained comparison'});
    await expect(comparison).toContainText('population:value'); await expect(comparison).toContainText('125'); await expect(comparison).toContainText('150');
    await history.getByRole('button',{name:'Inspect revision '+first.revision_id,exact:true}).click();
    await expect(page.getByLabel('Selected state')).toContainText('Historical revision — read only');
    await history.getByRole('button',{name:'Read private rationale for inspected revision',exact:true}).click();
    await expect(history.getByRole('region',{name:'Private rationale',exact:true})).toContainText('Private history UI canary');
    await history.getByRole('button',{name:'Hide private rationale',exact:true}).click();
    await expect(history.getByRole('region',{name:'Private rationale',exact:true})).toHaveCount(0);
    await expect(history.getByRole('button',{name:'Undo design change',exact:true})).toBeDisabled();
    await history.getByRole('button',{name:'Return to branch head',exact:true}).click();
    await expect(history.getByRole('button',{name:'Undo design change',exact:true})).toBeEnabled();
    await history.getByLabel('Branch name',{exact:true}).fill('Historical experiment');
    await history.getByLabel('Revision to fork or restore').fill(first.revision_id);
    await history.getByRole('button',{name:'Fork revision',exact:true}).click();
    await expect(page.getByLabel('Selected state')).toContainText('Historical experiment');
    await history.getByLabel('Branch name',{exact:true}).fill('Renamed experiment');
    await history.getByRole('button',{name:'Rename branch',exact:true}).click();
    await expect(page.getByLabel('Selected state')).toContainText('Renamed experiment');
    await history.getByLabel('Revision to fork or restore').fill(root.revision_id);
    await history.getByRole('button',{name:'Restore revision and retain current future',exact:true}).click();
    await expect(history.getByRole('button',{name:'Undo design change',exact:true})).toBeDisabled();
    await app.close(); app = await electron.launch({executablePath,args:['--no-sandbox'],env:environment(join(directory,'app'))});
    page=await app.firstWindow(); await expect(page.getByRole('status')).toHaveText('Local engine ready'); await choose();
    await page.getByLabel('Open civilization and branch').selectOption(root.civilization_id+'/main');
    await expect(page.getByRole('cell',{name:'150 people',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'History and comparison',exact:true}).click();
    history=page.getByRole('region',{name:'Design history',exact:true});
    await expect(history.getByRole('button',{name:'Inspect revision '+first.revision_id,exact:true})).toBeEnabled();
    expect((await page.evaluate(()=>window.poliscope.workspaceCatalogue())).branches.some(b=>b.context.revision_id===second.revision_id)).toBe(true);
    await history.getByRole('table').first().locator('summary').last().click();
    await expect(history).not.toContainText('Private history UI canary');
    await expect(history.locator('img')).toHaveCount(0);
  } finally {await app.close();await rm(directory,{recursive:true,force:true});}
});

test('packaged comparison reads exact durable quantities without the fixture executable model', async () => {
  test.setTimeout(180000);
  const directory = await mkdtemp(join(tmpdir(),'poliscope-numeric-comparison-'));
  const worlds = join(directory,'worlds'); await mkdir(worlds);
  const seeded = spawnSync(resolve('.venv/bin/python'),['tests/engine/comparison_fixture.py',worlds],{encoding:'utf8'});
  expect(seeded.status,seeded.stderr).toBe(0);
  const revisions = JSON.parse(seeded.stdout) as {root:string;head:string};
  const app = await electron.launch({executablePath,args:['--no-sandbox'],env:environment(join(directory,'app'))});
  try {
    const page = await app.firstWindow();await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},worlds);
    await page.getByRole('button',{name:'Choose sandbox folder'}).click();
    await page.getByLabel('Open civilization and branch').selectOption('civ/main');
    await page.getByRole('button',{name:'History and comparison',exact:true}).click();
    const history=page.getByRole('region',{name:'Design history',exact:true});
    await history.getByRole('button',{name:'Compare with '+revisions.root,exact:true}).click();
    const comparison=history.getByRole('region',{name:'Retained comparison'});
    const reserve=comparison.getByRole('row').filter({hasText:'regional-reserve'});
    await expect(reserve).toContainText('250 kg'); await expect(reserve).toContainText('200 kg'); await expect(reserve).toContainText('-50 kg');
    await expect(reserve).toContainText('Retained evidence');await expect(reserve).toContainText('Trace evidence: complete');
    const partial=comparison.getByRole('row').filter({hasText:'status:1'});
    await expect(partial).toContainText('Not comparable');
    const missing=comparison.getByRole('row').filter({hasText:'status:2'});
    await expect(missing).toContainText('Unknown'); await expect(missing).toContainText('Not comparable');
    await history.getByRole('button',{name:'Next comparison page',exact:true}).click();
    await expect(history.getByRole('button',{name:'First comparison page',exact:true})).toBeEnabled();
    expect((await page.evaluate(()=>window.poliscope.workspaceCatalogue())).branches[0].context.revision_id).toBe(revisions.head);
  } finally {await app.close();await rm(directory,{recursive:true,force:true});}
});
