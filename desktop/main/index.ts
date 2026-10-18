import { app, BrowserWindow, ipcMain, session, dialog } from 'electron';
import { isAbsolute, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { DesktopShell } from './shell';
import { authorizeCaller, developmentURL, secureSession, secureWindow } from './security';
import { registerShellIPC } from './ipc';

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
  const devURL = developmentURL(app.isPackaged, MAIN_WINDOW_VITE_DEV_SERVER_URL);
  const page = join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`);
  const documentURL = devURL ? new URL(devURL).href : pathToFileURL(page).href;
  secureSession(session.defaultSession, documentURL, devURL);
  window = new BrowserWindow({ width: 1040, height: 720, webPreferences: {
    preload: join(__dirname, 'preload.cjs'), nodeIntegration: false, contextIsolation: true, sandbox: true,
  }});
  secureWindow(window);
  registerShellIPC((channel, handler) => ipcMain.handle(channel, handler),
    event => authorizeCaller(event, window, documentURL), engine, async () => {
      const result = await dialog.showOpenDialog(window!, { title: 'Select saved historical evidence store',
        properties: ['openFile'], filters: [{ name: 'SQLite store', extensions: ['sqlite3', 'sqlite', 'db'] }] });
      return result.canceled ? undefined : result.filePaths[0];
    });
  app.on('second-instance', () => { if (window?.isMinimized()) window.restore(); window?.focus(); });
  engine.start();
  if (devURL) await window.loadURL(devURL);
  else await window.loadFile(page);
});
