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
/** All launches share this controller; the path and exact grant never leave main. */
export class DesktopShell {
  private engine = new BootstrapEngine();
  private reader = new HistoricalReader();
  private selected?: { database: string; selection: HistorySelection };
  private active?: Promise<unknown>;
  private closing = false;
  private historical = false;
  private detail = 'Stored historical evidence; simulation and edits unavailable';
  constructor(private packaged: boolean, private root: string, private resources: string) {}
  get status(): ShellStatus { return this.historical ? { state: 'historical', detail: this.detail } : { ...this.engine.status }; }
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
      this.selected = { database, selection };
      this.historical = true;
      return this.read(selection.request);
    });
  }
  historyPage(collection: unknown, offset: unknown) {
    if (typeof collection !== 'string' || !collections.includes(collection) || typeof offset !== 'number' || !Number.isInteger(offset) || offset < 0 || offset > 100 || (collection === 'summary' && offset !== 0)) throw new Error('Invalid historical page');
    return this.run(async () => {
      if (!this.selected || !this.historical) throw new Error('Select historical evidence first');
      return this.read({ ...this.selected.selection.request, collection: collection as HistoryRequest['collection'], offset, limit: collection === 'summary' ? 1 : 10 });
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
