/** Main-only request lifecycle. Polling returns snapshots; generation is never retried. */
import { randomUUID } from 'node:crypto';
import type { AssistantPrepare, AssistantAction, AssistantReply } from '../../contracts/assistant';
import type { SpendBinding } from '../../contracts/spending';
import schema from '../../contracts/assistant.schema.json';
import { valid, type Schema } from './wire';
import { SharingEnvelope } from './sharing';
import { ChatStream, StreamError, ProviderStreamError, wholeResponse } from './provider-stream';
import { type BuiltRequest } from './provider-requests';
import type { ProviderController } from './providers';
import type { GenerationTransport } from './provider-network';
import type { Spend } from './spending';
const defs=schema.$defs as Record<string,Schema>;
export const assistantValid=(input:unknown,type:string)=>valid(input,defs[type],defs);
export const assistantRequestValid=(input:unknown):input is AssistantPrepare|AssistantAction=>assistantValid(input,'AssistantPrepare')||assistantValid(input,'AssistantAction');
type Job={reply:AssistantReply;request:BuiltRequest;envelope:SharingEnvelope;controller:AbortController;query:AssistantPrepare;binding:SpendBinding;started:boolean};
export class AssistantController {
  private jobs=new Map<string,Job>();private session=randomUUID();private closed=false;
  private pending=0;
  constructor(private providers:Pick<ProviderController,'prepareGeneration'|'dispatchGeneration'>,private transport:GenerationTransport,private spend:Spend,private context:()=>string) {}
  async request(input:unknown):Promise<AssistantReply> {
    if(this.closed||!assistantRequestValid(input)||Buffer.byteLength(JSON.stringify(input))>16384)throw new Error('Assistant request rejected');
    if(input.action==='prepare') {
      if(this.jobs.size+this.pending>=16)throw new Error('Close the application to clear retained requests');
      this.pending++;
      try {
        const context=this.context();if(Buffer.byteLength(context)>1024)throw new Error('Context unavailable');
        const request=await this.providers.prepareGeneration({generation_contract:1,profile_id:input.profile_id,expected_revision:input.expected_revision,messages:[{role:'user',content:input.text}],stream:input.stream,response_format:{type:'text'},tools:[]});
        if(this.closed)throw new Error('Assistant closed');
        const context_json=JSON.stringify({context:JSON.parse(context),endpoint:request.endpoint,profile_id:request.profile_id,revision:request.revision,models:request.allowed_models});
        const envelope=new SharingEnvelope(request,context_json), id=envelope.id;
        const reply:AssistantReply={assistant_contract:1,request_id:id,status:'prepared',context_json,sharing_json:JSON.stringify(envelope.manifest),payload_json:request.json,text:'',reasoning:'',tools_json:'[]',usage_json:null,result:null,diagnostic:'none',exposure:input.exposure,exposure_status:'not-reserved'};
        if(!assistantValid(reply,'AssistantReply'))throw new Error('Assistant preview exceeds bounds');
        this.jobs.set(id,{reply,request,envelope,controller:new AbortController(),query:structuredClone(input),binding:{dispatch_id:id,turn_id:id,session_id:this.session,profile_id:input.profile_id,payload_sha256:envelope.payload_sha256,binding_sha256:envelope.binding_sha256,currency:'USD',estimate_version:'explicit-bounded-exposure-v1'},started:false});
        return structuredClone(reply);
      }finally{this.pending--;}
    }
    const job=this.jobs.get(input.request_id);if(!job)throw new Error('Assistant request unavailable');
    if(input.action==='send'&&!job.started&&job.reply.status==='prepared') {
      job.envelope.approve();job.started=true;job.reply.status='pending';void this.run(job);
    }
    if(input.action==='cancel'||input.action==='revoke') {
      job.envelope.revoke();job.controller.abort();
      if(['prepared','pending','streaming'].includes(job.reply.status)) {job.reply.status=input.action==='revoke'?'revoked':'cancelled';job.reply.result=null;}
    }
    job.reply.sharing_json=JSON.stringify(job.envelope.manifest);
    return structuredClone(job.reply);
  }
  private async run(job:Job) {
    const reply=job.reply, signal=job.controller.signal;
    let reserved=false, uncertain=false, receivedOutput=false;
    try {
      // Acquire a profile/key lease, revalidate metadata and bound request first.
      await this.providers.dispatchGeneration(job.request,signal,async(key,leaseSignal)=> {
        const revoke=()=>job.controller.abort();leaseSignal.addEventListener('abort',revoke,{once:true});
        try {
          if(signal.aborted||leaseSignal.aborted)throw new Error('Cancelled');
          job.envelope.authorize(job.request);
          reply.exposure_status='unresolved';
          const grant=await this.spend({action:'reserve',binding:job.binding,exposure:job.query.exposure,turn_limit:job.query.turn_limit,session_limit:job.query.session_limit,profile_limit:job.query.profile_limit});
          if(grant.status!=='reserved'){if(grant.status==='denied')reply.exposure_status='not-reserved';reply.diagnostic='budget';throw new Error('Spending denied');}
          reserved=true;reply.exposure_status='reserved';
          if(signal.aborted||leaseSignal.aborted)throw new Error('Cancelled');
          // Persist uncertain send *before* invoking transport. Crash/cancel cannot
          // release this exposure; only full WP-048 reconciliation may resolve it.
          const marked=await this.spend({action:'uncertain',binding:job.binding});
          if(marked.status!=='uncertain'){reply.diagnostic='budget';throw new Error('Spending unavailable');}
          uncertain=true;reply.exposure_status='unresolved';
          if(signal.aborted||leaseSignal.aborted)throw new Error('Cancelled');
          // Reservation is asynchronous: repeat production capability/profile
          // validation at the final dispatch boundary, not just before the grant.
          reply.diagnostic='configuration';
          const current=await this.providers.prepareGeneration(job.request.plan);
          if(signal.aborted||leaseSignal.aborted)throw new Error('Cancelled');
          job.envelope.authorize(current);reply.diagnostic='none';
          const parser=job.request.plan.stream?new ChatStream(job.request):null;
          reply.status='streaming';
          const response=await this.transport(job.request.endpoint+job.request.path,job.request.json,key,leaseSignal,job.request.plan.stream,chunk=> {
            if(signal.aborted||leaseSignal.aborted)throw new Error('Cancelled');
            parser!.push(chunk);
            const state=parser!.snapshot();
            if(JSON.stringify(state).includes(JSON.stringify(key).slice(1,-1)))throw new StreamError();
            receivedOutput=Boolean(state.text||state.reasoning||state.tools.length);
            // Withhold a key-length suffix so a key split over chunks cannot
            // become visible before the complete credential-echo check.
            reply.text=state.text.slice(0,Math.max(0,state.text.length-key.length));
            reply.reasoning=state.reasoning.slice(0,Math.max(0,state.reasoning.length-key.length));
            reply.usage_json=state.usage_json;
          });
          if(signal.aborted||leaseSignal.aborted)throw new Error('Cancelled');
          if(response.code<200||response.code>=300) {
            reply.diagnostic=response.code===401||response.code===403?'authentication':response.code===402?'credits':response.code===429?'rate-limit':response.code===404?'model':response.code>=300&&response.code<400?'redirect':'provider';
            throw new Error('Provider rejected');
          }
          let completed;
          if(parser)completed=parser.end();
          else {
            let body:unknown;try{body=JSON.parse(response.body);}catch{throw new StreamError();}
            completed=wholeResponse(job.request,body);
          }
          const {snapshot,result}=completed;
          if(JSON.stringify(completed).includes(JSON.stringify(key).slice(1,-1)) || snapshot.tools.some(t=>JSON.stringify(JSON.parse(t.arguments)).includes(JSON.stringify(key).slice(1,-1))))throw new StreamError();
          reply.text=snapshot.text;reply.reasoning=snapshot.reasoning;reply.tools_json=JSON.stringify(snapshot.tools);reply.usage_json=snapshot.usage_json;reply.result=result;
          reply.status=snapshot.finish_reason==='tool_calls'?'tool-calls':result.status==='complete'?'complete':'incomplete';
          // Completion retains exposure. Usage observations are never zero-cost.
          try{await this.spend({action:'complete',binding:job.binding});}catch{/* already durable uncertain */}
        }finally{leaseSignal.removeEventListener('abort',revoke);}
      });
    }catch(error) {
      if(signal.aborted) {if(reply.status!=='revoked')reply.status='cancelled';reply.result=null;}
      else {reply.status=receivedOutput||reply.text||reply.tools_json!=='[]'?'incomplete':'failed';reply.result=null;if(reply.diagnostic==='none')reply.diagnostic=error instanceof ProviderStreamError?error.diagnostic:error instanceof StreamError?'invalid-response':uncertain?'network':'configuration';}
      // No-send is only known before any uncertain-send transition was attempted.
      // A lost response to that transition may already have committed uncertainty;
      // the ledger refuses release in that case.
      if(reserved&&!uncertain) {
        try{const state=await this.spend({action:'no-send',binding:job.binding});reply.exposure_status=state.status==='no-send'?'no-send':'unresolved';}catch{reply.exposure_status='unresolved';}
      }
    }
  }
  close() {this.closed=true;for(const job of this.jobs.values()){job.envelope.revoke();job.controller.abort();} }
}
