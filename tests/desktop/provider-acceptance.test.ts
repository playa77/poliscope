/** WP-050: actual catalog/controller, immutable Python context and SQLite gates.
 * The transport is a provider-visible sink; all data and keys are synthetic. */
import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { AssistantController } from '../../desktop/main/assistant';
import { ProviderController } from '../../desktop/main/providers';
import { WorkspaceController } from '../../desktop/main/workspace';
import { spendingService, type Spend } from '../../desktop/main/spending';
import type { AssistantPrepare, AssistantReply } from '../../contracts/assistant';
import type { ProviderProfile } from '../../contracts/provider';
import type { GenerationTransport } from '../../desktop/main/provider-network';
import official from '../fixtures/providers/openrouter-contract-2026-10-26.json';

const model='synthetic/gpt';
const profile:ProviderProfile={id:'p',name:'Synthetic only',kind:'openrouter',endpoint:'https://openrouter.ai/api/v1',model,
 generation:{temperature:null,top_p:null,max_output_tokens:128},
 routing:{order:['fixture'],only:['fixture'],ignore:['excluded'],allow_fallbacks:false,require_parameters:true,data_collection:'deny',zdr:true,max_price:{prompt:'123456789.123456789',completion:'0'}},
 capabilities:{text:'unknown',tools:'unknown',structured_output:'unknown',reasoning:'unknown',image:'unknown',audio:'unknown',video:'unknown'}};
const query:AssistantPrepare={action:'prepare',profile_id:'p',expected_revision:2,text:'Explicit public question.',stream:false,exposure:'0.6',turn_limit:'1',session_limit:'1',profile_limit:'1'};
const completion=(text='Synthetic answer')=>({code:200,body:JSON.stringify({id:'gen_fixture',model,provider:'fixture',choices:[{index:0,message:{content:text},finish_reason:'stop'}]})});
const argumentsJSON=(entry:string)=>JSON.stringify({operation:'inspect',entry_id:entry,other_id:null,value_json:null});
async function terminal(app:AssistantController,id:string) {
 let reply!:AssistantReply;
 await vi.waitFor(async()=>{reply=await app.request({action:'status',request_id:id});expect(['pending','streaming']).not.toContain(reply.status);},{timeout:15000});
 return reply;
}
async function fixture(run:(f:{app:AssistantController;providers:ProviderController;world:WorkspaceController;spend:Spend;sent:string[];setResponse:(value:GenerationTransport)=>void;wrapSpend:(value:(spend:Spend)=>Spend)=>void})=>Promise<void>) {
 const directory=await mkdtemp(join(tmpdir(),'poliscope-provider-acceptance-'));
 const providers=new ProviderController(join(directory,'profile'),{isEncryptionAvailable:()=>false,encryptString:()=>Buffer.alloc(0),decryptString:()=>''},async()=>200,process.platform,
 async url=>({code:200,body:JSON.stringify(url.includes('/generation?')?{data:{id:'gen_fixture',model,total_cost:'0.7'}}:{data:[{id:model,architecture:{tokenizer:'GPT',input_modalities:['text'],output_modalities:['text']},context_length:32768,top_provider:{max_completion_tokens:1024},supported_parameters:['max_tokens','tools','tool_choice']} ]})}));
 const world=new WorkspaceController(false,resolve('.'),'');
 const spend=spendingService(false,resolve('.'),'',directory);let dispatchSpend=spend;
 const sent:string[]=[];let response:GenerationTransport=async()=>completion();
 const app=new AssistantController(providers,async(...args)=>{sent.push(args[1]);expect(args[2]).toBe('synthetic-acceptance-key');return response(...args);},q=>dispatchSpend(q),()=>world.assistantContext,s=>world.ground(s));
 try {
  await providers.request({action:'save',profile,expected_revision:null});
  await providers.request({action:'replace-key',profile_id:'p',expected_revision:1,key:'synthetic-acceptance-key'});
  expect((await providers.request({action:'refresh-catalog',profile_id:'p',expected_revision:2})).status).toBe('metadata-ready');
  await world.choose(join(directory,'world'));await world.create({name:'Original public world',setup:'blank',scope_name:'Home',population:'12',land_area:'3'});
  await run({app,providers,world,spend,sent,setResponse:value=>{response=value;},wrapSpend:value=>{dispatchSpend=value(spend);}});
 }finally{app.close();await providers.close();await rm(directory,{recursive:true,force:true});}
}

