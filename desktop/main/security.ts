import type { BrowserWindow, IpcMainInvokeEvent, Session } from 'electron';
import { dirname, extname, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

/** A packaged build never trusts a development URL, even if one is supplied. */
export function developmentURL(packaged: boolean, value?: string): string | undefined {
  if (packaged || !value) return undefined;
  const url = new URL(value);
  if (url.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) || url.username || url.password || url.search || url.hash) throw new Error('Invalid development server');
  return url.href;
}
export function contentPolicy(devURL?: string): string {
  const origin = devURL ? new URL(devURL).origin : undefined;
  return `default-src 'none'; script-src 'self'${origin ? " 'unsafe-inline'" : ''}; style-src 'self' 'unsafe-inline'; img-src 'none'; font-src 'none'; media-src 'none'; connect-src ${origin ? `${origin} ${origin.replace('http:', 'ws:')}` : "'none'"}; object-src 'none'; base-uri 'none'; frame-src 'none'; form-action 'none'; worker-src 'none'`;
}
export function allowedResource(url: string, resourceType: string, documentURL: string, devURL?: string): boolean {
  try {
    const target = new URL(url);
    if (target.username || target.password) return false;
    if (devURL) {
      const dev = new URL(devURL);
      return target.origin === dev.origin || (target.protocol === 'ws:' && target.host === dev.host && resourceType === 'webSocket');
    }
    if (resourceType === 'mainFrame') return url === documentURL;
    if (target.protocol !== 'file:' || target.host || target.search || target.hash) return false;
    const path = fileURLToPath(target);
    const child = relative(dirname(fileURLToPath(documentURL)), path);
    if (!child || child.startsWith('..') || isAbsolute(child)) return false;
    return (resourceType === 'script' && extname(path) === '.js') || (resourceType === 'stylesheet' && extname(path) === '.css');
  } catch { return false; }
}
export function authorizeCaller(event: IpcMainInvokeEvent, window: BrowserWindow | undefined, documentURL: string): void {
  if (!window || window.isDestroyed() || event.sender !== window.webContents ||
      !event.senderFrame || event.senderFrame !== window.webContents.mainFrame ||
      event.senderFrame.url !== documentURL || window.webContents.getURL() !== documentURL) throw new Error('Unauthorized desktop request');
}
export function secureSession(session: Session, documentURL: string, devURL?: string): void {
  const csp = contentPolicy(devURL);
  session.webRequest.onBeforeRequest((details, callback) => callback({ cancel: !allowedResource(details.url, details.resourceType, documentURL, devURL) }));
  session.webRequest.onHeadersReceived((details, callback) => callback({
    responseHeaders: { ...Object.fromEntries(Object.entries(details.responseHeaders ?? {}).filter(([key]) => key.toLowerCase() !== 'content-security-policy')), 'Content-Security-Policy': [csp] },
  }));
  session.setPermissionCheckHandler(() => false);
  session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  session.on('will-download', event => event.preventDefault());
}
export function secureWindow(window: BrowserWindow): void {
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', event => event.preventDefault());
  window.webContents.on('will-frame-navigate', event => event.preventDefault());
  window.webContents.on('will-redirect', event => event.preventDefault());
  window.webContents.on('will-attach-webview', event => event.preventDefault());
}
