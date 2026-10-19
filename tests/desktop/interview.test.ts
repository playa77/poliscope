import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import { DesktopShell } from '../../desktop/main/shell';
import type { InterviewQuestion, InterviewEdit } from '../../contracts/interview';
const options = { name: 'Interview', setup: 'blank', scope_name: 'Home', population: null, land_area: null };

it('grants preview/apply separately, preserves one operation after a lost reply, revokes old contexts', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-interview-'));
  try {
    const controller = new WorkspaceController(false, resolve('.'), '');
    await controller.choose(directory);
    const state = await controller.create(options);
    const query = { context: state.context, scope_id: 'home', domain_id: 'domain:1' };
    const question = await controller.interview(query);
    expect(question.options).toHaveLength(3);
    const edit: InterviewEdit = { query, choice_id: question.options[0].definition.id, proposal: null, population: '25', land_area: '1.5', rationale: 'Private explanation' };
    const preview = await controller.previewInterview(edit);
    expect(preview.accounts).toEqual([]);
    await expect(controller.applyInterview({ candidate_digest: 'sha256:' + '0'.repeat(64) })).rejects.toThrow();
    await controller.cancelInterview();
    await expect(controller.applyInterview({ candidate_digest: preview.candidate_digest })).rejects.toThrow();
    const candidate = await controller.previewInterview(edit);
    // Let the actual Python/SQLite commit succeed, then drop only its reply.
    const host = controller as unknown as { request: (operation: string, ...args: unknown[]) => Promise<unknown> };
    const original = host.request.bind(host);
    let drop = true;
    vi.spyOn(host, 'request').mockImplementation(async (operation, ...args) => {
      const result = await original(operation, ...args);
      if (operation === 'apply-interview' && drop) { drop = false; throw new Error('Lost reply'); }
      return result;
    });
    await expect(controller.applyInterview({ candidate_digest: candidate.candidate_digest })).rejects.toThrow('Lost reply');
    await expect(controller.cancelInterview()).rejects.toThrow('uncertain');
    await expect(controller.previewInterview(edit)).rejects.toThrow('pending apply');
    const applied = await controller.applyInterview({ candidate_digest: candidate.candidate_digest });
    expect(applied.status).toBe('applied'); expect(applied.state.branch.sequence).toBe(1);
    await expect(controller.interview(query)).rejects.toThrow();
    const current = await controller.interview({ ...query, context: applied.state.context });
    expect(current.current_commitment).toContain('interview:domain-1/option-1');
    await controller.select({ civilization_id: state.context.civilization_id, branch_id: 'main', revision_id: state.context.revision_id });
    await expect(controller.previewInterview(edit)).rejects.toThrow('Historical');
    await expect(controller.interview({ ...query, scope_id: 'foreign' })).rejects.toThrow();
    controller.clear();
    await expect(controller.interview(query)).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 120_000);

it('returns a current state on stale Apply without committing the stale proposal', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-stale-'));
  try {
    const one = new WorkspaceController(false, resolve('.'), ''), two = new WorkspaceController(false, resolve('.'), '');
    await one.choose(directory); const state = await one.create(options);
    await two.choose(directory); await two.select({ civilization_id: state.context.civilization_id, branch_id: 'main', revision_id: null });
    const query = { context: state.context, scope_id: 'home', domain_id: 'domain:3' };
    const edit: InterviewEdit = { query, choice_id: 'player:proposal', proposal: 'Unmodeled arrangement', population: null, land_area: null, rationale: '' };
    const p1 = await one.previewInterview(edit), p2 = await two.previewInterview({ ...edit, proposal: 'Other arrangement' });
    const accepted = await two.applyInterview({ candidate_digest: p2.candidate_digest });
    const stale = await one.applyInterview({ candidate_digest: p1.candidate_digest });
    expect(stale.status).toBe('stale'); expect(stale.state.context).toEqual(accepted.state.context);
    expect(stale.state.branch.sequence).toBe(1);
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 120_000);

it('rejects unauthorized callers, executable payloads and extra arguments on every interview endpoint', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { interview: vi.fn(), previewInterview: vi.fn(), applyInterview: vi.fn(), cancelInterview: vi.fn() };
  const authorize = vi.fn<() => void>(() => { throw new Error('Untrusted caller'); });
  registerShellIPC((channel, handler) => handlers.set(channel, handler), authorize, service as unknown as DesktopShell, vi.fn());
  for (const channel of ['interview:read', 'interview:preview', 'interview:apply', 'interview:cancel']) {
    await expect(handlers.get(channel)!({} as IpcMainInvokeEvent)).rejects.toThrow(IPC_ERROR);
  }
  authorize.mockImplementation(() => {});
  for (const [channel, args] of [ ['interview:read', [{ context: {}, path: '/etc' }]], ['interview:preview', [{ changes: [], code: 'execute' }]],
    ['interview:apply', [{ candidate_digest: 'sha256:' + '0'.repeat(64), operation_id: 'forged' }]], ['interview:cancel', ['extra']] ] as [string, unknown[]][]) {
    await expect(handlers.get(channel)!({} as IpcMainInvokeEvent, ...args)).rejects.toThrow(IPC_ERROR);
  }
  for (const action of Object.values(service)) expect(action).not.toHaveBeenCalled();
});

it('coalesces obsolete queued interviews and lets a new-world action supersede queued reads', async () => {
  const shell = new DesktopShell(false, resolve('.'), '');
  let release!: (question: InterviewQuestion) => void;
  const read = vi.spyOn(WorkspaceController.prototype, 'interview').mockImplementation(input =>
    input === 'first' || input === 'blocker' ? new Promise(resolve => { release = resolve; }) : Promise.resolve({} as InterviewQuestion));
  const create = vi.spyOn(WorkspaceController.prototype, 'create').mockResolvedValue({} as never);
  try {
    const first = shell.interview('first');
    await vi.waitFor(() => expect(read).toHaveBeenCalledWith('first'));
    const old = shell.interview('old').catch(error => error.message);
    const latest = shell.interview('latest');
    release({} as InterviewQuestion);
    await first; expect(await old).toContain('superseded'); await latest;
    expect(read.mock.calls.map(call => call[0])).toEqual(['first', 'latest']);
    const blocker = shell.interview('blocker');
    await vi.waitFor(() => expect(read).toHaveBeenCalledWith('blocker'));
    const obsolete = shell.interview('old-context').catch(error => error.message);
    const creation = shell.createWorld(options);
    release({} as InterviewQuestion);
    await blocker; expect(await obsolete).toContain('superseded'); await creation;
    expect(read).toHaveBeenCalledTimes(3); expect(create).toHaveBeenCalledWith(options);
  } finally { read.mockRestore(); create.mockRestore(); await shell.stop(); }
});
