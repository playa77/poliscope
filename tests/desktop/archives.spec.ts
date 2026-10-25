import { test, expect as baseExpect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const expect = baseExpect.configure({ timeout: 20000 });
const executablePath = resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform === 'win32' ? '.exe' : ''}`);

test('WP-039 keyboard portable export/import, privacy defaults, historical data and dialog cancel', async () => {
  test.setTimeout(120000);
  const directory=await mkdtemp(join(tmpdir(),'poliscope-archive-ui-'));
  const source=join(directory,'source'),target=join(directory,'target'),file=join(directory,'portable.poliscope');
  await mkdir(source);await mkdir(target);
  const env: Record<string,string | undefined>={...process.env,POLISCOPE_USER_DATA:join(directory,'app')};delete env.ELECTRON_RUN_AS_NODE;
  const app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
  try {
    const page=await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},source);
    await page.getByRole('button',{name:'Choose sandbox folder'}).press('Enter');
    await page.getByLabel('Civilization name').fill('Portable society');
    await page.getByLabel('Starting population').fill('12');
    await page.getByRole('button',{name:'Create sandbox',exact:true}).press('Enter');
    await expect(page.getByRole('button',{name:'Portable archives',exact:true})).toBeEnabled();
    await page.getByRole('button',{name:'Portable archives',exact:true}).press('Enter');
    const region=page.getByRole('region',{name:'Portable archives'});
    await expect(region.getByLabel('Include active private notes from all revisions')).not.toBeChecked();
    await expect(region.getByLabel('Include active private rationale')).not.toBeChecked();
    await expect(region.getByLabel('Retained evidence')).toHaveValue('complete');
    await app.evaluate(({dialog},selected)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:selected});},file);
    await region.getByRole('button',{name:'Export portable history',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toContainText('Portable history exported');
    await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},target);
    await expect(page.getByRole('button',{name:'Choose sandbox folder'})).toBeEnabled();
    await page.getByRole('button',{name:'Choose sandbox folder'}).press('Enter');
    // Empty target has no native civilization; imported inspection must still be available.
    await expect(page.getByRole('button',{name:'Portable archives',exact:true})).toBeEnabled();
    await page.getByRole('button',{name:'Portable archives',exact:true}).press('Enter');
    await app.evaluate(({dialog},selected)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[selected]});},file);
    await region.getByRole('button',{name:'Import portable history',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toContainText('Portable history imported');
    await region.getByRole('button',{name:'Inspect imported history'}).press('Enter');
    const historical=region.getByRole('region',{name:'Imported historical data'});
    await expect(historical).toContainText('Stored facts and evidence');
    await expect(historical).toContainText('12');
    await expect(historical).toContainText('not freshly reproduced');
    await app.evaluate(({dialog})=>{dialog.showOpenDialog=async()=>({canceled:true,filePaths:[]});});
    await region.getByRole('button',{name:'Import portable history',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toHaveText('File selection cancelled.');
    expect((await page.evaluate(()=>window.poliscope.workspaceCatalogue())).branches).toEqual([]);
  } finally {await app.close();await rm(directory,{recursive:true,force:true});}
});
