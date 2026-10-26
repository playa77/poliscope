/** WP-046-envelope. Exact-byte, revocable main-owned capability.
 * No implicit history, private notes, attachments or tool retrieval. A future
 * grounded-context consumer must obtain explicit inclusion for every expansion.
 */
import { createHash, randomUUID } from 'node:crypto';
import type { BuiltRequest } from './provider-requests';
export const sha256=(text:string)=>createHash('sha256').update(text).digest('hex');
export class SharingEnvelope {
  readonly id=randomUUID();
  readonly payload_sha256:string;
  readonly binding_sha256:string;
  private expected:{profile_id:string;revision:number;endpoint:string};
  private revoked=false; private approved=false;
  private disclosed=new Set<string>(); private bytes=0;
  constructor(readonly request:BuiltRequest,readonly context_json:string,readonly max_bytes=65536) {
    if (Buffer.byteLength(request.json)>max_bytes) throw new Error('Sharing limit');
    this.expected={profile_id:request.profile_id,revision:request.revision,endpoint:request.endpoint};
    this.payload_sha256=sha256(request.json);
    this.binding_sha256=sha256(JSON.stringify([request.profile_id,request.revision,request.endpoint,request.allowed_models,context_json,request.plan]));
  }
  approve() { if(this.revoked)throw new Error('Sharing revoked');this.approved=true; }
  revoke() { this.revoked=true;this.approved=false; }
  authorize(request:BuiltRequest) {
    if(this.revoked||!this.approved||request.profile_id!==this.expected.profile_id||request.revision!==this.expected.revision||request.endpoint!==this.expected.endpoint||sha256(request.json)!==this.payload_sha256)throw new Error('Sharing rejected');
    if(!this.disclosed.has(this.payload_sha256)) {
      const bytes=Buffer.byteLength(request.json);
      if(this.bytes+bytes>this.max_bytes)throw new Error('Sharing limit');
      this.bytes+=bytes;this.disclosed.add(this.payload_sha256);
    }
    return {payload_sha256:this.payload_sha256,binding_sha256:this.binding_sha256,bytes:this.bytes};
  }
  get manifest() {return {classifications:['explicit-user-text'],context_sha256:sha256(this.context_json),max_bytes:this.max_bytes,binding_sha256:this.binding_sha256,payload_sha256:this.payload_sha256,disclosed_sha256:[...this.disclosed],bytes:this.bytes,revoked:this.revoked};}
}
