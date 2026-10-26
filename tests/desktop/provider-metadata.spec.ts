import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
const executablePath=resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform==='win32'?'.exe':''}`);
test('WP-043 packaged catalog refresh, open variants, keyboard search, removed models and cold offline cache',async()=>{
  test.setTimeout(120000);
  const dir=await mkdtemp(join(tmpdir(),'poliscope-catalog-ui-'));const key='synthetic-WP043-key-not-in-replies';
  let mode='current';const requests:{path:string;auth?:string}[]=[];
  const server=createServer((req,res)=>{
    requests.push({path:req.url!,auth:req.headers.authorization});res.setHeader('Content-Type','application/json');
    if(mode==='error'){res.writeHead(401);res.end(JSON.stringify({error:'Authorization: '+key}));return;}
    res.end(JSON.stringify({data:mode==='removed'?[]:[{id:'future/vendor:preview',name:'Synthetic preview',owned_by:'synthetic',future_metadata:{preserve:'unknown-value'}}]}));
  });await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));const port=(server.address() as AddressInfo).port;
  const env:Record<string,string|undefined>={...process.env,POLISCOPE_USER_DATA:join(dir,'app')};delete env.ELECTRON_RUN_AS_NODE;
  let app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
  try {
    await app.evaluate(({safeStorage})=>{safeStorage.isEncryptionAvailable=()=>false;});
    let page=await app.firstWindow();await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');let region=page.getByRole('region',{name:'Provider settings',exact:true});
    await region.getByLabel('Profile name',{exact:true}).fill('Metadata fixture');await region.getByLabel('Provider type',{exact:true}).selectOption('openai-compatible');
    await region.getByLabel('API base endpoint',{exact:true}).fill(`http://127.0.0.1:${port}/v1`);await region.getByRole('button',{name:'Save provider profile',exact:true}).press('Enter');
    await expect(region.getByText('Key storage: missing.',{exact:false})).toBeVisible();await region.getByLabel('New provider key',{exact:true}).fill(key);await region.getByRole('button',{name:'Replace provider key',exact:true}).press('Enter');
    await expect(region.getByText('Key storage: session-only.',{exact:false})).toBeVisible();await region.getByRole('button',{name:'Refresh model catalog',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toContainText('Metadata loaded');await expect(region.getByText('Catalog: fresh;', {exact:false})).toBeVisible();
    expect(requests).toEqual([{path:'/v1/models',auth:'Bearer '+key}]);
    await expect(region.getByRole('button',{name:'Inspect key limits',exact:true})).toBeDisabled();await expect(region.getByRole('button',{name:'Refresh selected model providers',exact:true})).toBeDisabled();
    await region.getByRole('button',{name:'Choose future/vendor:preview',exact:true}).press('Enter');await expect(region.getByLabel('Selected model ID',{exact:true})).toHaveValue('future/vendor:preview');
    await expect(region.getByRole('button',{name:'Refresh model catalog',exact:true})).toBeDisabled();await region.getByRole('button',{name:'Save provider profile',exact:true}).press('Enter');await expect(region.getByRole('status')).toContainText('Saved provider');
    await region.getByLabel('Search models and variants',{exact:true}).fill(':preview');await region.getByRole('button',{name:'Search cached models',exact:true}).press('Enter');await expect(region.getByText('Catalog: cached;', {exact:false})).toBeVisible();
    const article=region.locator('article').first();await expect(article.getByText('Context: unknown',{exact:false})).toBeVisible();await expect(article.locator('dd')).toHaveText(Array(7).fill('unknown'));
    await article.getByText('Prices and complete provider metadata',{exact:true}).click();await expect(article.locator('pre')).toContainText('unknown-value');
    mode='error';await region.getByRole('button',{name:'Refresh model catalog',exact:true}).press('Enter');await expect(region.getByRole('status')).toContainText('rejected authentication');expect(await region.textContent()).not.toContain(key);
    mode='removed';await region.getByRole('button',{name:'Refresh model catalog',exact:true}).press('Enter');await expect(region.getByText('removed from latest catalog',{exact:false})).toBeVisible();await expect(region.getByRole('button',{name:'Choose future/vendor:preview',exact:true})).toBeDisabled();
    const cached=await readFile(join(dir,'app/providers/catalog-'+(await page.evaluate(()=>window.poliscope.provider({action:'list'}))).profiles[0].profile.id+'.json'),'utf8');expect(cached).not.toContain(key);expect(cached).toContain('unknown-value');
    await app.close();await new Promise<void>(r=>{server.closeAllConnections();server.close(()=>r());});
    app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});page=await app.firstWindow();await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');region=page.getByRole('region',{name:'Provider settings',exact:true});await region.getByLabel('Provider profile',{exact:true}).selectOption({label:'Metadata fixture'});
    await region.getByRole('button',{name:'Search cached models',exact:true}).press('Enter');await expect(region.getByText('Catalog: cached;', {exact:false})).toBeVisible();await expect(region.getByText('removed from latest catalog',{exact:false})).toBeVisible();await expect(region.getByLabel('Selected model ID',{exact:true})).toHaveValue('future/vendor:preview');
    await expect(region.getByText('Key storage: missing.',{exact:false})).toBeVisible();expect(requests).toHaveLength(3);
  } finally {await app.close();server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));await rm(dir,{recursive:true,force:true});}
});