it('official schema price strings survive production preparation and provider-visible routing',()=>fixture(async f=>{
 const prepared=await f.app.request(query);const body=JSON.parse(prepared.payload_json);
 for(const [field,value] of Object.entries(body.provider.max_price)) {
  expect((official.provider_preferences.properties.max_price.properties as Record<string,{type:string}>)[field].type).toBe('string');expect(typeof value).toBe('string');
 }
 expect(body.provider).toEqual({...profile.routing});
 await f.app.request({action:'send',request_id:prepared.request_id});expect((await terminal(f.app,prepared.request_id)).status).toBe('complete');
 expect(f.sent).toEqual([prepared.payload_json]);expect(f.sent[0]).not.toContain('synthetic-acceptance-key');
}),30000);

it('tool-driven expansion cannot disclose private, unselected or newly navigated data; explicit new inclusion needs review',()=>fixture(async f=>{
 // The private note is actually committed in Python, not merely omitted by a stub.
 const state=JSON.parse(f.world.assistantContext).context;
 const preview=await f.world.previewWorkbench({context:state,scope_id:'home',change:{kind:'note',note_kind:'proposal',text:'PRIVATE-NOTE-PAYLOAD-CANARY'}});
 const applied=await f.world.applyWorkbench({candidate_digest:preview.candidate_digest});
 const privateNote=(await f.world.workbench({context:applied.state.context,scope_id:'home',collection:'notes'})).items[0];
 expect(privateNote.text).toBe('PRIVATE-NOTE-PAYLOAD-CANARY');
 const selection={scope_id:'home',task:'Inspect declared facts',collections:['facts'] as ('facts')[],tools:true};
 const grant=await f.world.ground(selection);const firstEntry=grant.manifest.entries[0].id;
 f.setResponse(async()=>({code:200,body:JSON.stringify({id:'gen_fixture',model,provider:'fixture',choices:[{index:0,message:{content:'',tool_calls:[firstEntry,privateNote.id,'note:missing','sources:excluded'].map((entry,i)=>({id:'call_'+i,type:'function',function:{name:'inspect_context',arguments:argumentsJSON(entry)}}))},finish_reason:'tool_calls'}]})}));
 const initial=await f.app.request({...query,exposure:'0.1',grounding:selection});await f.app.request({action:'send',request_id:initial.request_id});expect((await terminal(f.app,initial.request_id)).status).toBe('tool-calls');
 const other=await f.world.create({name:'OTHER-WORLD-PAYLOAD-CANARY',setup:'blank',scope_name:'Other',population:'99',land_area:'9'});
 const next=await f.app.request({action:'continue',request_id:initial.request_id});expect(f.sent).toHaveLength(1);
 const results=JSON.parse(next.payload_json).messages.filter((m:{role:string})=>m.role==='tool');
 expect(results).toHaveLength(4);expect(JSON.parse(results[0].content).classification).toBe('public-scoped');
 for(const result of results.slice(1))expect(result.content).toBe('{"status":"unavailable"}');
 f.setResponse(async()=>completion());await f.app.request({action:'send',request_id:next.request_id});expect((await terminal(f.app,next.request_id)).status).toBe('complete');
 expect(f.sent[1]).toBe(next.payload_json);
 for(const body of f.sent)for(const forbidden of ['PRIVATE-NOTE-PAYLOAD-CANARY','OTHER-WORLD-PAYLOAD-CANARY',other.context.civilization_id,'synthetic-acceptance-key'])expect(body).not.toContain(forbidden);
 const manifest=JSON.parse((await f.app.request({action:'status',request_id:next.request_id})).sharing_json);expect(manifest.disclosed_sha256).toHaveLength(2);
 // A new explicitly selected scope/collection has its own review, no inherited send.
 const expanded=await f.app.request({...query,grounding:{...selection,collections:['facts','sources']}});
 expect(JSON.parse(expanded.grounding_json!).context).toEqual(other.context);expect(f.sent).toHaveLength(2);
 await f.app.request({action:'revoke',request_id:initial.request_id});const replay=await f.app.request({action:'send',request_id:next.request_id});expect(JSON.parse(replay.sharing_json).revoked).toBe(true);expect(f.sent).toHaveLength(2);
}),30000);

