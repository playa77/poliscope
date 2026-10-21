import { test, expect as baseExpect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
const expect = baseExpect.configure({ timeout: 20000 });
const executablePath = resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform === 'win32' ? '.exe' : ''}`);

test('WP-030 packaged keyboard overlap projections layout isolation shared edits matrix and history', async () => {
  test.setTimeout(180000);
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-world-ui-'));
  const worlds = join(directory, 'worlds'); await mkdir(worlds);
  const seeded = spawnSync(resolve('.venv/bin/python'), ['tests/engine/exploration_fixture.py', worlds], { encoding: 'utf8' });
  expect(seeded.status,seeded.stderr).toBe(0);
  const env: Record<string,string | undefined> = { ...process.env, POLISCOPE_USER_DATA: join(directory,'app') }; delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath, args:['--no-sandbox'],env:env as Record<string,string> });
  try {
    const page=await app.firstWindow(); await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await app.evaluate(({dialog},folder)=>{ dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]}); },worlds);
    await page.getByRole('button',{name:'Choose sandbox folder'}).press('Enter');
    await page.getByLabel('Open civilization and branch').selectOption('civ/main');
    await page.getByRole('button',{name:'World and institutions',exact:true}).press('Enter');
    const world=page.getByRole('region',{name:'Canonical world and institutions'});
    await expect(world.getByRole('table')).toContainText('Shared clinic');
    await world.getByLabel('Projection',{exact:true}).selectOption('authority');
    await expect(world.getByRole('table')).toContainText('council-a → clinic');
    await expect(world.getByRole('table')).toContainText('council-b → clinic');
    await expect(world.getByRole('button',{name:'Edit clinic',exact:true})).toHaveCount(1);
    const snapshot = await page.evaluate(async () => {
      const catalogue=await window.poliscope.workspaceCatalogue();
      const context=catalogue.branches[0].context;
      return { context, page:await window.poliscope.exploration({context,scope_id:'home'}) };
    });
    const beforeSvg = await world.locator('svg').innerHTML();
    await world.getByRole('button',{name:'Rearrange diagram'}).press('Enter');
    expect(await world.locator('svg').innerHTML()).not.toBe(beforeSvg);
    expect(await page.evaluate(async context=>await window.poliscope.exploration({context,scope_id:'home'}),snapshot.context)).toEqual(snapshot.page);
    await world.getByLabel('Projection',{exact:true}).selectOption('networks');
    await expect(world.getByRole('table')).toContainText('clinic → care-network');
    await world.getByLabel('Projection',{exact:true}).selectOption('all');
    await world.getByRole('button',{name:'Edit land:value',exact:true}).press('Enter');
    await expect(page.getByRole('button',{name:'History and comparison',exact:true})).toBeDisabled();
    await world.getByLabel('Condition value',{exact:true}).fill('9');
    await world.getByRole('button',{name:'Preview world edit'}).press('Enter');
    const preview=world.getByRole('region',{name:'World edit preview'});
    await expect(preview).toContainText('9 km2');
    expect(await page.evaluate(async context => (await window.poliscope.exploration({context,scope_id:'home'})).items.find(r=>r.value?.id==='land:value')?.value?.value,snapshot.context)).toMatchObject({value:'3'});
    await world.getByRole('button',{name:'Apply world edit'}).press('Enter');
    await expect(world.getByRole('table')).toContainText('9 km2');
    await world.getByRole('button',{name:'Open world relationships in matrix'}).press('Enter');
    const matrix=page.getByRole('region',{name:'Sparse relationship matrix'});
    // Model a user reaching the next control before a pending animation frame.
    // Relationship focus must not later steal the inspector's Enter key.
    await page.evaluate(() => {
      const original = window.requestAnimationFrame.bind(window);
      const pending: FrameRequestCallback[] = [];
      window.requestAnimationFrame = callback => { pending.push(callback); return pending.length; };
      window.addEventListener('flush-matrix-focus-frame', () => {
        window.requestAnimationFrame = original;
        pending.forEach(callback => callback(performance.now()));
      }, { once: true });
    });
    await matrix.getByRole('button',{name:'Shared clinic → Starting land · requires',exact:true}).press('Enter');
    const inspectCondition = matrix.getByRole('button',{name:'Inspect conditions land:value',exact:true});
    await inspectCondition.focus();
    await page.evaluate(() => window.dispatchEvent(new Event('flush-matrix-focus-frame')));
    await expect(inspectCondition).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(matrix.getByRole('complementary',{name:'Evidence inspector'})).toContainText('9 km2');
    await matrix.getByRole('button',{name:'Inspect canonical world clinic',exact:true}).press('Enter');
    await expect(world.getByLabel('Inspect canonical identity')).toHaveValue('clinic');
    await expect(world.getByRole('table')).toContainText('Shared clinic');
    await world.getByRole('button',{name:'Show all identities'}).press('Enter');
    await world.getByRole('button',{name:'Add entity or relationship'}).press('Enter');
    await world.getByLabel('Edit kind',{exact:true}).selectOption('relationship');
    await world.getByLabel('Canonical ID',{exact:true}).fill('clinic-duty');
    await world.getByLabel('Relationship kind',{exact:true}).selectOption('obligation');
    await world.getByLabel('From identity',{exact:true}).fill('council-a');
    await world.getByLabel('To identity',{exact:true}).fill('clinic');
    await world.getByLabel('Declared terms or obligations').fill('Inspect monthly; staffing remains unanswered');
    await world.getByRole('button',{name:'Preview world edit'}).press('Enter');
    await expect(preview).toContainText('Inspect monthly');
    await world.getByRole('button',{name:'Apply world edit'}).press('Enter');
    await expect(world.getByRole('table')).toContainText('Inspect monthly');
    await page.getByRole('button',{name:'History and comparison',exact:true}).press('Enter');
    await page.getByRole('button',{name:'World and institutions',exact:true}).press('Enter');
    await expect(world.getByRole('table')).toContainText('Inspect monthly');
    await page.screenshot({path:'/tmp/poliscope-world.png',fullPage:true});
  } finally { await app.close(); await rm(directory,{recursive:true,force:true}); }
});
