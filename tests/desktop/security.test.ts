import { it, expect, vi } from 'vitest';
import type { BrowserWindow, IpcMainInvokeEvent } from 'electron';
import { allowedResource, authorizeCaller, contentPolicy, developmentURL } from '../../desktop/main/security';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import fixtures from '../../contracts/fixtures.json';
const documentURL = 'file:///app/renderer/index.html';
const summary = JSON.parse(fixtures.find(f => f.name === 'evidence:incomplete')!.frame).result;
const selection = { storage_context_id: 'selected', request: { history_protocol: 1, context: summary.context, result_id: summary.result_id, collection: 'summary', offset: 0, limit: 1 } };
it('authorizes only the live owner main frame at the exact active document', () => {
  const frame = { url: documentURL };
  const contents = { mainFrame: frame, getURL: () => documentURL };
  const owner = { isDestroyed: () => false, webContents: contents } as unknown as BrowserWindow;
  const event = { sender: contents, senderFrame: frame } as unknown as IpcMainInvokeEvent;
  expect(() => authorizeCaller(event, owner, documentURL)).not.toThrow();
  for (const forged of [{ ...event, sender: {} }, { ...event, senderFrame: { url: documentURL } }, { ...event, senderFrame: null }]) {
    expect(() => authorizeCaller(forged as IpcMainInvokeEvent, owner, documentURL)).toThrow();
  }
  frame.url = documentURL + '#changed';
  expect(() => authorizeCaller(event, owner, documentURL)).toThrow();
  frame.url = documentURL;
  contents.getURL = () => 'file:///other.html';
  expect(() => authorizeCaller(event, owner, documentURL)).toThrow();
  expect(() => authorizeCaller(event, undefined, documentURL)).toThrow();
});
it('permits only packaged document and local script/style assets', () => {
  expect(allowedResource(documentURL, 'mainFrame', documentURL)).toBe(true);
  expect(allowedResource('file:///app/renderer/assets/main.js', 'script', documentURL)).toBe(true);
  expect(allowedResource('file:///app/renderer/assets/main.css', 'stylesheet', documentURL)).toBe(true);
  for (const url of ['https://sink.test/leak', 'http://127.0.0.1/leak', 'file:///etc/passwd', 'file:///app/renderer/../secret.js', 'data:text/html,attack', 'file://host/app/renderer/main.js']) {
    for (const type of ['image', 'media', 'font', 'script', 'stylesheet', 'subFrame', 'xhr', 'mainFrame']) expect(allowedResource(url, type, documentURL)).toBe(false);
  }
  expect(allowedResource(documentURL, 'subFrame', documentURL)).toBe(false);
  expect(contentPolicy()).toContain("connect-src 'none'");
  expect(contentPolicy()).not.toContain('ws:');
});
it('keeps loopback development transport out of packaged builds', () => {
  expect(developmentURL(true, 'https://attacker.test')).toBeUndefined();
  for (const url of ['https://localhost:5173', 'http://attacker.test', 'http://localhost.evil:5173', 'http://user@localhost:5173', 'http://localhost:5173/?secret']) expect(() => developmentURL(false, url)).toThrow();
  const dev = developmentURL(false, 'http://127.0.0.1:5173')!;
  expect(allowedResource('ws://127.0.0.1:5173/', 'webSocket', documentURL, dev)).toBe(true);
  expect(allowedResource('http://127.0.0.1:9999/leak', 'image', documentURL, dev)).toBe(false);
});
function harness() {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { status: { state: 'ready', detail: 'Local engine ready' }, openHistory: vi.fn().mockResolvedValue(null), historyPage: vi.fn().mockResolvedValue({ history_protocol: 1, mode: 'stored_historical', result: summary }), reconnect: vi.fn().mockResolvedValue(undefined) };
  const authorize = vi.fn();
  const choose = vi.fn();
  registerShellIPC((channel, handler) => handlers.set(channel, handler), authorize, service as unknown as DesktopShell, choose);
  const call = (channel: string, ...args: unknown[]) => handlers.get(channel)!({} as IpcMainInvokeEvent, ...args);
  return { call, service, authorize, handlers, choose };
}
it('rejects unauthorized and malformed requests before any service or dialog call', async () => {
  const h = harness();
  expect([...h.handlers.keys()].sort()).toEqual(['bootstrap:status', 'history:open', 'history:page', 'runtime:reconnect', 'workspace:catalogue', 'workspace:choose', 'workspace:create', 'workspace:page', 'workspace:select']);
  h.authorize.mockImplementationOnce(() => { throw new Error('/private/store/path'); });
  await expect(h.call('history:open', selection)).rejects.toThrow(IPC_ERROR);
  for (const [channel, args] of [
    ['history:open', []], ['history:open', [selection, 'extra']], ['history:open', [{ ...selection, path: '/etc/passwd' }]],
    ['history:open', [{ ...selection, storage_context_id: 'x'.repeat(20_000) }]], ['history:open', [null]],
    ['history:page', ['sql', 0]], ['history:page', ['outputs', -1]], ['history:page', ['outputs', NaN]],
    ['history:page', ['summary', 1]], ['runtime:reconnect', ['shell command']], ['bootstrap:status', [1]],
  ] as [string, unknown[]][]) await expect(h.call(channel, ...args)).rejects.toThrow(IPC_ERROR);
  for (const action of [h.service.openHistory, h.service.historyPage, h.service.reconnect, h.choose]) expect(action).not.toHaveBeenCalled();
  await expect(h.call('bootstrap:status')).resolves.toEqual(h.service.status);
  await expect(h.call('history:open', selection)).resolves.toBeNull();
  await expect(h.call('history:page', 'summary', 0)).resolves.toHaveProperty('result.result_id', summary.result_id);
});
it('bounds errors and validates service results before exposing them', async () => {
  const h = harness();
  h.service.openHistory.mockRejectedValueOnce(new Error('/private/store.sqlite token=private'));
  await expect(h.call('history:open', selection)).rejects.toThrow(new Error(IPC_ERROR));
  for (const reply of [{ path: '/private' }, { history_protocol: 1, result: {} }, 'x'.repeat(1_048_577), null]) {
    h.service.historyPage.mockResolvedValueOnce(reply);
    await expect(h.call('history:page', 'outputs', 0)).rejects.toThrow(IPC_ERROR);
  }
  h.service.status.detail = 'x'.repeat(257);
  await expect(h.call('bootstrap:status')).rejects.toThrow(IPC_ERROR);
  h.service.status = { state: 'ready', detail: 'Local engine ready' };
  await expect(h.call('bootstrap:status')).resolves.toEqual(h.service.status);
});
