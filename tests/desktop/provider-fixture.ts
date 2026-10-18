/** Synthetic in-memory network sink. No real endpoint or credential is accepted. */
export class ProviderFixture {
  readonly requests: Array<{ url: string; headers: Record<string, string>; body: unknown }> = [];
  async send(url: string, headers: Record<string, string>, body: unknown) {
    if (url !== 'https://provider.invalid/generate' || headers.authorization !== 'Bearer synthetic-key') {
      throw new Error('Only the synthetic provider is allowed');
    }
    this.requests.push(structuredClone({ url, headers, body }));
    return { text: 'Synthetic response', usage: { input: 1, output: 1 }, fixtureVersion: 1 };
  }
}
