/** Main-only launch and selection grants. Renderer never supplies a path or operation. */
import { execFile } from 'node:child_process';
import { isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import { engineCommand } from './engine';
import { valid, type Schema } from './wire';
import schema from '../../contracts/workspace.schema.json';
import interviewSchema from '../../contracts/interview.schema.json';
import type { InterviewQuery, InterviewEdit, InterviewQuestion, InterviewPreview, InterviewApply, InterviewCommit } from '../../contracts/interview';
import type { CreateOptions, WorkspaceCatalogue, WorkspaceSelection, WorkspaceState, WorkspacePageRequest, WorkspacePage } from '../../contracts/workspace';
const defs = { ...schema.$defs, ...interviewSchema.$defs } as Record<string, Schema>;
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
  private candidate?: { edit: InterviewEdit; identity: string; preview: InterviewPreview; applying: boolean };
  private directory?: string;
  private storeId?: string;
  get active(): boolean { return Boolean(this.directory && this.storeId); }
  private pendingCreate?: { input: string; identity: string };
  private selected?: WorkspaceState;
  private branches?: WorkspaceCatalogue['branches'];
  constructor(private packaged: boolean, private root: string, private resources: string) {}
  clear() { this.directory = undefined; this.storeId = undefined; this.selected = undefined; this.branches = undefined; this.pendingCreate = undefined; this.candidate = undefined; }
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
    this.candidate = undefined;
    return state;
  }
  private authorizeInterview(query: InterviewQuery) {
    if (!this.selected || JSON.stringify(query.context) !== JSON.stringify(this.selected.context)) throw new Error('Interview outside selected context');
  }
  async interview(input: unknown): Promise<InterviewQuestion> {
    if (!workspaceValid(input, 'InterviewQuery')) throw new Error('Invalid interview');
    const query = input as InterviewQuery;
    this.authorizeInterview(query);
    const result = await this.request('interview', query, 'InterviewQuestion') as InterviewQuestion;
    if (JSON.stringify(result.query) !== JSON.stringify(query)) throw new Error('Interview binding mismatch');
    return result;
  }
  async previewInterview(input: unknown): Promise<InterviewPreview> {
    if (!workspaceValid(input, 'InterviewEdit') || this.candidate?.applying) throw new Error('Resolve pending apply first');
    const edit = structuredClone(input as InterviewEdit);
    this.authorizeInterview(edit.query);
    if (this.selected!.context.revision_id !== this.selected!.branch.context.revision_id) throw new Error('Historical state is read only');
    this.candidate = undefined;
    const identity = randomUUID();
    const preview = await this.request('preview-interview', edit, 'InterviewPreview', identity) as InterviewPreview;
    if (JSON.stringify(preview.query) !== JSON.stringify(edit.query) || preview.selected_id !== edit.choice_id || !preview.alternatives.includes(edit.choice_id)) throw new Error('Preview binding mismatch');
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
    if (this.candidate?.applying) throw new Error('Retry uncertain apply or reopen confirmed state');
    this.candidate = undefined;
  }
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
