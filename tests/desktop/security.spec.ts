import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { createServer, get } from 'node:http';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import fixtures from '../../contracts/fixtures.json';

test('E2E-012.a packaged sender schema and passive hostile resources', async () => {
  const data = await mkdtemp(join(tmpdir(), 'poliscope-security-'));
  let hits = 0;
  const sink = createServer((_request, response) => { hits++; response.end('controlled sink'); });
  await new Promise<void>(resolve => sink.listen(0, '127.0.0.1', resolve));
  const address = sink.address() as { port: number };
  const target = `http://127.0.0.1:${address.port}/passive`;
  // Positive control: the sink is reachable before renderer probes begin.
  await new Promise<void>((resolve, reject) => get(target, response => { response.resume(); response.on('end', resolve); }).on('error', reject));
  expect(hits).toBe(1); hits = 0;
  const base = resolve(`out/Poliscope-${process.platform}-${process.arch}`);
  const executablePath = process.platform === 'darwin' ? join(base, 'Poliscope.app/Contents/MacOS/poliscope') : join(base, `poliscope${process.platform === 'win32' ? '.exe' : ''}`);
  const env = Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
  env.POLISCOPE_USER_DATA = data;
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath, args: ['--no-sandbox'], env });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('Local engine ready');
    const summary = JSON.parse(fixtures.find(f => f.name === 'evidence:incomplete')!.frame).result;
    const selection = { storage_context_id: 'selected', request: { history_protocol: 1, context: summary.context, result_id: summary.result_id, collection: 'summary', offset: 0, limit: 1 } };
    await app.evaluate(({ dialog }) => {
      const tracked = dialog as typeof dialog & { attempted: boolean };
      tracked.attempted = false;
      dialog.showOpenDialog = async () => { tracked.attempted = true; throw new Error('Private path must never escape'); };
    });
    for (const value of [null, { ...selection, path: '/etc/passwd' }, { ...selection, storage_context_id: 'x'.repeat(20_000) }]) {
      const error = await page.evaluate(async value => {
        try { await window.poliscope.openHistory(value as never); return ''; } catch (error) { return String(error); }
      }, value);
      expect(error).toContain('Desktop request rejected. Retry or reconnect.');
      expect(error).not.toContain('/etc');
    }
    // A genuine IPC invocation from another WebContents, with valid arguments.
    // This deliberately unsafe test-only window has its own ephemeral session.
    const preload = join(data, 'attacker-preload.cjs');
    await writeFile(preload, `const { ipcRenderer } = require('electron'); window.securityInvoke = (...args) => ipcRenderer.invoke(...args);`);
    const frameFile = join(data, 'attacker.html');
    await writeFile(frameFile, '<!doctype html><html><body>Isolated security probe</body></html>');
    const frameURL = pathToFileURL(frameFile).href;
    const errors = await app.evaluate(async ({ BrowserWindow }, { selection, preload, frameURL }) => {
      const attacker = new BrowserWindow({ show: false, webPreferences: { partition: 'security-probe', preload, nodeIntegration: true, nodeIntegrationInSubFrames: true, contextIsolation: false, sandbox: false } });
      try {
        await attacker.loadURL(frameURL);
        const errors = await attacker.webContents.executeJavaScript(`Promise.all(${JSON.stringify([
          ['workspace:choose', []], ['workspace:catalogue', []], ['workspace:create', [{ name: 'Forged', setup: 'blank', scope_name: 'Home', population: null, land_area: null }]], ['workspace:select', [{ civilization_id: 'civ', branch_id: 'main', revision_id: null }]], ['workspace:page', [{ context: selection.request.context, scope_id: 'home', collection: 'values', cursor: null }]],
          ['interview:read', [{ context: selection.request.context, scope_id: 'home', domain_id: 'domain:1' }]], ['interview:preview', [{}]], ['interview:apply', [{ candidate_digest: 'sha256:' + '0'.repeat(64) }]], ['interview:cancel', []],
          ['design-history:rationale', [{}]], ['design-history:action', [{}]], ['design-history:compare', [{}]], ['design-history:lineage', [{}]], ['overview:read', [{}]], ['overview:target', [{}]], ['overview:chart', [{}]],
          ['bootstrap:status', []], ['history:open', [selection]], ['history:page', ['summary', 0]], ['runtime:reconnect', []],
        ])}.map(async ([channel,args]) => { try { await require('electron').ipcRenderer.invoke(channel,...args); return 'accepted'; } catch(e) { return String(e); } }))`);
        await attacker.webContents.executeJavaScript(`new Promise(resolve => { const frame = document.createElement('iframe'); frame.onload = resolve; frame.src = ${JSON.stringify(frameURL)}; document.body.append(frame); })`);
        errors.push(await attacker.webContents.mainFrame.frames[0].executeJavaScript(`window.securityInvoke('bootstrap:status').then(() => 'accepted', error => String(error))`));
        return errors;
      } finally { attacker.destroy(); }
    }, { selection, preload, frameURL });
    for (const error of errors) expect(error).toContain('Desktop request rejected. Retry or reconnect.');
    expect(await app.evaluate(({ dialog }) => (dialog as typeof dialog & { attempted: boolean }).attempted)).toBe(false);
    await page.evaluate(() => { location.hash = 'stale-document'; });
    expect(await page.evaluate(async () => { try { await window.poliscope.bootstrapStatus(); return 'accepted'; } catch (error) { return String(error); } })).toContain('Desktop request rejected');
    // Keep the stale URL through a background status poll so the rejected
    // request is reflected in React Query, rather than racing its 500ms timer.
    await expect(page.getByRole('status')).toHaveText('Local engine unavailable');
    await page.evaluate(() => { history.replaceState(null, '', location.href.split('#')[0]); });
    expect(await page.evaluate(() => window.poliscope.bootstrapStatus())).toHaveProperty('state', 'ready');
    // The direct IPC result precedes React Query's next poll/render. Assert
    // recovery through the UI before proceeding to further hostile probes.
    await expect(page.getByRole('status')).toHaveText('Local engine ready');

    const documentURL = page.url();
    // Deliberately inject DOM beyond the application's text-only presentation.
    // Production CSP and main's request policy must still block every resource.
    const probe = await page.evaluate(async target => {
      const container = document.createElement('section');
      container.id = 'hostile-probe';
      container.innerHTML = `<img src="${target}/image" onerror="window.executed=true"><video poster="${target}/poster" src="${target}/media"></video><audio src="${target}/audio" autoplay></audio><iframe src="${target}/frame"></iframe><object data="${target}/object"></object><embed src="${target}/embed"><svg><image href="${target}/svg"/></svg><style>@import url('${target}/import'); @font-face {font-family: hostile; src:url('${target}/font')} #hostile-probe {font-family:hostile;background-image:url('${target}/css')}</style><link rel="stylesheet" href="${target}/style"><span>probe text</span>`;
      document.body.append(container);
      const script = document.createElement('script'); script.src = `${target}/script`; container.append(script);
      const fetchBlocked = await fetch(`${target}/fetch`).then(() => false, () => true);
      const popup = window.open(`${target}/popup`);
      await new Promise(resolve => setTimeout(resolve, 350));
      return { fetchBlocked, popupBlocked: popup === null, executed: (window as unknown as { executed?: boolean }).executed === true, require: typeof (window as unknown as { require?: unknown }).require };
    }, target);
    expect(probe).toEqual({ fetchBlocked: true, popupBlocked: true, executed: false, require: 'undefined' });
    expect(hits).toBe(0);
    expect(page.url()).toBe(documentURL);
    await page.evaluate(target => { location.href = target + '/navigation'; }, target);
    expect(await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.getURL())).toBe(documentURL);
    expect(hits).toBe(0);
    // Chromium cancels this navigation before commit; Playwright's frame URL
    // becomes empty. Inspect and interact with the live document via Electron.
    await expect.poll(() => app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.executeJavaScript(`({ url: location.href, status: document.querySelector('[role="status"]').textContent })`))).toEqual({ url: documentURL, status: 'Local engine ready' });
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(button => button.textContent === 'Reconnect local engine').click()`));
    await expect.poll(() => app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.executeJavaScript('window.poliscope.bootstrapStatus()'))).toHaveProperty('state', 'ready');
  } finally {
    await app.close();
    await new Promise<void>((resolve, reject) => sink.close(error => error ? reject(error) : resolve()));
    await rm(data, { recursive: true, force: true });
  }
});
