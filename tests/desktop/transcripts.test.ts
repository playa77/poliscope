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