it('two simultaneous 0.6 requests under 1 produce one POST; cancellation, deletion and late actuals keep the charge',()=>fixture(async f=>{
 let entered=false;
 f.setResponse(async(_url,_json,_key,signal)=>{entered=true;await new Promise<void>((_resolve,reject)=>{if(signal.aborted)reject(new Error('cancelled'));else signal.addEventListener('abort',()=>reject(new Error('cancelled')),{once:true});});return completion();});
 const turns=await Promise.all([f.app.request(query),f.app.request(query)]);
 await Promise.all(turns.map(r=>f.app.request({action:'send',request_id:r.request_id})));
 await vi.waitFor(()=>expect(entered).toBe(true),{timeout:15000});
 await vi.waitFor(async()=>{const states=await Promise.all(turns.map(r=>f.app.request({action:'status',request_id:r.request_id})));expect(states.filter(r=>r.diagnostic==='budget')).toHaveLength(1);},{timeout:15000});
 expect(f.sent).toHaveLength(1);
 const states=await Promise.all(turns.map(r=>f.app.request({action:'status',request_id:r.request_id})));const winner=states.find(r=>r.diagnostic!=='budget')!;
 await f.app.request({action:'cancel',request_id:winner.request_id});expect((await terminal(f.app,winner.request_id)).status).toBe('cancelled');
 const history=await f.app.request({action:'usage-history',request_id:winner.request_id});const record=history.spending!.records!.find(r=>r.binding.dispatch_id===winner.request_id)!;
 expect(record.exposure).toBe('0.6');
 // Provider facts can arrive after cancellation; exact duplicates replace once.
 const observation={source:'generation-metadata' as const,generation_id:'gen_fixture',actual_cost:'0.7'};
 await f.spend({action:'observe',binding:record.binding,observation});await f.spend({action:'observe',binding:record.binding,observation});
 await f.app.request({action:'delete',request_id:winner.request_id});
 const durable=await f.spend({action:'status',binding:record.binding});expect(durable.profile_total).toBe('0.7');
 const retry=await f.app.request(query);await f.app.request({action:'send',request_id:retry.request_id});expect((await terminal(f.app,retry.request_id)).diagnostic).toBe('budget');expect(f.sent).toHaveLength(1);
}),30000);

it('a real continuation cannot reuse its initial reservation to exceed the turn allowance',()=>fixture(async f=>{
 const selection={scope_id:'home',task:'Inspect',collections:['facts'] as ('facts')[],tools:true};const grant=await f.world.ground(selection);
 f.setResponse(async()=>({code:200,body:JSON.stringify({model,choices:[{index:0,message:{content:'',tool_calls:[{id:'inspect_one',type:'function',function:{name:'inspect_context',arguments:argumentsJSON(grant.manifest.entries[0].id)}}]},finish_reason:'tool_calls'}]})}));
 const initial=await f.app.request({...query,grounding:selection});await f.app.request({action:'send',request_id:initial.request_id});expect((await terminal(f.app,initial.request_id)).status).toBe('tool-calls');
 const next=await f.app.request({action:'continue',request_id:initial.request_id});await f.app.request({action:'send',request_id:next.request_id});
 const denied=await terminal(f.app,next.request_id);expect(denied.diagnostic).toBe('budget');expect(f.sent).toHaveLength(1);
 const history=await f.app.request({action:'usage-history',request_id:initial.request_id});expect(history.spending!.records).toHaveLength(1);expect(history.spending!.records![0].binding.turn_id).toBe(initial.request_id);
}),30000);

it.each(['reserve','uncertain'] as const)('cancel while %s response is delayed cannot leak a POST or release uncertain exposure',stage=>fixture(async f=>{
 let release!:()=>void,entered=false;const blocked=new Promise<void>(resolve=>{release=resolve;});
 f.wrapSpend(spend=>async q=>{const result=await spend(q);if(q.action===stage){entered=true;await blocked;}return result;});
 const prepared=await f.app.request(query);await f.app.request({action:'send',request_id:prepared.request_id});
 await vi.waitFor(()=>expect(entered).toBe(true),{timeout:15000});await f.app.request({action:'cancel',request_id:prepared.request_id});release();
 await vi.waitFor(async()=>{const result=await f.app.request({action:'usage-history',request_id:prepared.request_id});const record=result.spending!.records![0];expect(record.state).toBe(stage==='reserve'?'no-send':'uncertain');},{timeout:15000});
 expect(f.sent).toHaveLength(0);
 const next=await f.app.request(query);await f.app.request({action:'send',request_id:next.request_id});const result=await terminal(f.app,next.request_id);
 expect(result.status).toBe(stage==='reserve'?'complete':'failed');expect(result.diagnostic).toBe(stage==='reserve'?'none':'budget');expect(f.sent).toHaveLength(stage==='reserve'?1:0);
}),30000);
