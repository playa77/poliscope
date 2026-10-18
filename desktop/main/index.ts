import { app, BrowserWindow, ipcMain, session, dialog } from 'electron';
import { isAbsolute, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { DesktopShell } from './shell';

const dataPath = process.env.POLISCOPE_USER_DATA;
if (dataPath) {
  if (!isAbsolute(dataPath)) throw new Error('POLISCOPE_USER_DATA must be absolute');
  app.setPath('userData', dataPath);
}
const ownsData = app.requestSingleInstanceLock();
if (!ownsData) app.quit();
const engine = new DesktopShell(app.isPackaged, process.env.POLISCOPE_PROJECT_ROOT ?? '', process.resourcesPath);
let closing = false;
let window: BrowserWindow | undefined;
app.on('before-quit', (event) => {
  if (closing) return;
  event.preventDefault();
  closing = true;
  void engine.stop().then(() => app.quit()).catch(() => { closing = false; });
});
app.on('window-all-closed', () => app.quit());
if (ownsData) void app.whenReady().then(async () => {
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
  const authorize = (event: Electron.IpcMainInvokeEvent) => {
    if (!window || window.isDestroyed() || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame ||
        event.senderFrame.url !== documentURL) throw new Error('Unauthorized desktop request');
  };
  ipcMain.handle('bootstrap:status', (event, ...args: unknown[]) => {
    authorize(event);
    if (args.length) throw new Error('Invalid desktop request');
    return engine.status;
  });
  ipcMain.handle('history:open', (event, ...args: unknown[]) => {
    authorize(event);
    if (args.length !== 1) throw new Error('Invalid desktop request');
    return engine.openHistory(args[0], async () => {
      const result = await dialog.showOpenDialog(window!, { title: 'Select saved historical evidence store',
        properties: ['openFile'], filters: [{ name: 'SQLite store', extensions: ['sqlite3', 'sqlite', 'db'] }] });
      return result.canceled ? undefined : result.filePaths[0];
    });
  });
  ipcMain.handle('history:page', (event, ...args: unknown[]) => {
    authorize(event);
    if (args.length !== 2) throw new Error('Invalid desktop request');
    return engine.historyPage(args[0], args[1]);
  });
  ipcMain.handle('runtime:reconnect', (event, ...args: unknown[]) => {
    authorize(event);
    if (args.length) throw new Error('Invalid desktop request');
    return engine.reconnect();
  });
  app.on('second-instance', () => { if (window?.isMinimized()) window.restore(); window?.focus(); });
  engine.start();
  if (devURL) await window.loadURL(devURL);
  else await window.loadFile(page);
});
