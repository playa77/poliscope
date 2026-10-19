import { workspaceValid } from './workspace';
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
  shell: DesktopShell, choose: () => Promise<string | undefined>, chooseWorkspace: () => Promise<string | undefined> = async () => undefined): void {
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
  const workspaceReply = (type: string) => (reply: unknown) => Buffer.byteLength(JSON.stringify(reply)) <= 1_048_576 && workspaceValid(reply, type);
  handle('design-history:rationale', 1, input => { if (!workspaceValid(input, 'RationaleQuery')) throw new Error(); return shell.rationale(input); }, workspaceReply('RationaleReply'));
  handle('design-history:lineage', 1, input => { if (!workspaceValid(input, 'LineageQuery')) throw new Error(); return shell.lineage(input); }, workspaceReply('LineagePage'));
  handle('design-history:compare', 1, input => { if (!workspaceValid(input, 'CompareQuery')) throw new Error(); return shell.compare(input); }, workspaceReply('ComparePage'));
  handle('design-history:action', 1, input => { if (!workspaceValid(input, 'HistoryAction')) throw new Error(); return shell.historyAction(input); }, workspaceReply('WorkspaceState'));
  handle('overview:read', 1, input => { if (!workspaceValid(input, 'OverviewQuery')) throw new Error(); return shell.overview(input); }, workspaceReply('OverviewPage'));
  handle('overview:target', 1, input => { if (!workspaceValid(input, 'TargetQuery')) throw new Error(); return shell.target(input); }, workspaceReply('TargetReply'));
  handle('overview:chart', 1, input => { if (!workspaceValid(input, 'ChartQuery')) throw new Error(); return shell.chart(input); }, workspaceReply('ChartReply'));
  handle('workspace:choose', 0, () => shell.chooseWorkspace(chooseWorkspace), reply => reply === null || workspaceReply('WorkspaceCatalogue')(reply));
  handle('workspace:catalogue', 0, () => shell.workspaceCatalogue(), workspaceReply('WorkspaceCatalogue'));
  handle('workspace:create', 1, input => { if (!workspaceValid(input, 'CreateOptions')) throw new Error(); return shell.createWorld(input); }, workspaceReply('WorkspaceState'));
  handle('workspace:select', 1, input => { if (!workspaceValid(input, 'WorkspaceSelection')) throw new Error(); return shell.selectWorld(input); }, workspaceReply('WorkspaceState'));
  handle('workspace:page', 1, input => { if (!workspaceValid(input, 'WorkspacePageRequest')) throw new Error(); return shell.worldPage(input); }, workspaceReply('WorkspacePage'));
  handle('interview:read', 1, input => { if (!workspaceValid(input, 'InterviewQuery')) throw new Error(); return shell.interview(input); }, workspaceReply('InterviewQuestion'));
  handle('interview:preview', 1, input => { if (!workspaceValid(input, 'InterviewEdit')) throw new Error(); return shell.previewInterview(input); }, workspaceReply('InterviewPreview'));
  handle('interview:apply', 1, input => { if (!workspaceValid(input, 'InterviewApply')) throw new Error(); return shell.applyInterview(input); }, workspaceReply('InterviewCommit'));
  handle('interview:cancel', 0, () => shell.cancelInterview(), reply => reply === undefined);
  handle('bootstrap:status', 0, () => shell.status, reply => {
    if (!reply || typeof reply !== 'object' || Object.keys(reply).sort().join() !== 'detail,state') return false;
    const status = reply as { state: unknown; detail: unknown };
    return typeof status.state === 'string' && ['starting', 'ready', 'failed', 'historical'].includes(status.state) && typeof status.detail === 'string' && status.detail.length <= 256;
  });
  handle('history:open', 1, input => shell.openHistory(validateSelection(input), choose), reply => reply === null || historyReply(reply));
  handle('history:page', 2, (collection, offset) => { validatePage(collection, offset); return shell.historyPage(collection, offset); }, historyReply);
  handle('runtime:reconnect', 0, () => shell.reconnect(), reply => reply === undefined);
}
