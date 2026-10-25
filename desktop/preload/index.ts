import type { ShellAPI } from '../shell';
import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('poliscope', Object.freeze({
  report: query => ipcRenderer.invoke('report:export', query),
  archive: query => ipcRenderer.invoke('archive:request', query),
  uncertainty: query => ipcRenderer.invoke('uncertainty:read', query),
  sensitivity: query => ipcRenderer.invoke('uncertainty:sensitivity', query),
  capacity: query => ipcRenderer.invoke('uncertainty:capacity', query),
  timeline: query => ipcRenderer.invoke('timeline:request', query),
  workbench: query => ipcRenderer.invoke('evidence:read', query),
  previewWorkbench: edit => ipcRenderer.invoke('evidence:preview', edit),
  applyWorkbench: candidate => ipcRenderer.invoke('evidence:apply', candidate),
  cancelWorkbench: () => ipcRenderer.invoke('evidence:cancel'),
  deleteNote: query => ipcRenderer.invoke('evidence:delete-note', query),
  exploration: query => ipcRenderer.invoke('world:explore', query),
  previewWorld: edit => ipcRenderer.invoke('world:preview', edit),
  applyWorld: candidate => ipcRenderer.invoke('world:apply', candidate),
  cancelWorld: () => ipcRenderer.invoke('world:cancel'),
  matrixModel: query => ipcRenderer.invoke('matrix:model', query),
  matrix: query => ipcRenderer.invoke('matrix:read', query),
  atlas: query => ipcRenderer.invoke('atlas:read', query),
  atlasSource: query => ipcRenderer.invoke('atlas:source', query),
  rationale: query => ipcRenderer.invoke('design-history:rationale', query),
  lineage: query => ipcRenderer.invoke('design-history:lineage', query),
  compare: query => ipcRenderer.invoke('design-history:compare', query),
  historyAction: query => ipcRenderer.invoke('design-history:action', query),
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
