import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, mkdir, readFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const executablePath=resolve(`out/Poliscope-${process.platform}-${process.arch}/poliscope${process.platform==='win32'?'.exe':''}`);

test('E2E-006.c forced application exit after rejected import and failed export preserves confirmed history',async()=>{
 test.setTimeout(120000);
 const dir=await mkdtemp(join(tmpdir(),'poliscope-fault-audit-'));
 const worlds=join(dir,'worlds');await mkdir(worlds);
 const env:Record<string,string>={...process.env as Record<string,string>,POLISCOPE_USER_DATA:join(dir,'app'),OPENAI_API_KEY:'SYNTHETIC_ENGINE_ENV_CANARY',POLISCOPE_DIAGNOSTIC_CANARY:'PRIVATE_DIAGNOSTIC_CANARY'};delete env.ELECTRON_RUN_AS_NODE;
 let app=await electron.launch({executablePath,args:['--no-sandbox'],env});
 try {
  let page=await app.firstWindow();
  await expect(page.getByRole('status')).toHaveText('Local engine ready');
  await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},worlds);
  await page.evaluate(()=>window.poliscope.chooseWorkspace());
  const saved=await page.evaluate(()=>window.poliscope.createWorld({name:'Fault audit society',setup:'blank',scope_name:'Home',population:'17',land_area:null}));
  const before=await page.evaluate(()=>window.poliscope.workspaceCatalogue());
  const archive=join(dir,'confirmed.poliscope');
  await app.evaluate(({dialog},path)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:path});},archive);
  expect((await page.evaluate(()=>window.poliscope.archive({action:'export'}))).status).toBe('complete');
  const bytes=await readFile(archive);
  const error=await page.evaluate(async()=>{try{await window.poliscope.archive({action:'export'});return 'accepted';}catch(e){return String(e);}});
  expect(error).toContain('Desktop request rejected');expect(error).not.toContain(dir);
  expect(await readFile(archive)).toEqual(bytes);
  const hostile=join(dir,'hostile.poliscope');
  execFileSync(resolve('.venv/bin/python'),['-I','-c','import sys,zipfile\nwith zipfile.ZipFile(sys.argv[1],"w") as z: z.writestr("../executable.py", "raise SystemExit(99)")',hostile]);
  await app.evaluate(({dialog},path)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[path]});},hostile);
  expect(await page.evaluate(async()=>{try{await window.poliscope.archive({action:'import'});return false;}catch{return true;}})).toBe(true);
  expect(await page.evaluate(()=>window.poliscope.workspaceCatalogue())).toEqual(before);
  // Kill main without before-quit, then cold-open the real WAL-backed store.
  const exited=new Promise<void>(resolve=>app.process().once('exit',()=>resolve()));
  app.process().kill('SIGKILL');await exited;
  app=await electron.launch({executablePath,args:['--no-sandbox'],env});page=await app.firstWindow();
  await expect(page.getByRole('status')).toHaveText('Local engine ready');
  await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},worlds);
  await page.evaluate(()=>window.poliscope.chooseWorkspace());
  expect(await page.evaluate(()=>window.poliscope.workspaceCatalogue())).toEqual(before);
  await app.evaluate(({dialog},path)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[path]});},join(worlds,'poliscope.sqlite3'));
  expect((await page.evaluate(()=>window.poliscope.recovery({action:'inspect'}))).branches?.[0].context).toEqual(saved.context);
  const read=await page.evaluate(context=>window.poliscope.recovery({action:'read',context}),saved.context);
  expect(read.status).toBe('complete');expect(read.detail).toContain('not freshly reproduced');
  for(const forbidden of [dir,'SYNTHETIC_ENGINE_ENV_CANARY','PRIVATE_DIAGNOSTIC_CANARY'])expect(JSON.stringify(read)).not.toContain(forbidden);
  expect(await readFile(archive)).toEqual(bytes);
 }finally{await app.close();await rm(dir,{recursive:true,force:true});}
});
