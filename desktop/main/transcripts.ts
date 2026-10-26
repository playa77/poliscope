/** Explicit local text snapshots; never a source of provider history or exports. */
import { constants, openSync, closeSync, fstatSync, readFileSync, mkdirSync, writeFileSync, renameSync, unlinkSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import type { AssistantTranscript } from '../../contracts/assistant';
import schema from '../../contracts/assistant.schema.json';
import { valid, type Schema } from './wire';
const defs=schema.$defs as Record<string,Schema>;
export class TranscriptStore {
  constructor(private directory:string) {}
  private path() {return join(this.directory,'transcripts.json');}
  list():AssistantTranscript[] {
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
    try {writeFileSync(temporary,text,{flag:'wx',mode:0o600});renameSync(temporary,this.path());}
    finally {try{unlinkSync(temporary);}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}}
  }
  save(row:AssistantTranscript) {this.write([...this.list().filter(r=>r.request_id!==row.request_id),row]);}
  deleteTurn(turn:string) {this.write(this.list().filter(row=>row.turn_id!==turn));}
  deleteSaved(id:string) {const rows=this.list(),row=rows.find(r=>r.request_id===id);if(row)this.write(rows.filter(r=>r.turn_id!==row.turn_id));}
}
