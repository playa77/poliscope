"""Trusted-host revision services. No public IPC or implicit player authorization.

Schema-1 immutable records are sufficient: branch states form append-only journals.
BEGIN IMMEDIATE serializes read/check/write; all retained effects share that commit.
"""
import json
from uuid import uuid4
from pydantic import TypeAdapter
from poliscope_engine.contracts.base import Identifier
from poliscope_engine.contracts.revisions import (
    RevisionInputs, CreateRequest, PreviewRequest, ApplyRequest, Candidate,
    BranchRequest, BranchState, RevisionRecord, MutationOutcome, DecisionArchive,
    HistoryQuery, HistoryPage, RevisionSummary, ObservationDifference)
from poliscope_engine.contracts.world import (
    RevisionContext, WorldInspectParams, WorldPageResult)
from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph
from poliscope_engine.evaluation import evaluate
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.measurements import observe
from poliscope_engine.explanation import retain, read_retained
from poliscope_engine.numeric import RUNTIME_ID

MAX_BLOB_BYTES = 64 * 1024 * 1024
CHUNK_CHARACTERS = 100000  # JSON escapes and 4-byte UTF-8 remain below storage's 1 MiB.
EMPTY_DECISION = DecisionArchive(alternatives=[], selected_id=None, rationale_ref=None)


class RevisionError(ValueError):
    pass


def checked(model, value):
    return model.model_validate_json(value.model_dump_json())


def graph(inputs, civilization_id):
    registry = WorldRegistry(civilization_id, entities=inputs.entities, scopes=inputs.scopes,
        values=inputs.values, owners=[StateOwner(**o.model_dump()) for o in inputs.owners],
        populations=[PopulationDeclaration(**p.model_dump()) for p in inputs.populations])
    return WorldGraph(registry, inputs.relationships)


