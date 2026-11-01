/** Explicit local text snapshots; never a source of provider history or exports. */
import { constants, openSync, closeSync, fstatSync, readFileSync, mkdirSync, writeFileSync, renameSync, unlinkSync, readdirSync, fsyncSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import type { AssistantTranscript } from '../../contracts/assistant';
import schema from '../../contracts/assistant.schema.json';
import { valid, type Schema } from './wire';
const defs=schema.$defs as Record<string,Schema>;
export class TranscriptStore {
  constructor(private directory:string) {}
  private path() {return join(this.directory,'transcripts.json');}
  private discardInterruptedWrites() {
    // The application holds the user-data single-instance lock; snapshot writes
    // are synchronous. Only our UUID staging names can be abandoned here.
    try {
      for(const name of readdirSync(this.directory)) {
        if(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.tmp$/.test(name))unlinkSync(join(this.directory,name));
      }
    } catch(error) {
      if((error as NodeJS.ErrnoException).code!=='ENOENT')throw new Error('Transcript storage unavailable');
    }
  }
  list():AssistantTranscript[] {
    this.discardInterruptedWrites();
    let fd:number;
    try {fd=openSync(this.path(),constants.O_RDONLY|constants.O_NOFOLLOW);}
    catch(error) {if((error as NodeJS.ErrnoException).code==='ENOENT')return [];throw new Error('Transcript storage unavailable');}
    try {
      const stat=fstatSync(fd);if(!stat.isFile()||stat.size>3_000_000)throw new Error();
      const data:unknown=JSON.parse(readFileSync(fd,'utf8'));
      if(!Array.isArray(data)||data.length>16||data.some(row=>!valid(row,defs.AssistantTranscript,defs))||new Set(data.map(row=>row.request_id)).size!==data.length)throw new Error();
      return data;
    } finally {closeSync(fd);}
  }
  private write(rows:AssistantTranscript[]) {
    if(rows.length>16||rows.some(row=>!valid(row,defs.AssistantTranscript,defs)))throw new Error('Transcript limit reached');
    const text=JSON.stringify(rows);if(Buffer.byteLength(text)>3_000_000)throw new Error('Transcript storage limit reached');
    mkdirSync(this.directory,{recursive:true,mode:0o700});
    const temporary=join(this.directory,randomUUID()+'.tmp');
    try {
      const fd=openSync(temporary,'wx',0o600);
      try {writeFileSync(fd,text);fsyncSync(fd);} finally {closeSync(fd);}
      renameSync(temporary,this.path());
    }
    finally {try{unlinkSync(temporary);}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}}
  }
  save(row:AssistantTranscript) {this.write([...this.list().filter(r=>r.request_id!==row.request_id),row]);}
  deleteTurn(turn:string) {this.write(this.list().filter(row=>row.turn_id!==turn));}
  deleteSaved(id:string) {const rows=this.list(),row=rows.find(r=>r.request_id===id);if(row)this.write(rows.filter(r=>r.turn_id!==row.turn_id));}
}
