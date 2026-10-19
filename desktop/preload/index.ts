import type { ShellAPI } from '../shell';
import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('poliscope', Object.freeze({
  overview: query => ipcRenderer.invoke('overview:read', query),
  target: query => ipcRenderer.invoke('overview:target', query),
  chart: query => ipcRenderer.invoke('overview:chart', query),
  interview: query => ipcRenderer.invoke('interview:read', query),
  previewInterview: edit => ipcRenderer.invoke('interview:preview', edit),
  applyInterview: candidate => ipcRenderer.invoke('interview:apply', candidate),
  cancelInterview: () => ipcRenderer.invoke('interview:cancel'),
  chooseWorkspace: () => ipcRenderer.invoke('workspace:choose'),
  workspaceCatalogue: () => ipcRenderer.invoke('workspace:catalogue'),
  createWorld: options => ipcRenderer.invoke('workspace:create', options),
  selectWorld: selection => ipcRenderer.invoke('workspace:select', selection),
  worldPage: request => ipcRenderer.invoke('workspace:page', request),
  openHistory: (selection) => ipcRenderer.invoke('history:open', selection),
  historyPage: (collection, offset) => ipcRenderer.invoke('history:page', collection, offset),
  reconnect: () => ipcRenderer.invoke('runtime:reconnect'),
  bootstrapStatus: async () => {
    const value: unknown = await ipcRenderer.invoke('bootstrap:status');
    if (!value || typeof value !== 'object' || !('state' in value) || !('detail' in value) ||
        !['starting', 'ready', 'failed', 'historical'].includes(String(value.state)) || typeof value.detail !== 'string' || value.detail.length > 256) {
      throw new Error('Invalid bootstrap status');
    }
    return { state: value.state as 'starting' | 'ready' | 'failed' | 'historical', detail: value.detail };
  },
} satisfies ShellAPI));
