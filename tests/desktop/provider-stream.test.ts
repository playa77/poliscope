import { describe,it,expect } from 'vitest';
import { ChatStream } from '../../desktop/main/provider-stream';
import type { BuiltRequest } from '../../desktop/main/provider-requests';
export const request:BuiltRequest={profile_id:'p',revision:1,endpoint:'https://openrouter.ai/api/v1',path:'/chat/completions',method:'POST',json:'{}',selected_model:'m',allowed_models:['m'],plan:{generation_contract:1,profile_id:'p',expected_revision:1,messages:[{role:'user',content:'hello'}],stream:true,response_format:{type:'text'},tools:[{name:'inspect',description:'',parameters_json:'{"type":"object","properties":{"x":{"type":"integer"}},"required":[],"additionalProperties":false}' }]}};
const event=(value:unknown)=>`data: ${JSON.stringify(value)}\n\n`;
const delta=(value:unknown,finish:string|null=null)=>({model:'m',provider:'provider',choices:[{index:0,delta:value,finish_reason:finish}]});
const fixture=Buffer.from(': comment\r\n\r\n'+event(delta({role:'assistant',content:'hi 🌍'})).replaceAll('\n','\r\n')+event(delta({reasoning:'visible'}))+event(delta({},'stop'))+event({choices:[],usage:{prompt_tokens:3,completion_tokens:2,total_tokens:5}})+'data: [DONE]\n\n');
describe('bounded SSE assembly',()=> {
  it('every byte boundary, mixed line endings and split UTF8 preserve independent expected content',()=> {
    for(let split=0;split<=fixture.length;split++) {
      const parser=new ChatStream(request);parser.push(fixture.subarray(0,split));parser.push(fixture.subarray(split));
      const output=parser.end();expect(output.snapshot.text).toBe('hi 🌍');expect(output.snapshot.reasoning).toBe('visible');expect(output.result.status).toBe('complete');expect(JSON.parse(output.snapshot.usage_json!)).toEqual({prompt_tokens:3,completion_tokens:2,total_tokens:5});
    }
  });
  it('one-byte delivery assembles interleaved parallel tool fragments without executing them',()=> {
    const bytes=Buffer.from(event(delta({tool_calls:[{index:1,id:'two',type:'function',function:{name:'in',arguments:'{"x":'}},{index:0,id:'one',type:'function',function:{name:'inspect',arguments:'{}'}}]}))+event(delta({tool_calls:[{index:1,function:{name:'spect',arguments:'2}'}}]}))+event(delta({},'tool_calls'))+'data: [DONE]\n\n');
    const parser=new ChatStream(request);for(const byte of bytes)parser.push(Buffer.from([byte]));
    const output=parser.end();expect(output.snapshot.tools).toEqual([{index:0,id:'one',name:'inspect',arguments:'{}'},{index:1,id:'two',name:'inspect',arguments:'{"x":2}'}]);expect(output.result.status).toBe('incomplete');
  });
  it.each([
    event(delta({content:'partial'})),
    event(delta({content:'x'},'stop'))+'data: [DONE]',
    event(delta({content:'x'}))+'data: [DONE]\n\n',
    'data: {broken}\n\n',
    event({error:{message:'secret-canary'}}),
    event({model:'wrong',choices:[]}),
    event({choices:[{index:1,delta:{content:'other'}}]}),
    event(delta({},'stop'))+event(delta({content:'late'}))+'data: [DONE]\n\n',
    event(delta({tool_calls:[{index:0,id:'a',function:{name:'inspect',arguments:'{'}}]},'tool_calls'))+'data: [DONE]\n\n',
    event(delta({tool_calls:[{index:0,id:'a',function:{name:'unknown',arguments:'{}'}}]},'tool_calls'))+'data: [DONE]\n\n',
    event(delta({},'stop'))+'data: [DONE]\n\n'+event(delta({content:'late'})),
  ])('rejects malformed/incomplete/late stream %#',text=> {
    expect(()=>{const parser=new ChatStream(request);parser.push(Buffer.from(text));parser.end();}).toThrow();
  });
  it('accepts current documented OpenRouter terminal usage accounting shape',()=> {
    const parser=new ChatStream(request);
    parser.push(Buffer.from(event(delta({content:'answer'},'stop'))+event({...delta({content:'',role:'assistant'},'stop'),usage:{prompt_tokens:3,total_tokens:5,completion_tokens:2}})+'data: [DONE]\n\n'));
    expect(parser.end().result.text).toBe('answer');
  });
  it('rejects invalid UTF8 and bounded bytes',()=> {
    expect(()=>new ChatStream(request).push(Buffer.from([0xff]))).toThrow();
    expect(()=>new ChatStream(request).push(Buffer.alloc(2097153))).toThrow();
  });
  it('marks truncation/refusal explicitly',()=> {
    const parser=new ChatStream(request);parser.push(Buffer.from(event(delta({content:'partial'},'length'))+'data: [DONE]\n\n'));expect(parser.end().result.status).toBe('incomplete');
    const refused=new ChatStream(request);refused.push(Buffer.from(event(delta({refusal:'no'},'stop'))+'data: [DONE]\n\n'));expect(refused.end().result.status).toBe('refused');
  });
});

it('preserves precise decimal USD observations and rejects malformed prices',async()=> {
 const {costText,usageObservation}=await import('../../desktop/main/provider-stream');
 expect(costText(1e-7)).toBe('0.0000001');expect(costText('0.012345678901234567')).toBe('0.012345678901234567');
 expect(JSON.parse(usageObservation({cost:'0.012345678901234567'})).cost_observation).toBe('0.012345678901234567');
 for(const value of [-1,NaN,Infinity,'-1','USD 1',{},'0.0000000000000000001'])expect(()=>costText(value)).toThrow();
});
it('preserves only documented monetary JSON paths and leaves opaque nested metadata unchanged',async()=>{
 const {providerJson,costText}=await import('../../desktop/main/provider-stream');
 const value=providerJson('{"usage":{"cost":0.123456789012345678},"data":{"total_cost":1e-7},"text":"cost: 99","tokens":7,"choices":[{"delta":{"reasoning_details":[{"type":"reasoning.encrypted","cost":5}]}}]}') as {usage:{cost:string};data:{total_cost:string};text:string;tokens:number;choices:unknown};
 expect(value.usage.cost).toBe('0.123456789012345678');expect(costText(value.data.total_cost)).toBe('0.0000001');expect(value.tokens).toBe(7);expect(value.text).toBe('cost: 99');
 expect(value.choices).toEqual([{delta:{reasoning_details:[{type:'reasoning.encrypted',cost:5}]}}]);
 expect(providerJson('{"usage":{"co\\u0073t":0.000000000000000001}}')).toEqual({usage:{cost:'0.000000000000000001'}});
 for(const malformed of ['{"usage":{"cost":01}}','{"usage":{"cost":1x}}','{"text":"unterminated}'])expect(()=>providerJson(malformed)).toThrow();
});
