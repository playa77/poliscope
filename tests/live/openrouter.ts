/** Bounded opt-in production Electron/Python/SQLite/OpenRouter acceptance.
 * The credential exists only in this Electron main process. No private world,
 * provider error body, prompt, completion or credential is written to evidence.
 */
import { app, net, session } from 'electron';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, mkdir, writeFile, rm, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash, randomUUID } from 'node:crypto';
import { LiveBudget } from './budget';
import { ProviderController } from '../../desktop/main/providers';
import { AssistantController } from '../../desktop/main/assistant';
import { WorkspaceController } from '../../desktop/main/workspace';
import { spendingService } from '../../desktop/main/spending';
import { keyTestTransport, metadataTransport, generationTransport, type GenerationTransport } from '../../desktop/main/provider-network';
import { openRouterAdapter } from '../../desktop/main/provider-adapters';
import type { ProviderProfile } from '../../contracts/provider';
import type { AssistantPrepare, AssistantReply } from '../../contracts/assistant';
import type { GenerationPlan, GenerationFormat } from '../../contracts/generation';
const MODEL = 'deepseek/deepseek-v3.2';
const ENDPOINT = 'https://openrouter.ai/api/v1';
const directory = resolve('artifacts/wp-055-live');
const preflight = process.argv.includes('--preflight');
const key = process.env.OPENROUTER_API_KEY ?? '';
delete process.env.OPENROUTER_API_KEY;
const proxy = process.env.HTTPS_PROXY ?? process.env.HTTP_PROXY;
const outcomes: Record<string, unknown>[] = [];
const digest = (text: string) => createHash('sha256').update(text).digest('hex');
function check(value: unknown, reason: string): asserts value { if (!value) throw new Error(reason); }
const pause = (ms: number) => new Promise(r => setTimeout(r, ms));
const root = resolve('.');
let posts = 0;
let providers: ProviderController | undefined;
let world: WorkspaceController | undefined;
let controller: AssistantController | undefined;
let privateDirectory: string | undefined;
let activeCase = 'initialization';
let budget: LiveBudget | undefined;
const report: Record<string, unknown> = {
  version: 1, package: 'WP-055', prerequisite: 'WP-050-live', model: MODEL,
  started: new Date().toISOString(), authorized_budget_usd: '10',
  per_dispatch_exposure_usd: '0.5', maximum_dispatches: 12,
  maximum_run_reserved_exposure_usd: '6',
  privacy: 'Isolated synthetic world, selected public facts, no private user data; credential main-only/session-only.',
  cases: outcomes, readiness: false,
  unsupported_for_selected_model: ['image', 'audio', 'video'],
  untested_live: ['other models/providers', 'OS-protected native keychain', 'provider account hard-cap enforcement'],
};
async function runCase(id: string, run: () => Promise<Record<string, unknown> | void>) {
  activeCase = id;
  const result = await run();
  outcomes.push({ id, status: 'passed', ...result });
  console.log(id + ': passed');
}
async function terminal(id: string) {
  const until = Date.now() + 125000;
  while (Date.now() < until) {
    const result = await controller!.request({ action: 'status', request_id: id });
    if (!['pending', 'streaming'].includes(result.status)) return result;
    await pause(100);
  }
  await controller!.request({ action: 'cancel', request_id: id });
  throw new Error('Completion deadline exceeded; request cancelled');
}
const query = (text: string, stream = false): AssistantPrepare => ({
  action: 'prepare', profile_id: 'live', expected_revision: 2, text, stream,
  exposure: '0.5', turn_limit: '2', session_limit: '10', profile_limit: '10',
});
async function send(prepared: AssistantReply) {
  // The profile is pinned to one model and provider price ceilings. The native
  // transport additionally has a hard 12-POST count and bounded serialized body.
  await controller!.request({ action: 'send', request_id: prepared.request_id });
  const result = await terminal(prepared.request_id);
  check(result.status === 'complete', 'Generation did not complete: ' + result.status + '/' + result.diagnostic);
  check(result.result?.actual_model === MODEL, 'Unexpected model identity');
  check(result.exposure_status !== 'not-reserved', 'Dispatch lacks durable reservation');
  return result;
}
function summary(result: AssistantReply) {
  return { status: result.status, diagnostic: result.diagnostic,
    selected_model: MODEL, actual_model: result.result?.actual_model,
    actual_provider: result.result?.actual_provider, output_sha256: digest(result.text ?? ''),
    usage: result.usage_json ? JSON.parse(result.usage_json) : null,
    exposure_status: result.exposure_status, actual_cost: result.spending?.actual_cost ?? null };
}
async function main() {
  await app.whenReady();
  if (proxy) await session.defaultSession.setProxy({ proxyRules: proxy });
  // Chromium's Linux trust store does not consume NODE_EXTRA_CA_CERTS. Validate
  // the proxy-issued chain against the configured session CA with OpenSSL,
  // including hostname, validity, server purpose and chain constraints. Never
  // accept an arbitrary certificate or disable verification globally.
  const ca = process.env.NODE_EXTRA_CA_CERTS;
  if (ca) {
    const certificates = await mkdtemp(join(tmpdir(), 'poliscope-live-public-certs-'));
    session.defaultSession.setCertificateVerifyProc((request, callback) => {
      if (request.errorCode === 0) { callback(-3); return; }
      if (request.hostname !== 'openrouter.ai') { callback(-2); return; }
      void (async () => {
        const stem = join(certificates, randomUUID());
        const leaf = stem + '.pem', chain = stem + '-chain.pem';
        try {
          let cert = request.certificate;
          const parts: string[] = [];
          for (let i = 0; cert?.data && i < 12; i++) {
            if (parts.includes(cert.data)) break;
            parts.push(cert.data);
            cert = cert.issuerCert;
          }
          check(parts.length > 0 && parts.join('').length < 131072, 'Invalid peer chain');
          await writeFile(leaf, parts[0], { mode: 0o600 });
          const args = ['verify', '-CAfile', ca, '-purpose', 'sslserver', '-verify_hostname', request.hostname];
          if (parts.length > 1) { await writeFile(chain, parts.slice(1).join('\n'), { mode: 0o600 }); args.push('-untrusted', chain); }
          args.push(leaf);
          await promisify(execFile)('openssl', args, { timeout: 5000, maxBuffer: 65536 });
          callback(0);
        } catch { callback(-2); }
        finally { await rm(leaf, { force: true }); await rm(chain, { force: true }); }
      })();
    });
    app.once('will-quit', () => { void rm(certificates, { recursive: true, force: true }); });
  }
  await mkdir(directory, { recursive: true });
  // Public catalog preflight uses native Chromium transport and the actual
  // production parser, never a Node HTTP substitute or disabled TLS check.
  const metadata = metadataTransport(options => net.request(options));
  await runCase('native-public-catalog', async () => {
    const response = await metadata(ENDPOINT + '/models', '', new AbortController().signal);
    check(response.code === 200, 'Public catalog unavailable');
    const models = openRouterAdapter.models(JSON.parse(response.body), new Date().toISOString());
    const model = models.find(m => m.id === MODEL);
    check(model?.capabilities.text === 'supported' && model.capabilities.tools === 'supported', 'Required model capabilities unavailable');
    report.catalog_sha256 = digest(response.body);
    report.model = { id: MODEL, source: model.source, capabilities: model.capabilities, pricing: model.pricing };
    return { count: models.length, model: MODEL };
  });
  if (preflight) { report.status = 'preflight-passed'; return; }
  check(process.env.POLISCOPE_LIVE_OPENROUTER === '1' && key.length > 10, 'Secure key/opt-in missing');
  // A durable count prevents repeated runner starts silently renewing the budget.
  // Removing this file to renew a live run requires a new explicit authorization.
  budget = await LiveBudget.acquire(directory);
  posts = budget.posts;
  privateDirectory = await mkdtemp(join(tmpdir(), 'poliscope-live-private-'));
  providers = new ProviderController(privateDirectory, {
    isEncryptionAvailable: () => false, encryptString: () => { throw new Error('No key persistence'); }, decryptString: () => { throw new Error('No key persistence'); },
  }, keyTestTransport(options => net.request(options)), process.platform, metadata);
  const profile: ProviderProfile = { id: 'live', name: 'Explicit bounded WP-055 live acceptance', kind: 'openrouter', endpoint: ENDPOINT, model: MODEL,
    generation: { temperature: null, top_p: null, max_output_tokens: 1024 },
    routing: { order: [], only: [], ignore: [], allow_fallbacks: false, require_parameters: true, data_collection: 'deny', max_price: { prompt: '2', completion: '2', request: '0' } },
    capabilities: { text: 'unknown', tools: 'unknown', structured_output: 'unknown', reasoning: 'unknown', image: 'unknown', audio: 'unknown', video: 'unknown' } };
  await providers.request({ action: 'save', profile, expected_revision: null });
  await providers.request({ action: 'replace-key', profile_id: 'live', expected_revision: 1, key });
  await runCase('authenticated-metadata', async () => {
    const accepted = await providers!.request({ action: 'test-key', profile_id: 'live', expected_revision: 2 });
    check(accepted.status === 'test-accepted', 'Key test failed: ' + accepted.status);
    const catalog = await providers!.request({ action: 'refresh-catalog', profile_id: 'live', expected_revision: 2 });
    check(catalog.status === 'metadata-ready', 'Catalog failed: ' + catalog.status);
    const endpoints = await providers!.request({ action: 'model-endpoints', profile_id: 'live', expected_revision: 2, model_id: MODEL });
    check(endpoints.status === 'metadata-ready' && endpoints.endpoints?.providers.length, 'Provider endpoint metadata unavailable');
    const status = await providers!.request({ action: 'key-status', profile_id: 'live', expected_revision: 2 });
    check(status.status === 'metadata-ready', 'Account status unavailable');
    return { key_storage: 'session-only', account_metadata: 'allowlisted; account limits not exported' };
  });
  world = new WorkspaceController(false, root, '');
  await world.choose(join(privateDirectory, 'world'));
  await world.create({ name: 'Synthetic public live-validation world', setup: 'blank', scope_name: 'Home', population: '12', land_area: '3' });
  const spend = spendingService(false, root, '', privateDirectory);
  const native = generationTransport(options => net.request(options));
  const bounded: GenerationTransport = async (url, body, credential, signal, stream, chunk) => {
    check(url === ENDPOINT + '/chat/completions', 'Unexpected billable endpoint');
    const data = JSON.parse(body);
    check(data.model === MODEL && data.max_tokens === 1024 && !data.models && Buffer.byteLength(body) < 32768, 'Payload exceeds live scope');
    check(data.provider.max_price.prompt === '2' && data.provider.max_price.completion === '2' && data.provider.max_price.request === '0', 'Price guard missing');
    await budget!.reserve();
    posts = budget!.posts;
    return native(url, body, credential, signal, stream, chunk);
  };
  let format: GenerationFormat = { type: 'text' };
  let toolChoice = 'auto';
  controller = new AssistantController({
    prepareGeneration: plan => providers!.prepareGeneration({ ...plan, response_format: format, tool_choice: toolChoice }),
    dispatchGeneration: (request, signal, dispatch) => providers!.dispatchGeneration(request, signal, dispatch),
    generationUsage: (request, id) => providers!.generationUsage(request, id),
  }, bounded, spend, () => world!.assistantContext, selection => world!.ground(selection));
  let first!: AssistantReply;
  await runCase('whole-json-generation-and-usage', async () => {
    first = await send(await controller!.request(query('Reply with exactly READY. This is a synthetic software compatibility check.')));
    check((first.text ?? '').includes('READY'), 'Expected answer absent');
    return summary(first);
  });
  await runCase('generation-metadata-and-durable-usage', async () => {
    let reconciled: AssistantReply | undefined;
    // Only this read-only metadata lookup may poll; generation is never retried.
    for (let attempt = 0; attempt < 3; attempt++) {
      try { reconciled = await controller!.request({ action: 'reconcile', request_id: first.request_id }); break; }
      catch { if (attempt < 2) await pause(1000); }
    }
    check(reconciled?.spending?.actual_cost != null, 'Actual generation cost unavailable');
    return { actual_cost_usd: reconciled.spending.actual_cost, usage_source: 'generation-metadata', deduplicated_ledger: true };
  });
  await runCase('streaming-generation', async () => summary(await send(await controller!.request(query('Reply with exactly STREAM_READY.', true)))));
  await runCase('structured-output', async () => {
    format = { type: 'json_schema', name: 'live_check', schema_text: JSON.stringify({ type: 'object', properties: { status: { type: 'string', enum: ['READY'] } }, required: ['status'], additionalProperties: false }) };
    try {
      const result = await send(await controller!.request(query('Return an object with status READY.')));
      check(result.result?.validated_json && JSON.parse(result.result.validated_json).status === 'READY', 'Structured answer invalid');
      return summary(result);
    } finally { format = { type: 'text' }; }
  });
  await runCase('tools-and-separately-approved-continuation', async () => {
    const selection = { scope_id: 'home', task: 'Inspect a declared synthetic population fact', collections: ['facts' as const], tools: true };
    const grant = await world!.ground(selection);
    const entry = grant.manifest.entries[0]?.id; check(entry, 'No public synthetic fact');
    toolChoice = 'inspect_context';
    const initial = await controller!.request({ ...query('Call inspect_context once with operation inspect, entry_id ' + entry + ', other_id null, value_json null.'), grounding: selection });
    await controller!.request({ action: 'send', request_id: initial.request_id });
    const tools = await terminal(initial.request_id);
    check(tools.status === 'tool-calls', 'Expected tool call unavailable');
    toolChoice = 'none';
    const next = await controller!.request({ action: 'continue', request_id: initial.request_id });
    check(next.status === 'prepared' && next.request_id !== initial.request_id, 'Continuation must require its own dispatch');
    const result = await send(next);
    toolChoice = 'auto';
    return { ...summary(result), initial_tools: JSON.parse(tools.tools_json ?? '[]').length, separate_dispatch: true };
  });
  await runCase('explicit-reasoning', async () => {
    // Catalog documents reasoning, but no supported effort/max-token range.
    // enabled=true requests reasoning without inventing unsupported controls.
    await providers!.request({ action: 'save', profile: { ...profile, generation: { ...profile.generation, reasoning: { enabled: true } } }, expected_revision: 2 });
    const result = await send(await controller!.request({ ...query('What is 2 plus 3? Explain in one short sentence.', true), expected_revision: 3 }));
    return { ...summary(result), reasoning_present: Boolean(result.reasoning) };
  });
  await runCase('cancel-stream-and-remove-key', async () => {
    const prepared = await controller!.request({ ...query('Write a long numbered list of integers from 1 to 1000.', true), expected_revision: 3 });
    const before = posts;
    await controller!.request({ action: 'send', request_id: prepared.request_id });
    const until = Date.now() + 10000;
    while (Date.now() < until && posts === before) await pause(50);
    check(posts > before, 'Cancellation check did not reach native transport');
    await controller!.request({ action: 'cancel', request_id: prepared.request_id });
    const cancelled = await terminal(prepared.request_id);
    check(cancelled.status === 'cancelled', 'Cancellation did not retain terminal state');
    const removed = await providers!.request({ action: 'remove-key', profile_id: 'live', expected_revision: 3 });
    check(removed.profiles[0]?.key_status === 'missing', 'Credential removal failed');
    return { status: cancelled.status, exposure_status: cancelled.exposure_status, key_removed: true };
  });
  report.status = 'passed';
}
main().catch(() => {
  outcomes.push({ id: activeCase, status: 'failed', diagnostic: 'Live check failed; no provider body, prompt, key or account details retained' });
  report.status = 'failed';
  process.exitCode = 1;
}).finally(async () => {
  controller?.close(); await providers?.close();
  await budget?.close();
  if (privateDirectory) await rm(privateDirectory, { recursive: true, force: true });
  report.finished = new Date().toISOString(); report.dispatches_lifetime = posts;
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, preflight ? 'preflight.json' : 'evidence.json'), JSON.stringify(report, null, 2) + '\n');
  app.exit(report.status === 'failed' ? 1 : 0);
});
