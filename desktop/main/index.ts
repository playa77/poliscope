import { app, BrowserWindow, ipcMain, session } from 'electron';
import { isAbsolute, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { BootstrapEngine } from './engine';

const dataPath = process.env.POLISCOPE_USER_DATA;
if (dataPath) {
  if (!isAbsolute(dataPath)) throw new Error('POLISCOPE_USER_DATA must be absolute');
  app.setPath('userData', dataPath);
}
const engine = new BootstrapEngine();
let closing = false;
let window: BrowserWindow | undefined;
app.on('before-quit', (event) => {
  if (closing) return;
  event.preventDefault();
  closing = true;
  void engine.stop().finally(() => app.quit());
});
app.on('window-all-closed', () => app.quit());
void app.whenReady().then(async () => {
  const devURL = MAIN_WINDOW_VITE_DEV_SERVER_URL;
  const page = join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`);
  const documentURL = devURL ? new URL(devURL).href : pathToFileURL(page).href;
  const devOrigin = devURL ? new URL(devURL).origin : undefined;
  const csp = `default-src 'none'; script-src 'self'${devURL ? " 'unsafe-inline'" : ''}; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src ${devOrigin ? `${devOrigin} ${devOrigin.replace('http:', 'ws:')}` : "'none'"}; object-src 'none'; base-uri 'none'; frame-src 'none'; form-action 'none'`;
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => callback({
    responseHeaders: { ...details.responseHeaders, 'Content-Security-Policy': [csp] },
  }));
  window = new BrowserWindow({ width: 1040, height: 720, webPreferences: {
    preload: join(__dirname, 'preload.cjs'), nodeIntegration: false, contextIsolation: true, sandbox: true,
  }});
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event) => event.preventDefault());
  ipcMain.handle('bootstrap:status', (event, ...args: unknown[]) => {
    if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame ||
        event.senderFrame.url !== documentURL || args.length !== 0) throw new Error('Unauthorized bootstrap request');
    return { ...engine.status };
  });
  const root = process.env.POLISCOPE_PROJECT_ROOT ?? '';
  engine.start(app.isPackaged, root, process.resourcesPath);
  if (devURL) await window.loadURL(devURL);
  else await window.loadFile(page);
});
