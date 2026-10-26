/** Main-owned recovery grants; renderer receives neither paths nor raw databases. */
import { execFile } from 'node:child_process';
import { isAbsolute } from 'node:path';
import { createHash } from 'node:crypto';
import type { RecoveryRequest, RecoveryReply } from '../../contracts/recovery';
import { engineCommand } from './engine';
import { decodeWorkspace, workspaceValid } from './workspace';
export type RecoveryChoice = 'source' | 'archive' | 'backup' | 'restore' | 'sandbox';
export class RecoveryController {
  private source?: string;
  private archive = false;
  private branches: NonNullable<RecoveryReply['branches']> = [];
  private pending?: { encoded: string; identity: string; destination?: string };
  constructor(private packaged: boolean, private root: string, private resources: string) {}
  async request(input: unknown, choose: (kind: RecoveryChoice) => Promise<string | undefined>): Promise<RecoveryReply> {
    if (!workspaceValid(input, 'RecoveryRequest')) throw new Error('Invalid recovery request');
    const query = { recovery_contract: 1, context: null, offset: 0, detail_offset: 0, name: 'Migrated comparison', ...structuredClone(input as RecoveryRequest) } as RecoveryRequest;
    const encoded = JSON.stringify(query);
    if (this.pending && this.pending.encoded !== encoded) throw new Error('Retry the uncertain migration before changing its request');
    if (query.action === 'inspect' || query.action === 'archive-open') {
      const source = await choose(query.action === 'inspect' ? 'source' : 'archive');
      if (!source) return this.cancelled();
      if (!isAbsolute(source)) throw new Error('Invalid recovery source');
      this.source = source; this.archive = query.action === 'archive-open'; this.branches = [];
    }
    if (!this.source || (this.archive !== ['archive-open', 'archive-read', 'archive-migrate'].includes(query.action))) throw new Error('Select the matching historical source first');
    if (['read', 'migrate-model'].includes(query.action) && (!query.context || !this.branches.some(b =>
      b.context.data_store_id === query.context?.data_store_id && b.context.civilization_id === query.context?.civilization_id && b.context.branch_id === query.context?.branch_id))) throw new Error('Context outside selected historical store');
    let destination = this.pending?.destination;
    const kind = query.action === 'restore' ? 'restore' : query.action === 'archive-migrate' ? 'sandbox' : ['backup', 'migrate-schema'].includes(query.action) ? 'backup' : undefined;
    if (kind && !destination) {
      destination = await choose(kind);
      if (!destination) return this.cancelled();
      if (!isAbsolute(destination)) throw new Error('Invalid recovery destination');
    }
    const mutation = ['migrate-model', 'archive-migrate'].includes(query.action);
    if (mutation) {
      const binding = { action: query.action, context: this.archive ? null : query.context, offset: this.archive ? query.offset : 0, name: query.name };
      this.pending ??= { encoded, identity: createHash('sha256').update(JSON.stringify([this.source, destination ?? null, binding])).digest('hex'), destination };
    }
    const command = engineCommand(this.packaged, this.root, this.resources);
    const args = this.packaged ? ['--recovery'] : ['-I', '-m', 'poliscope_engine.recovery_host'];
    const frame = await new Promise<Buffer>((resolve, reject) => {
      const child = execFile(command.executable, [...args, '--source', this.source!, ...(destination ? ['--destination', destination] : []), '--identity', this.pending?.identity ?? 'unused'], {
        shell: false, windowsHide: true, encoding: 'buffer', maxBuffer: 1_048_576, timeout: 30_000, killSignal: 'SIGKILL',
        env: Object.fromEntries(['SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'].flatMap(k => process.env[k] === undefined ? [] : [[k, process.env[k]!]])),
      }, (error, stdout) => error ? reject(new Error('Recovery unconfirmed; retry identical migration or inspect saved history')) : resolve(stdout));
      child.stdin?.on('error', () => {}); child.stdin?.end(JSON.stringify(query) + '\n');
    });
    const reply = decodeWorkspace(frame, 'RecoveryReply') as RecoveryReply;
    // A structured failure is terminal: the host completed/rolled back its transaction.
    this.pending = undefined;
    if (query.action === 'inspect' && reply.status === 'complete') this.branches = reply.branches ?? [];
    return reply;
  }
  private cancelled(): RecoveryReply { return { recovery_contract: 1, status: 'cancelled', diagnostic: 'ok', detail: 'Selection cancelled.', schema_version: null, branches: [], rows: [], next_offset: null }; }
}
