/** Exact-byte review plus cumulative, revocable turn disclosure. */
import { createHash, randomUUID } from 'node:crypto';
import type { BuiltRequest } from './provider-requests';
export const sha256=(text:string)=>createHash('sha256').update(text).digest('hex');
type Disclosure={revoked:boolean;disclosed:Set<string>;bytes:number};
export class SharingEnvelope {
  readonly id=randomUUID();
  readonly payload_sha256:string;
  readonly binding_sha256:string;
  private expected:{profile_id:string;revision:number;endpoint:string};
  private approved=false;
  private disclosure:Disclosure;
  constructor(readonly request:BuiltRequest,readonly context_json:string,readonly max_bytes=196608,previous?:SharingEnvelope,private classifications=['explicit-user-text']) {
    if (Buffer.byteLength(request.json)>max_bytes) throw new Error('Sharing limit');
    this.expected={profile_id:request.profile_id,revision:request.revision,endpoint:request.endpoint};
    if(previous && (previous.context_json!==context_json || JSON.stringify(previous.expected)!==JSON.stringify(this.expected) || JSON.stringify(previous.request.allowed_models)!==JSON.stringify(request.allowed_models)))throw new Error('Sharing binding changed');
    this.disclosure=previous?.disclosure??{revoked:false,disclosed:new Set(),bytes:0};
    if(this.disclosure.revoked || this.disclosure.bytes+Buffer.byteLength(request.json)>max_bytes)throw new Error('Sharing limit');
    this.payload_sha256=sha256(request.json);
    this.binding_sha256=sha256(JSON.stringify([request.profile_id,request.revision,request.endpoint,request.allowed_models,context_json,request.plan]));
  }
  approve() { if(this.disclosure.revoked)throw new Error('Sharing revoked');this.approved=true; }
  revoke() { this.disclosure.revoked=true;this.approved=false; }
  authorize(request:BuiltRequest) {
    if(this.disclosure.revoked||!this.approved||request.profile_id!==this.expected.profile_id||request.revision!==this.expected.revision||request.endpoint!==this.expected.endpoint||sha256(request.json)!==this.payload_sha256||JSON.stringify(request.allowed_models)!==JSON.stringify(this.request.allowed_models))throw new Error('Sharing rejected');
    if(!this.disclosure.disclosed.has(this.payload_sha256)) {
      const bytes=Buffer.byteLength(request.json);
      if(this.disclosure.bytes+bytes>this.max_bytes)throw new Error('Sharing limit');
      this.disclosure.bytes+=bytes;this.disclosure.disclosed.add(this.payload_sha256);
    }
    return {payload_sha256:this.payload_sha256,binding_sha256:this.binding_sha256,bytes:this.disclosure.bytes};
  }
  get manifest() {return {classifications:this.classifications,context_sha256:sha256(this.context_json),max_bytes:this.max_bytes,binding_sha256:this.binding_sha256,payload_sha256:this.payload_sha256,disclosed_sha256:[...this.disclosure.disclosed],bytes:this.disclosure.bytes,revoked:this.disclosure.revoked};}
}
