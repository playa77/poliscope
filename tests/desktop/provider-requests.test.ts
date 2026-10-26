import { it, expect } from 'vitest';
import { buildGenerationRequest, contextPayloadHash, normalizeGenerationResponse, RequestError, type RequestEvidence } from '../../desktop/main/provider-requests';
import { openRouterAdapter } from '../../desktop/main/provider-adapters';
import { parseSchema, validateStructured } from '../../desktop/main/provider-schema';
import type { ProviderView } from '../../contracts/provider';
import type { GenerationPlan } from '../../contracts/generation';
const time = '2026-10-26T12:00:00Z', now = Date.parse(time);
const schema = JSON.stringify({type:'object',properties:{quantity:{type:'integer',minimum:0},unit:{type:'string',enum:['kg']}},required:['quantity','unit'],additionalProperties:false});
function fixture() {
  const view: ProviderView = {revision:3,key_status:'missing',profile:{id:'request',name:'Synthetic',kind:'openrouter',endpoint:'https://openrouter.ai/api/v1',model:'future/model',generation:{temperature:'0.7',top_p:'0.9',max_output_tokens:128},routing:{order:[],only:[],ignore:[],allow_fallbacks:false,require_parameters:true,data_collection:'deny'},capabilities:{text:'unknown',image:'unknown',audio:'unknown',video:'unknown',tools:'unknown',structured_output:'unknown',reasoning:'unknown'}}};
  const plan: GenerationPlan = {generation_contract:1,profile_id:'request',expected_revision:3,messages:[{role:'user',content:'Return the supplied fictional quantity.'}],stream:false,response_format:{type:'text'}};
  const models = openRouterAdapter.models({data:[{id:'future/model',architecture:{input_modalities:['text'],output_modalities:['text']},context_length:1024,top_provider:{max_completion_tokens:256},supported_parameters:['temperature','top_p','max_tokens','frequency_penalty','presence_penalty','seed','stop','tools','tool_choice','response_format','structured_outputs','reasoning'],reasoning:{supported_efforts:['low','high','none'],supports_max_tokens:true}}]},time);
  const evidence: RequestEvidence = {profile_id:'request',revision:3,endpoint:view.profile.endpoint,models,budgets:[]};
  const bind = () => { evidence.budgets = evidence.models.map(m => ({model_id:m.id,input_tokens_upper_bound:100,payload_sha256:contextPayloadHash(plan),source:'tokenizer'})); };
  const build = () => buildGenerationRequest(view,plan,evidence,now);
  bind(); return {view,plan,evidence,bind,build};
}
const completion = (content: string, extra: Record<string,unknown> = {}) => ({model:'future/model',provider:'Synthetic provider',choices:[{finish_reason:'stop',message:{role:'assistant',content}}],...extra});
function error(run: () => unknown, code: string, parameter?: string) {
  try { run(); throw new Error('Expected request rejection'); }
  catch(e) { expect(e).toBeInstanceOf(RequestError); expect((e as RequestError).code).toBe(code); if(parameter) expect((e as RequestError).parameter).toBe(parameter); }
}
it('constructs documented literal OpenRouter requests without inventing defaults, headers, keys or routes', () => {
  const f = fixture(), request = f.build();
  expect(request.path).toBe('/chat/completions'); expect(request.method).toBe('POST');
  expect(JSON.parse(request.json)).toEqual({model:'future/model',messages:[{role:'user',content:'Return the supplied fictional quantity.'}],stream:false,temperature:0.7,top_p:0.9,max_tokens:128,provider:{order:[],only:[],ignore:[],allow_fallbacks:false,require_parameters:true,data_collection:'deny'}});
  expect(request.json).not.toMatch(/Authorization|endpoint|key_status|capabilities|expected_revision/);
  f.view.profile.generation.temperature = '1.8'; f.plan.messages[0].content = 'mutated';
  expect(request.plan.messages[0].content).toBe('Return the supplied fictional quantity.'); expect(Object.isFrozen(request.plan.messages)).toBe(true);
});
it('preserves all explicit routing, privacy and price choices with correct price units and streamed output', () => {
  const f = fixture(); f.plan.stream = true;
  Object.assign(f.view.profile.routing,{order:['provider-a'],only:['provider-a','provider-b'],ignore:['provider-c'],allow_fallbacks:true,zdr:true,max_price:{prompt:'1.25',completion:'0',request:'0.01',image:'0.5'}}); f.bind();
  expect(JSON.parse(f.build().json).provider).toEqual({order:['provider-a'],only:['provider-a','provider-b'],ignore:['provider-c'],allow_fallbacks:true,require_parameters:true,data_collection:'deny',zdr:true,max_price:{prompt:1.25,completion:0,request:0.01,image:0.5}});
  expect(JSON.parse(f.build().json).stream).toBe(true);
  f.view.profile.routing.order=[]; f.view.profile.routing.sort='latency'; expect(JSON.parse(f.build().json).provider.sort).toBe('latency');
});
it('model fallback is an explicit ordered list independent of provider fallback; all candidates revalidate', () => {
  const f = fixture(); f.view.profile.routing.allow_fallbacks = true;
  expect(JSON.parse(f.build().json).models).toBeUndefined();
  f.view.profile.routing.model_fallbacks=['future/second']; f.evidence.models.push({...f.evidence.models[0],id:'future/second'}); f.bind();
  expect(JSON.parse(f.build().json).models).toEqual(['future/model','future/second']); expect(JSON.parse(f.build().json).model).toBeUndefined();
  const reply = normalizeGenerationResponse(f.build(),completion('ok',{model:'future/second'}));
  expect(reply.status).toBe('complete'); expect(reply.selected_model).toBe('future/model'); expect(reply.actual_model).toBe('future/second'); expect(reply.actual_provider).toBe('Synthetic provider');
  f.evidence.models[1].supported_parameters=[]; error(f.build,'unsupported-control','temperature');
});
it.each(['unknown','unsupported'] as const)('unverified profile preferences cannot override %s model capabilities', support => {
  const f=fixture(); f.view.profile.capabilities.text='supported'; f.evidence.models[0].capabilities.text=support;
  error(f.build,'capability-unknown','text');
});
it.each(['temperature','top_p','max_tokens'] as const)('rejects selected unsupported %s without dropping it', key => {
  const f=fixture(); f.evidence.models[0].supported_parameters = f.evidence.models[0].supported_parameters!.filter(v=>v!==key); error(f.build,'unsupported-control',key);
});
it.each([['temperature','2.1'],['top_p','0'],['top_p','1.1'],['frequency_penalty','-2.1'],['presence_penalty','3']] as const)('checks the documented %s range (%s)', (key,value) => {
  const f=fixture(); f.view.profile.generation[key]=value; error(f.build,'invalid-control',key);
});
it('emits optional sampling controls literally and leaves unset defaults absent', () => {
  const f=fixture(); Object.assign(f.view.profile.generation,{temperature:null,top_p:null,frequency_penalty:'-1.5',presence_penalty:'0.5',seed:0,stop:['END']});
  const body=JSON.parse(f.build().json); expect(body).toMatchObject({frequency_penalty:-1.5,presence_penalty:0.5,seed:0,stop:['END']}); expect(body.temperature).toBeUndefined(); expect(body.top_p).toBeUndefined();
});
it('cannot weaken parameter/privacy enforcement or resolve contradictory routes silently', () => {
  const f=fixture(); f.view.profile.routing.require_parameters=false; error(f.build,'parameter-enforcement-required');
  f.view.profile.routing.require_parameters=true; f.view.profile.routing.only=['one']; f.view.profile.routing.ignore=['one']; error(f.build,'invalid-control','provider');
  f.view.profile.routing.ignore=[]; f.view.profile.routing.order=['two']; error(f.build,'invalid-control','provider');
  f.view.profile.routing.order=[]; f.view.profile.routing.max_price={prompt:'-0.1'}; error(f.build,'invalid-control','max_price');
});
it('binds profile, endpoint, revision and payload budgets; stale evidence and unknown limits block', () => {
  const f=fixture(); f.evidence.endpoint='https://sink.example'; error(f.build,'stale-profile'); f.evidence.endpoint=f.view.profile.endpoint;
  f.plan.expected_revision=2; error(f.build,'stale-profile'); f.plan.expected_revision=3;
  f.plan.messages[0].content='changed after counting'; error(f.build,'context-unknown'); f.bind();
  f.evidence.models[0].observed_at='2026-10-24T00:00:00Z'; error(f.build,'stale-metadata');
  f.evidence.models[0].observed_at='2026-10-27T00:00:00Z'; error(f.build,'stale-metadata');
  f.evidence.models[0].observed_at=time; f.evidence.models[0].context_length=null; error(f.build,'context-unknown');
});
it('enforces both context plus output and completion limits with independent literal boundaries', () => {
  const f=fixture(); f.evidence.budgets[0].input_tokens_upper_bound=896; expect(f.build()).toBeDefined();
  f.evidence.budgets[0].input_tokens_upper_bound=897; error(f.build,'context-exceeded');
  f.evidence.budgets[0].input_tokens_upper_bound=1; f.view.profile.generation.max_output_tokens=257; error(f.build,'context-exceeded');
  f.view.profile.generation.max_output_tokens=null; error(f.build,'context-unknown');
});
it('rejects removed, missing, duplicate fallback models and absent directional metadata', () => {
  const f=fixture(); f.evidence.models[0].available=false; error(f.build,'model-unavailable');
  f.evidence.models[0].available=true; f.view.profile.routing.model_fallbacks=['absent']; error(f.build,'model-unavailable');
  f.view.profile.routing.model_fallbacks=['future/model']; error(f.build,'invalid-control');
  f.view.profile.routing.model_fallbacks=[]; f.evidence.models[0].output_modalities=null; error(f.build,'capability-unknown','text');
});
it('encodes schema output and tools in documented wire format after local schema checks', () => {
  const f=fixture(); f.plan.response_format={type:'json_schema',name:'quantity',schema_text:schema};
  f.plan.tools=[{name:'inspect',description:'Read supplied synthetic data',parameters_json:schema}]; f.plan.tool_choice='inspect'; f.bind();
  const body=JSON.parse(f.build().json);
  expect(body.response_format).toEqual({type:'json_schema',json_schema:{name:'quantity',strict:true,schema:JSON.parse(schema)}});
  expect(body.tools).toEqual([{type:'function',function:{name:'inspect',description:'Read supplied synthetic data',parameters:JSON.parse(schema),strict:true}}]);
  expect(body.tool_choice).toEqual({type:'function',function:{name:'inspect'}});
  const reply=normalizeGenerationResponse(f.build(),completion('{"quantity":3,"unit":"kg"}'));
  expect(reply.status).toBe('complete'); expect(reply.validated_json).toBe('{"quantity":3,"unit":"kg"}');
});
it('revalidates reasoning options, budget, mandatory status and model-specific effort evidence', () => {
  const f=fixture(); f.view.profile.generation.reasoning={effort:'high',exclude:true};
  expect(JSON.parse(f.build().json).reasoning).toEqual({effort:'high',exclude:true});
  f.view.profile.generation.reasoning={max_tokens:64,enabled:true}; expect(JSON.parse(f.build().json).reasoning).toEqual({max_tokens:64,enabled:true});
  f.view.profile.generation.reasoning={max_tokens:128}; error(f.build,'invalid-control','reasoning');
  f.view.profile.generation.reasoning={effort:'minimal'}; error(f.build,'unsupported-control','reasoning');
  f.view.profile.generation.reasoning={effort:'none'}; f.evidence.models[0].raw_json=JSON.stringify({reasoning:{mandatory:true,supported_efforts:['none']}}); error(f.build,'unsupported-control','reasoning');
});
it('generic compatible bodies contain no OpenRouter controls and require separate declared evidence', () => {
  const f=fixture(); f.view.profile.kind='openai-compatible'; f.view.profile.endpoint='https://compatible.example/v1'; f.evidence.endpoint=f.view.profile.endpoint;
  f.view.profile.routing.data_collection='unknown'; f.evidence.models[0].supported_parameters!.push('max_completion_tokens');
  error(f.build,'capability-unknown'); f.evidence.models[0].source='declared:synthetic-compatible';
  const body=JSON.parse(f.build().json); expect(body).toEqual({model:'future/model',messages:f.plan.messages,stream:false,temperature:0.7,top_p:0.9,max_completion_tokens:128});
  f.view.profile.routing.data_collection='deny'; error(f.build,'unsupported-control','provider');
  f.view.profile.routing.data_collection='unknown'; f.view.profile.routing.zdr=true; error(f.build,'unsupported-control','provider');
});
it.each(['{"quantity":"3","unit":"kg"}','{"quantity":-1,"unit":"kg"}','{"quantity":3,"unit":"lb"}','{"quantity":3}','{"quantity":3,"unit":"kg","apply":true}','null','```json\n{}\n```','{"quantity":3'])('never promotes invalid schema output %s', text => {
  const f=fixture(); f.plan.response_format={type:'json_schema',name:'quantity',schema_text:schema}; f.bind();
  const reply=normalizeGenerationResponse(f.build(),completion(text)); expect(reply.status).toBe('structured-invalid'); expect(reply.validated_json).toBeNull(); expect(reply.text).toBeNull();
});
it.each(['length','content_filter','tool_calls','future_finish',null])('nonfinal finish %s cannot produce validated JSON', reason => {
  const f=fixture(); f.plan.response_format={type:'json_object'}; f.bind();
  const reply=normalizeGenerationResponse(f.build(),{choices:[{finish_reason:reason,message:{content:'{}'}}]}); expect(reply.status).toBe('incomplete'); expect(reply.validated_json).toBeNull();
});
it('refusals, unexpected model changes, missing identities and provider errors remain explicit and safe', () => {
  const f=fixture(), request=f.build();
  expect(normalizeGenerationResponse(request,{choices:[{finish_reason:'stop',message:{content:'{}',refusal:'private canary'}}]}).status).toBe('refused');
  expect(normalizeGenerationResponse(request,completion('ok',{model:'unexpected/fallback'})).status).toBe('response-invalid');
  const absent=normalizeGenerationResponse(request,completion('ok',{model:undefined,provider:undefined})); expect(absent.actual_model).toBeNull(); expect(absent.actual_provider).toBeNull();
  const rejection=normalizeGenerationResponse(request,{error:{param:'temperature',message:'SECRET',metadata:{raw_error:'SECRET'}}},400);
  expect(rejection.status).toBe('unsupported-parameter'); expect(rejection.parameter).toBe('temperature'); expect(JSON.stringify(rejection)).not.toContain('SECRET');
  expect(normalizeGenerationResponse(request,{error:{param:'SECRET',message:'SECRET'}},500).parameter).toBeNull();
});
it.each(['{"type":"object","$ref":"https://sink.example"}','{"type":"string","pattern":"(a+)+$"}','{"type":"object","properties":{},"required":[],"additionalProperties":true}','{"type":"array"}','{"type":"string","minLength":2,"maxLength":1}'])('rejects unsupported or unsound schemas before request construction: %s', text => {
  expect(()=>parseSchema(text)).toThrow();
  const f=fixture(); f.plan.response_format={type:'json_schema',name:'bad',schema_text:text}; f.bind(); expect(f.build).toThrow();
});
it('local schema dialect handles nested arrays, alternatives, null, Unicode and hostile object keys', () => {
  const nested=JSON.stringify({type:'object',properties:{items:{type:'array',maxItems:2,items:{anyOf:[{type:'null'},{type:'string',minLength:1,maxLength:1}]}}},required:['items'],additionalProperties:false});
  expect(validateStructured('{"items":[null,"😀"]}',nested)).toBe('{"items":[null,"😀"]}');
  for(const text of ['{"items":["two"]}','{"items":[],"__proto__":{}}','{"items":[null,null,null]}']) expect(()=>validateStructured(text,nested)).toThrow();
  expect(()=>validateStructured('1e999')).toThrow(); expect(()=>validateStructured('"\\ud800"')).toThrow();
});
it('refuses price ceilings that cannot round-trip without changing the selected decimal', () => {
  const f=fixture(); f.view.profile.routing.max_price={prompt:'123456789.123456789'}; error(f.build,'invalid-control','max_price');
});
it('empty JSON-object mode, stale provider evidence, unknown controls and unsound tool selection fail explicitly', () => {
  const f=fixture(); f.plan.response_format={type:'json_object'}; f.bind();
  expect(normalizeGenerationResponse(f.build(),completion('[]')).status).toBe('structured-invalid');
  f.evidence.endpoints=[{model_id:'future/model',observed_at:'2026-10-20T00:00:00Z',source:'synthetic',providers:[],raw_json:'{}'}]; error(f.build,'stale-metadata');
  f.evidence.endpoints=[]; f.plan.tool_choice='unregistered'; f.bind(); error(f.build,'invalid-control','tool_choice');
  f.plan.tool_choice='auto'; (f.view.profile.generation as Record<string,unknown>).future_control=true; error(f.build,'invalid-plan');
});
it('compatible reasoning emits only the documented scalar and checks declared effort values', () => {
  const f=fixture(); f.view.profile.kind='openai-compatible'; f.view.profile.endpoint='https://compatible.example/v1'; f.evidence.endpoint=f.view.profile.endpoint; f.view.profile.routing.data_collection='unknown';
  f.evidence.models[0].source='declared:synthetic-compatible'; f.evidence.models[0].supported_parameters!.push('max_completion_tokens','reasoning_effort');
  f.view.profile.generation.reasoning={effort:'high'};
  expect(JSON.parse(f.build().json).reasoning_effort).toBe('high'); expect(JSON.parse(f.build().json).reasoning).toBeUndefined();
  f.view.profile.generation.reasoning={effort:'max'}; error(f.build,'unsupported-control','reasoning');
  f.evidence.models[0].raw_json=JSON.stringify({reasoning:{supported_efforts:['max']}});
  expect(JSON.parse(f.build().json).reasoning_effort).toBe('max');
  f.view.profile.generation.reasoning={effort:'max',exclude:true}; error(f.build,'unsupported-control','reasoning');
});
it('preserves small price ceilings when the wire uses equivalent scientific notation', () => {
  const f=fixture(); f.view.profile.routing.max_price={request:'0.000000001',completion:'0001.2500'};
  expect(JSON.parse(f.build().json).provider.max_price).toEqual({request:1e-9,completion:1.25});
});
it('retains catalog estimate inputs without doing authoritative money arithmetic in TypeScript',()=>{
 const f=fixture();f.evidence.models[0].pricing={prompt:'0.000001',completion:'0.000002',request:'0.01'};
 expect(f.build().catalog).toEqual({input_bound:100,output_bound:128,prompt_rate:'0.000001',completion_rate:'0.000002',request_rate:'0.01',source:f.evidence.models[0].source,observed_at:time});
 delete f.evidence.models[0].pricing.request;expect(f.build().catalog).toBeUndefined();
 f.evidence.models[0].pricing.request='0.01';f.evidence.models[0].pricing.image='0.1';expect(f.build().catalog).toBeUndefined();
 f.evidence.models[0].pricing={prompt:'-1',completion:'0'};expect(f.build().catalog).toBeUndefined();
});
