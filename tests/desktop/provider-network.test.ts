import { it, expect, vi } from 'vitest';
import { EventEmitter } from 'node:events';
import type { ClientRequest } from 'electron';
import { keyTestTransport } from '../../desktop/main/provider-network';
function fixture() {
  const request = Object.assign(new EventEmitter(), { abort: vi.fn(), setHeader: vi.fn(), end: vi.fn() });
  const create = vi.fn(() => request as unknown as ClientRequest);
  const controller = new AbortController();
  const pending = keyTestTransport(create)('https://provider.example/v1/models','synthetic-key',controller.signal);
  return { request, create, controller, pending };
}
it('uses fixed GET, manual redirects and no cookies; response body/headers are discarded', async () => {
  const f = fixture();
  expect(f.create).toHaveBeenCalledWith({url:'https://provider.example/v1/models',method:'GET',redirect:'manual',credentials:'omit',useSessionCookies:false});
  expect(f.request.setHeader.mock.calls).toEqual([['Authorization','Bearer synthetic-key'],['Accept','application/json']]);
  const response = Object.assign(new EventEmitter(),{statusCode:200}); f.request.emit('response',response);
  response.emit('data',Buffer.from('{"secret":"provider text"}')); response.emit('end');
  expect(await f.pending).toBe(200);
});
it.each([301,302,303,307,308])('aborts HTTP %s redirects without followRedirect or a second request', async code => {
  const f=fixture(); f.request.emit('redirect',code,'GET','https://sink.example/','Authorization: leaked');
  expect(await f.pending).toBe(code); expect(f.request.abort).toHaveBeenCalledOnce(); expect(f.create).toHaveBeenCalledOnce();
});
it('bounds metadata and safely handles transport/provider errors, login challenges and cancellation', async () => {
  for (const mode of ['size','error','login','cancel','abort','response-error','response-aborted']) {
    const f = fixture(); const rejected=expect(f.pending).rejects.toThrow('Provider connection failed');
    if (mode==='size' || mode.startsWith('response-')) {
      const response=Object.assign(new EventEmitter(),{statusCode:200}); f.request.emit('response',response);
      if (mode==='size') response.emit('data',Buffer.alloc(65537));
      else response.emit(mode==='response-error'?'error':'aborted',new Error('Authorization: secret'));
    } else if (mode==='cancel') f.controller.abort();
    else if (mode==='login') { const callback=vi.fn(); f.request.emit('login',{},callback); expect(callback).toHaveBeenCalledWith(); }
    else f.request.emit(mode,new Error('Authorization: secret'));
    await rejected;
  }
});
it('does not create a request when already cancelled', async () => {
  const create=vi.fn(), controller=new AbortController(); controller.abort();
  await expect(keyTestTransport(create)('https://example.com','key',controller.signal)).rejects.toThrow('cancelled'); expect(create).not.toHaveBeenCalled();
});
