import type { Locator } from '@playwright/test';
import { test,expect,_electron as electron } from '@playwright/test';
import { mkdtemp,mkdir,rm,readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join,resolve } from 'node:path';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
async function enter(button:Locator) {await expect(button).toBeEnabled();await button.press('Enter');}
const executablePath=resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform==='win32'?'.exe':''}`);
test('WP-049 packaged workspace snapshots, spending, restart, cancellation and safe errors',async()=> {
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
   await enter(page.getByRole('button',{name:'Open provider settings',exact:true}));
   const region=page.getByRole('region',{name:'Provider settings',exact:true});
   await region.getByLabel('Profile name',{exact:true}).fill('Generation synthetic fixture');await region.getByLabel('Selected model ID',{exact:true}).fill('synthetic/gpt');
   await region.getByText('Generation preferences',{exact:true}).click();await region.getByLabel('Maximum output tokens',{exact:true}).fill('128');await enter(region.getByRole('button',{name:'Save provider profile',exact:true}));
   await region.getByLabel('New provider key',{exact:true}).fill(key);await enter(region.getByRole('button',{name:'Replace provider key',exact:true}));await expect(region.getByText('Key storage: session-only.',{exact:false})).toBeVisible();
   await enter(region.getByRole('button',{name:'Refresh model catalog',exact:true}));await expect(region.getByText('Catalog: fresh;',{exact:false})).toBeVisible();
   const assistant=region.getByRole('region',{name:'Optional text assistance'});await assistant.getByLabel('Text to share',{exact:true}).fill('Explicitly approved synthetic text');await enter(assistant.getByRole('button',{name:'Review request',exact:true}));
   await expect(assistant.getByRole('status')).toContainText('prepared');expect(calls).toHaveLength(0);await expect(assistant.locator('pre').first()).toContainText('https://openrouter.ai/api/v1');
   await enter(assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}));await expect(assistant.getByRole('status')).toContainText(': complete.');await expect(assistant.getByLabel('Assistant response',{exact:true})).toHaveText('Only the explicitly approved text was shared. 🌍');expect(calls).toHaveLength(1);expect(calls[0].authorization).toBe('Bearer '+key);expect(calls[0].cookie).toBeUndefined();expect(JSON.parse(calls[0].body).messages).toEqual([{role:'user',content:'Explicitly approved synthetic text'}]);expect(await assistant.textContent()).not.toContain(key);
   await enter(assistant.getByRole('button',{name:'Save this text transcript locally',exact:true}));
   const local=assistant.getByRole('region',{name:'Local assistant workspace'});
   await expect(local.getByRole('button',{name:/Read saved text/})).toHaveCount(1);
   await enter(local.getByRole('button',{name:/Read saved text/}));
   await expect(local.getByRole('article',{name:'Saved private text transcript'})).toContainText('Explicitly approved synthetic text');
   const textFile=await readFile(join(dir,'assistant-private/transcripts.json'),'utf8');expect(textFile).not.toContain(key);expect(textFile).not.toContain('payload_json');expect(textFile).not.toContain('reasoning');
   const exported=join(dir,'without-transcripts.md');
   await app.evaluate(({dialog},filePath)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath});},exported);
   expect((await page.evaluate(()=>window.poliscope.report({format:'markdown',options:{}}))).status).toBe('complete');
   const exportedText=await readFile(exported,'utf8');expect(exportedText).not.toContain('Explicitly approved synthetic text');expect(exportedText).not.toContain('Only the explicitly approved text was shared.');expect(exportedText).not.toContain(key);
   const spending=assistant.getByRole('region',{name:'Spending controls'});
   await enter(spending.getByRole('button',{name:'Refresh durable usage',exact:true}));
   await expect(spending).toContainText('Reported actual: unknown USD');await expect(spending).toContainText('profile: 0.01 USD');
   for(let i=0;i<2;i++) {const retrieve=spending.getByRole('button',{name:'Retrieve generation usage',exact:true});await expect(retrieve).toBeEnabled();await retrieve.press('Enter');await expect(spending).toContainText('Reported actual: 0.003 USD');await expect(spending).toContainText('profile: 0.003 USD');}
   await assistant.getByLabel('Profile spending limit',{exact:true}).fill('0.001');await enter(spending.getByRole('button',{name:'Update spending limits from inputs',exact:true}));await expect(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true})).toBeEnabled();
   await enter(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}));await enter(assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}));await expect(assistant.getByRole('status')).toContainText('Spending reservation denied');expect(calls).toHaveLength(1);
   await assistant.getByLabel('Profile spending limit',{exact:true}).fill('1');await enter(spending.getByRole('button',{name:'Update spending limits from inputs',exact:true}));await expect(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true})).toBeEnabled();
   mode='slow';await enter(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}));await enter(assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}));await expect.poll(()=>calls.length).toBe(2);
   const switched=await page.evaluate(()=>window.poliscope.createWorld({name:'Different context',setup:'blank',scope_name:'all',population:null,land_area:null}));
   expect(switched.context.civilization_id).not.toBe(original.context.civilization_id);
   await expect(assistant.locator('pre').first()).toContainText(original.context.civilization_id);
   await expect(assistant.locator('pre').first()).not.toContainText(switched.context.civilization_id);
   expect(calls[1].body).not.toContain(original.context.civilization_id);expect(calls[1].body).not.toContain(switched.context.civilization_id);
   await enter(assistant.getByRole('button',{name:'Cancel request',exact:true}));await expect(assistant.getByRole('status')).toContainText(': cancelled.');await expect(assistant.getByRole('status')).toContainText('unresolved');await expect.poll(()=>closed).toBe(true);
   mode='error';await enter(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}));await enter(assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}));await expect(assistant.getByRole('status')).toContainText('Authentication failed');expect(calls).toHaveLength(3);expect(await assistant.textContent()).not.toContain(key);
   mode='json';await assistant.getByLabel('Stream response',{exact:true}).uncheck();await enter(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}));await enter(assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}));await expect(assistant.getByRole('status')).toContainText(': complete.');await expect(assistant.getByLabel('Assistant response',{exact:true})).toHaveText('Whole JSON answer');expect(calls).toHaveLength(4);
   mode='slow';closed=false;await assistant.getByLabel('Stream response',{exact:true}).check();await enter(assistant.getByRole('button',{name:'Review a deliberate new request',exact:true}));await enter(assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}));await expect.poll(()=>calls.length).toBe(5);
   await enter(region.getByRole('button',{name:'Remove key and cancel requests',exact:true}));await expect(assistant.getByRole('status')).toContainText(': cancelled.');await expect.poll(()=>closed).toBe(true);expect(await region.textContent()).not.toContain(key);
   await app.close();app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
   await app.evaluate(({net,safeStorage},port)=> {
     safeStorage.isEncryptionAvailable=()=>false;const original=net.request.bind(net);
     net.request=((options:Electron.ClientRequestConstructorOptions|string)=> {const opts=typeof options==='string'?{url:options}:options;return opts.url?.startsWith('https://openrouter.ai/api/v1/')?original({...opts,url:opts.url.replace('https://openrouter.ai',`http://127.0.0.1:${port}`)}):original(options);}) as typeof net.request;
   },port);
   const reopened=await app.firstWindow();await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},join(dir,'worlds'));
   await reopened.evaluate(()=>window.poliscope.chooseWorkspace());await reopened.evaluate(()=>window.poliscope.createWorld({name:'Usage recovery context',setup:'blank',scope_name:'all',population:null,land_area:null}));
   await enter(reopened.getByRole('button',{name:'Open provider settings',exact:true}));const restored=reopened.getByRole('region',{name:'Provider settings',exact:true});
   await expect(restored.getByRole('button',{name:/Read saved text/})).toHaveCount(1);
   await enter(restored.getByRole('button',{name:/Read saved text/}));
   await expect(restored.getByRole('article',{name:'Saved private text transcript'})).toContainText(original.context.civilization_id);
   await restored.getByLabel('Provider profile',{exact:true}).selectOption({label:'Generation synthetic fixture'});await restored.getByLabel('New provider key',{exact:true}).fill(key);await enter(restored.getByRole('button',{name:'Replace provider key',exact:true}));await expect(restored.getByText('Key storage: session-only.',{exact:false})).toBeVisible();
   await enter(restored.getByRole('button',{name:'Refresh model catalog',exact:true}));await expect(restored.getByText('Catalog: fresh;',{exact:false})).toBeVisible();
   const recovered=restored.getByRole('region',{name:'Optional text assistance'});
   const snapshots=recovered.getByRole('region',{name:'Local assistant workspace'});
   await expect(snapshots.getByRole('button',{name:/Read saved text/})).toHaveCount(1);
   await enter(snapshots.getByRole('button',{name:/Read saved text/}));
   await expect(snapshots.getByRole('article',{name:'Saved private text transcript'})).toContainText(original.context.civilization_id);
   const beforeDelete=await reopened.evaluate(()=>window.poliscope.workspaceCatalogue());
   await enter(snapshots.getByRole('button',{name:/Delete saved text/}));
   await expect(snapshots.getByRole('button',{name:/Read saved text/})).toHaveCount(0);
   expect(JSON.parse(await readFile(join(dir,'assistant-private/transcripts.json'),'utf8'))).toEqual([]);
   expect(await reopened.evaluate(()=>window.poliscope.workspaceCatalogue())).toEqual(beforeDelete);
   expect(calls).toHaveLength(5);
   await recovered.getByLabel('Text to share',{exact:true}).fill('Select profile for usage recovery; do not send');await enter(recovered.getByRole('button',{name:'Review request',exact:true}));await expect(recovered.getByRole('status')).toContainText('prepared');
   const durable=recovered.getByRole('region',{name:'Durable profile usage'});await enter(durable.getByRole('button',{name:'Load durable profile usage',exact:true}));await expect(durable.getByRole('button',{name:/Retrieve stored generation/})).toHaveCount(4);
   await durable.getByRole('button',{name:/Retrieve stored generation/}).first().press('Enter');await expect(durable).toContainText('actual 0.002 USD');expect(calls).toHaveLength(5);await expect(recovered.getByRole('status')).toContainText('prepared');
   const ledger=await readFile(join(dir,'assistant-private/spending.sqlite3'));expect(ledger.includes(Buffer.from(key))).toBe(false);expect(ledger.includes(Buffer.from('Explicitly approved synthetic text'))).toBe(false);
   mode='json';
   await recovered.getByLabel('Stream response',{exact:true}).uncheck();
   await recovered.getByLabel('Include grounded context from the selected revision',{exact:true}).check();
   await recovered.getByLabel('Text to share',{exact:true}).fill('PROMOTION-PROMPT-CANARY: suggest an alternative');
   await enter(recovered.getByRole('button',{name:'Review a deliberate new request',exact:true}));
   await enter(recovered.getByRole('button',{name:'Approve sharing and send once',exact:true}));
   await expect(recovered.getByRole('status')).toContainText(': complete.');
   await enter(recovered.getByRole('button',{name:'Save this text transcript locally',exact:true}));
   await recovered.getByLabel('Public qualitative excerpt',{exact:true}).fill('Whole JSON answer');
   await enter(recovered.getByRole('button',{name:'Preview this excerpt as a qualitative alternative',exact:true}));
   const proposal=recovered.getByRole('region',{name:'Qualitative alternative preview'});
   await expect(proposal).toContainText('This preview commits nothing');
   const beforePromotion=await reopened.evaluate(()=>window.poliscope.workspaceCatalogue());
   await enter(proposal.getByRole('button',{name:'Apply qualitative alternative',exact:true}));
   await expect(proposal).toContainText('Applied through ordinary player approval');
   const afterPromotion=await reopened.evaluate(()=>window.poliscope.workspaceCatalogue());
   const promoted=afterPromotion.branches.find(row=>beforePromotion.branches.some(old=>old.context.civilization_id===row.context.civilization_id&&old.context.revision_id!==row.context.revision_id))!;expect(promoted).toBeTruthy();
   await enter(recovered.getByRole('button',{name:'Delete this turn, attachments and all active derivatives',exact:true}));
   await expect(recovered.getByRole('button',{name:'Apply qualitative alternative',exact:true})).toHaveCount(0);
   expect(await reopened.evaluate(()=>window.poliscope.workspaceCatalogue())).toEqual(afterPromotion);
   const accepted=await reopened.evaluate(context=>window.poliscope.interview({context,scope_id:'home',domain_id:'domain:3'}),promoted.context);
   expect(accepted.current_commitment).toContain('Whole JSON answer');expect(accepted.current_commitment).toContain('ai_proposed');expect(accepted.current_commitment).not.toContain('PROMOTION-PROMPT-CANARY');
   expect(JSON.parse(await readFile(join(dir,'assistant-private/transcripts.json'),'utf8'))).toEqual([]);expect(calls).toHaveLength(6);

 }finally{await app.close();server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));await rm(dir,{recursive:true,force:true});}
});
