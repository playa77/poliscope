import { WorkspaceController } from './workspace';
import { isAbsolute } from 'node:path';
import type { HistoryRequest } from '../../contracts/history';
import type { HistorySelection, ShellStatus } from '../shell';
import { BootstrapEngine } from './engine';
import { HistoricalReader, historyCommand } from './history';
import { valid, type Schema } from './wire';
import schema from '../../contracts/history.schema.json';
const definitions = schema.$defs as Record<string, Schema>;
const collections = ['summary', 'outputs', 'findings', 'sources', 'assumptions', 'traces'];
export function validateSelection(value: unknown): HistorySelection {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join() !== 'request,storage_context_id') throw new Error('Invalid history selection');
  const selection = value as HistorySelection;
  if (typeof selection.storage_context_id !== 'string' || !selection.storage_context_id.trim() || Buffer.byteLength(selection.storage_context_id) > 512 ||
      !valid(selection.request, definitions.HistoryRequest, definitions) || selection.request.collection !== 'summary' || selection.request.offset !== 0 || selection.request.limit !== 1) throw new Error('Invalid history selection');
  return structuredClone(selection);
}
export function validatePage(collection: unknown, offset: unknown): void {
  if (typeof collection !== 'string' || !collections.includes(collection) || typeof offset !== 'number' || !Number.isInteger(offset) || offset < 0 || offset > 100 || (collection === 'summary' && offset !== 0)) throw new Error('Invalid historical page');
}
/** All launches share this controller; the path and exact grant never leave main. */
export class DesktopShell {
  private engine = new BootstrapEngine();
  private reader = new HistoricalReader();
  private selected?: { database: string; selection: HistorySelection };
  private active?: Promise<unknown>;
  private closing = false;
  private historical = false;
  private detail = 'Stored historical evidence; simulation and edits unavailable';
  private workspace: WorkspaceController;
  private workspaceQueued = 0;
  private interviewGeneration = 0;
  private workspaceTail: Promise<unknown> = Promise.resolve();
  private workspaceRun<T>(action: () => Promise<T>): Promise<T> {
    if (this.workspaceQueued >= 32 || this.closing) return Promise.reject(new Error('Workspace queue full'));
    this.workspaceQueued++;
    const pending = this.workspaceTail.then(() => this.run(action)).finally(() => { this.workspaceQueued--; });
    this.workspaceTail = pending.catch(() => {});
    return pending;
  }
  constructor(private packaged: boolean, private root: string, private resources: string) {
    this.workspace = new WorkspaceController(packaged, root, resources);
  }
  chooseWorkspace(choose: () => Promise<string | undefined>) {
    this.interviewGeneration++;
    return this.workspaceRun(async () => {
      const directory = await choose();
      if (!directory) return null;
      await this.engine.stop();
      this.selected = undefined;
      this.historical = false;
      return this.workspace.choose(directory);
    });
  }
  report(input: unknown, choose: (format: 'markdown' | 'csv') => Promise<string | undefined>) { return this.workspaceRun(() => this.workspace.report(input, choose)); }
  archive(input: unknown, choose: (action: 'import' | 'export') => Promise<string | undefined>) { return this.workspaceRun(() => this.workspace.archive(input, choose)); }
  workspaceCatalogue() { return this.workspaceRun(() => this.workspace.catalogue()); }
  createWorld(input: unknown) { this.interviewGeneration++; return this.workspaceRun(() => this.workspace.create(input)); }
  selectWorld(input: unknown) { this.interviewGeneration++; return this.workspaceRun(() => this.workspace.select(input)); }
  uncertainty(input: unknown) { return this.workspaceRun(() => this.workspace.uncertainty(input)); }
  sensitivity(input: unknown) { return this.workspaceRun(() => this.workspace.sensitivity(input)); }
  capacity(input: unknown) { return this.workspaceRun(() => this.workspace.capacity(input)); }
  timeline(input: unknown) { return this.workspaceRun(() => this.workspace.timeline(input)); }
  workbench(input: unknown) { return this.workspaceRun(() => this.workspace.workbench(input)); }
  previewWorkbench(input: unknown) { return this.workspaceRun(() => this.workspace.previewWorkbench(input)); }
  applyWorkbench(input: unknown) { return this.workspaceRun(() => this.workspace.applyWorkbench(input)); }
  cancelWorkbench() { return this.workspaceRun(() => this.workspace.cancelWorkbench()); }
  deleteNote(input: unknown) { return this.workspaceRun(() => this.workspace.deleteNote(input)); }
  exploration(input: unknown) { return this.workspaceRun(() => this.workspace.exploration(input)); }
  previewWorld(input: unknown) { return this.workspaceRun(() => this.workspace.previewWorld(input)); }
  applyWorld(input: unknown) { return this.workspaceRun(() => this.workspace.applyWorld(input)); }
  cancelWorld() { return this.workspaceRun(() => this.workspace.cancelWorld()); }
  matrixModel(input: unknown) { return this.workspaceRun(() => this.workspace.matrixModel(input)); }
  matrix(input: unknown) { return this.workspaceRun(() => this.workspace.matrix(input)); }
  atlas(input: unknown) { return this.workspaceRun(() => this.workspace.atlas(input)); }
  atlasSource(input: unknown) { return this.workspaceRun(() => this.workspace.atlasSource(input)); }
  rationale(input: unknown) { return this.workspaceRun(() => this.workspace.rationale(input)); }
  lineage(input: unknown) { return this.workspaceRun(() => this.workspace.lineage(input)); }
  compare(input: unknown) { return this.workspaceRun(() => this.workspace.compare(input)); }
  historyAction(input: unknown) { this.interviewGeneration++; return this.workspaceRun(() => this.workspace.historyAction(input)); }
  overview(input: unknown) { return this.workspaceRun(() => this.workspace.overview(input)); }
  target(input: unknown) { return this.workspaceRun(() => this.workspace.target(input)); }
  chart(input: unknown) { return this.workspaceRun(() => this.workspace.chart(input)); }
  worldPage(input: unknown) { return this.workspaceRun(() => this.workspace.page(input)); }
  interview(input: unknown) {
    const generation = ++this.interviewGeneration;
    return this.workspaceRun(() => {
      if (generation !== this.interviewGeneration) throw new Error('Interview read superseded');
      return this.workspace.interview(input);
    });
  }
  previewInterview(input: unknown) { return this.workspaceRun(() => this.workspace.previewInterview(input)); }
  applyInterview(input: unknown) { return this.workspaceRun(() => this.workspace.applyInterview(input)); }
  cancelInterview() { return this.workspaceRun(() => this.workspace.cancelInterview()); }
  get status(): ShellStatus { if (this.workspace.active) return { state: 'ready', detail: 'Local sandbox ready' }; return this.historical ? { state: 'historical', detail: this.detail } : { ...this.engine.status }; }
  start() { this.engine.start(this.packaged, this.root, this.resources); }
  private run<T>(action: () => Promise<T>): Promise<T> {
    if (this.closing || this.active) return Promise.reject(new Error('Desktop service busy'));
    const operation = action();
    this.active = operation;
    void operation.finally(() => { if (this.active === operation) this.active = undefined; }).catch(() => {});
    return operation;
  }
  openHistory(input: unknown, choose: () => Promise<string | undefined>) {
    const selection = validateSelection(input);
    return this.run(async () => {
      const database = await choose();
      if (!database) return null;
      if (!isAbsolute(database)) throw new Error('Invalid selected store');
      await this.engine.stop(); // Reject if exit is unconfirmed: no replacement child.
      this.workspace.clear();
      this.selected = { database, selection };
      this.historical = true;
      return this.read(selection.request);
    });
  }
  historyPage(collection: unknown, offset: unknown) {
    validatePage(collection, offset);
    return this.run(async () => {
      if (!this.selected || !this.historical) throw new Error('Select historical evidence first');
      return this.read({ ...this.selected.selection.request, collection: collection as HistoryRequest['collection'], offset: offset as number, limit: collection === 'summary' ? 1 : 10 });
    });
  }
  private async read(request: HistoryRequest) {
    const { database, selection } = this.selected!;
    try {
      const result = await this.reader.read(historyCommand(this.packaged, this.root, this.resources), database, selection.storage_context_id, selection.request, request);
      this.detail = 'error' in result ? `Stored evidence unavailable: ${result.error}. Original store preserved.` : 'Stored historical evidence; simulation and edits unavailable';
      return result;
    } catch {
      this.detail = 'Stored evidence reader failed. Original store preserved; retry or select another store.';
      throw new Error('Stored evidence reader failed');
    }
  }
  reconnect() {
    return this.run(async () => {
      await this.engine.stop();
      this.workspace.clear();
      this.selected = undefined;
      this.historical = false;
      this.engine = new BootstrapEngine();
      this.start();
    });
  }
  async stop() {
    this.closing = true;
    await this.active?.catch(() => {});
    await this.engine.stop();
  }
}
