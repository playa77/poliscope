import { it,expect,vi } from 'vitest';
import { mkdtemp,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join,resolve } from 'node:path';
import { WorkspaceController } from '../../desktop/main/workspace';
import { AssistantController } from '../../desktop/main/assistant';
import { contextTool } from '../../desktop/main/grounding';
import { validateStructured } from '../../desktop/main/provider-schema';
import { SharingEnvelope } from '../../desktop/main/sharing';
import type { AssistantPrepare,AssistantReply } from '../../contracts/assistant';
import type { BuiltRequest } from '../../desktop/main/provider-requests';
import type { Spend } from '../../desktop/main/spending';
import type { GroundedSession } from '../../desktop/main/grounding';
const query:AssistantPrepare={action:'prepare',profile_id:'p',expected_revision:1,text:'Explain only the supplied inputs.',stream:false,exposure:'0.01',turn_limit:'0.05',session_limit:'0.1',profile_limit:'1',grounding:{scope_id:'home',task:'Explain',collections:['facts'],tools:true}};
const args=(id='facts:one',operation='inspect')=>JSON.stringify({operation,entry_id:id,other_id:null,value_json:null});
const complete=(content:string)=>JSON.stringify({model:'m',choices:[{index:0,message:{content},finish_reason:'stop'}]});
function fixture(options:{previewQualitative?:ConstructorParameters<typeof AssistantController>[8];cancelPreview?:ConstructorParameters<typeof AssistantController>[9];callCount?:number;denied?:boolean;execute?:GroundedSession['execute'];allTools?:boolean;budgetDenied?:boolean}={}) {
 const sent:string[]=[],grants:Parameters<Spend>[0][]=[];
 const ground:GroundedSession={manifest:{grounding_contract:1,context:{data_store_id:'s',civilization_id:'c',branch_id:'main',revision_id:'r'},selection:query.grounding!,versions:{world_schema:1,catalog_id:'cat',model_id:'mod',numeric_runtime_id:'runtime'},effective_time:{tick:0,calendar_id:'calendar'},entries:[{id:'facts:one',collection:'facts',coverage:'declared input',data_json:'{"value":"12","unit":"people"}'}],limitations:['No private data or other scopes'],digest:'sha256:'+'a'.repeat(64)},execute:vi.fn<GroundedSession['execute']>(options.execute??(async()=>({status:options.denied?'unavailable':'available',data_json:options.denied?'{"status":"unavailable"}':'{"value":"12","unit":"people"}'})))};
 const providers={prepareGeneration:vi.fn(async(plan:BuiltRequest['plan']):Promise<BuiltRequest>=>({profile_id:'p',revision:1,endpoint:'http://127.0.0.1:1234',method:'POST',path:'/chat/completions',json:JSON.stringify({model:'m',messages:plan.messages,tools:plan.tools}),selected_model:'m',allowed_models:['m'],plan})),dispatchGeneration:async<T>(_r:BuiltRequest,signal:AbortSignal,send:(key:string,signal:AbortSignal)=>Promise<T>)=>send('credential-canary',signal)};
 const app=new AssistantController(providers,async(_url,json)=>{
  sent.push(json);
  if(sent.length===1||options.allTools)return{code:200,body:JSON.stringify({model:'m',choices:[{index:0,message:{content:'',tool_calls:Array.from({length:options.callCount??1},(_,i)=>({id:'call_'+sent.length+'_'+i,type:'function',function:{name:'inspect_context',arguments:args(options.denied?'forged-private-ref':'facts:one')}}))},finish_reason:'tool_calls'}]})};
  return{code:200,body:complete('Grounded answer with explicit coverage.')};
 },async q=>{grants.push(q);return{spending_contract:1,dispatch_id:q.binding.dispatch_id,status:options.budgetDenied&&sent.length===1?'denied':q.action==='reserve'?'reserved':q.action==='uncertain'?'uncertain':'complete',exposure:'0.01',currency:'USD'};},()=>'{"branch":"original"}',async()=>ground,undefined,undefined,undefined,options.previewQualitative,options.cancelPreview);
 return{app,sent,grants,ground,providers};
}
async function terminal(app:AssistantController,id:string){let reply:AssistantReply;await vi.waitFor(async()=>{reply=await app.request({action:'status',request_id:id});expect(['pending','streaming']).not.toContain(reply.status);});return reply!;}
async function first(f:ReturnType<typeof fixture>){const reply=await f.app.request(query);await f.app.request({action:'send',request_id:reply.request_id});return terminal(f.app,reply.request_id);}
it('complete calls execute once; exact continuation needs fresh approval and distinct same-turn spending',async()=>{
 const f=fixture();const initial=await first(f);expect(initial.status).toBe('tool-calls');expect(f.ground.execute).not.toHaveBeenCalled();
 await vi.waitFor(async()=>expect((await f.app.request({action:'status',request_id:initial.request_id})).spending).toBeDefined());
 const [next,duplicate]=await Promise.all([f.app.request({action:'continue',request_id:initial.request_id}),f.app.request({action:'continue',request_id:initial.request_id})]);
 expect(next.request_id).toBe(duplicate.request_id);expect(next.request_id).not.toBe(initial.request_id);expect(next.status).toBe('prepared');expect(next.spending).toBeNull();expect(f.ground.execute).toHaveBeenCalledTimes(1);expect(f.sent).toHaveLength(1);
 const body=JSON.parse(next.payload_json);expect(body.messages.at(-1)).toEqual({role:'tool',tool_call_id:'call_1_0',content:'{"value":"12","unit":"people"}'});expect(body.messages.at(-2).tool_calls[0].function.name).toBe('inspect_context');
 await f.app.request({action:'send',request_id:next.request_id});expect((await terminal(f.app,next.request_id)).status).toBe('complete');
 const reserves=f.grants.filter(q=>q.action==='reserve');expect(reserves).toHaveLength(2);expect(reserves[0].binding.turn_id).toBe(reserves[1].binding.turn_id);expect(reserves[0].binding.dispatch_id).not.toBe(reserves[1].binding.dispatch_id);expect(reserves[0].binding.payload_sha256).not.toBe(reserves[1].binding.payload_sha256);
 expect(JSON.parse((await f.app.request({action:'status',request_id:next.request_id})).sharing_json).disclosed_sha256).toHaveLength(2);
});
it('injection receives fixed unavailability; existence and backend errors are never added',async()=>{
 const f=fixture({denied:true});const initial=await first(f);const next=await f.app.request({action:'continue',request_id:initial.request_id});
 const body=JSON.parse(next.payload_json);expect(body.messages.at(-1).content).toBe('{"status":"unavailable"}');expect(next.payload_json).not.toContain('private-note-body-canary');expect(f.sent).toHaveLength(1);
});
it('revocation after tool completion blocks every child dispatch',async()=>{
 const f=fixture();const initial=await first(f);const next=await f.app.request({action:'continue',request_id:initial.request_id});await f.app.request({action:'revoke',request_id:initial.request_id});await expect(f.app.request({action:'send',request_id:next.request_id})).rejects.toThrow();expect(f.sent).toHaveLength(1);
});
it('continuation spending denial cannot POST or inherit initial reservation',async()=>{
 const f=fixture({budgetDenied:true});const initial=await first(f);const next=await f.app.request({action:'continue',request_id:initial.request_id});await f.app.request({action:'send',request_id:next.request_id});expect((await terminal(f.app,next.request_id)).diagnostic).toBe('budget');expect(f.sent).toHaveLength(1);
});
it('three rounds and eight total tool calls bound autonomous local inspection',async()=>{
 const f=fixture({allTools:true});let reply=await first(f);
 for(let n=0;n<3;n++){reply=await f.app.request({action:'continue',request_id:reply.request_id});await f.app.request({action:'send',request_id:reply.request_id});reply=await terminal(f.app,reply.request_id);}
 await expect(f.app.request({action:'continue',request_id:reply.request_id})).rejects.toThrow();expect(f.ground.execute).toHaveBeenCalledTimes(3);expect(f.sent).toHaveLength(4);
 const many=fixture({callCount:9});const tooMany=await first(many);await expect(many.app.request({action:'continue',request_id:tooMany.request_id})).rejects.toThrow();expect(many.ground.execute).not.toHaveBeenCalled();
});
it('tool schema excludes executable, state-selection and arbitrary access authority',()=>{
 validateStructured(args(),contextTool.parameters_json);
 for(const arg of [{...JSON.parse(args()),context:{revision_id:'forged'}},{...JSON.parse(args()),operation:'apply'},{...JSON.parse(args()),url:'https://sink.invalid'},{...JSON.parse(args()),key:'canary'}])expect(()=>validateStructured(JSON.stringify(arg),contextTool.parameters_json)).toThrow();
});
it('cumulative envelope refuses expanded bindings and revoked history',()=>{
 const f=fixture();const build=(text:string):BuiltRequest=>({profile_id:'p',revision:1,endpoint:'https://example.invalid',method:'POST',path:'/chat/completions',selected_model:'m',allowed_models:['m'],json:text,plan:{generation_contract:1,profile_id:'p',expected_revision:1,messages:[{role:'user',content:text}],stream:false,response_format:{type:'text'}}});
 const request=build('12345'),envelope=new SharingEnvelope(request,'original',8);envelope.approve();envelope.authorize(request);expect(()=>new SharingEnvelope(build('6789'),'original',8,envelope)).toThrow();expect(()=>new SharingEnvelope(build('a'),'different',8,envelope)).toThrow();envelope.revoke();expect(()=>new SharingEnvelope(build('a'),'original',8,envelope)).toThrow();f.app.close();
});
it('actual Python context stays pinned across civilization navigation and never reads private notes',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'poliscope-grounding-'));
 try{
  const c=new WorkspaceController(false,resolve('.'),'');await c.choose(directory);const base=await c.create({name:'Grounded',setup:'blank',scope_name:'Home',population:'12',land_area:'3'});
  const preview=await c.previewWorkbench({context:base.context,scope_id:'home',change:{kind:'note',note_kind:'proposal',text:'PRIVATE-NOTE-CANARY do not share this'}});await c.applyWorkbench({candidate_digest:preview.candidate_digest});
  const grant=await c.ground(query.grounding!);expect(JSON.stringify(grant.manifest)).not.toContain('PRIVATE-NOTE-CANARY');const id=grant.manifest.entries[0].id;
  const other=await c.create({name:'Other',setup:'blank',scope_name:'Elsewhere',population:'99',land_area:'9'});const result=await grant.execute(args(id),'turn');expect(result.status).toBe('available');expect(JSON.stringify(grant.manifest)).not.toContain(other.context.civilization_id);expect(grant.manifest.context.civilization_id).toBe(base.context.civilization_id);
  const denied=await grant.execute(args('note:existing-private'),'turn');expect(denied).toMatchObject({status:'unavailable',data_json:'{"status":"unavailable"}'});
 }finally{await rm(directory,{recursive:true,force:true});}
});
it('a grounded turn cannot change committed state; only explicit ordinary preview action stages a retained proposal',async()=>{
 const proposal={context:{data_store_id:'s',civilization_id:'c',branch_id:'main',revision_id:'r'},scope_id:'home',change:{kind:'proposal',id:'need',value:{kind:'label',value:'proposed'},origin:'ai_proposed',source_request_id:'turn',coverage:'hypothetical',manifest_digest:'sha256:'+'a'.repeat(64)}};
 const f=fixture({execute:async()=>({status:'available',data_json:'{"status":"valid"}',proposal_json:JSON.stringify(proposal)})});
 const initial=await first(f);const next=await f.app.request({action:'continue',request_id:initial.request_id});expect(JSON.parse(next.proposals_json!)[0]).toEqual(proposal);expect(next.proposal_preview).toBeNull();
 // No preview callback is installed in this fixture: a model-produced proposal
 // cannot manufacture an ordinary Apply grant or an engine mutation tool.
 await expect(f.app.request({action:'preview-proposal',request_id:next.request_id})).rejects.toThrow('Proposal unavailable');expect(f.sent).toHaveLength(1);
});

