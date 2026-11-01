import { it,expect,vi } from 'vitest';
import { mkdtemp,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ProviderController } from '../../desktop/main/providers';
import type { ProviderProfile } from '../../contracts/provider';
import type { GenerationPlan } from '../../contracts/generation';
const profile:ProviderProfile={id:'p',name:'fixture',kind:'openrouter',endpoint:'https://openrouter.ai/api/v1',model:'m',generation:{max_output_tokens:128,temperature:null,top_p:null},routing:{order:[],only:[],ignore:[],allow_fallbacks:false,require_parameters:true,data_collection:'unknown'},capabilities:{text:'unknown',image:'unknown',audio:'unknown',video:'unknown',tools:'unknown',structured_output:'unknown',reasoning:'unknown'}};
const model={id:'m',architecture:{tokenizer:'GPT',input_modalities:['text'],output_modalities:['text']},context_length:8192,top_provider:{max_completion_tokens:1024},supported_parameters:['max_tokens']};
const plan:GenerationPlan={generation_contract:1,profile_id:'p',expected_revision:2,messages:[{role:'user',content:'One explicit text 🌍'}],stream:true,response_format:{type:'text'},tools:[]};
async function fixture(run:(c:ProviderController,metadata:ReturnType<typeof vi.fn>)=>Promise<void>){
 const dir=await mkdtemp(join(tmpdir(),'poliscope-generation-lease-')),metadata=vi.fn(async()=>({code:200,body:JSON.stringify({data:[model]})}));
 const c=new ProviderController(dir,{isEncryptionAvailable:()=>false,encryptString:()=>Buffer.alloc(0),decryptString:()=>''},async()=>200,process.platform,metadata);
 try{await c.request({action:'save',profile,expected_revision:null});await c.request({action:'replace-key',profile_id:'p',expected_revision:1,key:'synthetic-generation-key'});await c.request({action:'refresh-catalog',profile_id:'p',expected_revision:2});await run(c,metadata);}finally{await c.close();await rm(dir,{recursive:true,force:true});}
}
it('production preparation freezes the exact text request; profile changes cannot reuse it',()=>fixture(async c=>{
 const request=await c.prepareGeneration(plan);expect(Object.isFrozen(request)).toBe(true);expect(JSON.parse(request.json).messages).toEqual([{role:'user',content:'One explicit text 🌍'}]);expect(JSON.parse(request.json).max_tokens).toBe(128);
 await c.request({action:'save',profile:{...profile,name:'changed'},expected_revision:2});const send=vi.fn();await expect(c.dispatchGeneration(request,new AbortController().signal,send)).rejects.toThrow();expect(send).not.toHaveBeenCalled();
}));
it.each(['remove-key','delete','refresh-catalog','close'])('%s revokes a real generation credential lease',action=>fixture(async c=>{
 const request=await c.prepareGeneration(plan);let entered=false;
 const pending=c.dispatchGeneration(request,new AbortController().signal,async(key,signal)=>{expect(key).toBe('synthetic-generation-key');entered=true;await new Promise<void>((_resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('cancelled')),{once:true}));});
 const rejected=expect(pending).rejects.toThrow('cancelled');await vi.waitFor(()=>expect(entered).toBe(true));
 if(action==='close')await c.close();else await c.request({action,profile_id:'p',expected_revision:2});await rejected;
}));
it('unknown tokenizer and removed models cannot acquire a context bound; complete text history is counted',()=>fixture(async(c,metadata)=>{
 expect((await c.prepareGeneration({...plan,messages:[...plan.messages,...plan.messages]})).plan.messages).toHaveLength(2);
 await expect(c.prepareGeneration({...plan,messages:[{role:'user',content:'x'.repeat(8192)}]})).rejects.toThrow('context-exceeded');
 metadata.mockResolvedValue({code:200,body:JSON.stringify({data:[{...model,architecture:{...model.architecture,tokenizer:'Unknown'}}]})});await c.request({action:'refresh-catalog',profile_id:'p',expected_revision:2});await expect(c.prepareGeneration(plan)).rejects.toThrow('context-unknown');
 metadata.mockResolvedValue({code:200,body:JSON.stringify({data:[]})});await c.request({action:'refresh-catalog',profile_id:'p',expected_revision:2});await expect(c.prepareGeneration(plan)).rejects.toThrow('model-unavailable');
}));
it('retrieves only the original OpenRouter generation route with bounded allowlisted usage',()=>fixture(async(c,metadata)=>{
 const request=await c.prepareGeneration(plan);
 metadata.mockResolvedValue({code:200,body:JSON.stringify({data:{id:'gen_123',model:'m',total_cost:'0.001234567890123456',tokens_prompt:5,tokens_completion:7,native_tokens_reasoning:2,secret:'private-provider-field'}})});
 expect(await c.generationUsage(request,'gen_123')).toEqual({source:'generation-metadata',generation_id:'gen_123',actual_cost:'0.001234567890123456',actual_model:'m',normalized_input_tokens:5,normalized_output_tokens:7,reasoning_tokens:2});
 expect(metadata.mock.calls.at(-1)?.[0]).toBe('https://openrouter.ai/api/v1/generation?id=gen_123');
 for(const id of ['../models','other?secret=x','https://elsewhere.invalid'])await expect(c.generationUsage(request,id)).rejects.toThrow();
 metadata.mockResolvedValue({code:200,body:JSON.stringify({data:{id:'wrong',total_cost:0}})});await expect(c.generationUsage(request,'gen_123')).rejects.toThrow();
 metadata.mockResolvedValue({code:200,body:JSON.stringify({data:{id:'gen_123',total_cost:0,secret:'synthetic-generation-key'}})});await expect(c.generationUsage(request,'gen_123')).rejects.toThrow();
 await c.request({action:'remove-key',profile_id:'p',expected_revision:2});await expect(c.generationUsage(request,'gen_123')).rejects.toThrow();
}));

