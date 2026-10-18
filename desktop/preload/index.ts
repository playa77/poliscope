import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('poliscope', Object.freeze({
  bootstrapStatus: async () => {
    const value: unknown = await ipcRenderer.invoke('bootstrap:status');
    if (!value || typeof value !== 'object' || !('state' in value) || !('detail' in value) ||
        !['starting', 'ready', 'failed'].includes(String(value.state)) || typeof value.detail !== 'string' || value.detail.length > 256) {
      throw new Error('Invalid bootstrap status');
    }
    return { state: value.state as 'starting' | 'ready' | 'failed', detail: value.detail };
  },
}));
