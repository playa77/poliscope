import { it,expect } from 'vitest';
import { mkdtemp,rm,writeFile,readFile,stat,symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { TranscriptStore } from '../../desktop/main/transcripts';
import type { AssistantTranscript } from '../../contracts/assistant';
const row=(id='a'):AssistantTranscript=>({request_id:id,turn_id:'root',created_at:'2026-10-26T12:00:00.000Z',saved_at:'2026-10-26T12:00:01.000Z',context_json:'{"branch":"original"}',status:'complete',selected_model:'selected',actual_model:null,actual_provider:null,prompt:'private prompt',text:'<img src="https://untrusted.invalid/">'});
it('empty by default, validates every field, replaces a snapshot and removes its whole lineage',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'poliscope-snapshot-store-'));
 try {
  const store=new TranscriptStore(dir);expect(store.list()).toEqual([]);
  store.save(row());store.save({...row(),text:'updated'});store.save(row('child'));
  expect(store.list()).toHaveLength(2);expect(store.list()[0].text).toBe('updated');
  if(process.platform!=='win32')expect((await stat(join(dir,'transcripts.json'))).mode&0o777).toBe(0o600);
  expect(()=>store.save({...row('bad'),payload_json:'hidden'} as AssistantTranscript)).toThrow();
  expect(()=>store.save({...row('bad'),text:'x'.repeat(32769)})).toThrow();
  expect(store.list()).toHaveLength(2);store.deleteSaved('a');expect(store.list()).toEqual([]);
  expect(await readFile(join(dir,'transcripts.json'),'utf8')).not.toContain('private prompt');
 }finally{await rm(dir,{recursive:true,force:true});}
});
it('bounded store fails closed on malformed, duplicate, oversized or linked local data',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'poliscope-snapshot-store-'));
 try {
  const file=join(dir,'transcripts.json'),store=new TranscriptStore(dir);
  for(const value of ['{',JSON.stringify([row(),row()]),JSON.stringify([{...row(),reasoning:'private derived copy'}]),' '.repeat(3_000_001)]) {
   await writeFile(file,value);expect(()=>store.list()).toThrow();expect(()=>store.save(row('new'))).toThrow();expect(await readFile(file,'utf8')).toBe(value);
  }
  await rm(file);await writeFile(join(dir,'other.json'),'[]');
  if(process.platform!=='win32'){await symlink(join(dir,'other.json'),file);expect(()=>store.list()).toThrow();}
 }finally{await rm(dir,{recursive:true,force:true});}
});
it('capacity never silently evicts private text and deletion allows a new snapshot',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'poliscope-snapshot-store-'));
 try {
  const store=new TranscriptStore(dir);for(let i=0;i<16;i++)store.save({...row('s'+i),turn_id:'t'+i});
  expect(()=>store.save(row('seventeenth'))).toThrow();expect(store.list()).toHaveLength(16);
  store.deleteTurn('t0');store.save(row('seventeenth'));expect(store.list()).toHaveLength(16);
 }finally{await rm(dir,{recursive:true,force:true});}
});

import { spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
it('cold restart discards only owned interrupted snapshots before listing or deleting private text',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'poliscope-snapshot-crash-'));
 try {
  const store=new TranscriptStore(dir);store.save(row());
  const staged=join(dir,randomUUID()+'.tmp'),unrelated=join(dir,'user-draft.tmp');
  await writeFile(unrelated,'retain unrelated draft');
  const child=spawnSync(process.execPath,['-e',`require('node:fs').writeFileSync(process.argv[1],process.argv[2],{mode:0o600});process.exit(17)`,staged,'PRIVATE_INTERRUPTED_TRANSCRIPT_CANARY']);
  expect(child.status).toBe(17);
  const cold=new TranscriptStore(dir);expect(cold.list()).toEqual([row()]);
  await expect(stat(staged)).rejects.toHaveProperty('code','ENOENT');
  // Interruption before the first confirmed snapshot has the same cleanup route.
  await rm(join(dir,'transcripts.json'));await writeFile(staged,'PRIVATE_UNCONFIRMED_CANARY');
  expect(new TranscriptStore(dir).list()).toEqual([]);
  await expect(stat(staged)).rejects.toHaveProperty('code','ENOENT');
  store.save(row());await writeFile(staged,'PRIVATE_DELETED_DERIVATIVE_CANARY');
  new TranscriptStore(dir).deleteSaved('a');expect(store.list()).toEqual([]);
  await expect(stat(staged)).rejects.toHaveProperty('code','ENOENT');
  expect(await readFile(unrelated,'utf8')).toBe('retain unrelated draft');
 }finally{await rm(dir,{recursive:true,force:true});}
});

import { chmod } from 'node:fs/promises';
it.runIf(process.platform!=='win32'&&process.getuid?.()!==0)('filesystem permission loss preserves the confirmed snapshot and permits a deliberate retry',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'poliscope-snapshot-permission-'));
 try {
  const store=new TranscriptStore(dir);store.save(row());
  const confirmed=await readFile(join(dir,'transcripts.json'),'utf8');
  await chmod(dir,0o500);
  expect(()=>store.save({...row(),text:'UNSAVED_PRIVATE_CANARY'})).toThrow();
  expect(await readFile(join(dir,'transcripts.json'),'utf8')).toBe(confirmed);
  await chmod(dir,0o700);store.save({...row(),text:'Retried explicitly'});
  expect(store.list()[0].text).toBe('Retried explicitly');
 }finally{await chmod(dir,0o700);await rm(dir,{recursive:true,force:true});}
});
