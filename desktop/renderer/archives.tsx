import React, { useState } from 'react';
import type { ArchiveOptions, ArchiveReply, ArchiveSummary } from '../../contracts/archive';
const defaults: ArchiveOptions = { include_private_notes: false, include_private_rationale: false, include_transcripts: false, include_attachments: false, evidence: 'complete' };
export function Archives() {
  const [options, setOptions] = useState(defaults);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [summaries, setSummaries] = useState<ArchiveSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [offset, setOffset] = useState(0), [detail, setDetail] = useState(0);
  const [page, setPage] = useState<ArchiveReply>();
  async function report(format: 'markdown' | 'csv', archive_id: string | null = null) {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await window.poliscope.report({ format, options, archive_id, scope_id: null });
      setNotice(result.status === 'cancelled' ? 'File selection cancelled.' : `${format === 'markdown' ? 'Inquiry report' : 'Typed CSV'} exported. ${result.bytes_written} bytes. Private material follows your selected choices.`);
    } catch { setError('Report export failed. Saved history is retained. Choose a new file; an uncertain export may already exist.'); }
    finally { setBusy(false); }
  }
  async function act(action: 'export' | 'import' | 'list' | 'read', id = selected, item = offset, part = detail) {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await window.poliscope.archive({ action, options, archive_id: id, offset: item, detail_offset: part });
      if (result.status === 'cancelled') { setNotice('File selection cancelled.'); return; }
      if (action === 'read') { setPage(result); setSelected(id); setOffset(item); setDetail(part); }
      else {
        if (action === 'export') setNotice('Portable history exported. Private material follows your selected choices.');
        if (action === 'import') setNotice('Portable history imported for historical inspection. Saved worlds are unchanged.');
        if (action !== 'export') setSummaries(result.summaries);
      }
    } catch { setError('Archive request failed. Saved history is retained. Use a new file for export; imported histories can be reopened after an uncertain reply.'); }
    finally { setBusy(false); }
  }
  return <section aria-label="Portable archives">
    <h3>Portable history</h3>
    <p>Export all civilizations, original alternatives, branches and experiment history from the selected folder. Results and calculation traces are included by default. Keys, key blobs, caches and private indexes are always excluded.</p>
    <p>Imported histories open for stored historical inspection. Privacy projections use new identities; edits require an explicit compatible migration. No imported model code runs.</p>
    <fieldset disabled={busy}><legend>Export privacy and evidence</legend>
      <label><input type="checkbox" checked={options.include_private_notes} onChange={e => setOptions({ ...options, include_private_notes: e.target.checked })} />Include active private notes from all revisions</label>
      <label><input type="checkbox" checked={options.include_private_rationale} onChange={e => setOptions({ ...options, include_private_rationale: e.target.checked })} />Include active private rationale</label>
      <p>Transcripts and attachments are excluded. This version has no transcript or attachment store to export. Public simulation inputs, goal questions, sources and assumptions remain included. Private source metadata and private identifiers are redacted throughout history.</p>
      <label>Retained evidence <select value={options.evidence} onChange={e => setOptions({ ...options, evidence: e.target.value as ArchiveOptions['evidence'] })}><option value="complete">Include saved results and traces</option><option value="reduced">Evidence-reduced: omit measurement reports and traces</option></select></label>
      {options.evidence === 'reduced' && <p>Every omitted measurement report is listed in the archive. Transition records remain included; omitted measurement results and calculation traces are unavailable.</p>}
      <p>Inquiry reports and CSV cover all retained revisions and experiments in this folder. CSV includes exact measurements, declared distributions and saved time series. Markdown includes private notes and rationale only when selected above. CSV contains measurements and state without private note payloads. Missing results remain unavailable; no AI explanation is generated.</p>
      <p>CSV text cells have one leading apostrophe for spreadsheet safety. Remove exactly one to decode text; numeric values retain their exact decimal strings. Compare only compatible units, scopes, times and models.</p>
      <button onClick={() => void report('markdown')}>Export Markdown inquiry report</button>
      <button onClick={() => void report('csv')}>Export typed CSV</button>
      <button onClick={() => void act('export', null)}>Export portable history</button>
      <button onClick={() => void act('import')}>Import portable history</button>
      <button onClick={() => void act('list')}>Show imported histories</button>
    </fieldset>
    {busy && <p role="status">Preparing local export or historical data…</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    <ul>{summaries.map(x => <li key={x.id}>
      <span>{x.revisions} revisions, {x.branches} branches, {x.experiments} experiments. Evidence: {x.evidence}. Stored historical; execution: {x.execution === 'unavailable' ? 'unavailable' : 'requires explicit migration'}. Redacted: {x.redactions.join(', ')}.</span>
      <button disabled={busy} onClick={() => void act('read', x.id, 0, 0)}>Inspect imported history</button>
    </li>)}</ul>
    {page && <section aria-label="Imported historical data"><h4>{page.heading}</h4>
      <p>Retained historical data, not freshly reproduced. Text is displayed as data.</p>
      <button disabled={busy} onClick={() => void act('export', selected)}>Export this imported history</button>
      <button disabled={busy} onClick={() => void report('markdown', selected)}>Export imported inquiry report</button>
      <button disabled={busy} onClick={() => void report('csv', selected)}>Export imported typed CSV</button>
      <table><caption>Stored facts and evidence</caption><thead><tr><th scope="col">Fact</th><th scope="col">Retained value</th></tr></thead><tbody>{(page.rows ?? []).map((row,i) => <tr key={i}><th scope="row">{row.label}</th><td style={{ overflowWrap: 'anywhere', whiteSpace: 'pre-wrap' }}>{row.detail}</td></tr>)}</tbody></table>
      <button disabled={busy || detail === 0} onClick={() => void act('read', selected, offset, Math.max(0, detail-25))}>Previous facts</button>
      <button disabled={busy || page.next_detail_offset == null} onClick={() => void act('read', selected, offset, page.next_detail_offset!)}>More facts</button>
      <button disabled={busy || offset === 0} onClick={() => void act('read', selected, offset-1, 0)}>Previous history entry</button>
      <button disabled={busy || page.next_offset == null} onClick={() => void act('read', selected, page.next_offset!, 0)}>Next history entry</button>
    </section>}
  </section>;
}
