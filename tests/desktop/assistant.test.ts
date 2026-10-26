import { it,expect,vi } from 'vitest';
import { mkdtemp,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { AssistantController,assistantRequestValid } from '../../desktop/main/assistant';
import { SharingEnvelope } from '../../desktop/main/sharing';
import { spendingService,type Spend } from '../../desktop/main/spending';
import type { BuiltRequest } from '../../desktop/main/provider-requests';
import type { GenerationTransport } from '../../desktop/main/provider-network';
import type { AssistantPrepare,AssistantReply } from '../../contracts/assistant';
const query:AssistantPrepare={action:'prepare',profile_id:'profile',expected_revision:1,text:'Only explicitly included text',stream:true,exposure:'0.04',turn_limit:'0.1',session_limit:'0.1',profile_limit:'0.1'};
const event=(content:string,finish:string|null=null)=>'data: '+JSON.stringify({model:'m',choices:[{index:0,delta:{content},finish_reason:finish}]})+'\n\n';
const complete=event('A sufficiently long synthetic answer.','stop')+'data: [DONE]\n\n';
const empty:BuiltRequest={profile_id:'profile',revision:1,endpoint:'http://127.0.0.1:1234',method:'POST',path:'/chat/completions',json:'{}',selected_model:'m',allowed_models:['m'],plan:{generation_contract:1,profile_id:'profile',expected_revision:1,messages:[{role:'user',content:'explicit'}],stream:true,response_format:{type:'text'},tools:[]}};
function fixture(transport?:GenerationTransport,spend?:Spend) {
  const order:string[]=[];let context='{"branch":"original"}';let keyLease=new AbortController();
  const providers={prepareGeneration:vi.fn(async(plan:BuiltRequest['plan'])=>({...empty,plan,json:JSON.stringify({model:'m',messages:plan.messages,stream:plan.stream})})),dispatchGeneration:async<T>(_r:BuiltRequest,signal:AbortSignal,send:(key:string,signal:AbortSignal)=>Promise<T>)=> {
    order.push('lease');const abort=()=>keyLease.abort();signal.addEventListener('abort',abort,{once:true});
    try{return await send('synthetic-key-never-render',keyLease.signal);}finally{signal.removeEventListener('abort',abort);}
  }};
  const send=vi.fn<GenerationTransport>(transport??(async(_url,_json,_key,_signal,_stream,chunk)=>{order.push('transport');chunk(Buffer.from(complete));return{code:200,body:''};}));
  const ledger:Spend=spend??(async q=>{order.push(q.action);return{spending_contract:1,dispatch_id:q.binding.dispatch_id,status:q.action==='reserve'?'reserved':q.action==='uncertain'?'uncertain':q.action==='no-send'?'no-send':'complete',exposure:'0.04',currency:'USD'};});
  const app=new AssistantController(providers,send,ledger,()=>context);
  return{app,send,order,providers,changeContext:()=>{context='{"branch":"different"}';},removeKey:()=>keyLease.abort()};
}
async function start(f:ReturnType<typeof fixture>,q=query){const prepared=await f.app.request(q);await f.app.request({action:'send',request_id:prepared.request_id});return prepared.request_id;}
async function terminal(f:ReturnType<typeof fixture>,id:string){let reply:AssistantReply;await vi.waitFor(async()=>{reply=await f.app.request({action:'status',request_id:id});expect(['pending','streaming']).not.toContain(reply.status);},{timeout:10000});return reply!;}
it('requires explicit review, reserves durably before transport, keeps context and deduplicates send',async()=> {
 const f=fixture();const prepared=await f.app.request(query);expect(f.send).not.toHaveBeenCalled();expect(prepared.payload_json).toContain(query.text);f.changeContext();
 await Promise.all([f.app.request({action:'send',request_id:prepared.request_id}),f.app.request({action:'send',request_id:prepared.request_id})]);
 const reply=await terminal(f,prepared.request_id);expect(reply.status).toBe('complete');expect(reply.text).toBe('A sufficiently long synthetic answer.');expect(reply.context_json).toContain('original');expect(reply.context_json).not.toContain('different');expect(f.order).toEqual(['lease','reserve','uncertain','transport','observe','complete']);expect(f.send).toHaveBeenCalledTimes(1);expect(reply.exposure_status).toBe('unresolved');
});
it.each([401,403,402,429,404,500,302])('safe HTTP %i never returns provider prose or headers',async code=> {
 const f=fixture(async()=>({code,body:'Authorization: synthetic-key-never-render private-provider-canary'}));const result=await terminal(f,await start(f));expect(result.status).toBe('failed');expect(result.diagnostic).not.toBe('none');expect(JSON.stringify(result)).not.toContain('private-provider-canary');expect(f.send).toHaveBeenCalledTimes(1);
});
it('budget denial sends no bytes',async()=> {
 const f=fixture(undefined,async q=>({spending_contract:1,dispatch_id:q.binding.dispatch_id,status:'denied',exposure:'0',currency:'USD'}));const result=await terminal(f,await start(f));expect(result.diagnostic).toBe('budget');expect(f.send).not.toHaveBeenCalled();
});
it.each(['cancel','key removal','close'])('retains uncertainty and partial status after %s',async mode=> {
 let deliver:(()=>void)|undefined;
 const f=fixture(async(_url,_json,_key,signal,_stream,chunk)=>new Promise((resolve,reject)=> {
   chunk(Buffer.from(event('Partial output is attached only to the original request.')));deliver=()=>{chunk(Buffer.from(event('', 'stop')+'data: [DONE]\n\n'));resolve({code:200,body:''});};
   signal.addEventListener('abort',()=>reject(new Error('cancelled')),{once:true});
 }));const id=await start(f);await vi.waitFor(()=>expect(deliver).toBeDefined());
 if(mode==='close'){f.app.close();expect(f.order).toContain('uncertain');return;}
 if(mode==='key removal')f.removeKey();else await f.app.request({action:'cancel',request_id:id});
 const reply=await terminal(f,id);expect(reply.status).toBe('cancelled');expect(reply.result).toBeNull();expect(reply.exposure_status).toBe('unresolved');expect(f.order).not.toContain('no-send');expect(f.send).toHaveBeenCalledTimes(1);
});
it('timeout/uncertain acceptance never retries; deliberate new review uses a fresh dispatch',async()=> {
 const f=fixture(async()=>{throw new Error('private-network-diagnostic');});const first=await start(f);const reply=await terminal(f,first);expect(reply.status).toBe('failed');await f.app.request({action:'send',request_id:first});expect(f.send).toHaveBeenCalledTimes(1);const second=await start(f);expect(second).not.toBe(first);await terminal(f,second);expect(f.send).toHaveBeenCalledTimes(2);expect(JSON.stringify(reply)).not.toContain('private-network-diagnostic');
});
it('cancellation during reservation releases only a known no-send',async()=> {
 let release:(()=>void)|undefined;
 const f=fixture(undefined,async q=> {
   if(q.action==='reserve')await new Promise<void>(resolve=>{release=resolve;});
   return{spending_contract:1,dispatch_id:q.binding.dispatch_id,status:q.action==='reserve'?'reserved':q.action==='no-send'?'no-send':'uncertain',exposure:'0.04',currency:'USD'};
 });const id=await start(f);await vi.waitFor(()=>expect(release).toBeDefined());await f.app.request({action:'cancel',request_id:id});release!();await vi.waitFor(async()=>expect((await f.app.request({action:'status',request_id:id})).exposure_status).toBe('no-send'));expect(f.send).not.toHaveBeenCalled();
});
it('rejects malformed output and suppresses credential echo across chunks',async()=> {
 const f=fixture(async(_u,_j,key,_s,_st,chunk)=>{chunk(Buffer.from(event(key.slice(0,10))));chunk(Buffer.from(event(key.slice(10),'stop')+'data: [DONE]\n\n'));return{code:200,body:''};});const reply=await terminal(f,await start(f));expect(reply.status).toBe('incomplete');expect(reply.diagnostic).toBe('invalid-response');expect(JSON.stringify(reply)).not.toContain('synthetic-key-never-render');expect(reply.text).toBe('');
});
it('whole JSON response retains reasoning, usage and incomplete text without declaring completion',async()=> {
 const f=fixture(async()=>({code:200,body:JSON.stringify({model:'m',choices:[{index:0,message:{content:'partial',reasoning:'visible'},finish_reason:'length'}],usage:{total_tokens:7}})}));const reply=await terminal(f,await start(f,{...query,stream:false}));expect(reply.status).toBe('incomplete');expect(reply.text).toBe('partial');expect(reply.reasoning).toBe('visible');expect(JSON.parse(reply.usage_json!)).toEqual({total_tokens:7});
});
it('revocation and exact complete payload authorization reject hidden context/continuations',()=> {
 const envelope=new SharingEnvelope(empty,'{"branch":"original"}');expect(()=>envelope.authorize(empty)).toThrow();envelope.approve();envelope.authorize(empty);expect(envelope.manifest.bytes).toBe(2);envelope.authorize(empty);expect(envelope.manifest.bytes).toBe(2);
 for(const next of [{...empty,json:'{"messages":["private-note-canary"]}'},{...empty,endpoint:'https://other.invalid'},{...empty,revision:2}])expect(()=>envelope.authorize(next)).toThrow();envelope.revoke();expect(()=>envelope.authorize(empty)).toThrow();
});
it('untrusted requests cannot supply a path, key, endpoint, context receipt or generic operation',()=> {
 for(const extra of [{path:'/tmp/secret'},{key:'secret'},{endpoint:'https://other.invalid'},{context_json:'forged'},{operation:'world.apply'}])expect(assistantRequestValid({...query,...extra})).toBe(false);
 expect(assistantRequestValid({...query,text:'x'.repeat(8193)})).toBe(false);
});
it('production Python host retains profile exposure across controller restart and denies overspend',async()=> {
 const directory=await mkdtemp(join(tmpdir(),'poliscope-spend-'));
 try {
  const spend=spendingService(false,process.cwd(),process.cwd(),directory);
  const first=fixture(undefined,spend);expect((await terminal(first,await start(first))).status).toBe('complete');first.app.close();
  const second=fixture(undefined,spend);expect((await terminal(second,await start(second))).status).toBe('complete');
  const third=fixture(undefined,spend);const blocked=await terminal(third,await start(third));expect(blocked.diagnostic).toBe('budget');expect(third.send).not.toHaveBeenCalled();
 }finally{await rm(directory,{recursive:true,force:true});}
});
it('revalidates after asynchronous grants so changed capabilities cannot dispatch',async()=> {
 const f=fixture();const id=await f.app.request(query);
 f.providers.prepareGeneration.mockRejectedValueOnce(new Error('stale-metadata'));
 await f.app.request({action:'send',request_id:id.request_id});const result=await terminal(f,id.request_id);expect(result.diagnostic).toBe('configuration');expect(f.send).not.toHaveBeenCalled();expect(result.exposure_status).toBe('unresolved');
});
it.each([401,402,429,404,503])('midstream provider code %i is safe and actionable',async code=> {
 const f=fixture(async(_u,_j,_k,_s,_stream,chunk)=>{chunk(Buffer.from('data: '+JSON.stringify({error:{code,message:'private-provider-error-canary'}})+'\n\n'));return{code:200,body:''};});const result=await terminal(f,await start(f));expect(result.diagnostic).not.toBe('none');expect(result.diagnostic).not.toBe('network');expect(JSON.stringify(result)).not.toContain('private-provider-error-canary');
});
it('lost reservation acknowledgment preserves unknown exposure and sends nothing',async()=> {
 const f=fixture(undefined,async()=>{throw new Error('lost response');});const result=await terminal(f,await start(f));expect(result.exposure_status).toBe('unresolved');expect(f.send).not.toHaveBeenCalled();
});
it('production ledger persists usage-only actuals, replaces exposure and deduplicates late retrieval',async()=> {
 const dir=await mkdtemp(join(tmpdir(),'poliscope-reconcile-'));
 try {
  const spend=spendingService(false,process.cwd(),process.cwd(),dir);
  const f=fixture(async(_u,_j,_k,_s,_stream,chunk)=>{chunk(Buffer.from(event('Complete paid response.','stop')+'data: '+JSON.stringify({id:'gen-fixture',choices:[],usage:{prompt_tokens:3,completion_tokens:2,completion_tokens_details:{reasoning_tokens:1},cost:'0.012345678901234567'}})+'\n\ndata: [DONE]\n\n'));return{code:200,body:''};},spend);
  const prepare=f.providers.prepareGeneration.getMockImplementation()!;
  f.providers.prepareGeneration.mockImplementation(async plan=>({...await prepare(plan),provider_kind:'openrouter'}));
  const id=await start(f);await terminal(f,id);
  await vi.waitFor(async()=>expect((await f.app.request({action:'usage',request_id:id})).spending?.actual_cost).toBe('0.012345678901234567'),{timeout:10000});
  const status=await f.app.request({action:'usage',request_id:id});
  expect(status.spending?.profile_total).toBe('0.012345678901234567');expect(status.spending?.usage?.reasoning_tokens).toBe(1);
  const providers=f.providers as typeof f.providers&{generationUsage:()=>Promise<import('../../contracts/spending').UsageObservation>};
  providers.generationUsage=async()=>({source:'generation-metadata',generation_id:'gen-fixture',actual_cost:'0.012345678901234567'});
  for(let i=0;i<2;i++)expect((await f.app.request({action:'reconcile',request_id:id})).spending?.profile_total).toBe('0.012345678901234567');
  await f.app.request({action:'configure-spending',request_id:id,turn_limit:'0.01',session_limit:'0.01',profile_limit:'0.01'});
  const second=await start(f,{...query,turn_limit:'0.01',session_limit:'0.01',profile_limit:'0.01'});expect((await terminal(f,second)).diagnostic).toBe('budget');expect(f.send).toHaveBeenCalledTimes(1);
 }finally{await rm(dir,{recursive:true,force:true});}
});
it('compatible cost has no established USD meaning and cancelled usage retains honest exposure',async()=> {
 const observations:unknown[]=[];
 const f=fixture(async(_u,_j,_k,signal,_stream,chunk)=>new Promise((_resolve,reject)=>{
  chunk(Buffer.from('data: '+JSON.stringify({id:'generation-cancel',model:'m',choices:[],usage:{total_tokens:4,cost:0}})+'\n\n'));
  signal.addEventListener('abort',()=>reject(new Error('cancelled')),{once:true});
 }),async q=>{if(q.action==='observe')observations.push(q.observation);return{dispatch_id:q.binding.dispatch_id,spending_contract:1,status:q.action==='reserve'?'reserved':'uncertain',exposure:'0.04',currency:'USD'};});
 const id=await start(f);await vi.waitFor(()=>expect(f.send).toHaveBeenCalledTimes(1));await f.app.request({action:'cancel',request_id:id});
 await vi.waitFor(()=>expect(observations).toHaveLength(1));expect(observations[0]).toEqual({source:'response',generation_id:'generation-cancel',outcome:'cancelled',actual_model:'m',total_tokens:4});
});
it('recovers usage after controller restart without storing or resending the original prompt',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'poliscope-usage-restart-'));
 try {
  const spend=spendingService(false,process.cwd(),process.cwd(),dir);
  const first=fixture(async(_u,_j,_k,_s,_st,chunk)=>{chunk(Buffer.from('data: '+JSON.stringify({id:'gen-restart',model:'m',choices:[{index:0,delta:{content:'Original answer'},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n'));return{code:200,body:''};},spend);
  const build=first.providers.prepareGeneration.getMockImplementation()!;first.providers.prepareGeneration.mockImplementation(async plan=>({...await build(plan),provider_kind:'openrouter'}));
  const old=await start(first);await terminal(first,old);
  await vi.waitFor(async()=>expect((await first.app.request({action:'usage-history',request_id:old})).spending?.records?.[0].usage?.generation_id).toBe('gen-restart'),{timeout:10000});
  first.app.close();
  const recovered=fixture(undefined,spend),selected=await recovered.app.request(query);
  const provider=recovered.providers as typeof recovered.providers&{generationUsage:()=>Promise<import('../../contracts/spending').UsageObservation>};
  provider.generationUsage=vi.fn(async()=>({source:'generation-metadata' as const,generation_id:'gen-restart',actual_cost:'0.01'}));
  const history=await recovered.app.request({action:'usage-history',request_id:selected.request_id});expect(history.spending?.records?.[0].binding.dispatch_id).toBe(old);
  const reconciled=await recovered.app.request({action:'reconcile-history',request_id:selected.request_id,lookup_dispatch:old});expect(reconciled.spending?.profile_total).toBe('0.01');expect(recovered.send).not.toHaveBeenCalled();
  expect(JSON.stringify(reconciled.spending)).not.toContain(query.text);
  await recovered.app.request({action:'delete',request_id:selected.request_id});
 }finally{await rm(dir,{recursive:true,force:true});}
});
