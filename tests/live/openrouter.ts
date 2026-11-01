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
import { RequestError } from '../../desktop/main/provider-requests';
import { openRouterAdapter } from '../../desktop/main/provider-adapters';
import type { ProviderProfile } from '../../contracts/provider';
import type { AssistantPrepare, AssistantReply } from '../../contracts/assistant';
import type { GenerationPlan, GenerationFormat } from '../../contracts/generation';
const MODEL = 'z-ai/glm-5.3-flash';
const ENDPOINT = 'https://openrouter.ai/api/v1';
const directory = resolve('artifacts/wp-055-live');
const authenticatedPreflight = process.argv.includes('--authenticated-preflight');
const preflight = process.argv.includes('--preflight') || authenticatedPreflight;
const key = process.env.OPENROUTER_API_KEY ?? '';
delete process.env.OPENROUTER_API_KEY;
const proxy = process.env.HTTPS_PROXY ?? process.env.HTTP_PROXY;
const outcomes: Record<string, unknown>[] = [];
const digest = (text: string) => createHash('sha256').update(text).digest('hex');
class LiveCheckError extends Error {}
function check(value: unknown, reason: string): asserts value { if (!value) throw new LiveCheckError(reason); }
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
  per_dispatch_exposure_usd: '0.1', maximum_dispatches: 100,
  maximum_run_reserved_exposure_usd: '10',
  privacy: 'Isolated synthetic world, selected public facts, no private user data; credential main-only/session-only.',
  cases: outcomes, readiness: false,
  unsupported_for_selected_model: ['audio'],
  advertised_but_unvalidated_live: ['image/video input: reviewed context accounting is text/tools only'],
  untested_live: ['other models/providers', 'OS-protected native keychain', 'provider account hard-cap enforcement'],
};
async function runCase(id: string, run: () => Promise<Record<string, unknown> | void>) {
  activeCase = id;
  const result = await run();
  outcomes.push({ ...result, id, status: 'passed' });
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
  exposure: '0.1', turn_limit: '2', session_limit: '10', profile_limit: '10',
});
async function send(prepared: AssistantReply) {
  // The profile is pinned to one model and provider price ceilings. The native
  // transport additionally has a durable exposure-unit limit and bounded serialized body.
  await controller!.request({ action: 'send', request_id: prepared.request_id });
  const result = await terminal(prepared.request_id);
  check(result.status === 'complete', 'Generation did not complete: ' + result.status + '/' + result.diagnostic);
  check(result.result?.actual_model === MODEL, 'Unexpected model identity');
  check(result.exposure_status !== 'not-reserved', 'Dispatch lacks durable reservation');
  return result;
}
function summary(result: AssistantReply) {
  return { response_status: result.status, diagnostic: result.diagnostic,
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
  const nativeMetadata = metadataTransport(options => net.request(options));
  const metadata: typeof nativeMetadata = async (url, credential, signal) => {
    const response = await nativeMetadata(url, credential, signal);
    if (url.includes('/generation?')) {
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(response.body)?.data ?? {}; } catch { /* no raw text retained */ }
      report.generation_metadata_diagnostic = { code: response.code,
        id_matches: data.id === new URL(url).searchParams.get('id'),
        model_matches: data.model === MODEL,
        canonical_model_matches: data.model === 'z-ai/glm-5.3-flash-20260826',
        model_absent: data.model == null, cost_present: data.total_cost != null };
    }
    return response;
  };
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
  if (preflight && !authenticatedPreflight) { report.status = 'preflight-passed'; return; }
  check(process.env.POLISCOPE_LIVE_OPENROUTER === '1' && key.length > 10, 'Secure key/opt-in missing');
  // A durable count prevents repeated runner starts silently renewing the budget.
  // Removing this file to renew a live run requires a new explicit authorization.
  const retained = JSON.parse(await readFile(resolve('docs/roadmap/execution/WP-055-live-review.json'), 'utf8')).dispatch_receipt;
  budget = await LiveBudget.acquire(directory, MODEL, {posts: retained.posts, units: retained.reserved_policy_units ?? retained.posts * 5});
  posts = budget.posts;
  report.initial_reserved_policy_units = budget.units;
  report.remaining_bounded_dispatches = 100 - budget.units;
  check(authenticatedPreflight || 100 - budget.units >= 5, 'Lifetime allocation cannot fund another complete live run; no paid request sent');
  privateDirectory = await mkdtemp(join(tmpdir(), 'poliscope-live-private-'));
  providers = new ProviderController(privateDirectory, {
    isEncryptionAvailable: () => false, encryptString: () => { throw new Error('No key persistence'); }, decryptString: () => { throw new Error('No key persistence'); },
  }, keyTestTransport(options => net.request(options)), process.platform, metadata);
  const profile: ProviderProfile = { id: 'live', name: 'Explicit bounded WP-055 live acceptance', kind: 'openrouter', endpoint: ENDPOINT, model: MODEL,
    generation: { temperature: null, top_p: null, max_output_tokens: 1024, reasoning: { effort: 'low' } },
    routing: { order: [], only: [], ignore: [], allow_fallbacks: false, require_parameters: true, data_collection: 'allow', max_price: { prompt: '2', completion: '2', request: '0' } },
    capabilities: { text: 'unknown', tools: 'unknown', structured_output: 'unknown', reasoning: 'unknown', image: 'unknown', audio: 'unknown', video: 'unknown' } };
  await providers.request({ action: 'save', profile, expected_revision: null });
  await providers.request({ action: 'replace-key', profile_id: 'live', expected_revision: 1, key });
  await runCase('authenticated-metadata', async () => {
    const accepted = await providers!.request({ action: 'test-key', profile_id: 'live', expected_revision: 2 });
    check(accepted.status === 'test-accepted', 'Key test failed: ' + accepted.status);
    const catalog = await providers!.request({ action: 'refresh-catalog', profile_id: 'live', expected_revision: 2 });
    check(catalog.status === 'metadata-ready', 'Catalog failed: ' + catalog.status);
    const selectedCatalog = await providers!.request({action: 'catalog', profile_id: 'live', expected_revision: 2, search: MODEL});
    report.authenticated_model_capabilities = selectedCatalog.catalog?.models.find(m => m.id === MODEL)?.capabilities;
    report.authenticated_model_parameters = selectedCatalog.catalog?.models.find(m => m.id === MODEL)?.supported_parameters;
    const endpoints = await providers!.request({ action: 'model-endpoints', profile_id: 'live', expected_revision: 2, model_id: MODEL });
    check(endpoints.status === 'metadata-ready' && endpoints.endpoints?.providers.length, 'Provider endpoint metadata unavailable');
    const status = await providers!.request({ action: 'key-status', profile_id: 'live', expected_revision: 2 });
    check(status.status === 'metadata-ready', 'Account status unavailable');
    return { key_storage: 'session-only', account_metadata: 'allowlisted; account limits not exported' };
  });
  if (authenticatedPreflight) {
    try {
      await providers.prepareGeneration({generation_contract: 1, profile_id: 'live', expected_revision: 2, messages: [{role: 'user', content: 'Return status READY.'}], stream: false, response_format: {type: 'json_schema', name: 'live_check', schema_text: JSON.stringify({type: 'object', properties: {status: {type: 'string', enum: ['READY']}}, required: ['status'], additionalProperties: false})}, tools: []});
      report.schema_preparation = 'passed';
    } catch (error) {report.schema_preparation = error instanceof RequestError ? {code: error.code, parameter: error.parameter} : 'failed';}
    report.status = 'authenticated-preflight-passed'; return;
  }
  world = new WorkspaceController(false, root, '');
  await world.choose(join(privateDirectory, 'world'));
  await world.create({ name: 'Synthetic public live-validation world', setup: 'blank', scope_name: 'Home', population: '12', land_area: '3' });
  const spend = spendingService(false, root, '', privateDirectory);
  const native = generationTransport(options => {
    const request = net.request(options);
    request.on('response', response => {
      if (response.statusCode < 400) return;
      let data = '';
      response.on('data', (chunk: Buffer) => { if (data.length < 65536) data += chunk.toString('utf8'); });
      response.on('end', () => {
        // Classify fixed public routing failures only; never retain server text.
        const reason = /data policy|data collection|privacy/i.test(data) ? 'routing-data-policy'
          : /parameter/i.test(data) ? 'routing-parameters'
          : /price/i.test(data) ? 'routing-price'
          : /no endpoints/i.test(data) ? 'routing-no-endpoints' : 'unclassified';
        outcomes.push({ id: 'http-failure', status: 'failed', code: response.statusCode, reason, bytes: Buffer.byteLength(data), known_terms: ['model','found','allowed','guardrail','invalid','endpoint','provider','region','account','available','blocked','policy','route','matching','reasoning','supported','price','limit'].filter(term => data.toLowerCase().includes(term)) });
      });
    });
    return request;
  });
  const bounded: GenerationTransport = async (url, body, credential, signal, stream, chunk) => {
    check(url === ENDPOINT + '/chat/completions', 'Unexpected billable endpoint');
    const data = JSON.parse(body);
    check(data.model === MODEL && data.max_tokens === 1024 && !data.models && Buffer.byteLength(body) < 32768, 'Payload exceeds live scope');
    check(Buffer.byteLength(body) + 1024 * (data.messages.length + (data.tools?.length ?? 0) + 1) < 40000, 'Live context exceeds reserved exposure policy');
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
    format = {type: 'json_object'};
    try {
      first = await send(await controller!.request(query('Return a JSON object with status READY. This is a synthetic software compatibility check.')));
      check(JSON.parse(first.text ?? '{}').status === 'READY', 'Expected answer absent');
      return {...summary(first), response_format: 'json_object'};
    } finally {format = {type: 'text'};}
  });
  let reasoningStream!: AssistantReply;
  let toolReasoningPresent = false;
  await runCase('streaming-generation', async () => {
    reasoningStream = await send(await controller!.request(query('What is 17 times 19? Think through the arithmetic, then give the answer.', true)));
    return summary(reasoningStream);
  });
  await runCase('generation-metadata-and-durable-usage', async () => {
    let reconciled: AssistantReply | undefined;
    // Only this read-only metadata lookup may poll; generation is never retried.
    const lookupFailures: string[] = [];
    for (let attempt = 0; attempt < 30; attempt++) {
      try { reconciled = await controller!.request({ action: 'reconcile', request_id: first.request_id }); if (reconciled.spending?.actual_cost != null) break; await pause(1000); }
      catch (error) {
        const allowed = ['Metadata unavailable', 'Usage lookup unavailable', 'Usage identity mismatch', 'Invalid usage', 'Spending service unavailable'];
        const diagnostic = error instanceof Error && allowed.includes(error.message) ? error.message : 'Lookup failed; details withheld';
        if (!lookupFailures.includes(diagnostic)) lookupFailures.push(diagnostic);
        if (attempt < 29) await pause(1000);
      }
    }
    report.usage_lookup_failures = lookupFailures;
    const persisted = await controller!.request({action: 'usage', request_id: first.request_id});
    report.response_ledger_actual_cost = persisted.spending?.actual_cost ?? null;
    report.response_ledger_status = persisted.spending?.status ?? null;
    check(reconciled?.spending?.actual_cost != null, 'Actual generation cost unavailable');
    return { actual_cost_usd: reconciled.spending.actual_cost, usage_source: 'generation-metadata', deduplicated_ledger: true };
  });
  await runCase('structured-output', async () => {
    format = { type: 'json_schema', name: 'live_check', schema_text: JSON.stringify({ type: 'object', properties: { status: { type: 'string', enum: ['READY'] } }, required: ['status'], additionalProperties: false }) };
    try {
      const strict = (report.authenticated_model_capabilities as Record<string, string>)?.structured_output === 'supported';
      if (!strict) {
        const before = posts;
        let blocked = false;
        try { await controller!.request(query('Return an object with status READY.')); }
        catch (error) { blocked = error instanceof RequestError && error.code === 'capability-unknown' && error.parameter === 'structured_output'; }
        check(blocked && posts === before, 'Unadvertised strict schema was not blocked before dispatch');
        format = {type: 'json_object'};
      }
      const result = strict ? await send(await controller!.request(query('Return a JSON object with status READY.'))) : first;
      const object = strict ? result.result?.validated_json : result.text;
      check(object && JSON.parse(object).status === 'READY', 'Structured answer invalid');
      return {...summary(result), strict_schema: strict ? 'validated' : 'unsupported in authenticated catalog; verified local rejection without dispatch', json_object: strict ? 'not separately requested' : 'validated object returned', shared_dispatch_with: strict ? null : 'whole-json-generation-and-usage'};
    } finally { format = { type: 'text' }; }
  });
  await runCase('tools-and-separately-approved-continuation', async () => {
    const selection = { scope_id: 'home', task: 'Inspect a declared synthetic population fact', collections: ['facts' as const], tools: true };
    const grant = await world!.ground(selection);
    const entry = grant.manifest.entries[0]?.id; check(entry, 'No public synthetic fact');
    toolChoice = 'auto';
    const initial = await controller!.request({ ...query('Call inspect_context once with operation inspect, entry_id ' + entry + ', other_id null, value_json null. After the tool result arrives, reply READY and do not call any more tools.', true), grounding: selection });
    await controller!.request({ action: 'send', request_id: initial.request_id });
    const tools = await terminal(initial.request_id);
    toolReasoningPresent = Boolean(tools.reasoning);
    report.tool_request_observation = {...summary(tools), tool_calls: JSON.parse(tools.tools_json ?? '[]').length};
    check(tools.status === 'tool-calls', 'Expected tool call unavailable');
    toolChoice = 'auto';
    const next = await controller!.request({ action: 'continue', request_id: initial.request_id });
    check(next.status === 'prepared' && next.request_id !== initial.request_id, 'Continuation must require its own dispatch');
    const result = await send(next);
    toolChoice = 'auto';
    return { ...summary(result), initial_tools: JSON.parse(tools.tools_json ?? '[]').length, separate_dispatch: true };
  });
  await runCase('explicit-reasoning', async () => {
    // The exact model advertises low effort; keep reasoning bounded by the
    // same total output-token ceiling and explicit spending reservation.
    await providers!.request({ action: 'save', profile: { ...profile, generation: { ...profile.generation, reasoning: { effort: 'low' } } }, expected_revision: 2 });
    return { ...summary(reasoningStream), requested_effort: 'low', reasoning_present: Boolean(reasoningStream.reasoning) || toolReasoningPresent, shared_dispatch_with: toolReasoningPresent ? 'tools-and-separately-approved-continuation' : 'streaming-generation', limitation: 'Accepted reasoning control does not guarantee that a provider returns visible reasoning text.' };
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
    return { response_status: cancelled.status, exposure_status: cancelled.exposure_status, key_removed: true };
  });
  report.status = 'passed';
}
main().catch(error => {
  // Only our fixed assertion/status messages and typed request codes are safe;
  // never forward arbitrary provider/OS errors that may carry a credential.
  const diagnostic = error instanceof LiveCheckError ? error.message : error instanceof RequestError ? error.code + '/' + error.parameter : 'Live check failed; provider/OS details withheld';
  outcomes.push({ id: activeCase, status: 'failed', diagnostic });
  console.error(activeCase + ': failed (' + diagnostic + ')');
  report.status = 'failed';
  process.exitCode = 1;
}).finally(async () => {
  controller?.close(); await providers?.close();
  await budget?.close();
  if (privateDirectory) await rm(privateDirectory, { recursive: true, force: true });
  report.finished = new Date().toISOString(); report.dispatches_lifetime = posts; report.reserved_policy_units = budget?.units ?? null;
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, preflight ? 'preflight.json' : 'evidence.json'), JSON.stringify(report, null, 2) + '\n');
  if (!preflight) {
    const target = 'E2E-013 authenticated exact-model metadata generation streaming schema tools reasoning usage and cancellation';
    const failed = report.status !== 'passed';
    const failure = failed ? '<failure message="Required live workflow did not pass; see redacted evidence.json"/>' : '';
    await writeFile(join(directory, 'junit.xml'), '<testsuites><testsuite name="WP-055-live" tests="1" failures="' + (failed ? 1 : 0) + '" errors="0" skipped="0"><testcase classname="tests.live.openrouter" name="' + target + '">' + failure + '</testcase></testsuite></testsuites>\n');
  }
  app.exit(report.status === 'failed' ? 1 : 0);
});
