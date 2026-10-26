import { test,expect,_electron as electron } from '@playwright/test';
import { mkdtemp,mkdir,rm,readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join,resolve } from 'node:path';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
const executablePath=resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform==='win32'?'.exe':''}`);
test('WP-048 packaged spending reconciliation, limit recovery, restart, cancellation and safe errors',async()=> {
 test.setTimeout(120000);
 const dir=await mkdtemp(join(tmpdir(),'poliscope-generation-ui-')), key='synthetic-WP045-never-in-replies';
 await mkdir(join(dir,'worlds'));
 let mode='complete',closed=false;
 const calls:{body:string;authorization?:string;cookie?:string}[]=[];
 const frame=(content:string,finish:string|null=null)=>'data: '+JSON.stringify({id:calls.length===1?'gen-first':'gen-'+calls.length,model:'synthetic/gpt',choices:[{index:0,delta:{content},finish_reason:finish}]})+'\n\n';
 const server=createServer((req,res)=> {
   if(req.url?.startsWith('/api/v1/generation?id=')){const id=new URL(req.url,'http://localhost').searchParams.get('id');res.setHeader('Content-Type','application/json');res.end(JSON.stringify({data:{id,model:'synthetic/gpt',total_cost:id==='gen-first'?'0.003':'0.002',tokens_prompt:4,tokens_completion:5}}));return;}
   if(req.url==='/api/v1/models'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({data:[{id:'synthetic/gpt',name:'Synthetic GPT byte fixture',architecture:{tokenizer:'GPT',input_modalities:['text'],output_modalities:['text']},context_length:65536,top_provider:{max_completion_tokens:1024},supported_parameters:['max_tokens'],pricing:{prompt:'0',completion:'0'}}]}));return;}
   let body='';req.on('data',data=>{body+=data;});req.on('end',()=> {
     calls.push({body,authorization:req.headers.authorization,cookie:req.headers.cookie});
     if(mode==='error'){res.writeHead(401,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{message:'Authorization: '+key}}));return;}
     if(mode==='json'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({id:calls.length===1?'gen-first':'gen-'+calls.length,model:'synthetic/gpt',choices:[{index:0,message:{content:'Whole JSON answer'},finish_reason:'stop'}],usage:{total_tokens:8}}));return;}
     res.writeHead(200,{'Content-Type':'text/event-stream','Set-Cookie':'must-not-return=1'});
     res.write(frame('Only the explicitly approved text was shared. 🌍'));
     if(mode==='slow'){res.on('close',()=>{closed=true;});return;}
     res.end(frame('','stop')+'data: '+JSON.stringify({choices:[{index:0,delta:{content:'',role:'assistant'},finish_reason:'stop'}],usage:{total_tokens:9}})+'\n\ndata: [DONE]\n\n');
   });
 });await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));const port=(server.address() as AddressInfo).port;
 const env:Record<string,string|undefined>={...process.env,POLISCOPE_USER_DATA:dir};delete env.ELECTRON_RUN_AS_NODE;
 let app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
 try {
   // Synthetic fixture rewrites only the test process's canonical OpenRouter
   // transport to loopback. Production profile, controller, Electron POST and
   // packaged Python reservation host remain in the executed path. No live API.
   await app.evaluate(({net,safeStorage},port)=> {
     safeStorage.isEncryptionAvailable=()=>false;
     const original=net.request.bind(net);
     net.request=((options:Electron.ClientRequestConstructorOptions|string)=> {
       const opts=typeof options==='string'?{url:options}:options;
       if(opts.url?.startsWith('https://openrouter.ai/api/v1/'))return original({...opts,url:opts.url.replace('https://openrouter.ai',`http://127.0.0.1:${port}`)});
       return original(options);
     }) as typeof net.request;
   },port);
   const page=await app.firstWindow();
   await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},join(dir,'worlds'));
   await page.evaluate(()=>window.poliscope.chooseWorkspace());
   const original=await page.evaluate(()=>window.poliscope.createWorld({name:'Original request context',setup:'blank',scope_name:'all',population:null,land_area:null}));
   await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');
   const region=page.getByRole('region',{name:'Provider settings',exact:true});
   await region.getByLabel('Profile name',{exact:true}).fill('Generation synthetic fixture');await region.getByLabel('Selected model ID',{exact:true}).fill('synthetic/gpt');
   await region.getByText('Generation preferences',{exact:true}).click();await region.getByLabel('Maximum output tokens',{exact:true}).fill('128');await region.getByRole('button',{name:'Save provider profile',exact:true}).press('Enter');
   await region.getByLabel('New provider key',{exact:true}).fill(key);await region.getByRole('button',{name:'Replace provider key',exact:true}).press('Enter');await expect(region.getByText('Key storage: session-only.',{exact:false})).toBeVisible();
   await region.getByRole('button',{name:'Refresh model catalog',exact:true}).press('Enter');await expect(region.getByText('Catalog: fresh;',{exact:false})).toBeVisible();
   const assistant=region.getByRole('region',{name:'Optional text assistance'});await assistant.getByLabel('Text to share',{exact:true}).fill('Explicitly approved synthetic text');await assistant.getByRole('button',{name:'Review request',exact:true}).press('Enter');
   await expect(assistant.getByRole('status')).toContainText('prepared');expect(calls).toHaveLength(0);await expect(assistant.locator('pre').first()).toContainText('https://openrouter.ai/api/v1');
   await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': complete.');await expect(assistant.getByLabel('Assistant response',{exact:true})).toHaveText('Only the explicitly approved text was shared. 🌍');expect(calls).toHaveLength(1);expect(calls[0].authorization).toBe('Bearer '+key);expect(calls[0].cookie).toBeUndefined();expect(JSON.parse(calls[0].body).messages).toEqual([{role:'user',content:'Explicitly approved synthetic text'}]);expect(await assistant.textContent()).not.toContain(key);
   const spending=assistant.getByRole('region',{name:'Spending controls'});
   await spending.getByRole('button',{name:'Refresh durable usage',exact:true}).press('Enter');
   await expect(spending).toContainText('Reported actual: unknown USD');await expect(spending).toContainText('profile: 0.01 USD');
   for(let i=0;i<2;i++) {await spending.getByRole('button',{name:'Retrieve generation usage',exact:true}).press('Enter');await expect(spending).toContainText('Reported actual: 0.003 USD');await expect(spending).toContainText('profile: 0.003 USD');}
   await assistant.getByLabel('Profile spending limit',{exact:true}).fill('0.001');await spending.getByRole('button',{name:'Update spending limits from inputs',exact:true}).press('Enter');await expect(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true})).toBeEnabled();
   await assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}).press('Enter');await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText('Spending reservation denied');expect(calls).toHaveLength(1);
   await assistant.getByLabel('Profile spending limit',{exact:true}).fill('1');await spending.getByRole('button',{name:'Update spending limits from inputs',exact:true}).press('Enter');await expect(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true})).toBeEnabled();
   mode='slow';await assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}).press('Enter');await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect.poll(()=>calls.length).toBe(2);
   const switched=await page.evaluate(()=>window.poliscope.createWorld({name:'Different context',setup:'blank',scope_name:'all',population:null,land_area:null}));
   expect(switched.context.civilization_id).not.toBe(original.context.civilization_id);
   await expect(assistant.locator('pre').first()).toContainText(original.context.civilization_id);
   await expect(assistant.locator('pre').first()).not.toContainText(switched.context.civilization_id);
   expect(calls[1].body).not.toContain(original.context.civilization_id);expect(calls[1].body).not.toContain(switched.context.civilization_id);
   await assistant.getByRole('button',{name:'Cancel request',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': cancelled.');await expect(assistant.getByRole('status')).toContainText('unresolved');await expect.poll(()=>closed).toBe(true);
   mode='error';await assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}).press('Enter');await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText('Authentication failed');expect(calls).toHaveLength(3);expect(await assistant.textContent()).not.toContain(key);
   mode='json';await assistant.getByLabel('Stream response',{exact:true}).uncheck();await assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}).press('Enter');await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': complete.');await expect(assistant.getByLabel('Assistant response',{exact:true})).toHaveText('Whole JSON answer');expect(calls).toHaveLength(4);
   mode='slow';closed=false;await assistant.getByLabel('Stream response',{exact:true}).check();await assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}).press('Enter');await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect.poll(()=>calls.length).toBe(5);
   await region.getByRole('button',{name:'Remove key and cancel requests',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': cancelled.');await expect.poll(()=>closed).toBe(true);expect(await region.textContent()).not.toContain(key);
   await app.close();app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
   await app.evaluate(({net,safeStorage},port)=> {
     safeStorage.isEncryptionAvailable=()=>false;const original=net.request.bind(net);
     net.request=((options:Electron.ClientRequestConstructorOptions|string)=> {const opts=typeof options==='string'?{url:options}:options;return opts.url?.startsWith('https://openrouter.ai/api/v1/')?original({...opts,url:opts.url.replace('https://openrouter.ai',`http://127.0.0.1:${port}`)}):original(options);}) as typeof net.request;
   },port);
   const reopened=await app.firstWindow();await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},join(dir,'worlds'));
   await reopened.evaluate(()=>window.poliscope.chooseWorkspace());await reopened.evaluate(()=>window.poliscope.createWorld({name:'Usage recovery context',setup:'blank',scope_name:'all',population:null,land_area:null}));
   await reopened.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');const restored=reopened.getByRole('region',{name:'Provider settings',exact:true});
   await restored.getByLabel('Provider profile',{exact:true}).selectOption({label:'Generation synthetic fixture'});await restored.getByLabel('New provider key',{exact:true}).fill(key);await restored.getByRole('button',{name:'Replace provider key',exact:true}).press('Enter');await expect(restored.getByText('Key storage: session-only.',{exact:false})).toBeVisible();
   await restored.getByRole('button',{name:'Refresh model catalog',exact:true}).press('Enter');await expect(restored.getByText('Catalog: fresh;',{exact:false})).toBeVisible();
   const recovered=restored.getByRole('region',{name:'Optional text assistance'});await recovered.getByLabel('Text to share',{exact:true}).fill('Select profile for usage recovery; do not send');await recovered.getByRole('button',{name:'Review request',exact:true}).press('Enter');await expect(recovered.getByRole('status')).toContainText('prepared');
   const durable=recovered.getByRole('region',{name:'Durable profile usage'});await durable.getByRole('button',{name:'Load durable profile usage',exact:true}).press('Enter');await expect(durable.getByRole('button',{name:/Retrieve stored generation/})).toHaveCount(4);
   await durable.getByRole('button',{name:/Retrieve stored generation/}).first().press('Enter');await expect(durable).toContainText('actual 0.002 USD');expect(calls).toHaveLength(5);await expect(recovered.getByRole('status')).toContainText('prepared');
   const ledger=await readFile(join(dir,'assistant-private/spending.sqlite3'));expect(ledger.includes(Buffer.from(key))).toBe(false);expect(ledger.includes(Buffer.from('Explicitly approved synthetic text'))).toBe(false);
 }finally{await app.close();server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));await rm(dir,{recursive:true,force:true});}
});
