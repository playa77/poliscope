/** Trusted main-only primitive. Shell must authorize player selection before use. */
import { execFile } from 'node:child_process';
import { isAbsolute } from 'node:path';
import { engineCommand } from './engine';
import { valid, type Schema } from './wire';
import schema from '../../contracts/history.schema.json';
import type { HistoryRequest, HistoryResult, HistoryError } from '../../contracts/history';
const definitions = schema.$defs as Record<string, Schema>;
const matches = (value: unknown, name: string) => valid(value, definitions[name], definitions);
export function historyCommand(packaged: boolean, root: string, resources: string) {
  const command = engineCommand(packaged, root, resources);
  return { executable: command.executable, args: packaged ? ['--history-read'] : ['-I', '-m', 'poliscope_engine.history'] };
}
export function decodeHistory(frame: Buffer, request: HistoryRequest): HistoryResult | HistoryError {
  if (frame.length > 1_048_576) throw new Error('Historical response too large');
  const text = new TextDecoder('utf-8', { fatal: true }).decode(frame);
  if (!text.endsWith('\n') || text.slice(0, -1).includes('\n') || text.includes('\r')) throw new Error('Invalid historical frame');
  const tokens = text.match(/"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g) ?? [];
  if (tokens.some(token => !token.startsWith('"') && (!/^-?\d+$/.test(token) || !Number.isSafeInteger(Number(token))))) throw new Error('Invalid historical numeric token');
  const value: unknown = JSON.parse(text);
  if (matches(value, 'HistoryError')) return value as HistoryError;
  if (!matches(value, 'HistoryResult')) throw new Error('Invalid historical response');
  const response = value as HistoryResult;
  const result = response.result;
  if (Object.entries(request.context).some(([key, field]) => result.context[key as keyof typeof result.context] !== field)
      || result.result_id !== request.result_id
      || (request.collection === 'summary' ? result.kind !== 'evaluation' : result.kind !== 'evidence_page' || result.page.kind !== request.collection)) throw new Error('Historical response binding mismatch');
  if (result.kind === 'evidence_page' && (result.page.items.length > request.limit
      || (result.page.next_cursor !== null && (result.page.items.length === 0 || request.offset + result.page.items.length >= 100 || result.page.next_cursor !== String(request.offset + result.page.items.length))))) throw new Error('Invalid historical page');
  return response;
}

/** One replacement service at a time; caller must stop the numerical child first. */
export class HistoricalReader {
  private active = false;
  async read(command: ReturnType<typeof historyCommand>, database: string, contextId: string,
    grant: HistoryRequest, request: HistoryRequest): Promise<HistoryResult | HistoryError> {
    if (this.active) throw new Error('Historical reader already active');
    if (!isAbsolute(database) || !isAbsolute(command.executable) || !contextId || Buffer.byteLength(contextId) > 512
        || !matches(grant, 'HistoryRequest') || !matches(request, 'HistoryRequest')) throw new Error('Invalid historical launch');
    if (grant.result_id !== request.result_id || Object.entries(grant.context).some(([key, field]) => request.context[key as keyof typeof request.context] !== field)) throw new Error('Historical access denied');
    const input = Buffer.from(JSON.stringify(request) + '\n');
    if (input.length > 1_048_576) throw new Error('Historical request too large');
    this.active = true;
    try {
      const frame = await new Promise<Buffer>((resolve, reject) => {
        const child = execFile(command.executable, [...command.args, '--database', database, '--context-id', contextId, '--grant', JSON.stringify(grant)], {
          shell: false, windowsHide: true, encoding: 'buffer', maxBuffer: 1_048_576,
          timeout: 10_000, killSignal: 'SIGKILL',
          env: Object.fromEntries(['SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'].flatMap(key => process.env[key] === undefined ? [] : [[key, process.env[key]!]])),
        }, (error, stdout) => error ? reject(new Error('Historical reader failed; preserve the original store')) : resolve(stdout));
        child.stdin?.on('error', () => {});
        child.stdin?.end(input);
      });
      return decodeHistory(frame, request);
    } finally { this.active = false; }
  }
}
