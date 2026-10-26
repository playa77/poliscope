import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const executablePath=resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform==='win32'?'.exe':''}`);
test('WP-044 packaged request preferences preserve independent fallbacks, privacy, reasoning and prices after restart', async () => {
  test.setTimeout(120000);
  const directory=await mkdtemp(join(tmpdir(),'poliscope-requests-ui-'));
  const env: Record<string,string|undefined>={...process.env,POLISCOPE_USER_DATA:directory}; delete env.ELECTRON_RUN_AS_NODE;
  const launch=()=>electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
  let app=await launch();
  try {
    let page=await app.firstWindow(); await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');
    let region=page.getByRole('region',{name:'Provider settings',exact:true});
    await region.getByLabel('Profile name',{exact:true}).fill('Synthetic request preferences');
    await region.getByLabel('Selected model ID',{exact:true}).fill('future/open:model');
    await region.getByText('Generation preferences',{exact:true}).click();
    await region.getByLabel('Maximum output tokens',{exact:true}).fill('128');
    await region.getByLabel('Sampling seed',{exact:true}).fill('0');
    await region.getByLabel('frequency penalty',{exact:true}).fill('-1.5');
    await region.getByLabel('Reasoning effort',{exact:true}).selectOption('high');
    await region.getByLabel('Return reasoning',{exact:true}).selectOption('true');
    // Returning one field to default must not clear another explicit control.
    await region.getByLabel('Reasoning effort',{exact:true}).selectOption('');
    await expect(region.getByLabel('Return reasoning',{exact:true})).toHaveValue('true');
    await region.getByLabel('Reasoning effort',{exact:true}).selectOption('low');
    await region.getByText('Routing preferences',{exact:true}).click();
    await region.getByLabel('Model fallbacks in order (comma-separated)',{exact:true}).fill('future/alternate:free');
    await expect(region.getByLabel('Allow provider fallbacks',{exact:true})).not.toBeChecked();
    await region.getByLabel('Data collection preference',{exact:true}).selectOption('deny');
    await region.getByLabel('Zero data retention',{exact:true}).selectOption('true');
    await region.getByLabel('Provider sort',{exact:true}).selectOption('price');
    await region.getByLabel('Maximum prompt price',{exact:true}).fill('1.25');
    await region.getByLabel('Maximum completion price',{exact:true}).fill('0');
    await region.getByRole('button',{name:'Save provider profile',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toContainText('Saved provider settings');
    const before=await page.evaluate(()=>window.poliscope.provider({action:'list'}));
    expect(before.profiles[0].profile.routing).toMatchObject({model_fallbacks:['future/alternate:free'],allow_fallbacks:false,data_collection:'deny',zdr:true,sort:'price',max_price:{prompt:'1.25',completion:'0'}});
    expect(before.profiles[0].profile.generation).toMatchObject({seed:0,max_output_tokens:128,frequency_penalty:'-1.5',reasoning:{effort:'low',exclude:true}});
    await app.close(); app=await launch(); page=await app.firstWindow();
    await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter'); region=page.getByRole('region',{name:'Provider settings',exact:true});
    await region.getByLabel('Provider profile',{exact:true}).selectOption({label:'Synthetic request preferences'});
    await region.getByText('Routing preferences',{exact:true}).click();
    await expect(region.getByLabel('Model fallbacks in order (comma-separated)',{exact:true})).toHaveValue('future/alternate:free');
    await expect(region.getByLabel('Zero data retention',{exact:true})).toHaveValue('true');
    const after=await page.evaluate(()=>window.poliscope.provider({action:'list'})); expect(after.profiles).toEqual(before.profiles);
    await expect(region.getByRole('button',{name:'Test saved key',exact:true})).toBeDisabled();
  } finally {await app.close();await rm(directory,{recursive:true,force:true});}
});
