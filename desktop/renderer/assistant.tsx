import React, { useEffect, useState } from 'react';
import type { ProviderView } from '../../contracts/provider';
import type { AssistantReply } from '../../contracts/assistant';
const active=(reply?:AssistantReply)=>reply&&['pending','streaming'].includes(reply.status);
const diagnostic={none:'',authentication:'Authentication failed. Check the saved key.',credits:'Provider credits required.', 'rate-limit':'Provider rate limit. Wait before deliberately retrying.',model:'Model unavailable. Review the saved model.',provider:'Provider rejected the request.',network:'Connection failed or timed out. Acceptance and charges may be uncertain.', 'invalid-response':'Malformed or incomplete provider response.',budget:'Spending reservation denied or unavailable. Existing exposure still counts.',sharing:'Sharing approval revoked.',configuration:'Profile, capability, tokenizer, context or key unavailable. Refresh metadata and review saved settings.',redirect:'Provider redirect blocked.'};
export function Assistant({view,disabled}:{view?:ProviderView;disabled:boolean}) {
  const [text,setText]=useState(''),[stream,setStream]=useState(true),[exposure,setExposure]=useState('0.01'),[turn,setTurn]=useState('0.01'),[session,setSession]=useState('0.10'),[profile,setProfile]=useState('1');
  const [reply,setReply]=useState<AssistantReply>(),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=> {
    if(!active(reply))return;
    let stopped=false,pending=false;
    const id=reply!.request_id;
    const timer=setInterval(()=> {
      if(pending)return;pending=true;
      void window.poliscope.assistant({action:'status',request_id:id}).then(next=>{if(!stopped)setReply(current=>current?.request_id===id?next:current);}).catch(()=>{if(!stopped)setError('Request status unavailable. Do not assume that sending or charging failed.');}).finally(()=>{pending=false;});
    },250);
    return ()=>{stopped=true;clearInterval(timer);};
  },[reply?.request_id,reply?.status]);
  async function prepare() {
    if(!view)return;setBusy(true);setError('');
    try {setReply(await window.poliscope.assistant({action:'prepare',profile_id:view.profile.id,expected_revision:view.revision,text,stream,exposure,turn_limit:turn,session_limit:session,profile_limit:profile}));}
    catch {setError('Cannot prepare: save a model, set an output limit and refresh supported capabilities. Unknown tokenizers and generic compatible catalog capabilities remain blocked.');}
    finally{setBusy(false);}
  }
  async function action(action:'send'|'cancel'|'revoke') {
    if(!reply)return;setBusy(true);setError('');const id=reply.request_id;
    try {const next=await window.poliscope.assistant({action,request_id:id});setReply(current=>current?.request_id===id?next:current);}
    catch {setError('Request outcome uncertain. Check status before any deliberate retry.');}
    finally{setBusy(false);}
  }
  return <section aria-label="Optional text assistance"><h3>Optional text assistance</h3>
    <p>Only text you enter here is shared. No world data, private notes, attachments or earlier replies are added. Replies cannot change the society. Tools are displayed for inspection and are never executed here.</p>
    <p>Supported GPT byte-BPE catalog metadata and a saved output limit are required. Other tokenizer bounds remain unknown. No live provider is tested automatically.</p>
    <fieldset disabled={busy||Boolean(active(reply))}><legend>Review a new request</legend>
      <label>Text to share<textarea maxLength={8192} value={text} onChange={e=>setText(e.target.value)}/></label>
      <label><input type="checkbox" checked={stream} onChange={e=>setStream(e.target.checked)}/>Stream response</label>
      <p>Explicit bounded exposure in USD reserves unknown costs. Local limits cannot cap upstream charges; use provider account limits. Completed, cancelled and uncertain requests retain exposure until reconciliation is available. Reconciliation is not yet offered.</p>
      {([['Request exposure',exposure,setExposure],['Turn spending limit',turn,setTurn],['Session spending limit',session,setSession],['Profile spending limit',profile,setProfile]] as const).map(([label,value,set])=><label key={label}>{label}<input maxLength={15} inputMode="decimal" value={value} onChange={e=>set(e.target.value)}/></label>)}
      <p>Session and profile limits stay fixed after their first reservation. Restarting creates a new session; profile exposure persists.</p>
      <button disabled={disabled||!view||!text} onClick={()=>void prepare()}>{reply?'Review a deliberate new request':'Review request'}</button>
    </fieldset>
    {error&&<p role="alert">{error}</p>}
    {reply&&<><p role="status">Request {reply.request_id}: {reply.status}. Exposure {reply.exposure} USD ({reply.exposure_status}). {diagnostic[reply.diagnostic ?? 'none']}</p>
      <details open={reply.status==='prepared'}><summary>Exact sharing manifest and original context</summary><pre>{reply.context_json}</pre><pre>{reply.sharing_json}</pre><pre>{reply.payload_json}</pre><p>Only this complete payload may be sent to the saved endpoint. A changed request needs new review and approval.</p></details>
      {reply.status==='prepared'&&<button disabled={busy||disabled} onClick={()=>void action('send')}>Approve sharing and send once</button>}
      {['prepared','pending','streaming'].includes(reply.status)&&<button disabled={busy} onClick={()=>void action('cancel')}>Cancel request</button>}
      <pre aria-label="Assistant response">{reply.text}</pre>
      {reply.reasoning&&<details><summary>Provider reasoning text</summary><pre>{reply.reasoning}</pre></details>}
      {reply.tools_json!=='[]'&&<details><summary>Tool calls (not executed)</summary><pre>{reply.tools_json}</pre></details>}
      {reply.usage_json&&<details><summary>Provider-reported usage observation</summary><pre>{reply.usage_json}</pre></details>}
      {reply.result&&<p>Selected model: {reply.result.selected_model}; reported model: {reply.result.actual_model??'unknown'}; reported provider: {reply.result.actual_provider??'unknown'}; finish: {reply.result.finish_reason??'unknown'}.</p>}
      <p>Retrying requires reviewing and approving a new request and may create another charge. Partial or cancelled output is never a completed answer.</p>
    </>}
  </section>;
}
