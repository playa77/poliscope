/** Bounded incremental SSE and chat assembly. No dispatch, logging or tool execution. */
import type { BuiltRequest } from './provider-requests';
import { validateStructured } from './provider-schema';
import { normalizeGenerationResponse } from './provider-requests';
import type { GenerationResult } from '../../contracts/generation';
export class ProviderStreamError extends Error {
  constructor(readonly diagnostic:'authentication'|'credits'|'rate-limit'|'model'|'provider'){super('Provider stream rejected');}
}
export class StreamError extends Error { constructor() { super('Malformed or incomplete provider stream'); } }
export function usageObservation(value: unknown): string {
  const input=record(value), result:Record<string,unknown>={};
  for(const key of ['prompt_tokens','completion_tokens','total_tokens','input_tokens','output_tokens']) {
    if(input[key]!=null) {if(!Number.isSafeInteger(input[key]) || (input[key] as number)<0)throw new StreamError();result[key]=input[key];}
  }
  for(const key of ['prompt_tokens_details','completion_tokens_details']) if(input[key]!=null) {
    const detail=record(input[key]), safe:Record<string,number>={};
    for(const field of ['cached_tokens','cache_write_tokens','reasoning_tokens','audio_tokens','video_tokens','image_tokens','accepted_prediction_tokens','rejected_prediction_tokens']) if(detail[field]!=null) {
      if(!Number.isSafeInteger(detail[field]) || (detail[field] as number)<0)throw new StreamError();safe[field]=detail[field] as number;
    }
    result[key]=safe;
  }
  if(input.cost!=null) {if(typeof input.cost!=='number'||!Number.isFinite(input.cost)||input.cost<0)throw new StreamError();result.cost_observation=String(input.cost);}
  return JSON.stringify(result);
}
const record = (v: unknown): Record<string, unknown> => {
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw new StreamError();
  return v as Record<string, unknown>;
};
export interface AssembledTool { index: number; id: string; name: string; arguments: string }
export interface StreamSnapshot {
  text: string; reasoning: string; tools: AssembledTool[]; usage_json: string | null;
  model: string | null; provider: string | null; finish_reason: string | null;
}
export class ChatStream {
  private decoder = new TextDecoder('utf-8', {fatal:true});
  private line = ''; private data: string[] = []; private cr = false;
  private bytes = 0; private events = 0; private ended = false; private finished = false;
  private state: StreamSnapshot = {text:'',reasoning:'',tools:[],usage_json:null,model:null,provider:null,finish_reason:null};
  private tools = new Map<number, AssembledTool>();
  private refusal = false;
  constructor(private request: BuiltRequest) {}
  snapshot(): StreamSnapshot { return structuredClone({...this.state,tools:[...this.tools.values()].sort((a,b)=>a.index-b.index)}); }
  push(bytes: Uint8Array) {
    if (this.finished || (this.bytes += bytes.length) > 2_097_152) throw new StreamError();
    let text: string;
    try { text = this.decoder.decode(bytes,{stream:true}); } catch { throw new StreamError(); }
    this.consume(text);
  }
  private consume(text: string) {
    for (const char of text) {
      if (this.cr) { this.cr = false; if (char === '\n') continue; }
      if (char === '\r' || char === '\n') { this.flushLine(); this.cr = char === '\r'; }
      else { this.line += char; if (this.line.length > 262144) throw new StreamError(); }
    }
  }
  private flushLine() {
    const line = this.line; this.line = '';
    if (!line) {
      if (this.data.length) { const data=this.data.join('\n'); this.data=[]; this.event(data); }
      return;
    }
    if (line.startsWith(':')) return;
    const colon=line.indexOf(':'), name=colon<0?line:line.slice(0,colon);
    let value=colon<0?'':line.slice(colon+1); if (value.startsWith(' ')) value=value.slice(1);
    if (name === 'data') { this.data.push(value); if (this.data.reduce((n,s)=>n+s.length,0)>262144) throw new StreamError(); }
  }
  private event(data: string) {
    if (this.ended || ++this.events>16384) throw new StreamError();
    if (data === '[DONE]') { this.ended=true; return; }
    let body: Record<string,unknown>;
    try { body=record(JSON.parse(data)); } catch { throw new StreamError(); }
    if(body.error!=null) {
      const error=record(body.error), code=error.code;
      throw new ProviderStreamError(code===401||code===403?'authentication':code===402?'credits':code===429?'rate-limit':code===404?'model':'provider');
    }
    for (const key of ['model','provider'] as const) if (body[key] != null) {
      const value=body[key];
      if (typeof value !== 'string' || !value || value.length>256 || /[\u0000-\u001f\u007f]|\p{Surrogate}/u.test(value)) throw new StreamError();
      if (key==='model' && !this.request.allowed_models.includes(value)) throw new StreamError();
      if (this.state[key] !== null && this.state[key] !== value) throw new StreamError();
      this.state[key]=value;
    }
    if (body.usage != null) {
      this.state.usage_json=usageObservation(body.usage);
    }
    if (!Array.isArray(body.choices) || body.choices.length>1) throw new StreamError();
    if (!body.choices.length) { if (body.usage == null) throw new StreamError(); return; }
    const choice=record(body.choices[0]); if (choice.index !== 0) throw new StreamError();
    const delta=record(choice.delta);
    // Current OpenRouter usage accounting repeats a terminal finish_reason
    // with an empty content/role delta. It is not another completion event.
    if(this.state.finish_reason!==null && body.usage!=null) {
      if(choice.finish_reason!==this.state.finish_reason || Object.entries(delta).some(([k,v])=>!((k==='content'&&(v===''||v===null))||(k==='role'&&v==='assistant'))))throw new StreamError();
      return;
    }
    const append=(key:'content'|'reasoning',target:'text'|'reasoning')=> {
      if (delta[key] == null) return;
      if (this.state.finish_reason !== null || typeof delta[key] !== 'string' || /\p{Surrogate}/u.test(delta[key])) throw new StreamError();
      this.state[target]+=delta[key]; if (this.state[target].length>1048576) throw new StreamError();
    };
    append('content','text'); append('reasoning','reasoning');
    if(delta.reasoning_details!=null) {
      if(!Array.isArray(delta.reasoning_details)||delta.reasoning_details.length>128)throw new StreamError();
      for(const item of delta.reasoning_details) {
        const detail=record(item);
        // Opaque encrypted continuation payloads stay out of visible reasoning.
        const text=detail.type==='reasoning.text'?detail.text:detail.type==='reasoning.summary'?detail.summary:null;
        if(text!=null && delta.reasoning==null) {
          if(typeof text!=='string'||this.state.finish_reason!==null||/\p{Surrogate}/u.test(text))throw new StreamError();
          this.state.reasoning+=text;if(this.state.reasoning.length>1048576)throw new StreamError();
        }
      }
    }
    if (delta.refusal != null) this.refusal=true;
    if (delta.tool_calls != null) {
      if (this.state.finish_reason !== null || !Array.isArray(delta.tool_calls) || delta.tool_calls.length>32) throw new StreamError();
      for (const fragment of delta.tool_calls) {
        const call=record(fragment), index=call.index;
        if (!Number.isSafeInteger(index) || (index as number)<0 || (index as number)>31) throw new StreamError();
        const tool=this.tools.get(index as number) ?? {index:index as number,id:'',name:'',arguments:''};
        if (call.type != null && call.type !== 'function') throw new StreamError();
        if (call.id != null) {
          if (typeof call.id !== 'string' || !call.id || (tool.id && tool.id!==call.id)) throw new StreamError();
          tool.id=call.id;
        }
        if (call.function != null) {
          const fn=record(call.function);
          for (const [key,target] of [['name','name'],['arguments','arguments']] as const) if (fn[key] != null) {
            if (typeof fn[key] !== 'string' || /\p{Surrogate}/u.test(fn[key])) throw new StreamError();
            tool[target]+=fn[key];
          }
        }
        if (tool.id.length>256 || tool.name.length>64 || tool.arguments.length>32768) throw new StreamError();
        this.tools.set(tool.index,tool);
      }
    }
    if (choice.finish_reason != null) {
      if (this.state.finish_reason !== null || typeof choice.finish_reason!=='string' || choice.finish_reason.length>256) throw new StreamError();
      this.state.finish_reason=choice.finish_reason;
    }
  }
  end(): {snapshot:StreamSnapshot; result:GenerationResult} {
    if (this.finished) throw new StreamError(); this.finished=true;
    try { this.consume(this.decoder.decode()); } catch { throw new StreamError(); }
    // SSE requires a blank line terminating the final event; EOF is not [DONE].
    if (this.line || this.data.length || !this.ended || !this.state.finish_reason) throw new StreamError();
    if (this.tools.size && this.state.finish_reason!=='tool_calls') throw new StreamError();
    if (this.state.finish_reason==='tool_calls') {
      if (!this.tools.size || this.tools.size>32) throw new StreamError();
      const ids=new Set<string>();
      for (const tool of this.tools.values()) {
        if (!tool.id || ids.has(tool.id) || !(this.request.plan.tools ?? []).some(t=>t.name===tool.name)) throw new StreamError();
        ids.add(tool.id);
        try { record(JSON.parse(tool.arguments)); validateStructured(tool.arguments,(this.request.plan.tools ?? []).find(t=>t.name===tool.name)!.parameters_json); } catch { throw new StreamError(); }
      }
    }
    const result=normalizeGenerationResponse(this.request,{model:this.state.model,provider:this.state.provider,choices:[{finish_reason:this.state.finish_reason,message:{content:this.state.text,...(this.refusal?{refusal:true}:{})}}]});
    return {snapshot:this.snapshot(),result};
  }
}

/** Use the same structural checks for whole JSON responses and assembled SSE. */
export function wholeResponse(request:BuiltRequest,value:unknown):{snapshot:StreamSnapshot;result:GenerationResult} {
  const body=record(value);
  if(body.error!=null||!Array.isArray(body.choices)||body.choices.length!==1)throw new StreamError();
  const choice=record(body.choices[0]), message=record(choice.message);
  if(choice.index!==0)throw new StreamError();
  const delta={...message};
  if(delta.tool_calls!=null) {
    if(!Array.isArray(delta.tool_calls))throw new StreamError();
    delta.tool_calls=delta.tool_calls.map((call,index)=>({...record(call),index}));
  }
  const parser=new ChatStream(request);
  const event={model:body.model,provider:body.provider,choices:[{index:0,delta,finish_reason:choice.finish_reason}]};
  const wire='data: '+JSON.stringify(event)+'\n\n'+(body.usage!=null?'data: '+JSON.stringify({choices:[],usage:body.usage})+'\n\n':'')+'data: [DONE]\n\n';
  parser.push(Buffer.from(wire));return parser.end();
}
