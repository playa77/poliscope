import type { IpcMainInvokeEvent } from 'electron';
import type { DesktopShell } from './shell';
import { validateSelection, validatePage } from './shell';
import { valid, type Schema } from './wire';
import schema from '../../contracts/history.schema.json';
const definitions = schema.$defs as Record<string, Schema>;
export const IPC_ERROR = 'Desktop request rejected. Retry or reconnect.';
type Register = (channel: string, handler: (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>) => void;
/** No renderer-controlled channel or operation name reaches a service. */
export function registerShellIPC(register: Register, authorize: (event: IpcMainInvokeEvent) => void,
  shell: DesktopShell, choose: () => Promise<string | undefined>): void {
  function handle(channel: string, arity: number, action: (...args: unknown[]) => unknown | Promise<unknown>, check: (reply: unknown) => boolean) {
    register(channel, async (event, ...args) => {
      try {
        authorize(event);
        if (args.length !== arity || Buffer.byteLength(JSON.stringify(args)) > 16_384) throw new Error();
        const reply = await action(...args);
        if (!check(reply)) throw new Error();
        return reply;
      } catch { throw new Error(IPC_ERROR); }
    });
  }
  const historyReply = (reply: unknown) => Buffer.byteLength(JSON.stringify(reply)) <= 1_048_576 &&
    (valid(reply, definitions.HistoryResult, definitions) || valid(reply, definitions.HistoryError, definitions));
  handle('bootstrap:status', 0, () => shell.status, reply => {
    if (!reply || typeof reply !== 'object' || Object.keys(reply).sort().join() !== 'detail,state') return false;
    const status = reply as { state: unknown; detail: unknown };
    return typeof status.state === 'string' && ['starting', 'ready', 'failed', 'historical'].includes(status.state) && typeof status.detail === 'string' && status.detail.length <= 256;
  });
  handle('history:open', 1, input => shell.openHistory(validateSelection(input), choose), reply => reply === null || historyReply(reply));
  handle('history:page', 2, (collection, offset) => { validatePage(collection, offset); return shell.historyPage(collection, offset); }, historyReply);
  handle('runtime:reconnect', 0, () => shell.reconnect(), reply => reply === undefined);
}
