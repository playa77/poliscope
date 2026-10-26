import recoverySchema from '../../contracts/recovery.schema.json';
import reportSchema from '../../contracts/report.schema.json';
import type { ReportRequest, ReportReply } from '../../contracts/report';
import archiveSchema from '../../contracts/archive.schema.json';
import type { ArchiveRequest, ArchiveReply } from '../../contracts/archive';
import uncertaintySchema from '../../contracts/uncertainty.schema.json';
import type { UncertaintyQuery, UncertaintyReport, SensitivityQuery, SensitivityReport, CapacityQuery, CapacityReport } from '../../contracts/uncertainty';
import timelineSchema from '../../contracts/timeline-workspace.schema.json';
import type { TimelineRequest, TimelineReply } from '../../contracts/timeline-workspace';
import workbenchSchema from '../../contracts/workbench.schema.json';
import type { WorkbenchQuery, WorkbenchPage, WorkbenchEdit, WorkbenchPreview, DeleteNote, DeleteNoteReply } from '../../contracts/workbench';
import explorationSchema from '../../contracts/exploration.schema.json';
import type { ExplorationQuery, ExplorationPage, ExplorationEdit, ExplorationPreview } from '../../contracts/exploration';
import matrixSchema from '../../contracts/matrix.schema.json';
import type { MatrixQuery, MatrixPage, MatrixModelQuery, MatrixModelReply } from '../../contracts/matrix';
import atlasSchema from '../../contracts/atlas.schema.json';
import type { AtlasQuery, AtlasPage, AtlasSourceQuery, AtlasSourcePage } from '../../contracts/atlas';
/** Main-only launch and selection grants. Renderer never supplies a path or operation. */
import { isDeepStrictEqual } from 'node:util';
import { execFile } from 'node:child_process';
import { isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import { engineCommand } from './engine';
import { valid, type Schema } from './wire';
import schema from '../../contracts/workspace.schema.json';
import comparisonSchema from '../../contracts/comparison.schema.json';
import type { RationaleQuery, RationaleReply, LineageQuery, LineagePage, HistoryAction, CompareQuery, ComparePage } from '../../contracts/comparison';
import overviewSchema from '../../contracts/overview.schema.json';
import type { OverviewQuery, OverviewPage, TargetQuery, TargetReply, ChartQuery, ChartReply } from '../../contracts/overview';
import interviewSchema from '../../contracts/interview.schema.json';
import type { InterviewQuery, InterviewEdit, InterviewQuestion, InterviewPreview, InterviewApply, InterviewCommit } from '../../contracts/interview';
import type { CreateOptions, WorkspaceCatalogue, WorkspaceSelection, WorkspaceState, WorkspacePageRequest, WorkspacePage } from '../../contracts/workspace';
const defs = { ...recoverySchema.$defs, ...reportSchema.$defs, ...archiveSchema.$defs, ...schema.$defs, ...interviewSchema.$defs, ...overviewSchema.$defs, ...comparisonSchema.$defs, ...atlasSchema.$defs, ...matrixSchema.$defs, ...explorationSchema.$defs, ...workbenchSchema.$defs, ...timelineSchema.$defs, ...uncertaintySchema.$defs } as Record<string, Schema>;
export function workspaceValid(value: unknown, type: string): boolean { return valid(value, defs[type], defs); }
export function decodeWorkspace(frame: Buffer, type: string): unknown {
  if (frame.length > 1_048_576) throw new Error('Workspace response exceeds limit');
  const text = new TextDecoder('utf-8', { fatal: true }).decode(frame);
  if (!text.endsWith('\n') || text.slice(0, -1).includes('\n') || text.includes('\r')) throw new Error('Invalid workspace frame');
  const tokens = text.match(/"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g) ?? [];
  if (tokens.some(token => !token.startsWith('"') && (!/^-?\d+$/.test(token) || !Number.isSafeInteger(Number(token))))) throw new Error('Invalid workspace numeric token');
  const value: unknown = JSON.parse(text);
  if (!workspaceValid(value, type)) throw new Error('Invalid workspace response');
  return value;
}
export class WorkspaceController {
  private workbenchCandidate?: { edit: WorkbenchEdit; identity: string; preview: WorkbenchPreview; applying: boolean };
  private worldCandidate?: { edit: ExplorationEdit; identity: string; preview: ExplorationPreview; applying: boolean };
  private candidate?: { edit: InterviewEdit; identity: string; preview: InterviewPreview; applying: boolean };
  private pendingHistory?: { query: HistoryAction; identity: string };
  private directory?: string;
  private storeId?: string;
  get assistantContext(): string { return JSON.stringify(this.selected ? {kind:'design',context:this.selected.context,effective_time:this.selected.effective_time,sharing:'Only explicitly entered text; no automatic world data'} : {kind:'standalone',sharing:'Only explicitly entered text; no world selected'}); }
  get active(): boolean { return Boolean(this.directory && this.storeId); }
  private pendingCreate?: { input: string; identity: string };
  private selected?: WorkspaceState;
  private branches?: WorkspaceCatalogue['branches'];
  constructor(private packaged: boolean, private root: string, private resources: string) {}
  clear() { this.directory = undefined; this.storeId = undefined; this.selected = undefined; this.branches = undefined; this.pendingCreate = undefined; this.candidate = undefined; this.pendingHistory = undefined; this.worldCandidate = undefined; this.workbenchCandidate = undefined; }
  private async request(operation: string, input: unknown, type: string, identity = 'unused'): Promise<unknown> {
    if (!this.directory) throw new Error('Select a store first');
    const command = engineCommand(this.packaged, this.root, this.resources);
    const args = this.packaged ? ['--workspace'] : ['-I', '-m', 'poliscope_engine.workspace'];
    const frame = await new Promise<Buffer>((resolve, reject) => {
      const child = execFile(command.executable, [...args, '--directory', this.directory!, '--operation', operation, '--identity', identity], {
        shell: false, windowsHide: true, encoding: 'buffer', maxBuffer: 1_048_576, timeout: 15_000, killSignal: 'SIGKILL',
        env: Object.fromEntries(['SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'].flatMap(k => process.env[k] === undefined ? [] : [[k, process.env[k]!]])),
      }, (error, stdout) => error ? reject(new Error('Workspace request failed')) : resolve(stdout));
      child.stdin?.on('error', () => {});
      child.stdin?.end(JSON.stringify(input) + '\n');
    });
    return decodeWorkspace(frame, type);
  }
  async report(input: unknown, choose: (format: 'markdown' | 'csv') => Promise<string | undefined>): Promise<ReportReply> {
    if (!this.directory || !workspaceValid(input, 'ReportRequest')) throw new Error('Invalid report grant');
    if (this.candidate || this.worldCandidate || this.workbenchCandidate || this.pendingHistory || this.pendingCreate) throw new Error('Resolve draft or uncertain operation first');
    const query: ReportRequest = { options: { include_private_notes: false, include_private_rationale: false, include_transcripts: false, include_attachments: false, evidence: 'complete' }, archive_id: null, scope_id: null, ...structuredClone(input as ReportRequest) };
    const path = await choose(query.format);
    if (!path) return { report_schema: 1, status: 'cancelled', format: query.format, rows: 0, bytes_written: 0, projection_digest: null, redactions: [] };
    if (!isAbsolute(path)) throw new Error('Invalid dialog selection');
    const command = engineCommand(this.packaged, this.root, this.resources);
    const args = this.packaged ? ['--report'] : ['-I', '-m', 'poliscope_engine.report_host'];
    const frame = await new Promise<Buffer>((resolve, reject) => {
      const child = execFile(command.executable, [...args, '--directory', this.directory!, '--selected-file', path], {
        shell: false, windowsHide: true, encoding: 'buffer', maxBuffer: 1_048_576, timeout: 120_000, killSignal: 'SIGKILL',
        env: Object.fromEntries(['SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'].flatMap(k => process.env[k] === undefined ? [] : [[k, process.env[k]!]])),
      }, (error, stdout) => error ? reject(new Error('Report export failed; saved history retained')) : resolve(stdout));
      child.stdin?.on('error', () => {});
      child.stdin?.end(JSON.stringify(query) + '\n');
    });
    const reply = decodeWorkspace(frame, 'ReportReply') as ReportReply;
    if (reply.status !== 'complete' || reply.format !== query.format || !reply.projection_digest) throw new Error('Report response binding mismatch');
    return reply;
  }
  async archive(input: unknown, choose: (action: 'import' | 'export') => Promise<string | undefined>): Promise<ArchiveReply> {
    if (!this.directory || !workspaceValid(input, 'ArchiveRequest')) throw new Error('Invalid archive grant');
    if (this.candidate || this.worldCandidate || this.workbenchCandidate || this.pendingHistory || this.pendingCreate) throw new Error('Resolve draft or uncertain operation first');
    const query: ArchiveRequest = { options: { include_private_notes: false, include_private_rationale: false, include_transcripts: false, include_attachments: false, evidence: 'complete' }, archive_id: null, offset: 0, detail_offset: 0, ...structuredClone(input as ArchiveRequest) };
    if (query.action === 'read' && !query.archive_id) throw new Error('Select an imported archive');
    const path = query.action === 'export' || query.action === 'import' ? await choose(query.action) : undefined;
    if ((query.action === 'export' || query.action === 'import') && !path) return { status: 'cancelled', summaries: [], heading: '', rows: [], next_offset: null, next_detail_offset: null };
    if (path && !isAbsolute(path)) throw new Error('Invalid dialog selection');
    const command = engineCommand(this.packaged, this.root, this.resources);
    const args = this.packaged ? ['--archive'] : ['-I', '-m', 'poliscope_engine.archive_host'];
    const frame = await new Promise<Buffer>((resolve, reject) => {
      const child = execFile(command.executable, [...args, '--directory', this.directory!, ...(path ? ['--selected-file', path] : [])], {
        shell: false, windowsHide: true, encoding: 'buffer', maxBuffer: 1_048_576, timeout: 120_000, killSignal: 'SIGKILL',
        env: Object.fromEntries(['SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'].flatMap(k => process.env[k] === undefined ? [] : [[k, process.env[k]!]])),
      }, (error, stdout) => error ? reject(new Error('Archive operation failed; saved history retained')) : resolve(stdout));
      child.stdin?.on('error', () => {});
      child.stdin?.end(JSON.stringify(query) + '\n');
    });
    return decodeWorkspace(frame, 'ArchiveReply') as ArchiveReply;
  }
  async choose(directory: string): Promise<WorkspaceCatalogue> {
    if (!isAbsolute(directory)) throw new Error('Invalid store selection');
    this.clear(); this.directory = directory;
    try { return await this.catalogue(); } catch (error) { this.clear(); throw error; }
  }
  async catalogue(): Promise<WorkspaceCatalogue> {
    const result = await this.request('catalogue', {}, 'WorkspaceCatalogue') as WorkspaceCatalogue;
    if (this.storeId && result.data_store_id !== this.storeId) throw new Error('Selected store identity changed');
    if (result.branches.some(b => b.context.data_store_id !== result.data_store_id)) throw new Error('Catalogue binding mismatch');
    this.storeId = result.data_store_id;
    this.branches = result.branches;
    return result;
  }
  async create(input: unknown): Promise<WorkspaceState> {
    if (!workspaceValid(input, 'CreateOptions')) throw new Error('Invalid creation request');
    const encoded = JSON.stringify(input);
    if (this.pendingCreate && this.pendingCreate.input !== encoded) throw new Error('Resolve the previous creation before changing the request');
    this.pendingCreate ??= { input: encoded, identity: randomUUID() };
    const identity = this.pendingCreate.identity;
    const state = await this.request('create', input as CreateOptions, 'WorkspaceState', identity) as WorkspaceState;
    if (state.context.data_store_id !== this.storeId || state.context.civilization_id !== 'civ:' + identity ||
        state.context.branch_id !== 'main' || JSON.stringify(state.context) !== JSON.stringify(state.branch.context) ||
        state.branch.name !== (input as CreateOptions).name || state.goal_count !== 0 || state.policy_count !== 0 || state.mechanism_count !== 0) throw new Error('Creation response binding mismatch');
    this.pendingCreate = undefined;
    this.selected = state;
    this.branches = [...(this.branches ?? []), state.branch];
    return state;
  }
  async select(input: unknown): Promise<WorkspaceState> {
    if (!workspaceValid(input, 'WorkspaceSelection')) throw new Error('Invalid selection');
    const selection = input as WorkspaceSelection;
    if (!this.branches?.some(b => b.context.civilization_id === selection.civilization_id && b.context.branch_id === selection.branch_id)) throw new Error('Selection is outside the store grant');
    const state = await this.request('select', selection, 'WorkspaceState') as WorkspaceState;
    if (state.context.civilization_id !== selection.civilization_id || state.context.branch_id !== selection.branch_id ||
        (selection.revision_id !== null && state.context.revision_id !== selection.revision_id) ||
        state.context.data_store_id !== this.storeId || state.branch.context.civilization_id !== selection.civilization_id ||
        state.branch.context.branch_id !== selection.branch_id || state.branch.context.data_store_id !== this.storeId) throw new Error('Workspace response binding mismatch');
    this.selected = state;
    this.worldCandidate = undefined; this.workbenchCandidate = undefined;
    this.candidate = undefined;
    return state;
  }
  private authorizeInterview(query: InterviewQuery) {
    if (!this.selected || JSON.stringify(query.context) !== JSON.stringify(this.selected.context)) throw new Error('Interview outside selected context');
  }
  async workbench(input: unknown): Promise<WorkbenchPage> {
    if (!workspaceValid(input, 'WorkbenchQuery')) throw new Error('Invalid evidence query');
    const query = structuredClone(input as WorkbenchQuery);
    this.authorizeHistory(query.context);
    const reply = await this.request('workbench', query, 'WorkbenchPage') as WorkbenchPage;
    if (!isDeepStrictEqual(reply.query, { cursor: null, ...query }) ||
        !isDeepStrictEqual(reply.versions, this.selected!.versions) || !isDeepStrictEqual(reply.effective_time, this.selected!.effective_time) ||
        reply.items.some(r => (r.note && (query.collection !== 'notes' || r.note.scope_id !== query.scope_id || r.note.id !== r.id)) ||
          (r.assumption && (query.collection !== 'assumptions' || r.assumption.id !== r.id)) ||
          (r.goal && (query.collection !== 'goals' || r.goal.id !== r.id)) ||
          (r.reference && query.collection !== 'references') || (r.model_id && query.collection !== 'models') ||
          (r.rationale && (query.collection !== 'rationale' || r.rationale.id !== r.id)) ||
          (r.text != null && !['notes', 'rationale'].includes(query.collection)))) throw new Error('Evidence response binding mismatch');
    return reply;
  }
  async previewWorkbench(input: unknown): Promise<WorkbenchPreview> {
    if (!workspaceValid(input, 'WorkbenchEdit') || this.workbenchCandidate?.applying || this.candidate?.applying || this.worldCandidate?.applying) throw new Error('Resolve pending Apply');
    const edit = structuredClone(input as WorkbenchEdit);
    this.authorizeHistory(edit.context);
    if (!isDeepStrictEqual(this.selected!.context, this.selected!.branch.context)) throw new Error('Historical state is read only');
    this.workbenchCandidate = undefined; this.candidate = undefined; this.worldCandidate = undefined;
    const identity = randomUUID();
    const reply = await this.request('preview-workbench', edit, 'WorkbenchPreview', identity) as WorkbenchPreview;
    const expected = { ...edit, change: edit.change.kind === 'goal' ? { remove: false, ...edit.change } : edit.change.kind === 'note' ? { id: null, ...edit.change } : edit.change };
    if (!isDeepStrictEqual(reply.edit, expected) || (edit.change.kind !== 'assumption' && reply.physical_before !== reply.physical_after)) throw new Error('Evidence preview binding mismatch');
    this.workbenchCandidate = { edit, identity, preview: reply, applying: false };
    return reply;
  }
  async applyWorkbench(input: unknown): Promise<InterviewCommit> {
    if (!workspaceValid(input, 'InterviewApply')) throw new Error('Invalid evidence Apply');
    const candidate = this.workbenchCandidate;
    if (!candidate || candidate.preview.candidate_digest !== (input as InterviewApply).candidate_digest) throw new Error('No granted evidence candidate');
    this.authorizeHistory(candidate.edit.context);
    candidate.applying = true;
    const reply = await this.request('apply-workbench', { edit: candidate.edit, candidate_digest: candidate.preview.candidate_digest }, 'InterviewCommit', candidate.identity) as InterviewCommit;
    const old = candidate.edit.context, current = reply.state.context;
    if (current.data_store_id !== old.data_store_id || current.civilization_id !== old.civilization_id || current.branch_id !== old.branch_id ||
        !isDeepStrictEqual(reply.state.versions, this.selected!.versions) || !isDeepStrictEqual(reply.state.effective_time, this.selected!.effective_time) ||
        (reply.status === 'applied' && current.revision_id === old.revision_id)) throw new Error('Evidence Apply binding mismatch');
    this.selected = reply.state; this.workbenchCandidate = undefined;
    return reply;
  }
  async cancelWorkbench(): Promise<void> {
    if (this.workbenchCandidate?.applying) throw new Error('Retry uncertain Apply');
    this.workbenchCandidate = undefined;
  }
  async deleteNote(input: unknown): Promise<DeleteNoteReply> {
    if (!workspaceValid(input, 'DeleteNote') || this.workbenchCandidate || this.candidate || this.worldCandidate) throw new Error('Resolve draft first');
    const query = structuredClone(input as DeleteNote);
    this.authorizeHistory(query.context);
    const reply = await this.request('delete-note', query, 'DeleteNoteReply') as DeleteNoteReply;
    if (!isDeepStrictEqual(reply.query, query)) throw new Error('Deletion binding mismatch');
    return reply;
  }
  async exploration(input: unknown): Promise<ExplorationPage> {
    if (!workspaceValid(input, 'ExplorationQuery')) throw new Error('Invalid world query');
    const query = structuredClone(input as ExplorationQuery);
    this.authorizeHistory(query.context);
    const result = await this.request('exploration', query, 'ExplorationPage') as ExplorationPage;
    if (!isDeepStrictEqual(result.query, { projection: 'all', identity: null, cursor: null, ...query }) ||
        !isDeepStrictEqual(result.versions, this.selected!.versions) || !isDeepStrictEqual(result.effective_time, this.selected!.effective_time) ||
        result.items.some(row => row.inspector && (!isDeepStrictEqual(row.inspector.context, query.context) || row.inspector.scope_id !== query.scope_id))) throw new Error('World projection binding mismatch');
    return result;
  }
  async previewWorld(input: unknown): Promise<ExplorationPreview> {
    if (!workspaceValid(input, 'ExplorationEdit') || this.worldCandidate?.applying || this.candidate?.applying || this.workbenchCandidate?.applying) throw new Error('Resolve pending apply first');
    const edit = structuredClone(input as ExplorationEdit);
    this.authorizeHistory(edit.context);
    if (!isDeepStrictEqual(this.selected!.context, this.selected!.branch.context)) throw new Error('Historical state is read only');
    this.worldCandidate = undefined; this.workbenchCandidate = undefined; this.candidate = undefined;
    const identity = randomUUID();
    const preview = await this.request('preview-world', edit, 'ExplorationPreview', identity) as ExplorationPreview;
    if (!isDeepStrictEqual(preview.edit, { ...edit, change: edit.change.kind === 'relationship' ? { terms: null, ...edit.change } : edit.change.kind === 'entity' ? { population_role: null, ...edit.change } : edit.change })) throw new Error('World preview binding mismatch');
    this.worldCandidate = { edit, identity, preview, applying: false };
    return preview;
  }
  async applyWorld(input: unknown): Promise<InterviewCommit> {
    if (!workspaceValid(input, 'InterviewApply')) throw new Error('Invalid world apply');
    const candidate = this.worldCandidate;
    if (!candidate || candidate.preview.candidate_digest !== (input as InterviewApply).candidate_digest) throw new Error('No granted world candidate');
    this.authorizeHistory(candidate.edit.context);
    candidate.applying = true;
    const result = await this.request('apply-world', { edit: candidate.edit, candidate_digest: candidate.preview.candidate_digest }, 'InterviewCommit', candidate.identity) as InterviewCommit;
    const old = candidate.edit.context, current = result.state.context;
    if (current.data_store_id !== old.data_store_id || current.civilization_id !== old.civilization_id || current.branch_id !== old.branch_id ||
        !isDeepStrictEqual(result.state.versions, this.selected!.versions) || !isDeepStrictEqual(result.state.effective_time, this.selected!.effective_time) ||
        (result.status === 'applied' && current.revision_id === old.revision_id)) throw new Error('World apply binding mismatch');
    this.selected = result.state; this.worldCandidate = undefined;
    return result;
  }
  async cancelWorld(): Promise<void> {
    if (this.worldCandidate?.applying || this.workbenchCandidate?.applying) throw new Error('Retry uncertain apply or reopen confirmed state');
    this.worldCandidate = undefined;
  }
  async matrixModel(input: unknown): Promise<MatrixModelReply> {
    if (!workspaceValid(input, 'MatrixModelQuery')) throw new Error('Invalid model query');
    const query = structuredClone(input as MatrixModelQuery);
    this.authorizeHistory(query.context);
    const result = await this.request('matrix-model', query, 'MatrixModelReply') as MatrixModelReply;
    if (!isDeepStrictEqual(result.query, { version: null, ...query }) || (result.mechanism && (query.kind !== 'mechanism' || result.mechanism.id !== query.identity || (query.version != null && result.mechanism.version !== query.version))) ||
        (result.policy_rule && result.policy_rule.identity.id !== query.identity) || (result.allocation_rule && result.allocation_rule.id !== query.identity) ||
        (result.condition_rule && result.condition_rule.identity.id !== query.identity)) throw new Error('Matrix model binding mismatch');
    return result;
  }
  async matrix(input: unknown): Promise<MatrixPage> {
    if (!workspaceValid(input, 'MatrixQuery')) throw new Error('Invalid matrix query');
    const query = structuredClone(input as MatrixQuery);
    this.authorizeHistory(query.context);
    const result = await this.request('matrix', query, 'MatrixPage') as MatrixPage;
    const expected = { axis: 'domain', relationship_type: null, provenance: 'any', row_id: null, column_id: null, cursor: null, detail_cursor: null, ...query };
    if (!isDeepStrictEqual(result.query, expected) || !isDeepStrictEqual(result.versions, this.selected!.versions) ||
        !isDeepStrictEqual(result.effective_time, this.selected!.effective_time) || result.relationships.some(r =>
          [...r.interviews, ...r.sources, ...r.inspectors].some(q => !isDeepStrictEqual(q.context, query.context)) ||
          [...r.interviews, ...r.inspectors].some(q => q.scope_id !== query.scope_id))) throw new Error('Matrix binding mismatch');
    return result;
  }
  async atlas(input: unknown): Promise<AtlasPage> {
    if (!workspaceValid(input, 'AtlasQuery')) throw new Error('Invalid atlas query');
    const query = structuredClone(input as AtlasQuery);
    this.authorizeHistory(query.context);
    const result = await this.request('atlas', query, 'AtlasPage') as AtlasPage;
    // Python defaults are explicit in the echoed query.
    const expected = { search: '', domain_ref: null, branch_ref: null, source_ref: null, selection: 'any', modeling: null, evidence: null, issues: 'any', cursor: null, ...query };
    if (!isDeepStrictEqual(result.query, expected) || result.items.some(row => row.interview &&
      (!isDeepStrictEqual(row.interview.context, query.context) || row.interview.scope_id !== query.scope_id))) throw new Error('Atlas binding mismatch');
    return result;
  }
  async atlasSource(input: unknown): Promise<AtlasSourcePage> {
    if (!workspaceValid(input, 'AtlasSourceQuery')) throw new Error('Invalid atlas source query');
    const query = structuredClone(input as AtlasSourceQuery);
    this.authorizeHistory(query.context);
    const result = await this.request('atlas-source', query, 'AtlasSourcePage') as AtlasSourcePage;
    if (!isDeepStrictEqual(result.query, { offset: 0, ...query }) || result.source.reference.id !== query.source_ref) throw new Error('Atlas source binding mismatch');
    return result;
  }
  async interview(input: unknown): Promise<InterviewQuestion> {
    if (!workspaceValid(input, 'InterviewQuery')) throw new Error('Invalid interview');
    const query = input as InterviewQuery;
    this.authorizeInterview(query);
    const result = await this.request('interview', query, 'InterviewQuestion') as InterviewQuestion;
    if (!isDeepStrictEqual(result.query, { ...query, question_id: query.question_id ?? null })) throw new Error('Interview binding mismatch');
    return result;
  }
  async previewInterview(input: unknown): Promise<InterviewPreview> {
    if (!workspaceValid(input, 'InterviewEdit') || this.candidate?.applying || this.worldCandidate?.applying || this.workbenchCandidate?.applying) throw new Error('Resolve pending apply first');
    const edit = structuredClone(input as InterviewEdit);
    this.authorizeInterview(edit.query);
    if (this.selected!.context.revision_id !== this.selected!.branch.context.revision_id) throw new Error('Historical state is read only');
    this.candidate = undefined; this.worldCandidate = undefined; this.workbenchCandidate = undefined;
    const identity = randomUUID();
    const preview = await this.request('preview-interview', edit, 'InterviewPreview', identity) as InterviewPreview;
    if (!isDeepStrictEqual(preview.query, { ...edit.query, question_id: edit.query.question_id ?? null }) || preview.selected_id !== edit.choice_id || !preview.alternatives.includes(edit.choice_id)) throw new Error('Preview binding mismatch');
    this.candidate = { edit, identity, preview, applying: false };
    return preview;
  }
  async applyInterview(input: unknown): Promise<InterviewCommit> {
    if (!workspaceValid(input, 'InterviewApply')) throw new Error('Invalid apply');
    const candidate = this.candidate;
    if (!candidate || candidate.preview.candidate_digest !== (input as InterviewApply).candidate_digest) throw new Error('No granted candidate');
    this.authorizeInterview(candidate.edit.query);
    candidate.applying = true;
    const result = await this.request('apply-interview', { edit: candidate.edit, candidate_digest: candidate.preview.candidate_digest }, 'InterviewCommit', candidate.identity) as InterviewCommit;
    const previous = candidate.edit.query.context, current = result.state.context;
    if (current.data_store_id !== previous.data_store_id || current.civilization_id !== previous.civilization_id || current.branch_id !== previous.branch_id ||
        JSON.stringify(result.state.versions) !== JSON.stringify(this.selected!.versions) ||
        JSON.stringify(result.state.effective_time) !== JSON.stringify(this.selected!.effective_time) ||
        (result.status === 'applied' && current.revision_id === previous.revision_id)) throw new Error('Apply binding mismatch');
    this.selected = result.state;
    this.candidate = undefined;
    return result;
  }
  async cancelInterview(): Promise<void> {
    if (this.candidate?.applying || this.workbenchCandidate?.applying) throw new Error('Retry uncertain apply or reopen confirmed state');
    this.candidate = undefined;
  }
  private async observationRequest(input: unknown, type: string, operation: string, replyType: string) {
    if (!workspaceValid(input, type)) throw new Error('Invalid observation request');
    const query = structuredClone(input as OverviewQuery | TargetQuery | ChartQuery);
    if (!this.selected || Object.entries(this.selected.context).some(([k, v]) => query.context[k as keyof typeof query.context] !== v)) throw new Error('Observation is outside selected context');
    const result = await this.request(operation, query, replyType) as OverviewPage | TargetReply | ChartReply;
    if (!isDeepStrictEqual(result.query, query)) throw new Error('Observation binding mismatch');
    if ('versions' in result && (JSON.stringify(result.versions) !== JSON.stringify(this.selected.versions) ||
        JSON.stringify(result.effective_time) !== JSON.stringify(this.selected.effective_time))) throw new Error('Observation model/time mismatch');
    return result;
  }
  private async uncertaintyRequest(input: unknown, operation: string, queryType: string, replyType: string): Promise<unknown> {
    if (!workspaceValid(input, queryType)) throw new Error('Invalid analysis request');
    const query = structuredClone(input as UncertaintyQuery | SensitivityQuery | CapacityQuery);
    this.authorizeHistory(query.context);
    if (this.candidate || this.worldCandidate || this.workbenchCandidate) throw new Error('Resolve draft first');
    const reply = await this.request(operation, query, replyType) as UncertaintyReport | SensitivityReport | CapacityReport;
    if (!isDeepStrictEqual(reply.query, query)) throw new Error('Analysis binding mismatch');
    if ('effective_time' in reply && !isDeepStrictEqual(reply.effective_time, this.selected!.effective_time)) throw new Error('Analysis time mismatch');
    return reply;
  }
  uncertainty(input: unknown) { return this.uncertaintyRequest(input, 'uncertainty', 'UncertaintyQuery', 'UncertaintyReport') as Promise<UncertaintyReport>; }
  sensitivity(input: unknown) { return this.uncertaintyRequest(input, 'sensitivity', 'SensitivityQuery', 'SensitivityReport') as Promise<SensitivityReport>; }
  capacity(input: unknown) { return this.uncertaintyRequest(input, 'capacity', 'CapacityQuery', 'CapacityReport') as Promise<CapacityReport>; }
  async timeline(input: unknown): Promise<TimelineReply> {
    if (!workspaceValid(input, 'TimelineRequest')) throw new Error('Invalid timeline request');
    const query: TimelineRequest = { sequence: 0, target_day: 0, other_id: null, source_revision_id: null,
      expected: null, control: null, after: null, indicator_id: null, trace_offset: 0, realization_policy: 'preserve', seed: null,
      ...structuredClone(input as TimelineRequest) };
    this.authorizeHistory(query.context);
    if (this.candidate || this.worldCandidate || this.workbenchCandidate) throw new Error('Resolve draft first');
    const reply = await this.request('timeline', query, 'TimelineReply') as TimelineReply;
    if (!isDeepStrictEqual(reply.query, query)) throw new Error('Timeline binding mismatch');
    for (const boundary of [reply.head, reply.checkpoint, reply.opening, reply.origin]) {
      if (boundary && (boundary.context.data_store_id !== query.context.data_store_id ||
          boundary.context.civilization_id !== query.context.civilization_id)) throw new Error('Foreign timeline result');
    }
    const expectedId = query.action === 'fork' || query.action === 'schedule' ? query.other_id : query.experiment_id;
    if (reply.head && reply.head.context.experiment_id !== expectedId) throw new Error('Wrong experiment');
    return reply;
  }
  private authorizeHistory(context: LineageQuery['context']) {
    if (!this.selected || !isDeepStrictEqual(context, this.selected.context)) throw new Error('History outside selected context');
  }
  async rationale(input: unknown): Promise<RationaleReply> {
    if (!workspaceValid(input, 'RationaleQuery')) throw new Error('Invalid rationale request');
    const query = structuredClone(input as RationaleQuery);
    this.authorizeHistory(query.context);
    const result = await this.request('rationale', query, 'RationaleReply') as RationaleReply;
    if (!isDeepStrictEqual(result.query, query)) throw new Error('Private rationale binding mismatch');
    return result;
  }
  async lineage(input: unknown): Promise<LineagePage> {
    if (!workspaceValid(input, 'LineageQuery')) throw new Error('Invalid lineage');
    const query = structuredClone(input as LineageQuery);
    this.authorizeHistory(query.context);
    const result = await this.request('lineage', query, 'LineagePage') as LineagePage;
    if (!isDeepStrictEqual(result.query, query) || result.branch.context.data_store_id !== this.storeId ||
        result.branch.context.civilization_id !== query.context.civilization_id || result.branch.context.branch_id !== query.context.branch_id ||
        result.items.some(r => r.context.data_store_id !== this.storeId || r.context.civilization_id !== query.context.civilization_id)) throw new Error('Lineage binding mismatch');
    return result;
  }
  async compare(input: unknown): Promise<ComparePage> {
    if (!workspaceValid(input, 'CompareQuery')) throw new Error('Invalid comparison');
    const query = structuredClone(input as CompareQuery);
    this.authorizeHistory(query.context);
    if (query.other.data_store_id !== this.storeId || query.other.civilization_id !== query.context.civilization_id ||
        !this.branches?.some(b => b.context.branch_id === query.other.branch_id && b.context.civilization_id === query.other.civilization_id)) throw new Error('Comparison outside store grant');
    const result = await this.request('compare', query, 'ComparePage') as ComparePage;
    if (!isDeepStrictEqual(result.query, query) || !isDeepStrictEqual(result.left_versions, this.selected!.versions)) throw new Error('Comparison binding mismatch');
    return result;
  }
  async historyAction(input: unknown): Promise<WorkspaceState> {
    if (!workspaceValid(input, 'HistoryAction') || this.candidate || this.worldCandidate || this.workbenchCandidate) throw new Error('Resolve interview draft first');
    const query = structuredClone(input as HistoryAction);
    // Replay the identical operation after an uncertain reply, preserving identity.
    if (this.pendingHistory && !isDeepStrictEqual(this.pendingHistory.query, query)) throw new Error('Resolve pending history action');
    this.authorizeHistory(query.context);
    if (!isDeepStrictEqual(query.context, this.selected!.branch.context)) throw new Error('Select the branch head before changing history');
    this.pendingHistory ??= { query, identity: randomUUID() };
    const result = await this.request('history-action', query, 'WorkspaceState', this.pendingHistory.identity) as WorkspaceState;
    if (result.context.data_store_id !== this.storeId || result.context.civilization_id !== query.context.civilization_id ||
        result.context.branch_id !== (query.action === 'fork' ? 'fork:' + this.pendingHistory.identity : query.context.branch_id) ||
        !isDeepStrictEqual(result.context, result.branch.context) ||
        result.branch.sequence !== (query.action === 'fork' ? 0 : query.expected_sequence + 1) ||
        ((query.action === 'fork' || query.action === 'restore') && result.context.revision_id !== (query.target_revision_id ?? query.context.revision_id)) ||
        ((query.action === 'fork' || query.action === 'rename') && result.branch.name !== query.name)) throw new Error('History action binding mismatch');
    this.pendingHistory = undefined; this.selected = result;
    this.branches = [...(this.branches ?? []).filter(b => b.context.civilization_id !== result.context.civilization_id || b.context.branch_id !== result.context.branch_id), result.branch];
    return result;
  }
  async overview(input: unknown): Promise<OverviewPage> { return await this.observationRequest(input, 'OverviewQuery', 'overview', 'OverviewPage') as OverviewPage; }
  async target(input: unknown): Promise<TargetReply> { return await this.observationRequest(input, 'TargetQuery', 'target', 'TargetReply') as TargetReply; }
  async chart(input: unknown): Promise<ChartReply> { return await this.observationRequest(input, 'ChartQuery', 'chart', 'ChartReply') as ChartReply; }
  async page(input: unknown): Promise<WorkspacePage> {
    if (!workspaceValid(input, 'WorkspacePageRequest')) throw new Error('Invalid page');
    const query = input as WorkspacePageRequest;
    if (!this.selected || Object.entries(this.selected.context).some(([k, v]) => query.context[k as keyof typeof query.context] !== v)) throw new Error('Page is outside selected context');
    const result = await this.request('page', query, 'WorkspacePage') as WorkspacePage;
    if (result.scope_id !== query.scope_id || result.result.page.kind !== query.collection ||
        Object.entries(query.context).some(([k, v]) => result.result.context[k as keyof typeof query.context] !== v) ||
        JSON.stringify(result.result.versions) !== JSON.stringify(this.selected.versions) ||
        JSON.stringify(result.result.effective_time) !== JSON.stringify(this.selected.effective_time)) throw new Error('Page response binding mismatch');
    return result;
  }
}
