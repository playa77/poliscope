"""Trusted-host revision services. No public IPC or implicit player authorization.

Schema-1 immutable records are sufficient: branch states form append-only journals.
BEGIN IMMEDIATE serializes read/check/write; all retained effects share that commit.
"""
import json
from bisect import bisect_right
from hashlib import sha256
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
from poliscope_engine.evaluation import EvaluationCache
from poliscope_engine.work_limits import checkpoint, limited, WorkLimits
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.measurements import observe
from poliscope_engine.explanation import retain, read_retained
from poliscope_engine.numeric import RUNTIME_ID

MAX_BLOB_BYTES = 64 * 1024 * 1024
CHUNK_CHARACTERS = 100000  # JSON escapes and 4-byte UTF-8 remain below storage's 1 MiB.
EMPTY_DECISION = DecisionArchive(alternatives=[], selected_id=None, rationale_ref=None)
_GRAPH_SHAPES = {}
_GRAPH_BYTES = 0


class RevisionError(ValueError):
    pass


def checked(model, value):
    return model.model_validate_json(value.model_dump_json())


def graph(inputs, civilization_id):
    global _GRAPH_BYTES
    # Every source byte participates; a forged DTO or changed owner cannot reuse
    # a previous shape. Values are revalidated separately for every new snapshot.
    shape = inputs.model_dump_json(include={'entities', 'scopes', 'owners', 'populations', 'relationships'})
    key = civilization_id, shape
    previous = _GRAPH_SHAPES.get(key)
    if previous is not None:
        _GRAPH_SHAPES[key] = _GRAPH_SHAPES.pop(key)
        return previous[0].with_registry(previous[0].registry._replace_values(inputs.values))
    registry = WorldRegistry(civilization_id, entities=inputs.entities, scopes=inputs.scopes,
        values=inputs.values, owners=[StateOwner(**o.model_dump()) for o in inputs.owners],
        populations=[PopulationDeclaration(**p.model_dump()) for p in inputs.populations])
    result = WorldGraph(registry, inputs.relationships)
    size = 2 * len(shape.encode())
    size += sum(len(row.encode()) for row in registry._values)
    if size <= 64 * 1024 * 1024:
        while _GRAPH_SHAPES and (len(_GRAPH_SHAPES) == 2 or _GRAPH_BYTES + size > 64 * 1024 * 1024):
            oldest = next(iter(_GRAPH_SHAPES))
            _GRAPH_BYTES -= _GRAPH_SHAPES.pop(oldest)[1]
        _GRAPH_SHAPES[key] = result, size
        _GRAPH_BYTES += size
    return result


