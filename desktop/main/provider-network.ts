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

/** Bounded JSON metadata only; error bodies never leave the transport. */
export function metadataTransport(create: (options: ClientRequestConstructorOptions) => ClientRequest): import('./provider-adapters').MetadataTransport {
  return (url, key, signal) => new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new Error('Provider request cancelled')); return; }
    let request: ClientRequest;
    try { request = create({ url, method:'GET', redirect:'manual', credentials:'omit', useSessionCookies:false }); }
    catch { reject(new Error('Provider connection failed')); return; }
    let done = false, bytes = 0;
    const chunks: Buffer[] = [];
    const finish = (code?: number, body = '') => {
      if (done) return; done = true; clearTimeout(timer);
      signal.removeEventListener('abort', cancel);
      if (code === undefined) reject(new Error('Provider connection failed'));
      else resolve({ code, body });
    };
    const cancel = () => { finish(); request.abort(); };
    const timer = setTimeout(cancel, 15000);
    signal.addEventListener('abort', cancel, { once:true });
    request.on('error', () => finish()); request.on('abort', () => finish());
    request.on('redirect', code => { finish(code); request.abort(); });
    request.on('login', (_auth, callback) => { callback(); cancel(); });
    request.on('response', response => {
      response.on('data', (chunk: Buffer) => {
        if (done) return;
        bytes += chunk.length;
        if (bytes > 8 * 1024 * 1024) { cancel(); return; }
        if (response.statusCode >= 200 && response.statusCode < 300) chunks.push(Buffer.from(chunk));
      });
      response.on('error', () => finish()); response.on('aborted', () => finish());
      response.on('end', () => {
        try { finish(response.statusCode, new TextDecoder('utf-8', { fatal:true }).decode(Buffer.concat(chunks))); }
        catch { finish(); }
      });
    });
    try { request.setHeader('Authorization', 'Bearer ' + key); request.setHeader('Accept','application/json'); request.end(); }
    catch { cancel(); }
  });
}
