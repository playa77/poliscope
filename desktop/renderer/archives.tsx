import React, { useState } from 'react';
import { Archive } from 'lucide-react';
import type { ArchiveOptions, ArchiveReply, ArchiveSummary } from '../../contracts/archive';
import { Button } from '@/components/ui/button';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, CheckField, DataTable, Field, Hint, SubHeading } from '@/components/app/form';
import { EmptyState, ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

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
  return <section aria-label="Portable archives" className="flex flex-col gap-4">
    <Panel title="Portable history" description="Export all civilizations, original alternatives, branches and experiment history from the selected folder. Results and calculation traces are included by default. Keys, key blobs, caches and private indexes are always excluded."
      action={<StateBadge tone="neutral"><Archive aria-hidden />Local files</StateBadge>}>
      <Hint>Imported histories open for stored historical inspection. Privacy projections use new identities; edits require an explicit compatible migration. No imported model code runs.</Hint>
      <fieldset disabled={busy} className="m-0 mt-3 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Export privacy and evidence</legend>
        <div className="flex flex-col gap-2">
          <CheckField checked={Boolean(options.include_private_notes)} onChange={checked => setOptions({ ...options, include_private_notes: checked })}>Include active private notes from all revisions</CheckField>
          <CheckField checked={Boolean(options.include_private_rationale)} onChange={checked => setOptions({ ...options, include_private_rationale: checked })}>Include active private rationale</CheckField>
        </div>
        <Hint className="mt-2">Transcripts and attachments are excluded. This version has no transcript or attachment store to export. Public simulation inputs, goal questions, sources and assumptions remain included. Private source metadata and private identifiers are redacted throughout history.</Hint>
        <Field label="Retained evidence" className="mt-3 w-72">
          <NativeSelect value={options.evidence} onChange={e => setOptions({ ...options, evidence: e.target.value as ArchiveOptions['evidence'] })}>
            <option value="complete">Include saved results and traces</option><option value="reduced">Evidence-reduced: omit measurement reports and traces</option>
          </NativeSelect>
        </Field>
        {options.evidence === 'reduced' && <Hint className="mt-2">Every omitted measurement report is listed in the archive. Transition records remain included; omitted measurement results and calculation traces are unavailable.</Hint>}
        <Hint className="mt-3">Inquiry reports and CSV cover all retained revisions and experiments in this folder. CSV includes exact measurements, declared distributions and saved time series. Markdown includes private notes and rationale only when selected above. CSV contains measurements and state without private note payloads. Missing results remain unavailable; no AI explanation is generated.</Hint>
        <Hint className="mt-1">CSV text cells have one leading apostrophe for spreadsheet safety. Remove exactly one to decode text; numeric values retain their exact decimal strings. Compare only compatible units, scopes, times and models.</Hint>
        <Actions className="mt-3">
          <Button onClick={() => void report('markdown')}>Export Markdown inquiry report</Button>
          <Button variant="outline" onClick={() => void report('csv')}>Export typed CSV</Button>
          <Button variant="outline" onClick={() => void act('export', null)}>Export portable history</Button>
          <Button variant="outline" onClick={() => void act('import')}>Import portable history</Button>
          <Button variant="ghost" onClick={() => void act('list')}>Show imported histories</Button>
        </Actions>
      </fieldset>
    </Panel>

    <Panel title="Local export state" description="One status at a time: the current action, its file, and any failure that left saved history intact.">
      {busy && <p role="status" className="text-sm text-muted-foreground">Preparing local export or historical data…</p>}
      {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
      {error && <ErrorNote>{error}</ErrorNote>}
      {!busy && !notice && !error && <Hint>No export has run in this session. Files are written only after you choose a destination.</Hint>}
    </Panel>

    {summaries.length > 0 && <Panel title="Imported histories" description="Stored historical data, not freshly reproduced. Execution compatibility is a separate decision from safe readability.">
      <ul className="flex flex-col gap-2">{summaries.map(x => <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-muted/40 p-3">
        <span className="min-w-0 text-xs leading-relaxed text-muted-foreground">
          {x.revisions} revisions, {x.branches} branches, {x.experiments} experiments. Evidence: {x.evidence}. Stored historical; execution: {x.execution === 'unavailable' ? 'unavailable' : 'requires explicit migration'}. Redacted: {x.redactions.join(', ')}.
        </span>
        <Button variant="outline" size="sm" disabled={busy} onClick={() => void act('read', x.id, 0, 0)}>Inspect imported history</Button>
      </li>)}</ul>
    </Panel>}

    {page && <Panel label="Imported historical data" title={page.heading} description="Retained historical data, not freshly reproduced. Text is displayed as data.">
      <Actions className="mb-3">
        <Button variant="outline" size="sm" disabled={busy} onClick={() => void act('export', selected)}>Export this imported history</Button>
        <Button variant="outline" size="sm" disabled={busy} onClick={() => void report('markdown', selected)}>Export imported inquiry report</Button>
        <Button variant="outline" size="sm" disabled={busy} onClick={() => void report('csv', selected)}>Export imported typed CSV</Button>
      </Actions>
      <DataTable>
        <caption>Stored facts and evidence</caption>
        <thead><tr><th scope="col">Fact</th><th scope="col">Retained value</th></tr></thead>
        <tbody>{(page.rows ?? []).map((row,i) => <tr key={i}><th scope="row">{row.label}</th><td className="whitespace-pre-wrap break-words">{row.detail}</td></tr>)}</tbody>
      </DataTable>
      <Actions className="mt-3">
        <Button variant="outline" size="sm" disabled={busy || detail === 0} onClick={() => void act('read', selected, offset, Math.max(0, detail-25))}>Previous facts</Button>
        <Button variant="outline" size="sm" disabled={busy || page.next_detail_offset == null} onClick={() => void act('read', selected, offset, page.next_detail_offset!)}>More facts</Button>
        <Button variant="ghost" size="sm" disabled={busy || offset === 0} onClick={() => void act('read', selected, offset-1, 0)}>Previous history entry</Button>
        <Button variant="ghost" size="sm" disabled={busy || page.next_offset == null} onClick={() => void act('read', selected, page.next_offset!, 0)}>Next history entry</Button>
      </Actions>
    </Panel>}
    {!page && summaries.length === 0 && <Panel title="No imported history open" description="Nothing from another folder is loaded. Import a portable archive to inspect its stored facts.">
      <EmptyState icon={Archive} title="No imported history in this session" description="Archives are ordinary files. Opening one reads stored facts only; no imported model code runs and saved worlds are unchanged." />
    </Panel>}
  </section>;
}
