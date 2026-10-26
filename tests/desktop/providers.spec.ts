import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createServer, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
const executablePath = resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform === 'win32' ? '.exe' : ''}`);
const listen = (server: Server) => new Promise<number>(r => server.listen(0,'127.0.0.1',()=>r((server.address() as AddressInfo).port)));
const close = (server: Server) => new Promise<void>(r => { server.closeAllConnections(); server.close(()=>r()); });
const canary = 'synthetic-WP042-KEY-never-persist-or-return';

test('WP-042 packaged temporary entry, native networking, redirect refusal, revocation and cold session-only restart', async () => {
  test.setTimeout(120000);
  const directory=await mkdtemp(join(tmpdir(),'poliscope-provider-ui-'));
  let mode: 'ok'|'redirect'|'slow'|'error'='ok', sinkHits=0, closedSlow=false;
  const requests: {path: string; auth?: string; cookie?: string}[]=[];
  const sink=createServer((_req,res)=>{sinkHits++;res.end('unexpected');}); const sinkPort=await listen(sink);
  const server=createServer((req,res)=>{
    requests.push({path:req.url!,auth:req.headers.authorization,cookie:req.headers.cookie});
    if(mode==='redirect'){res.writeHead(302,{Location:`http://127.0.0.1:${sinkPort}/stolen`});res.end();}
    else if(mode==='slow'){res.on('close',()=>{closedSlow=true;});res.writeHead(200);res.write('partial');}
    else if(mode==='error'){res.writeHead(401);res.end('Authorization: Bearer '+canary);}
    else {res.setHeader('Set-Cookie','provider-secret=must-not-return');res.end('{"untrusted":"provider text '+canary+'"}');}
  }); const port=await listen(server);
  const env: Record<string,string|undefined>={...process.env,POLISCOPE_USER_DATA:join(directory,'app')};delete env.ELECTRON_RUN_AS_NODE;
  let app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
  let diagnostics='';app.process().stderr?.on('data',data=>{diagnostics+=String(data);});
  try {
    let page=await app.firstWindow();
    // Exercise unavailable-backend production behavior explicitly, without writing
    // plaintext or supplying a fixture key to Python/environment variables.
    await app.evaluate(({safeStorage})=>{safeStorage.isEncryptionAvailable=()=>false;});
    await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');
    let region=page.getByRole('region',{name:'Provider settings',exact:true});
    await region.getByLabel('Profile name',{exact:true}).fill('Local synthetic provider');
    await region.getByLabel('Provider type',{exact:true}).selectOption('openai-compatible');
    await region.getByLabel('API base endpoint',{exact:true}).fill(`http://127.0.0.1:${port}/v1`);
    await region.getByLabel('Selected model ID',{exact:true}).fill('unlisted/future:model');
    await region.getByRole('button',{name:'Save provider profile',exact:true}).press('Enter');
    await expect(region.getByText('Key storage: missing.',{exact:false})).toBeVisible();
    await region.getByLabel('New provider key',{exact:true}).fill(canary);
    await region.getByRole('button',{name:'Replace provider key',exact:true}).press('Enter');
    await expect(region.getByLabel('New provider key',{exact:true})).toHaveValue('');
    await expect(region.getByText('Key storage: session-only.',{exact:false})).toBeVisible();
    await region.getByLabel('API base endpoint',{exact:true}).fill('https://another.example/v1');
    await expect(region.getByRole('button',{name:'Test saved key',exact:true})).toBeDisabled();
    await expect(region.getByLabel('New provider key',{exact:true})).toBeDisabled();
    await region.getByLabel('API base endpoint',{exact:true}).fill(`http://127.0.0.1:${port}/v1`);
    await region.getByRole('button',{name:'Test saved key',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toContainText('Metadata endpoint accepted');
    expect(requests).toEqual([{path:'/v1/models',auth:'Bearer '+canary,cookie:undefined}]);
    expect(await region.textContent()).not.toContain(canary);
    mode='error';await region.getByRole('button',{name:'Test saved key',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toContainText('rejected authentication');
    mode='redirect';await region.getByRole('button',{name:'Test saved key',exact:true}).press('Enter');
    await expect(region.getByRole('status')).toContainText('redirect blocked');expect(sinkHits).toBe(0);
    expect(requests.every(r=>r.cookie===undefined)).toBe(true);
    mode='slow';await region.getByRole('button',{name:'Test saved key',exact:true}).press('Enter');
    await expect.poll(()=>requests.length).toBe(4);
    await region.getByRole('button',{name:'Remove key and cancel requests',exact:true}).press('Enter');
    await expect(region.getByText('Key storage: missing.',{exact:false})).toBeVisible();
    await expect.poll(()=>closedSlow).toBe(true);
    await region.getByLabel('New provider key',{exact:true}).fill(canary);
    await region.getByRole('button',{name:'Replace provider key',exact:true}).press('Enter');
    await expect(region.getByText('Key storage: session-only.',{exact:false})).toBeVisible();
    const reply=await page.evaluate(()=>window.poliscope.provider({action:'list'}));
    expect(JSON.stringify(reply)).not.toMatch(/never-persist|credential-|\.bin|binding/);
    const files=await readdir(join(directory,'app/providers'));expect(files).toEqual(['profiles.json']);
    expect(await readFile(join(directory,'app/providers/profiles.json'),'utf8')).not.toContain(canary);
    expect(diagnostics).not.toContain(canary);
    await app.close();
    app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});page=await app.firstWindow();
    await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');region=page.getByRole('region',{name:'Provider settings',exact:true});
    await region.getByLabel('Provider profile',{exact:true}).selectOption({label:'Local synthetic provider'});
    await expect(region.getByText('Key storage: missing.',{exact:false})).toBeVisible();
    await expect(region.getByLabel('Selected model ID',{exact:true})).toHaveValue('unlisted/future:model');
    await expect(region.getByRole('button',{name:'Test saved key',exact:true})).toBeDisabled();
  } finally {await app.close();await close(server);await close(sink);await rm(directory,{recursive:true,force:true});}
});
