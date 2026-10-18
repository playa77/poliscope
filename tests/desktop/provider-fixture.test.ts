import { expect, it } from 'vitest';
import { ProviderFixture } from './provider-fixture';

it('captures the entire outbound payload including nested attachments and headers', async () => {
  const sink = new ProviderFixture();
  const body = { messages: [{ text: 'synthetic', attachment: { bytes: 'fixture' } }], metadata: { scope: 'fixture' } };
  await sink.send('https://provider.invalid/generate', { authorization: 'Bearer synthetic-key', 'x-scope': 'fixture' }, body);
  body.metadata.scope = 'changed';
  expect(sink.requests).toEqual([{ url: 'https://provider.invalid/generate', headers: { authorization: 'Bearer synthetic-key', 'x-scope': 'fixture' }, body: { ...body, metadata: { scope: 'fixture' } } }]);
});
it('rejects actual endpoints and nonfixture credentials before dispatch', async () => {
  const sink = new ProviderFixture();
  await expect(sink.send('https://example.com', {}, {})).rejects.toThrow('synthetic');
  await expect(sink.send('https://provider.invalid/generate', { authorization: 'other' }, {})).rejects.toThrow('synthetic');
  expect(sink.requests).toHaveLength(0);
});