it('only explicit exact visible excerpts of completed grounded replies can enter ordinary qualitative preview',async()=>{
 const preview=vi.fn<NonNullable<ConstructorParameters<typeof AssistantController>[8]>>(async()=>{throw new Error('stale original context');});
 const f=fixture({previewQualitative:preview});const initial=await first(f);
 await expect(f.app.request({action:'preview-qualitative',request_id:initial.request_id,proposal_text:'invented',domain_id:'domain:3'})).rejects.toThrow();expect(preview).not.toHaveBeenCalled();
 const child=await f.app.request({action:'continue',request_id:initial.request_id});await f.app.request({action:'send',request_id:child.request_id});const reply=await terminal(f.app,child.request_id);
 await expect(f.app.request({action:'preview-qualitative',request_id:reply.request_id,proposal_text:'private prompt canary',domain_id:'domain:3'})).rejects.toThrow();expect(preview).not.toHaveBeenCalled();
 await expect(f.app.request({action:'preview-qualitative',request_id:reply.request_id,proposal_text:'Grounded answer',domain_id:'domain:3'})).rejects.toThrow('stale original context');
 expect(preview).toHaveBeenCalledTimes(1);expect(preview.mock.calls[0][0]).toMatchObject({query:{context:f.ground.manifest.context,scope_id:'home',domain_id:'domain:3'},proposal:'Grounded answer',rationale:'',promotion:{source_request_id:initial.request_id,coverage:'unverified qualitative assistant excerpt'}});
 await f.app.request({action:'revoke',request_id:reply.request_id});await expect(f.app.request({action:'preview-qualitative',request_id:reply.request_id,proposal_text:'Grounded answer',domain_id:'domain:3'})).rejects.toThrow();expect(preview).toHaveBeenCalledTimes(1);
});

