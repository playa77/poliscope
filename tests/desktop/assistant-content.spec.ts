import { test,expect,_electron as electron } from '@playwright/test';
import { mkdtemp,mkdir,rm,readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join,resolve } from 'node:path';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
const executablePath=resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform==='win32'?'.exe':''}`);
test('WP-047 packaged attachment inclusion, safe artifacts, deletion and no passive resource loads',async()=>{
 test.setTimeout(120000);
 const dir=await mkdtemp(join(tmpdir(),'poliscope-media-ui-'));await mkdir(join(dir,'worlds'));
 const audio=Buffer.alloc(48);audio.write('RIFF');audio.writeUInt32LE(40,4);audio.write('WAVEfmt ',8);audio.writeUInt32LE(16,16);audio.writeUInt16LE(1,20);audio.writeUInt16LE(1,22);audio.writeUInt32LE(16000,24);audio.writeUInt32LE(32000,28);audio.writeUInt16LE(2,32);audio.writeUInt16LE(16,34);audio.write('data',36);audio.writeUInt32LE(4,40);
 const calls:string[]=[],unexpected:string[]=[],key='synthetic-media-key-canary',privateText='PRIVATE-ATTACHMENT-CANARY';
 const server=createServer((req,res)=>{
  res.setHeader('Content-Type','application/json');
  if(req.url==='/api/v1/models'){res.end(JSON.stringify({data:[{id:'openai/gpt-audio',architecture:{tokenizer:'GPT',input_modalities:['text','audio'],output_modalities:['text','audio']},context_length:131072,top_provider:{max_completion_tokens:1024},supported_parameters:['max_tokens','modalities','audio']}]}));return;}
  if(req.url!=='/api/v1/chat/completions'){unexpected.push(req.url??'');res.end('{}');return;}
  let body='';req.on('data',data=>{body+=data;});req.on('end',()=>{
   calls.push(body);
   res.setHeader('Content-Type','text/event-stream');
   const delta={content:`Untrusted response <svg><image href="http://127.0.0.1:${(server.address() as AddressInfo).port}/track"/></svg><style>@import url(https://sink.invalid/track)</style>`,...(calls.length===1?{reasoning_details:[{type:'reasoning.encrypted',data:'OPAQUE-PRIVATE-CANARY'}],audio:{data:audio.toString('base64')}}:{})};
   res.end('data: '+JSON.stringify({model:'openai/gpt-audio',choices:[{index:0,delta,finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n');
  });
 });await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));const port=(server.address() as AddressInfo).port;
 const env:Record<string,string>={...process.env as Record<string,string>,POLISCOPE_USER_DATA:dir};delete env.ELECTRON_RUN_AS_NODE;
 const app=await electron.launch({executablePath,args:['--no-sandbox'],env});
 try{
  await app.evaluate(({net,safeStorage},port)=>{safeStorage.isEncryptionAvailable=()=>false;const original=net.request.bind(net);net.request=((options:Electron.ClientRequestConstructorOptions|string)=>{const opts=typeof options==='string'?{url:options}:options;return opts.url?.startsWith('https://openrouter.ai/api/v1/')?original({...opts,url:opts.url.replace('https://openrouter.ai',`http://127.0.0.1:${port}`)}):original(options);}) as typeof net.request;},port);
  const page=await app.firstWindow();await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},join(dir,'worlds'));
  await page.evaluate(()=>window.poliscope.chooseWorkspace());await page.evaluate(()=>window.poliscope.createWorld({name:'Media civilization',setup:'blank',scope_name:'Home',population:'12',land_area:'3'}));
  await page.getByRole('button',{name:'Open provider settings',exact:true}).press('Enter');const region=page.getByRole('region',{name:'Provider settings',exact:true});
  await region.getByLabel('Profile name',{exact:true}).fill('Media fixture');await region.getByLabel('Selected model ID',{exact:true}).fill('openai/gpt-audio');await region.getByText('Generation preferences',{exact:true}).click();await region.getByLabel('Maximum output tokens',{exact:true}).fill('128');await region.getByRole('button',{name:'Save provider profile',exact:true}).press('Enter');await region.getByLabel('New provider key',{exact:true}).fill(key);await region.getByRole('button',{name:'Replace provider key',exact:true}).press('Enter');await expect(region.getByText('Key storage: session-only.',{exact:false})).toBeVisible();await region.getByRole('button',{name:'Refresh model catalog',exact:true}).press('Enter');await expect(region.getByText('Catalog: fresh;',{exact:false})).toBeVisible();
  const assistant=region.getByRole('region',{name:'Optional text assistance'});
  await assistant.getByLabel('Choose attachments',{exact:true}).setInputFiles([{name:'private.txt',mimeType:'text/plain',buffer:Buffer.from(privateText)}]);
  await assistant.getByLabel('Text to share',{exact:true}).fill('Explain selected attachments.');await expect(assistant.getByRole('button',{name:'Review request',exact:true})).toBeDisabled();
  await assistant.getByLabel('Include these attachments and their excerpts in this turn and its reviewed continuations',{exact:true}).check();await assistant.getByLabel('Requested output',{exact:true}).selectOption('audio');
  await assistant.getByRole('button',{name:'Review request',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': prepared.');expect(calls).toHaveLength(0);expect(await assistant.textContent()).toContain(privateText);
  const status=(await assistant.getByRole('status').textContent())!;const id=status.split('Request ')[1].split(': ')[0];
  await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': complete.');expect(calls).toHaveLength(1);expect(calls[0]).toContain(privateText);expect(JSON.parse(calls[0]).messages[0].content[1].type).toBe('text');
  await expect(assistant.getByRole('region',{name:'Untrusted provider artifacts'})).toContainText('audio/wav');expect(await assistant.textContent()).not.toContain('OPAQUE-PRIVATE-CANARY');expect(await assistant.locator('img,svg,video,audio,iframe,style').count()).toBe(0);
  const exported=join(dir,'explicit-user-copy.wav');await app.evaluate(({dialog},filePath)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath});},exported);
  await assistant.getByRole('button',{name:'Save artifact 1 to a new file',exact:true}).press('Enter');await expect(async()=>expect(await readFile(exported)).toEqual(audio)).toPass();
  await expect(assistant.getByRole('button',{name:'Delete this turn, attachments and all active derivatives',exact:true})).toBeEnabled();
  await assistant.getByRole('button',{name:'Delete this turn, attachments and all active derivatives',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toHaveCount(0);expect(await assistant.textContent()).not.toContain(privateText);
  expect(await page.evaluate(async id=>{try{await window.poliscope.assistant({action:'status',request_id:id});return false;}catch{return true;}},id)).toBe(true);
  await assistant.getByLabel('Requested output',{exact:true}).selectOption('text');await assistant.getByLabel('Text to share',{exact:true}).fill('New thread without old attachments.');await assistant.getByRole('button',{name:'Review request',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': prepared.');await assistant.getByRole('button',{name:'Approve sharing and send once',exact:true}).press('Enter');await expect(assistant.getByRole('status')).toContainText(': complete.');expect(calls).toHaveLength(2);expect(calls[1]).not.toContain(privateText);expect(calls[1]).not.toContain('OPAQUE-PRIVATE-CANARY');
  expect(unexpected).toEqual([]);expect(await readFile(exported)).toEqual(audio);
 }finally{await app.close();server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));await rm(dir,{recursive:true,force:true});}
});
