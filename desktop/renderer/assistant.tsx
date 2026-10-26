import type { Attachment } from '../../contracts/assistant';
import React, { useEffect, useState } from 'react';
import type { ProviderView } from '../../contracts/provider';
import type { GroundingSelection } from '../../contracts/grounding';
import type { AssistantReply } from '../../contracts/assistant';
const active=(reply?:AssistantReply)=>reply&&['pending','streaming'].includes(reply.status);
const diagnostic={none:'',authentication:'Authentication failed. Check the saved key.',credits:'Provider credits required.', 'rate-limit':'Provider rate limit. Wait before deliberately retrying.',model:'Model unavailable. Review the saved model.',provider:'Provider rejected the request.',network:'Connection failed or timed out. Acceptance and charges may be uncertain.', 'invalid-response':'Malformed or incomplete provider response.',budget:'Spending reservation denied or unavailable. Existing exposure still counts.',sharing:'Sharing approval revoked.',configuration:'Profile, capability, tokenizer, context or key unavailable. Refresh metadata and review saved settings.',redirect:'Provider redirect blocked.'};
export function Assistant({view,disabled,onApplied}:{view?:ProviderView;disabled:boolean;onApplied?:()=>void}) {
  const [files,setFiles]=useState<Attachment[]>([]),[consent,setConsent]=useState(false),[output,setOutput]=useState<'text'|'image'|'audio'>('text');
  const [text,setText]=useState(''),[stream,setStream]=useState(true),[exposure,setExposure]=useState('0.01'),[turn,setTurn]=useState('0.01'),[session,setSession]=useState('0.10'),[profile,setProfile]=useState('1');
  const [grounded,setGrounded]=useState(false),[scope,setScope]=useState('home'),[task,setTask]=useState('Explain the selected design'),[tools,setTools]=useState(false);
  const [collections,setCollections]=useState<GroundingSelection['collections']>(['facts']);
  const [proposalApplied,setProposalApplied]=useState(false);
  const [reply,setReply]=useState<AssistantReply>(),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=> {
    if(!active(reply))return;
    let stopped=false,pending=false;
    const id=reply!.request_id;
    const timer=setInterval(()=> {
      if(pending)return;pending=true;
      void window.poliscope.assistant({action:'status',request_id:id}).then(next=>{if(!stopped)setReply(current=>current?.request_id===id?next:current);setProposalApplied(false);}).catch(()=>{if(!stopped)setError('Request status unavailable. Do not assume that sending or charging failed.');}).finally(()=>{pending=false;});
    },250);
    return ()=>{stopped=true;clearInterval(timer);};
  },[reply?.request_id,reply?.status]);
  async function prepare() {
    if(!view)return;setBusy(true);setError('');
    try {setReply(await window.poliscope.assistant({action:'prepare',profile_id:view.profile.id,expected_revision:view.revision,text,stream,attachments:consent?files:[],output,exposure,turn_limit:turn,session_limit:session,profile_limit:profile,...(grounded?{grounding:{scope_id:scope,task,collections,tools}}:{})}));setFiles([]);setConsent(false);}
    catch {setError('Cannot prepare: save a model, set an output limit and refresh supported capabilities. Check the attachment format, selected modality and model against the support limits shown above. Unknown tokenizers and generic compatible catalog capabilities remain blocked.');}
    finally{setBusy(false);}
  }
  async function action(action:'send'|'cancel'|'revoke'|'continue'|'preview-proposal'|'delete'|'save-artifact',proposal_index=0) {
    if(!reply)return;setBusy(true);setError('');const id=reply.request_id;
    try {const next=await window.poliscope.assistant({action,request_id:id,proposal_index,artifact_index:Math.min(proposal_index,1)});setReply(current=>current?.request_id===id?next:current);setProposalApplied(false);if(action==='delete'){setFiles([]);setConsent(false);setText('');setReply(undefined);}}
    catch {setError(action==='continue'?'Cannot continue: the original model, pinned provider, context, limits and completed tool history must remain compatible. Start a new request when translation is unavailable.':action==='save-artifact'?'Artifact not saved. Choose a new file; existing files are protected.':action==='delete'?'Deletion was not confirmed. Retry deletion; do not assume provider exposure was erased.':'Request outcome uncertain. Check status before any deliberate retry.');}
    finally{setBusy(false);}
  }
  return <section aria-label="Optional text assistance"><h3>Optional text assistance</h3>
    <p>Review exactly what will be shared before each send. Grounded context is optional and limited to selected public collections in one immutable revision and scope. Private notes, rationale and other branches are excluded. Attachments require explicit inclusion. Provider text is untrusted and cannot apply changes.</p>
    <p>Supported GPT byte-BPE catalog metadata and a saved output limit are required. Other tokenizer bounds remain unknown. No live provider is tested automatically.</p>
    <fieldset disabled={busy||Boolean(active(reply))}><legend>Review a new request</legend>
      <label><input type="checkbox" checked={grounded} onChange={e=>setGrounded(e.target.checked)}/>Include grounded context from the selected revision</label>
      {grounded&&<fieldset><legend>Explicit context selection</legend>
        <label>Context scope ID<input maxLength={128} value={scope} onChange={e=>setScope(e.target.value)}/></label>
        <label>Context task<input maxLength={256} value={task} onChange={e=>setTask(e.target.value)}/></label>
        {(['facts','choices','accounts','traces','sources','assumptions'] as const).map(c=><label key={c}><input type="checkbox" checked={collections.includes(c)} onChange={e=>setCollections(v=>e.target.checked?[...v,c]:v.filter(x=>x!==c))}/>Share {c}</label>)}
        <label><input type="checkbox" checked={tools} onChange={e=>setTools(e.target.checked)}/>Offer bounded read-only tools</label>
        <p>No-tool models can explain the supplied manifest. Tool support must be verified by provider metadata. Tools inspect only approved entries; at most 3 continuation rounds and 8 calls per turn. Each continuation requires exact-payload review and a new spending grant.</p>
      </fieldset>}
      <fieldset><legend>Session attachments and output</legend>
        <p>Up to four files, 64 KiB total. Plain UTF-8 text: local excerpt up to 8,192 characters. PNG: at most 512 × 512, low detail, supported GPT-4o models only. WAV: canonical mono PCM16 at 16kHz on supported OpenAI audio models. MP4 video and PDF remote processing are blocked while trusted context accounting is unavailable. SVG, HTML and other active formats are rejected. No automatic URL fetch or media decoding occurs.</p>
        <label>Choose attachments<input type="file" multiple accept=".txt,.png,.wav,.mp4,.pdf" onChange={e=>{const selected=Array.from(e.target.files??[]);e.target.value='';setFiles([]);setConsent(false);setError('');if(selected.length>4||selected.reduce((n,f)=>n+f.size,0)>65536){setError('Choose at most four files totalling 64 KiB.');return;}setBusy(true);void Promise.all(selected.map(async file=>{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);const mime=file.type==='audio/x-wav'?'audio/wav':file.type;return{name:file.name,mime,data_base64:btoa(binary),processing:mime==='text/plain'?'local-excerpt':'provider',provenance:'Explicit local file selection: '+file.name,classification:'private',consent:'this-turn',retention:'session'} as Attachment;})).then(setFiles).catch(()=>setError('Attachment read failed.')).finally(()=>setBusy(false));}}/></label>
        <ul>{files.map((f,i)=><li key={i}>{f.name} · {f.mime} · {f.processing} · private · session only</li>)}</ul>
        <label><input type="checkbox" checked={consent} disabled={!files.length} onChange={e=>setConsent(e.target.checked)}/>Include these attachments and their excerpts in this turn and its reviewed continuations</label>
        <button type="button" onClick={()=>{setFiles([]);setConsent(false);}}>Clear selected attachments</button>
        <label>Requested output<select aria-label="Requested output" value={output} onChange={e=>{const value=e.target.value as 'text'|'image'|'audio';setOutput(value);if(value==='audio')setStream(true);}}><option value="text">Text</option><option value="image" disabled>Image generation unavailable (dedicated API required)</option><option value="audio">Text and streamed WAV artifact</option></select></label>
        <p>Attachment turns cannot combine with proposal tools. Audio output needs verified model capabilities, requires streaming, and cannot combine with tools. Image generation uses a separate unsupported API and is unavailable here. Artifacts are untrusted private session data. Only metadata is rendered; saving is an explicit action. Saved external copies belong to you and are outside session deletion. Video/file output renderers are unavailable.</p>
        <p>A new request always starts fresh history. Profile/model changes never forward prior private reasoning or attachments. Existing tool continuations require their exact original profile, model and endpoint; start a new request when incompatible.</p>
      </fieldset>
      <label>Text to share<textarea maxLength={8192} value={text} onChange={e=>setText(e.target.value)}/></label>
      <label><input type="checkbox" disabled={output==='audio'} checked={stream} onChange={e=>setStream(e.target.checked)}/>Stream response</label>
      <p>Explicit bounded exposure in USD reserves unknown costs. Local limits cannot cap upstream charges; use provider account limits. Completed, cancelled and uncertain requests retain exposure until reconciliation is available. Reconciliation is not yet offered.</p>
      {([['Request exposure',exposure,setExposure],['Turn spending limit',turn,setTurn],['Session spending limit',session,setSession],['Profile spending limit',profile,setProfile]] as const).map(([label,value,set])=><label key={label}>{label}<input maxLength={15} inputMode="decimal" value={value} onChange={e=>set(e.target.value)}/></label>)}
      <p>Session and profile limits stay fixed after their first reservation. Restarting creates a new session; profile exposure persists.</p>
      <button disabled={disabled||!view||!text||(files.length>0&&!consent)} onClick={()=>void prepare()}>{reply?'Review a deliberate new request':'Review request'}</button>
    </fieldset>
    {error&&<p role="alert">{error}</p>}
    {reply&&<><p role="status">Request {reply.request_id}: {reply.status}. Exposure {reply.exposure} USD ({reply.exposure_status}). {diagnostic[reply.diagnostic ?? 'none']}</p>
      <details open={reply.status==='prepared'}><summary>Exact sharing manifest and original context</summary><pre>{reply.context_json}</pre><pre>{reply.sharing_json}</pre><pre>{reply.payload_json}</pre><p>Only this complete payload may be sent to the saved endpoint. A changed request needs new review and approval.</p></details>
      {reply.attachments_json&&reply.attachments_json!=='[]'&&<details><summary>Attachment ownership and exact inclusion</summary><pre>{reply.attachments_json}</pre></details>}
      {reply.artifacts_json&&reply.artifacts_json!=='[]'&&<section aria-label="Untrusted provider artifacts"><p>Private session artifacts. No rendering, decoding, autoplay or network fetch.</p>{(JSON.parse(reply.artifacts_json) as {mime:string;size:number;sha256:string}[]).map((a,i)=><div key={i}><p>{a.mime} · {a.size} bytes · SHA-256 {a.sha256}</p><button disabled={busy} onClick={()=>void action('save-artifact',i)}>Save artifact {i+1} to a new file</button></div>)}</section>}
      {reply.grounding_json&&<details><summary>Approved grounded entries and coverage</summary><pre>{reply.grounding_json}</pre></details>}
      {reply.status==='tool-calls'&&<button disabled={busy||disabled||(reply.round??0)>=3} onClick={()=>void action('continue')}>Inspect approved tool calls and review continuation</button>}
      {reply.status==='prepared'&&<button disabled={busy||disabled} onClick={()=>void action('send')}>Approve sharing and send once</button>}
      {['prepared','pending','streaming'].includes(reply.status)&&<button disabled={busy} onClick={()=>void action('cancel')}>Cancel request</button>}
      <pre aria-label="Assistant response">{reply.text}</pre>
      {reply.reasoning&&<details><summary>Provider reasoning text (unverified, separate from simulation facts)</summary><pre>{reply.reasoning}</pre></details>}
      {reply.tools_json!=='[]'&&<details><summary>Complete provider tool calls (untrusted)</summary><pre>{reply.tools_json}</pre></details>}
      {reply.proposals_json&&reply.proposals_json!=='[]'&&<><details open><summary>AI proposals · coverage retained</summary><pre>{reply.proposals_json}</pre></details>{(JSON.parse(reply.proposals_json) as unknown[]).map((_,i)=><button key={i} disabled={busy||disabled||proposalApplied||Boolean(reply.proposal_preview)} onClick={()=>void action('preview-proposal',i)}>Open proposal {i+1} in ordinary evidence preview</button>)}</>}
      {reply.proposal_preview&&<section aria-label="Evidence edit preview"><p>{reply.proposal_preview.disclosure}</p><pre>{JSON.stringify(reply.proposal_preview.edit,null,2)}</pre><p>{reply.proposal_preview.changed_observations} changed observations. This is a noncommitting ordinary parameter preview.</p>
        <button disabled={busy||disabled||proposalApplied} onClick={()=>{setBusy(true);void window.poliscope.applyWorkbench({candidate_digest:reply.proposal_preview!.candidate_digest}).then(result=>{if(result.status==='applied'){setProposalApplied(true);onApplied?.();}else setError('Proposal is stale. Reopen the current revision and prepare a new grounded request.');}).catch(()=>setError('Apply unavailable or uncertain. Retry the same ordinary Apply; do not assume a commit failed.')).finally(()=>setBusy(false));}}>Apply evidence edit</button>
        <button disabled={busy||proposalApplied} onClick={()=>{void window.poliscope.cancelWorkbench().then(()=>setReply(r=>r?{...r,proposal_preview:null}:r));}}>Cancel evidence edit</button>
        {proposalApplied&&<p role="status">Proposal applied through ordinary player approval. Origin and coverage are retained. Reopen the civilization to inspect its new revision.</p>}
      </section>}
      <button disabled={busy} onClick={()=>void action('delete')}>Delete this turn, attachments and all active derivatives</button>
      <button disabled={busy} onClick={()=>void action('revoke')}>Revoke this turn and later sharing</button>
      {reply.usage_json&&<details><summary>Provider-reported usage observation</summary><pre>{reply.usage_json}</pre></details>}
      {reply.result&&<p>Selected model: {reply.result.selected_model}; reported model: {reply.result.actual_model??'unknown'}; reported provider: {reply.result.actual_provider??'unknown'}; finish: {reply.result.finish_reason??'unknown'}.</p>}
      <p>Retrying requires reviewing and approving a new request and may create another charge. Partial or cancelled output is never a completed answer.</p>
    </>}
  </section>;
}
