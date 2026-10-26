import { test,expect,_electron as electron } from '@playwright/test';
import { mkdtemp,mkdir,rm,readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join,resolve } from 'node:path';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
const executablePath=resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform==='win32'?'.exe':''}`);
test('WP-045 packaged explicit review, actual Electron POST, production spending, partial cancel and safe errors',async()=> {
 test.setTimeout(120000);
 const dir=await mkdtemp(join(tmpdir(),'poliscope-generation-ui-')), key='synthetic-WP045-never-in-replies';
 await mkdir(join(dir,'worlds'));
 let mode='complete',closed=false;
 const calls:{body:string;authorization?:string;cookie?:string}[]=[];
 const frame=(content:string,finish:string|null=null)=>'data: '+JSON.stringify({model:'synthetic/gpt',choices:[{index:0,delta:{content},finish_reason:finish}]})+'\n\n';
 const server=createServer((req,res)=> {
   if(req.url==='/api/v1/models'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({data:[{id:'synthetic/gpt',name:'Synthetic GPT byte fixture',architecture:{tokenizer:'GPT',input_modalities:['text'],output_modalities:['text']},context_length:65536,top_provider:{max_completion_tokens:1024},supported_parameters:['max_tokens'],pricing:{prompt:'0',completion:'0'}}]}));return;}
   let body='';req.on('data',data=>{body+=data;});req.on('end',()=> {
     calls.push({body,authorization:req.headers.authorization,cookie:req.headers.cookie});
     if(mode==='error'){res.writeHead(401,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{message:'Authorization: '+key}}));return;}
     if(mode==='json'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({model:'synthetic/gpt',choices:[{index:0,message:{content:'Whole JSON answer'},finish_reason:'stop'}],usage:{total_tokens:8}}));return;}
     res.writeHead(200,{'Content-Type':'text/event-stream','Set-Cookie':'must-not-return=1'});
     res.write(frame('Only the explicitly approved text was shared. 🌍'));
     if(mode==='slow'){res.on('close',()=>{closed=true;});return;}
     res.end(frame('','stop')+'data: '+JSON.stringify({choices:[{index:0,delta:{content:'',role:'assistant'},finish_reason:'stop'}],usage:{total_tokens:9}})+'\n\ndata: [DONE]\n\n');
   });
 });await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));const port=(server.address() as AddressInfo).port;
 const env:Record<string,string|undefined>={...process.env,POLISCOPE_USER_DATA:dir};delete env.ELECTRON_RUN_AS_NODE;
 const app=await electron.launch({executablePath,args:['--no-sandbox'],env:env as Record<string,string>});
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
   const ledger=await readFile(join(dir,'assistant-private/spending.sqlite3'));expect(ledger.includes(Buffer.from(key))).toBe(false);expect(ledger.includes(Buffer.from('Explicitly approved synthetic text'))).toBe(false);
 }finally{await app.close();server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));await rm(dir,{recursive:true,force:true});}
});
