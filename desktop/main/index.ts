import { ProviderController } from './providers';
import { keyTestTransport, metadataTransport } from './provider-network';
import { app, safeStorage, net, BrowserWindow, ipcMain, session, dialog } from 'electron';
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
let providers: ProviderController | undefined;
let closing = false;
let window: BrowserWindow | undefined;
app.on('before-quit', (event) => {
  if (closing) return;
  event.preventDefault();
  closing = true;
  const providerStop = providers?.close();
  void Promise.all([engine.stop(), providerStop]).then(() => app.quit()).catch(() => { closing = false; });
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
  // Memory-only session separates provider networking from renderer CSP/cookies.
  const providerSession = session.fromPartition('poliscope-providers');
  providerSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  providers = new ProviderController(app.getPath('userData'), safeStorage,
    keyTestTransport(options => net.request({ ...options, session: providerSession })), process.platform,
    metadataTransport(options => net.request({ ...options, session: providerSession })));
  registerShellIPC((channel, handler) => ipcMain.handle(channel, handler),
    event => authorizeCaller(event, window, documentURL), engine, async () => {
      const result = await dialog.showOpenDialog(window!, { title: 'Select saved historical evidence store',
        properties: ['openFile'], filters: [{ name: 'SQLite store', extensions: ['sqlite3', 'sqlite', 'db'] }] });
      return result.canceled ? undefined : result.filePaths[0];
    }, async () => {
      const result = await dialog.showOpenDialog(window!, { title: 'Choose a local sandbox folder',
        properties: ['openDirectory', 'createDirectory'] });
      return result.canceled ? undefined : result.filePaths[0];
    }, async action => {
      if (action === 'export') {
        const result = await dialog.showSaveDialog(window!, { title: 'Export portable history to a new file',
          filters: [{ name: 'Poliscope portable archive', extensions: ['poliscope'] }] });
        return result.canceled ? undefined : result.filePath;
      }
      const result = await dialog.showOpenDialog(window!, { title: 'Import portable history', properties: ['openFile'],
        filters: [{ name: 'Poliscope portable archive', extensions: ['poliscope', 'zip'] }] });
      return result.canceled ? undefined : result.filePaths[0];
    }, async format => {
      const result = await dialog.showSaveDialog(window!, { title: 'Export inquiry report to a new file',
        filters: [{ name: format === 'markdown' ? 'Markdown inquiry report' : 'Typed measurements CSV', extensions: [format === 'markdown' ? 'md' : 'csv'] }] });
      return result.canceled ? undefined : result.filePath;
    }, async kind => {
      if (kind === 'backup') {
        const result = await dialog.showSaveDialog(window!, { title: 'Save a new database backup', filters: [{ name: 'SQLite backup', extensions: ['sqlite3'] }] });
        return result.canceled ? undefined : result.filePath;
      }
      const folder = kind === 'restore' || kind === 'sandbox';
      const result = await dialog.showOpenDialog(window!, { title: kind === 'restore' ? 'Restore into a new empty folder' : kind === 'sandbox' ? 'Choose comparison sandbox folder' : kind === 'archive' ? 'Inspect portable archive without a model' : 'Inspect saved database without a model',
        properties: folder ? ['openDirectory', 'createDirectory'] : ['openFile'] });
      return result.canceled ? undefined : result.filePaths[0];
    }, providers);
  app.on('second-instance', () => { if (window?.isMinimized()) window.restore(); window?.focus(); });
  engine.start();
  if (devURL) await window.loadURL(devURL);
  else await window.loadFile(page);
});
