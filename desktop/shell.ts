import type { HistoryRequest, HistoryResult, HistoryError } from '../contracts/history';
export type ShellStatus = { state: 'starting' | 'ready' | 'failed' | 'historical'; detail: string };
export type HistorySelection = { storage_context_id: string; request: HistoryRequest };
export type HistoryReply = HistoryResult | HistoryError | null;
export interface ShellAPI {
  bootstrapStatus(): Promise<ShellStatus>;
  openHistory(selection: HistorySelection): Promise<HistoryReply>;
  historyPage(collection: HistoryRequest['collection'], offset: number): Promise<HistoryReply>;
  reconnect(): Promise<void>;
}