class Revisions:
    """Bound to one main-selected Store and trusted executable mechanism registry.

    The host must authorize civilization/context access before constructing calls.
    Store/civilization/branch are checked on every read, mutation and status query.
    Historical reads do not require the current model to remain executable.
    """
    def __init__(self, store, *, registry, limits=None):
        self.store, self.registry = store, registry
        self.limits = limits
        self.cache = EvaluationCache(incremental_bytes=4 * 1024 * 1024)
        self._verified_evidence = {}
        self._assembled_evidence = {}
        self._assembled_bytes = 0
        self._assembled_checksums = {}
        self._assembly_witnesses = {}
        with store.transaction():
            metadata = store.read_context('revision-service:v1')
            if metadata is None:
                metadata = serialized(dict(data_store_id='store:' + str(uuid4()), revision_contract=1))
                store.add_context('revision-service:v1', metadata)
            self.data_store_id = json.loads(metadata)['data_store_id']

    def create_chunks(self, chunks, *, expected_sha256, cancelled=None):
        from poliscope_engine.ingestion import decode_chunks
        request = decode_chunks(chunks, expected_sha256=expected_sha256,
            model=CreateRequest, cancelled=cancelled)
        with limited(WorkLimits(cancelled=cancelled)):
            return self.create(request)

    def preview_chunks(self, chunks, *, expected_sha256, cancelled=None):
        from poliscope_engine.ingestion import decode_chunks
        request = decode_chunks(chunks, expected_sha256=expected_sha256,
            model=PreviewRequest, cancelled=cancelled)
        with limited(WorkLimits(cancelled=cancelled)):
            return self.preview(request)

    def apply_chunks(self, chunks, *, expected_sha256, cancelled=None):
        from poliscope_engine.ingestion import decode_chunks
        request = decode_chunks(chunks, expected_sha256=expected_sha256,
            model=ApplyRequest, cancelled=cancelled)
        with limited(WorkLimits(cancelled=cancelled)):
            return self.apply(request)

    def catalogue(self):
        """Latest confirmed branches of the main-authorized local store."""
        latest = {}
        for scope, kind, _, payload in self.store.revision_catalogue_rows():
            if (scope, kind) in latest:
                continue
            state = BranchState.model_validate_json(payload)
            if self._context(state.context) != scope or self._kind(state.context.branch_id) != kind:
                raise RevisionError('invalid_branch_catalogue')
            latest[scope, kind] = state
        if len(latest) > 1000:
            raise RevisionError('branch_catalogue_too_large')
        return list(latest.values())

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
            checkpoint('retaining')
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
        text = self._read_blob(scope, 'accepted', context.revision_id)
        # Always read and integrity-check every retained chunk. Only the costly
        # semantic closure verification can be reused for these exact bytes.
        # A marker holds no DTOs, registry authority or mutable result state.
        key = sha256(text.encode()).hexdigest()
        if key in self._verified_evidence:
            from poliscope_engine.contracts.measurements import AcceptedEvidence
            saved = AcceptedEvidence.model_validate_json(text)
            self._verified_evidence[key] = self._verified_evidence.pop(key)
        else:
            saved = read_retained(text)
            if len(self._verified_evidence) == 16:
                del self._verified_evidence[next(iter(self._verified_evidence))]
            self._verified_evidence[key] = True
        if saved.closure_digest != record.evidence_digest:
            raise RevisionError('revision_evidence_mismatch')
        return saved

    def clear_caches(self):
        global _GRAPH_BYTES
        _GRAPH_SHAPES.clear()
        _GRAPH_BYTES = 0
        from poliscope_engine.evaluation.canonical import clear
        from poliscope_engine.measurements import clear_observation_cache
        from poliscope_engine.verification import clear as clear_verifications
        from poliscope_engine.readonly import clear as clear_readonly
        from poliscope_engine.explanation import _trace_plans, _reference_sets
        clear()
        clear_observation_cache()
        clear_verifications()
        clear_readonly()
        _trace_plans.clear()
        _reference_sets.clear()
        if self.registry is not None:
            self.registry._compiled_dependencies.clear()
            object.__setattr__(self.registry, '_compiled_bytes', 0)
        self.cache.clear()
        self._verified_evidence.clear()
        self._assembled_evidence.clear()
        self._assembled_bytes = 0
        self._assembled_checksums.clear()
        self._assembly_witnesses.clear()

    def _assembly_key(self, inputs, evidence, civilization_id):
        return (civilization_id, self.registry._cache_token,
            sha256(inputs.model_dump_json().encode()).digest(),
            sha256(evidence.model_dump_json().encode()).digest())

    def _witness_assembly(self, inputs, evidence, civilization_id):
        key = self._assembly_key(inputs, evidence, civilization_id)
        if len(self._assembly_witnesses) == 8:
            del self._assembly_witnesses[next(iter(self._assembly_witnesses))]
        self._assembly_witnesses[key] = True

    def _matches_assembly(self, inputs, evidence, civilization_id):
        return self.registry is not None and self._assembly_key(inputs, evidence, civilization_id) in self._assembly_witnesses

    def _evaluate(self, inputs, civilization_id):
        inputs = checked(RevisionInputs, inputs)
        if (self.registry is None or inputs.versions.model_id != self.registry.model[0] or
                inputs.versions.numeric_runtime_id != RUNTIME_ID):
            raise RevisionError('unavailable_model_or_numeric_runtime')
        result = self.cache.evaluate(graph(inputs, civilization_id), inputs.design, inputs.assumptions,
                          self.registry.model, registry=self.registry)
        # Fresh physical identity/review preparation above is mandatory even on
        # a hit. Measurement, goal and reference content have separate authority
        # and must also bind the complete retained closure.
        key = digest(dict(physical=result.identities.output_digest,
            measurements=inputs.measurements, goals=inputs.goals, references=inputs.references))
        payload = self._assembled_evidence.get(key)
        if payload is not None and sha256(payload).digest() != self._assembled_checksums.get(key):
            self._assembled_bytes -= len(self._assembled_evidence.pop(key))
            self._assembled_checksums.pop(key, None)
            payload = None
        if payload is not None:
            from poliscope_engine.contracts.measurements import AcceptedEvidence
            checkpoint('retained_cache_hit', size=len(payload))
            self._assembled_evidence[key] = self._assembled_evidence.pop(key)
            saved = AcceptedEvidence.model_validate_json(payload)
            self._witness_assembly(inputs, saved, civilization_id)
            return saved
        checkpoint('measurements')
        report = observe(result, inputs.measurements, inputs.goals)
        saved = retain(result, report, inputs.references)
        payload = saved.model_dump_json().encode()
        checkpoint('retained', size=len(payload))
        if len(payload) <= 64 * 1024 * 1024:
            while self._assembled_evidence and (len(self._assembled_evidence) >= 8 or
                    self._assembled_bytes + len(payload) > 64 * 1024 * 1024):
                oldest = next(iter(self._assembled_evidence))
                self._assembled_bytes -= len(self._assembled_evidence.pop(oldest))
                self._assembled_checksums.pop(oldest, None)
            self._assembled_evidence[key] = payload
            self._assembled_checksums[key] = sha256(payload).digest()
            self._assembled_bytes += len(payload)
        self._witness_assembly(inputs, saved, civilization_id)
        return saved

    def _operation(self, scope, kind, operation_id, request):
        if kind == 'branch':
            kind = 'branch:' + request.action
        key = digest(dict(kind=kind, operation_id=operation_id))
        binding = serialized(dict(revision_contract=1, store=self.data_store_id, kind=kind, request=request))
        if len(binding.encode()) > 1024 * 1024:
            # Operation bindings remain single bounded storage records. The
            # complete immutable request is bound by its canonical digest; it
            # never needs to be duplicated in the operation journal.
            payload = dict(revision_contract=1, store=self.data_store_id,
                kind=kind, request_digest=digest(request))
            if kind == 'model-migration':
                payload['recovery'] = dict(context=request.context,
                    operation_id=request.operation_id, new_branch_id=request.new_branch_id, name=request.name)
            binding = serialized(payload)
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
        checkpoint('persisting')
        self._identities(scope, record.inputs, publish=True)
        self._blob(scope, 'revision', record.context.revision_id, record)
        self._blob(scope, 'accepted', record.context.revision_id, evidence)
        self._index_world(scope, record)
        previous = self.store.record_page(scope, 'revision_index', limit=1, descending=True)
        sequence = int(previous[0][0]) + 1 if previous else 0
        if sequence > 9007199254740991:
            raise RevisionError('history_sequence_exhausted')
        self.store.add_record(scope, 'revision_index', f'{sequence:016d}',
            RevisionSummary(context=record.context, parent_id=record.parent_id,
                            evidence_digest=record.evidence_digest).model_dump_json())

    def _index_world(self, scope, record):
        """Derived read projections of the immutable canonical revision.

        Each block is individually hash-checked and bounded; metadata permits
        an arbitrary <=100-row page without loading the complete world. Legacy
        snapshots keep the verified full-reader fallback. These projections
        never supply simulation inputs or replace retained accepted evidence.
        """
        for collection in ('entities', 'scopes', 'relationships', 'values'):
            kind = 'world-page:' + digest([record.context.revision_id, collection])
            blocks, items, size, offset = [], [], 2, 0
            def save():
                nonlocal items, size, offset
                if not items:
                    return
                payload = '[' + ','.join(items) + ']'
                self.store.add_record(scope, kind, f'{len(blocks):06d}', payload)
                blocks.append(dict(offset=offset, count=len(items), digest=digest(payload)))
                offset += len(items)
                items, size = [], 2
            for row in sorted(getattr(record.inputs, collection), key=lambda r: r.id):
                checkpoint('indexing_world')
                encoded = serialized(row)
                cost = len(encoded.encode()) + 1
                if cost > 750000:
                    raise RevisionError('world_row_requires_chunking')
                if len(items) == 100 or size + cost > 750000:
                    save()
                items.append(encoded)
                size += cost
            save()
            metadata = dict(
                projection_version=1, versions=record.inputs.versions,
                effective_time=record.inputs.design.effective_time, total=offset, blocks=blocks)
            self.store.add_record(scope, kind, 'metadata', serialized(dict(
                metadata, projection_digest=digest(metadata))))

    def _indexed_world_page(self, query):
        scope = self._context(query.context)
        self.branch(query.context)
        kind = 'world-page:' + digest([query.context.revision_id, query.collection])
        metadata = self.store.read_record(scope, kind, 'metadata')
        if metadata is None:
            return None
        metadata = json.loads(metadata)
        checksum = metadata.pop('projection_digest', None)
        if checksum != digest(metadata):
            raise RevisionError('invalid_world_projection')
        if metadata.get('projection_version') != 1:
            raise RevisionError('invalid_world_projection')
        prefix = digest(dict(context=query.context, collection=query.collection))
        offset = 0
        if query.cursor is not None:
            try:
                bound, raw = query.cursor.rsplit(':', 1)
                offset = int(raw)
                if bound != prefix or str(offset) != raw or not 0 < offset < metadata['total']:
                    raise ValueError()
            except ValueError as error:
                raise RevisionError('invalid_world_cursor') from error
        blocks = metadata['blocks']
        starts = [b['offset'] for b in blocks]
        index = max(0, bisect_right(starts, offset) - 1)
        items, size = [], 0
        for number in range(index, len(blocks)):
            block = blocks[number]
            payload = self.store.read_record(scope, kind, f'{number:06d}')
            if payload is None or digest(payload) != block['digest']:
                raise RevisionError('unavailable_world_projection')
            rows = json.loads(payload)
            if len(rows) != block['count']:
                raise RevisionError('invalid_world_projection')
            for row in rows[max(0, offset - block['offset']):]:
                cost = len(serialized(row).encode()) + 1
                if len(items) == query.limit or size + cost > 750000:
                    break
                items.append(row)
                size += cost
            if len(items) == query.limit:
                break
            # A byte-limited partial block must continue on the next request.
            if offset + len(items) < block['offset'] + block['count']:
                break
        end = offset + len(items)
        if not items and offset < metadata['total']:
            raise RevisionError('world_row_requires_chunking')
        return WorldPageResult(kind='world_page', context=query.context,
            versions=metadata['versions'], effective_time=metadata['effective_time'],
            page=dict(kind=query.collection, items=items,
                next_cursor=f'{prefix}:{end}' if end < metadata['total'] else None))

    def create(self, request):
        with limited(self.limits):
            return self._create_limited(request)

    def _create_limited(self, request):
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
            checkpoint('confirming')
            self.store.complete_operation(scope, key, binding, outcome.model_dump_json())
            return outcome

    def migration_status(self, context, operation_id, branch_id, name):
        """Main-authorized recovery before loading the currently installed model."""
        from poliscope_engine.contracts.recovery import ModelMigration
        scope = self._context(context)
        key = digest(dict(kind='model-migration', operation_id=operation_id))
        row = self.store._connection.execute(
            'SELECT binding FROM operations WHERE context_id=? AND id=?', (scope, key)).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        if 'recovery' in payload:
            if payload['recovery'] != dict(context=context.model_dump(mode='json'),
                    operation_id=operation_id, new_branch_id=branch_id, name=name):
                raise RevisionError('migration_recovery_binding_mismatch')
            outcome = self.store.operation_outcome(scope, key, row[0])
            return MutationOutcome.model_validate_json(outcome) if outcome else None
        saved = ModelMigration.model_validate(payload['request'])
        if (saved.context != context or saved.operation_id != operation_id or
                saved.new_branch_id != branch_id or saved.name != name):
            raise RevisionError('migration_recovery_binding_mismatch')
        return self._operation(scope, 'model-migration', operation_id, saved)[2]

    def migrate_model(self, request):
        with limited(self.limits):
            return self._migrate_model_limited(request)

    def _migrate_model_limited(self, request):
        """Player-approved compatible inputs become a new branch and new evidence.

        The source head is never moved. Replays return before source/head/model
        checks, including after a restart or restored operation journal.
        """
        from poliscope_engine.contracts.recovery import ModelMigration
        request = checked(ModelMigration, request)
        scope = self._context(request.context)
        with self.store.transaction():
            key, binding, old = self._operation(scope, 'model-migration', request.operation_id, request)
            if old:
                return old
            base = self.read(request.context)
            if self.store.record_page(scope, self._kind(request.new_branch_id), limit=1):
                raise RevisionError('migration_branch_exists')
            # An explicit migration may change versions; ordinary edits cannot.
            evidence = self._evaluate(request.inputs, request.context.civilization_id)
            context = request.context.model_copy(update={'branch_id': request.new_branch_id,
                'revision_id': digest(dict(migration=request))})
            record = RevisionRecord(revision_contract=1, context=context,
                parent_id=base.context.revision_id, inputs=request.inputs,
                decision=EMPTY_DECISION, evidence_digest=evidence.closure_digest, applied_preview=None)
            self._persist(scope, record, evidence)
            self._save_branch(scope, BranchState(revision_contract=1, context=context,
                name=request.name, sequence=0, redo=[], forked_from=request.context))
            outcome = MutationOutcome(revision_contract=1, context=context, branch_sequence=0)
            checkpoint('confirming')
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
        with limited(self.limits):
            return self._preview_limited(request)

    def _preview_limited(self, request):
        request = checked(PreviewRequest, request)
        # Previewing an immutable historical revision is useful; apply checks head.
        candidate = self._stage(request)[2]
        checkpoint('preview_complete')
        return candidate

    def apply(self, request):
        with limited(self.limits):
            return self._apply_limited(request)

    def _apply_limited(self, request):
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
            if state.redo:
                self._retain_future(scope, state)
            state = checked(BranchState, state.model_copy(update=dict(context=new_context,
                sequence=state.sequence + 1, redo=[])))
            self._save_branch(scope, state)
            outcome = MutationOutcome(revision_contract=1, context=new_context, branch_sequence=state.sequence)
            checkpoint('confirming')
            self.store.complete_operation(scope, key, binding, outcome.model_dump_json())
            return outcome

    def _retain_future(self, scope, state):
        # Preserve a named head before abandoning a future. Stable IDs make
        # recovery idempotent within the enclosing transaction.
        head = state.redo[0] if state.redo else state.context.revision_id
        identity = 'retained:' + digest(dict(context=state.context, sequence=state.sequence))
        future = checked(BranchState, state.model_copy(update=dict(sequence=0, redo=[],
            name='Retained future · ' + state.name[:220], forked_from=state.context,
            context=state.context.model_copy(update=dict(branch_id=identity, revision_id=head)))))
        self._save_branch(scope, future)

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
            target = state.context
            if request.target_revision_id is not None:
                if request.action not in ('fork', 'restore'):
                    raise RevisionError('unexpected_target_revision')
                target = state.context.model_copy(update={'revision_id': request.target_revision_id})
                self.read(target)
            updates = dict(sequence=state.sequence + 1)
            if request.action == 'fork':
                if self.store.record_page(scope, self._kind(request.new_branch_id), limit=1):
                    raise RevisionError('branch_exists')
                updates = dict(sequence=0, redo=[], name=request.name, forked_from=target,
                    context=target.model_copy(update={'branch_id': request.new_branch_id}))
            elif request.action == 'restore':
                if request.target_revision_id is None:
                    raise RevisionError('restore_requires_target')
                self._retain_future(scope, state)
                updates.update(context=target, redo=[])
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
            checkpoint('confirming')
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

    def has_scope(self, context, identity):
        query = WorldInspectParams(world_schema=1, context=context,
            collection='scopes', cursor=None, limit=100)
        while True:
            page = self.inspect(query)
            if any(row.id == identity for row in page.page.items):
                return True
            if page.page.next_cursor is None:
                return False
            query = query.model_copy(update={'cursor': page.page.next_cursor})

    def inspect(self, query):
        query = checked(WorldInspectParams, query)
        if query.collection != 'mechanisms':
            indexed = self._indexed_world_page(query)
            if indexed is not None:
                return indexed
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