class Revisions:
    """Bound to one main-selected Store and trusted executable mechanism registry.

    The host must authorize civilization/context access before constructing calls.
    Store/civilization/branch are checked on every read, mutation and status query.
    Historical reads do not require the current model to remain executable.
    """
    def __init__(self, store, *, registry):
        self.store, self.registry = store, registry
        with store.transaction():
            metadata = store.read_context('revision-service:v1')
            if metadata is None:
                metadata = serialized(dict(data_store_id='store:' + str(uuid4()), revision_contract=1))
                store.add_context('revision-service:v1', metadata)
            self.data_store_id = json.loads(metadata)['data_store_id']

    def _scope(self, store_id, civ):
        TypeAdapter(Identifier).validate_python(civ, strict=True)
        if store_id != self.data_store_id:
            raise RevisionError('wrong_data_store')
        return digest(dict(store=self.data_store_id, civilization=civ))

    def _context(self, context):
        context = checked(RevisionContext, context)
        scope = self._scope(context.data_store_id, context.civilization_id)
        if self.store.read_context(scope) is None:
            raise RevisionError('unknown_civilization')
        return scope

    def open(self, *, data_store_id, civilization_id, branch_id):
        """Open the latest confirmed branch without evaluating or rewriting it."""
        context = RevisionContext(data_store_id=data_store_id, civilization_id=civilization_id,
                                  branch_id=branch_id, revision_id='head')
        return self.branch(context)

    def _kind(self, branch):
        TypeAdapter(Identifier).validate_python(branch, strict=True)
        return 'branch:' + digest(branch)

    def branch(self, context):
        scope = self._context(context)
        rows = self.store.record_page(scope, self._kind(context.branch_id), limit=1, descending=True)
        if not rows:
            raise RevisionError('unknown_branch')
        return BranchState.model_validate_json(rows[0][1])

    def _save_branch(self, scope, state):
        if state.sequence > 9007199254740991:
            raise RevisionError('branch_sequence_exhausted')
        self.store.add_record(scope, self._kind(state.context.branch_id),
                              f'{state.sequence:016d}', state.model_dump_json())

    def _blob(self, scope, kind, identity, payload):
        text = serialized(payload)
        if len(text.encode()) > MAX_BLOB_BYTES:
            raise RevisionError('retained_snapshot_too_large')
        chunks = [text[i:i + CHUNK_CHARACTERS] for i in range(0, len(text), CHUNK_CHARACTERS)]
        for i, chunk in enumerate(chunks):
            self.store.add_record(scope, 'chunk:' + kind, identity + ':' + str(i), serialized(chunk))
        self.store.add_record(scope, kind, identity, serialized(dict(chunks=len(chunks), digest=digest(text))))

    def _read_blob(self, scope, kind, identity):
        manifest = self.store.read_record(scope, kind, identity)
        if manifest is None:
            raise RevisionError('unknown_' + kind)
        manifest = json.loads(manifest)
        count = manifest['chunks']
        if type(count) is not int or not 1 <= count <= MAX_BLOB_BYTES // CHUNK_CHARACTERS + 1:
            raise RevisionError('invalid_snapshot_manifest')
        chunks, size = [], 0
        for i in range(count):
            raw = self.store.read_record(scope, 'chunk:' + kind, identity + ':' + str(i))
            if raw is None:
                raise RevisionError('unavailable_snapshot_chunk')
            chunk = json.loads(raw)
            if not isinstance(chunk, str) or len(chunk) > CHUNK_CHARACTERS:
                raise RevisionError('invalid_snapshot_chunk')
            size += len(chunk.encode())
            if size > MAX_BLOB_BYTES:
                raise RevisionError('retained_snapshot_too_large')
            chunks.append(chunk)
        text = ''.join(chunks)
        if digest(text) != manifest['digest']:
            raise RevisionError('snapshot_identity_mismatch')
        return text

    def read(self, context):
        scope = self._context(context)
        self.branch(context)  # branch existence and civilization authorization
        record = RevisionRecord.model_validate_json(self._read_blob(scope, 'revision', context.revision_id))
        # Forks may legitimately read a revision originally accepted on another branch.
        if (record.context.data_store_id, record.context.civilization_id) != (context.data_store_id, context.civilization_id):
            raise RevisionError('revision_context_mismatch')
        return record

    def evidence(self, context):
        record = self.read(context)
        scope = self._context(context)
        saved = read_retained(self._read_blob(scope, 'accepted', context.revision_id))
        if saved.closure_digest != record.evidence_digest:
            raise RevisionError('revision_evidence_mismatch')
        return saved

    def _evaluate(self, inputs, civilization_id):
        inputs = checked(RevisionInputs, inputs)
        if (self.registry is None or inputs.versions.model_id != self.registry.model[0] or
                inputs.versions.numeric_runtime_id != RUNTIME_ID):
            raise RevisionError('unavailable_model_or_numeric_runtime')
        result = evaluate(graph(inputs, civilization_id), inputs.design, inputs.assumptions,
                          self.registry.model, registry=self.registry)
        report = observe(result, inputs.measurements, inputs.goals)
        return retain(result, report, inputs.references)

    def _operation(self, scope, kind, operation_id, request):
        if kind == 'branch':
            kind = 'branch:' + request.action
        key = digest(dict(kind=kind, operation_id=operation_id))
        binding = serialized(dict(revision_contract=1, store=self.data_store_id, kind=kind, request=request))
        old = self.store.operation_outcome(scope, key, binding)
        return key, binding, MutationOutcome.model_validate_json(old) if old else None

    def status(self, kind, request):
        """Exact authorized request lookup. Unknown never implies a safe new ID.

        Synchronous transactions have no externally visible pending state; rejected
        requests do not create terminal records. Only confirmed completions replay.
        """
        model = {'create': CreateRequest, 'apply': ApplyRequest, 'branch': BranchRequest}.get(kind)
        if model is None:
            raise RevisionError('unknown_operation_kind')
        request = checked(model, request)
        if kind == 'create':
            scope = self._scope(request.data_store_id, request.civilization_id)
        else:
            context = request.preview.context if kind == 'apply' else request.context
            scope = self._context(context)
            self.branch(context)
        return self._operation(scope, kind, request.operation_id, request)[2]

    def _identities(self, scope, inputs, *, publish=False):
        """Reserve canonical meanings across deleted/reintroduced branch futures."""
        descriptions = []
        for row in inputs.entities:
            descriptions.append((row.id, dict(kind='entity', entity_kind=row.entity_kind)))
        for row in inputs.scopes:
            descriptions.append((row.id, dict(kind='scope', scope_kind=row.scope_kind)))
        for row in inputs.values:
            descriptions.append((row.id, dict(kind='value', entity_id=row.entity_id,
                scope_id=row.scope_id, property_id=row.property_id, partition=row.partition)))
        for row in inputs.relationships:
            descriptions.append((row.id, dict(kind='relationship', relationship_kind=row.relationship_kind,
                from_id=row.from_id, to_id=row.to_id)))
        for identity, description in descriptions:
            text = serialized(description)
            old = self.store.read_record(scope, 'canonical_identity', identity)
            if old is not None and old != text:
                raise RevisionError('canonical_identity_rebound')
            if publish and old is None:
                self.store.add_record(scope, 'canonical_identity', identity, text)

    def _persist(self, scope, record, evidence):
        self._identities(scope, record.inputs, publish=True)
        self._blob(scope, 'revision', record.context.revision_id, record)
        self._blob(scope, 'accepted', record.context.revision_id, evidence)
        previous = self.store.record_page(scope, 'revision_index', limit=1, descending=True)
        sequence = int(previous[0][0]) + 1 if previous else 0
        if sequence > 9007199254740991:
            raise RevisionError('history_sequence_exhausted')
        self.store.add_record(scope, 'revision_index', f'{sequence:016d}',
            RevisionSummary(context=record.context, parent_id=record.parent_id,
                            evidence_digest=record.evidence_digest).model_dump_json())

    def create(self, request):
        request = checked(CreateRequest, request)
        scope = self._scope(request.data_store_id, request.civilization_id)
        with self.store.transaction():
            key, binding, old = self._operation(scope, 'create', request.operation_id, request)
            if old:
                return old
            if self.store.read_context(scope) is not None:
                raise RevisionError('civilization_exists')
            evidence = self._evaluate(request.inputs, request.civilization_id)
            revision_id = digest(dict(create=request))
            context = RevisionContext(data_store_id=self.data_store_id, civilization_id=request.civilization_id,
                                      branch_id=request.branch_id, revision_id=revision_id)
            record = RevisionRecord(revision_contract=1, context=context, parent_id=None,
                inputs=request.inputs, decision=EMPTY_DECISION, evidence_digest=evidence.closure_digest, applied_preview=None)
            self.store.add_context(scope, serialized(dict(civilization_id=request.civilization_id)))
            self._persist(scope, record, evidence)
            self._save_branch(scope, BranchState(revision_contract=1, context=context,
                name=request.name, sequence=0, redo=[], forked_from=None))
            outcome = MutationOutcome(revision_contract=1, context=context, branch_sequence=0)
            self.store.complete_operation(scope, key, binding, outcome.model_dump_json())
            return outcome

    def _stage(self, request):
        base = self.read(request.context)
        inputs = base.inputs
        selected = request.decision.selected_id
        alternatives = {a.id: a for a in request.decision.alternatives}
        if len(alternatives) != len(request.decision.alternatives):
            raise RevisionError('duplicate_alternative')
        if selected is not None and (selected not in alternatives or alternatives[selected].changes != request.changes):
            raise RevisionError('selected_alternative_mismatch')
        for change in request.changes:
            if change.kind == 'replace_inputs':
                inputs = checked(RevisionInputs, change.inputs)
                if inputs.versions != base.inputs.versions:
                    raise RevisionError('model_migration_requires_separate_branch_service')
                graph(inputs, request.context.civilization_id)
            else:
                world = graph(inputs, request.context.civilization_id)
                staged = world.registry.with_values(writer_id=change.writer_id,
                    partition=change.partition, changes=change.values)
                inputs = checked(RevisionInputs, inputs.model_copy(update={'values': list(staged.values)}))
        self._identities(self._context(request.context), inputs)
        evidence = self._evaluate(inputs, request.context.civilization_id)
        before = {v.id: v for v in base.inputs.values}
        after = {v.id: v for v in inputs.values}
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        # Whole structure/design changes conservatively affect all old/new scopes.
        affected = sorted({s.id for s in base.inputs.scopes} | {s.id for s in inputs.scopes})
        prior = self.evidence(request.context).evaluation
        previous = {tuple(o.node): o for o in prior.observations}
        current = {tuple(o.node): o for o in evidence.evaluation.observations}
        differences = [ObservationDifference(node=list(k), before=previous.get(k), after=current.get(k))
            for k in sorted(previous.keys() | current.keys()) if previous.get(k) != current.get(k)]
        payload = dict(request=request, inputs_digest=digest(inputs), evidence_digest=evidence.closure_digest)
        candidate = Candidate(revision_contract=1, request=request, candidate_digest=digest(payload),
            inputs_digest=payload['inputs_digest'], evidence_digest=evidence.closure_digest,
            affected_scope_ids=affected, changed_value_ids=changed, report=evidence.report, differences=differences)
        return inputs, evidence, candidate

    def preview(self, request):
        request = checked(PreviewRequest, request)
        # Previewing an immutable historical revision is useful; apply checks head.
        return self._stage(request)[2]

    def apply(self, request):
        request = checked(ApplyRequest, request)
        context = request.preview.context
        scope = self._context(context)
        with self.store.transaction():
            self.branch(context)
            key, binding, old = self._operation(scope, 'apply', request.operation_id, request)
            if old:
                return old
            state = self.branch(context)
            if state.context.revision_id != context.revision_id:
                raise RevisionError('stale_revision')
            inputs, evidence, candidate = self._stage(request.preview)
            if candidate.candidate_digest != request.candidate_digest:
                raise RevisionError('candidate_digest_mismatch')
            revision_id = digest(dict(apply=request, sequence=state.sequence + 1))
            new_context = context.model_copy(update={'revision_id': revision_id})
            record = RevisionRecord(revision_contract=1, context=new_context, parent_id=context.revision_id,
                inputs=inputs, decision=request.preview.decision, evidence_digest=evidence.closure_digest,
                applied_preview=request.preview)
            self._persist(scope, record, evidence)
            state = checked(BranchState, state.model_copy(update=dict(context=new_context,
                sequence=state.sequence + 1, redo=[])))
            self._save_branch(scope, state)
            outcome = MutationOutcome(revision_contract=1, context=new_context, branch_sequence=state.sequence)
            self.store.complete_operation(scope, key, binding, outcome.model_dump_json())
            return outcome

    def change_branch(self, request):
        request = checked(BranchRequest, request)
        scope = self._context(request.context)
        with self.store.transaction():
            key, binding, old = self._operation(scope, 'branch', request.operation_id, request)
            if old:
                return old
            state = self.branch(request.context)
            if state.context != request.context or state.sequence != request.expected_sequence:
                raise RevisionError('stale_branch')
            if (request.action == 'fork') != (request.new_branch_id is not None):
                raise RevisionError('invalid_new_branch')
            if (request.action in ('fork', 'rename')) != (request.name is not None):
                raise RevisionError('invalid_branch_name')
            updates = dict(sequence=state.sequence + 1)
            if request.action == 'fork':
                if self.store.record_page(scope, self._kind(request.new_branch_id), limit=1):
                    raise RevisionError('branch_exists')
                updates = dict(sequence=0, redo=[], name=request.name, forked_from=state.context,
                    context=state.context.model_copy(update={'branch_id': request.new_branch_id}))
            elif request.action == 'rename':
                updates['name'] = request.name
            elif request.action == 'undo':
                parent = self.read(state.context).parent_id
                if parent is None:
                    raise RevisionError('no_undo')
                updates.update(context=state.context.model_copy(update={'revision_id': parent}),
                               redo=state.redo + [state.context.revision_id])
            else:
                if not state.redo:
                    raise RevisionError('no_redo')
                updates.update(context=state.context.model_copy(update={'revision_id': state.redo[-1]}),
                               redo=state.redo[:-1])
            state = checked(BranchState, state.model_copy(update=updates))
            self._save_branch(scope, state)
            outcome = MutationOutcome(revision_contract=1, context=state.context, branch_sequence=state.sequence)
            self.store.complete_operation(scope, key, binding, outcome.model_dump_json())
            return outcome

    def history(self, query):
        query = checked(HistoryQuery, query)
        scope = self._context(query.context)
        self.branch(query.context)
        # Acceptance order across all civilization futures, including undone heads.
        prefix = digest(dict(context=query.context, kind='revision_index'))
        after = None
        if query.cursor is not None:
            if not query.cursor.startswith(prefix + ':'):
                raise RevisionError('invalid_history_cursor')
            after = query.cursor[len(prefix) + 1:]
            if self.store.read_record(scope, 'revision_index', after) is None:
                raise RevisionError('invalid_history_cursor')
        rows = self.store.record_page(scope, 'revision_index', after=after, limit=query.limit)
        more = rows and self.store.record_page(scope, 'revision_index', after=rows[-1][0], limit=1)
        return HistoryPage(items=[RevisionSummary.model_validate_json(v) for _, v in rows],
                           next_cursor=prefix + ':' + rows[-1][0] if more else None)

    def inspect(self, query):
        query = checked(WorldInspectParams, query)
        record = self.read(query.context)
        inputs = record.inputs
        # Mechanism instances are execution bindings, not policy inheritance DTOs.
        if query.collection == 'mechanisms':
            raise RevisionError('use_revision_design_execution_bindings')
        rows = sorted(getattr(inputs, query.collection), key=lambda r: r.id)
        prefix = digest(dict(context=query.context, collection=query.collection))
        offset = 0
        if query.cursor is not None:
            try:
                key, raw = query.cursor.rsplit(':', 1)
                offset = int(raw)
                if key != prefix or str(offset) != raw or not 0 < offset < len(rows):
                    raise ValueError()
            except ValueError as exc:
                raise RevisionError('invalid_world_cursor') from exc
        end = min(offset + query.limit, len(rows))
        result = WorldPageResult(kind='world_page', context=query.context, versions=inputs.versions,
            effective_time=inputs.design.effective_time, page=dict(kind=query.collection,
                items=[r.model_dump() for r in rows[offset:end]],
                next_cursor=prefix + ':' + str(end) if end < len(rows) else None))
        if len(result.model_dump_json().encode()) > 900000:
            raise RevisionError('world_page_requires_smaller_limit')
        return result
