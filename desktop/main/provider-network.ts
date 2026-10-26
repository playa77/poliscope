/** Electron net uses Chromium/system proxy configuration; no Node HTTP fallback. */
import type { ClientRequest, ClientRequestConstructorOptions } from 'electron';
import type { KeyTest } from './providers';
export function keyTestTransport(create: (options: ClientRequestConstructorOptions) => ClientRequest): KeyTest {
  return (url, key, signal) => new Promise<number>((resolve, reject) => {
    if (signal.aborted) { reject(new Error('Provider request cancelled')); return; }
    let request: ClientRequest;
    try { request = create({ url, method: 'GET', redirect: 'manual', credentials: 'omit', useSessionCookies: false }); }
    catch { reject(new Error('Provider connection failed')); return; }
    let done = false;
    const finish = (code?: number) => {
      if (done) return; done = true;
      signal.removeEventListener('abort', cancel);
      if (code === undefined) reject(new Error('Provider connection failed'));
      else resolve(code);
    };
    const cancel = () => { finish(); request.abort(); };
    signal.addEventListener('abort', cancel, { once: true });
    request.on('error', () => finish());
    request.on('abort', () => finish());
    request.on('redirect', (code) => { finish(code); request.abort(); });
    // No proxy/server interactive authentication, cookies, retries or redirects.
    request.on('login', (_auth, callback) => { callback(); cancel(); });
    request.on('response', response => {
      let bytes = 0;
      response.on('data', (data: Buffer) => {
        bytes += data.length;
        if (bytes > 65536) cancel();
      });
      response.on('error', () => finish());
      response.on('aborted', () => finish());
      response.on('end', () => finish(response.statusCode));
    });
    try {
      request.setHeader('Authorization', 'Bearer ' + key);
      request.setHeader('Accept', 'application/json');
      request.end();
    } catch { cancel(); }
  });
}