it.each(['deepseek/deepseek-v3.2','deepseek/deepseek-v4.1-flash-1017'])('admits reviewed %s text bounds including schema and rejects unknown tokenizers and media',id=>fixture(async(c,metadata)=>{
 const ds={...model,id,context_length:16384,architecture:{...model.architecture,tokenizer:'DeepSeek'},supported_parameters:['max_tokens','response_format','structured_outputs']};
 metadata.mockResolvedValue({code:200,body:JSON.stringify({data:[ds]})});
 await c.request({action:'save',profile:{...profile,model:id},expected_revision:2});
 await c.request({action:'refresh-catalog',profile_id:'p',expected_revision:3});
 const query={...plan,expected_revision:3,messages:[{role:'user' as const,content:'ASCII, 中文, 🌍, é, \uFDFA and literal <｜begin▁of▁sentence｜>'}]};
 expect((await c.prepareGeneration(query)).selected_model).toBe(id);
 expect((await c.prepareGeneration({...query,response_format:{type:'json_object'}})).plan.response_format.type).toBe('json_object');
 await expect(c.prepareGeneration({...query,response_format:{type:'json_schema',name:'test',schema_text:JSON.stringify({type:'object',additionalProperties:false,required:['answer'],properties:{answer:{type:'string',description:'x'.repeat(16384)}}})}})).rejects.toThrow('context-exceeded');
 await expect(c.prepareGeneration({...query,messages:[{role:'user',content:[{type:'image_url',image_url:{url:'data:image/png;base64,AAAA',detail:'low'}}]}]})).rejects.toThrow();
 metadata.mockResolvedValue({code:200,body:JSON.stringify({data:[{...ds,architecture:{...ds.architecture,tokenizer:'Unknown'}}]})});
 await c.request({action:'refresh-catalog',profile_id:'p',expected_revision:3});await expect(c.prepareGeneration(query)).rejects.toThrow('context-unknown');
}));

it('prepares the exact authorized V4.1 model from captured real metadata with bounded reasoning and strict output',()=>fixture(async(c,metadata)=>{
 const { default: current } = await import('../fixtures/providers/openrouter-live-catalog-2026-11-01.json');
 const id='deepseek/deepseek-v4.1-flash-1017';
 metadata.mockResolvedValue({code:200,body:JSON.stringify(current)});
 const selected={...profile,model:id,generation:{...profile.generation,max_output_tokens:1024,reasoning:{enabled:false}},routing:{...profile.routing,data_collection:'deny' as const,max_price:{prompt:'2',completion:'2',request:'0'}}};
 await c.request({action:'save',profile:selected,expected_revision:2});
 expect((await c.request({action:'refresh-catalog',profile_id:'p',expected_revision:3})).status).toBe('metadata-ready');
 const input={...plan,expected_revision:3};
 const text=await c.prepareGeneration(input);
 expect(JSON.parse(text.json)).toMatchObject({model:id,max_tokens:1024,reasoning:{enabled:false},provider:{allow_fallbacks:false,max_price:{prompt:'2',completion:'2',request:'0'}}});
 expect(text.catalog).toBeUndefined(); // Scheduled pricing is not a flat estimate.
 const schema=JSON.stringify({type:'object',properties:{status:{type:'string',enum:['READY']}},required:['status'],additionalProperties:false});
 expect((await c.prepareGeneration({...input,response_format:{type:'json_schema',name:'live_check',schema_text:schema}})).selected_model).toBe(id);
 await c.request({action:'save',profile:{...selected,generation:{...selected.generation,reasoning:{effort:'low'}}},expected_revision:3});
 expect(JSON.parse((await c.prepareGeneration({...input,expected_revision:4})).json).reasoning).toEqual({effort:'low'});
}));