it('deletion during an ordinary qualitative preview revokes late grants without restoring private turn data',async()=>{
 let release!:(preview:Awaited<ReturnType<NonNullable<ConstructorParameters<typeof AssistantController>[8]>>>)=>void;
 const preview=vi.fn<NonNullable<ConstructorParameters<typeof AssistantController>[8]>>(()=>new Promise(resolve=>{release=resolve;}));
 const cancel=vi.fn(async()=>{}),f=fixture({previewQualitative:preview,cancelPreview:cancel});
 const initial=await first(f),child=await f.app.request({action:'continue',request_id:initial.request_id});await f.app.request({action:'send',request_id:child.request_id});await terminal(f.app,child.request_id);
 const pending=f.app.request({action:'preview-qualitative',request_id:child.request_id,proposal_text:'Grounded answer',domain_id:'domain:3'});
 await vi.waitFor(()=>expect(preview).toHaveBeenCalledTimes(1));
 await f.app.request({action:'delete',request_id:initial.request_id});
 release({interview_contract:1,query:{context:f.ground.manifest.context,scope_id:'home',domain_id:'domain:3'},candidate_digest:'sha256:'+'b'.repeat(64),affected_scope_ids:['home'],changed_value_ids:[],coverage:'qualitative',findings:[],dependencies:[],accounts:[],alternatives:['player:proposal'],selected_id:'player:proposal',before:[],after:[]});
 await expect(pending).rejects.toThrow('Revoked');expect(cancel).toHaveBeenCalledWith('interview','sha256:'+'b'.repeat(64));
 expect((await f.app.request({action:'workspace',request_id:'workspace'})).turns).toEqual([]);
});
it('deleting a root turn cancels a completed descendant preview while preserving public history authority',async()=>{
 const cancel=vi.fn(async()=>{});
 const f=fixture({cancelPreview:cancel,previewQualitative:async edit=>({interview_contract:1,query:edit.query,candidate_digest:'sha256:'+'c'.repeat(64),affected_scope_ids:['home'],changed_value_ids:[],coverage:'qualitative',findings:[],dependencies:[],accounts:[],alternatives:['player:proposal'],selected_id:'player:proposal',before:[],after:[]})});
 const initial=await first(f),child=await f.app.request({action:'continue',request_id:initial.request_id});await f.app.request({action:'send',request_id:child.request_id});await terminal(f.app,child.request_id);
 const staged=await f.app.request({action:'preview-qualitative',request_id:child.request_id,proposal_text:'Grounded answer',domain_id:'domain:3'});expect(staged.qualitative_text).toBe('Grounded answer');
 const deleted=await f.app.request({action:'delete',request_id:initial.request_id});expect(cancel).toHaveBeenCalledWith('interview','sha256:'+'c'.repeat(64));expect(deleted.interview_preview).toBeNull();expect((await f.app.request({action:'workspace',request_id:'workspace'})).turns).toEqual([]);
});
