"""Bounded data-only portable projections. No ZIP entry is ever extracted.

Imports create immutable historical collections, never engine registrations.
Public projected identities cannot be mistaken for original private-bound hashes.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import struct
import tempfile
import zipfile
from pydantic import ValidationError
from poliscope_engine.contracts.archives import (ArchiveOptions, ArchiveManifest,
    ArchiveEntry, ArchiveRevision, ArchiveBranch, ArchiveExperiment, ArchiveBoundary,
    ArchivePrivate, ArchiveEvidence, ArchiveSummary, ArchiveTransition, archive_item_adapter)
from poliscope_engine.contracts.boundaries import ExperimentRecord, ExperimentContext
from poliscope_engine.contracts.experiments import Checkpoint, ExperimentControl
from poliscope_engine.contracts.revisions import RevisionSummary
from poliscope_engine.boundaries import BoundaryStore, JOURNAL
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.explanation import read_retained, build_traces, _reference_closure
from poliscope_engine.storage.blobs import RetainedBlobs

MAX_ARCHIVE = 256 * 1024 * 1024
MAX_ENTRY = 64 * 1024 * 1024
MAX_MANIFEST = 1024 * 1024
MAX_ENTRIES = 10000
ARCHIVES = 'portable-archives:v1'

class ArchiveError(ValueError):
    pass


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ArchiveError('duplicate_json_key')
            result[key] = value
        return result
    def constant(_):
        raise ArchiveError('non_json_constant')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ArchiveError('unreadable_archive_json') from exc


def _page(store, scope, kind):
    after = None
    while True:
        rows = store.record_page(scope, kind, after=after, limit=100)
        for key, raw in rows:
            yield key, raw
        if len(rows) < 100:
            break
        after = rows[-1][0]


def _cancel(cancelled):
    if cancelled is not None and cancelled():
        raise ArchiveError('archive_cancelled')


def _scrub(value, allowed):
    """All typed snapshots, alternatives, provenance and evidence use this policy."""
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json')
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == 'notes':
                result[key] = []
            elif key == 'rationale_ref':
                result[key] = None
            elif key == 'references' and isinstance(item,list) and all(isinstance(r,dict) and 'visibility' in r for r in item):
                result[key] = [_scrub(r, allowed) for r in item if r.get('visibility') == 'public' and r.get('availability') == 'available' and r.get('id') in allowed]
            elif key in ('source_refs', 'assumption_refs', 'supersedes_refs', 'source_ids', 'assumption_ids'):
                result[key] = [r for r in item if r in allowed]
                if key == 'assumption_refs' and 'distribution' in value and 'variable_id' in value and not result[key]:
                    result[key] = ['archive:redacted-probability-assumption']
            else:
                result[key] = _scrub(item, allowed)
        return result
    if isinstance(value, list):
        return [_scrub(v, allowed) for v in value]
    return value


def _evidence(saved, allowed, options):
    if options.evidence == 'reduced':
        return None
    allowed = allowed & {r.id for r in saved.references if r.visibility == 'public' and r.availability == 'available'}
    data = _scrub(saved, allowed)
    if saved.state == 'complete':
        evaluation = data['evaluation']
        for key in ('input_json', 'model_json', 'realization_json', 'final_batch_json'):
            if evaluation[key] is not None:
                evaluation[key] = serialized(_scrub(strict_json(evaluation[key]), allowed))
        identities = evaluation['identities']
        identities['input_digest'] = digest(strict_json(evaluation['input_json']))
        identities['model_digest'] = digest(strict_json(evaluation['model_json']))
        identities['realization_digest'] = digest(strict_json(evaluation['realization_json']))
        identities['cache_key'] = digest({k:v for k,v in identities.items() if k not in ('cache_key','output_digest')})
        identities['output_digest'] = digest({k:v for k,v in evaluation.items() if k != 'identities'})
        from poliscope_engine.contracts.evaluation import EvaluationResult
        typed = EvaluationResult.model_validate_json(json.dumps(evaluation))
        traces, _ = build_traces(typed)
        report = data['report']
        report['traces'] = [t.model_dump(mode='json') for t in traces]
        report['physical_output_digest'] = identities['output_digest']
        for finding in report['findings']:
            finding['id'] = digest({k:v for k,v in finding.items() if k != 'id'})
        report['report_digest'] = digest({k:v for k,v in report.items() if k != 'report_digest'})
        # Physical assumption bindings keep their public parameter identity. The
        # private descriptor becomes a redaction reference with no content/hash.
        from poliscope_engine.contracts.measurements import MeasurementReport
        report_model = MeasurementReport.model_validate_json(json.dumps(report))
        existing = {(r['kind'],r['id']) for r in data['references']}
        for kind, identity in sorted(_reference_closure(typed,report_model,{}) - existing):
            data['references'].append(dict(id=identity,kind=kind,visibility='public',
                availability='redacted',description=None,source=None,assumption=None))
    data['closure_digest'] = digest({k:v for k,v in data.items() if k != 'closure_digest'})
    return ArchiveEvidence(saved=read_retained(json.dumps(data)))


def project(service, options, *, cancelled=None):
    """A single committed SQLite snapshot; no filesystem enumeration or cache use."""
    from poliscope_engine import private_notes
    from poliscope_engine.comparison import rationale
    options = ArchiveOptions.model_validate_json(options.model_dump_json())
    store = service.store
    if store.in_write_transaction:
        raise ArchiveError('unconfirmed_write_in_progress')
    # A read transaction pins branches, revisions and experiments to one snapshot.
    store._connection.execute('BEGIN')
    try:
        branches = service.catalogue()
        branch_ids = {(b.context.civilization_id,b.context.branch_id):'branch:'+str(index)
            for index,b in enumerate(branches)}
        def bid(civilization, identity):
            try:return branch_ids[civilization,identity]
            except KeyError as exc:raise ArchiveError('missing_branch_reference') from exc
        records, evidence, mapping = [], {}, {}
        snapshot_bytes = 0
        for civ in sorted({b.context.civilization_id for b in branches}):
            scope = service._scope(service.data_store_id, civ)
            for _, raw in _page(store, scope, 'revision_index'):
                summary = RevisionSummary.model_validate_json(raw)
                record = service.read(summary.context)
                key = (civ, record.context.revision_id)
                if key in mapping:
                    raise ArchiveError('duplicate_revision')
                mapping[key] = 'revision:' + str(len(records))
                records.append(record)
                evidence[key] = service.evidence(record.context)
                snapshot_bytes += len(record.model_dump_json().encode()) + len(evidence[key].model_dump_json().encode())
                if snapshot_bytes > MAX_ARCHIVE:
                    raise ArchiveError('archive_snapshot_budget')
                if len(records) > MAX_ENTRIES:
                    raise ArchiveError('archive_entry_budget')
        # Missing/unknown reference descriptors are private by default across history.
        allowed = {r.id for saved in evidence.values() for r in saved.references
                   if r.visibility == 'public' and r.availability == 'available'}
        # A reference ever classified private stays private even if another version exposes it.
        allowed -= {r.id for saved in evidence.values() for r in saved.references if r.visibility != 'public'}
        def rid(civ, identity):
            if identity is None:
                return None
            try:
                return mapping[civ, identity]
            except KeyError as exc:
                raise ArchiveError('missing_revision_reference') from exc
        def context(ctx):
            return dict(data_store_id='archive:projection', civilization_id=ctx.civilization_id,
                branch_id=bid(ctx.civilization_id,ctx.branch_id), revision_id=rid(ctx.civilization_id, ctx.revision_id))
        class BoundedItems(list):
            size = 0
            def append(self, item):
                size = len(serialized(item).encode())
                if size > MAX_ENTRY or self.size + size > MAX_ARCHIVE or len(self) >= MAX_ENTRIES:
                    raise ArchiveError('archive_size_budget')
                self.size += size
                super().append(item)
        items, omissions = BoundedItems(), []
        for record in records:
            _cancel(cancelled)
            civ, old = record.context.civilization_id, record.context.revision_id
            identity = rid(civ, old)
            saved = evidence[civ, old]
            items.append(ArchiveRevision.model_validate(dict(id=identity, civilization_id=civ,
                branch_id=bid(civ,record.context.branch_id), parent_id=rid(civ, record.parent_id),
                inputs=_scrub(record.inputs, allowed), alternatives=_scrub(record.decision.alternatives, allowed),
                selected_id=record.decision.selected_id, evidence=_evidence(saved, allowed, options))))
            if options.evidence == 'reduced':
                omissions.append(identity)
            if options.include_private_notes:
                for ref in record.inputs.notes:
                    status, _, text = private_notes.read(service, record.context, ref)
                    items.append(ArchivePrivate(category='note', revision_id=identity, status=status, text=text))
            if options.include_private_rationale and record.decision.rationale_ref is not None:
                reply = rationale(service, dict(context=record.context))
                items.append(ArchivePrivate(category='rationale', revision_id=identity,
                    status='available' if reply.text else 'unavailable', text=reply.text))
        for branch in branches:
            civ = branch.context.civilization_id
            origin = branch.forked_from
            items.append(ArchiveBranch(civilization_id=civ, id=bid(civ,branch.context.branch_id), name=branch.name,
                revision_id=rid(civ, branch.context.revision_id), redo=[rid(civ, x) for x in branch.redo],
                fork_branch_id=None if origin is None else bid(civ,origin.branch_id),
                fork_revision_id=None if origin is None else rid(civ, origin.revision_id)))
        boundaries = BoundaryStore(service)
        for _, metadata in store._connection.execute('SELECT id,metadata FROM contexts ORDER BY id'):
            data = strict_json(metadata)
            if not isinstance(data, dict) or 'boundary_contract' not in data:
                continue
            experiment = ExperimentRecord.model_validate(data)
            ctx = experiment.context
            scope, _ = boundaries._experiment(ctx)
            plan = _scrub(experiment.plan, allowed)
            plan['opening_revision'] = context(experiment.plan.opening_revision)
            for a, original in zip(plan['adoptions'], experiment.plan.adoptions, strict=True):
                a['source_revision'], a['base_revision'] = context(original.source_revision), context(original.base_revision)
            history = []
            history_bytes = 0
            for key, _ in _page(store, scope, JOURNAL):
                _cancel(cancelled)
                confirmed = boundaries.read(ctx, int(key))
                receipt = confirmed.state.transition
                history.append(ArchiveBoundary(sequence=confirmed.record.sequence, day=confirmed.record.day,
                    inputs=_scrub(confirmed.state.inputs, allowed), conditions=confirmed.state.conditions,
                    changes=_scrub(confirmed.record.changes, allowed),
                    transition=None if receipt is None else ArchiveTransition.model_validate_json(json.dumps(
                        _scrub(receipt.model_dump(exclude={'opening_digest','plan_digest','receipt_digest','day','random_draws'}),allowed)
                        | dict(draws=_scrub(receipt.random_draws,allowed)))),
                    evidence=_evidence(confirmed.evidence, allowed, options)))
                history_bytes += len(history[-1].model_dump_json().encode())
                if history_bytes > MAX_ENTRY:
                    raise ArchiveError('archive_experiment_budget')
                if options.evidence == 'reduced':
                    omissions.append(f'{ctx.civilization_id}:{ctx.experiment_id}:{int(key)}')
                if len(history) > MAX_ENTRIES:
                    raise ArchiveError('archive_boundary_budget')
            checkpoints = [Checkpoint.model_validate_json(raw).boundary.sequence
                for _, raw in _page(store, scope, 'experiment-checkpoint:v1')]
            controls = store.record_page(scope, 'experiment-control:v1', limit=1, descending=True)
            items.append(ArchiveExperiment(civilization_id=ctx.civilization_id, id=ctx.experiment_id,
                plan=plan, transition_plan=_scrub(experiment.transition_plan, allowed),
                origin_id=None if experiment.origin is None else experiment.origin.context.experiment_id,
                origin_sequence=None if experiment.origin is None else experiment.origin.sequence,
                checkpoint_sequences=checkpoints,
                control='ready' if not controls else ExperimentControl.model_validate_json(controls[0][1]).state,
                boundaries=history))
        # Fork declarations bind projected parent plans, never old hashes which
        # could include redacted reference identities.
        indexed = {(x.civilization_id,x.id):x for x in items if isinstance(x,ArchiveExperiment)}
        completed,visiting = set(),set()
        def normalize(key):
            if key in completed:return indexed[key]
            if key in visiting:raise ArchiveError('cyclic_experiment_lineage')
            visiting.add(key)
            item=indexed[key]
            if item.origin_id is not None:
                parent=normalize((item.civilization_id,item.origin_id))
                plan=item.transition_plan
                if plan is not None and plan.random_plan is not None and plan.random_plan.fork is not None:
                    if parent.transition_plan is None or parent.transition_plan.random_plan is None:
                        raise ArchiveError('missing_random_parent')
                    declaration=plan.random_plan.fork.model_copy(update={'parent_plan_digest':digest(parent.transition_plan.random_plan)})
                    random=plan.random_plan.model_copy(update={'fork':declaration})
                    item=item.model_copy(update={'transition_plan':plan.model_copy(update={'random_plan':random})})
                    indexed[key]=item
            visiting.remove(key);completed.add(key)
            return item
        for index,item in enumerate(items):
            if isinstance(item,ArchiveExperiment):items[index]=normalize((item.civilization_id,item.id))
        return items, omissions
    finally:
        store._connection.execute('ROLLBACK')


def _validate_items(items, options, omissions):
    if not any(isinstance(x, ArchiveRevision) for x in items):
        raise ArchiveError('archive_requires_revision')
    revisions = {(x.civilization_id, x.id): x for x in items if isinstance(x, ArchiveRevision)}
    branches = {(x.civilization_id, x.id): x for x in items if isinstance(x, ArchiveBranch)}
    experiments = {(x.civilization_id, x.id): x for x in items if isinstance(x, ArchiveExperiment)}
    for cls, index in ((ArchiveRevision, revisions), (ArchiveBranch, branches), (ArchiveExperiment, experiments)):
        if sum(isinstance(x, cls) for x in items) != len(index):
            raise ArchiveError('duplicate_archive_identity')
    expected_omissions = []
    validated_ancestors = set()
    def check_evidence(e, label):
        if options.evidence == 'reduced':
            if e is not None:
                raise ArchiveError('evidence_completeness_mismatch')
            expected_omissions.append(label)
        elif e is None:
            raise ArchiveError('missing_retained_evidence')
        else:
            saved=read_retained(e.saved.model_dump_json())
            if saved.report is not None:
                traces={t.id for t in saved.report.traces}
                if any(ref not in traces for item in [*saved.report.measurements,*saved.report.findings] for ref in item.trace_refs):
                    raise ArchiveError('missing_result_trace')
    for x in items:
        if isinstance(x, ArchiveRevision):
            if (x.civilization_id, x.branch_id) not in branches or x.parent_id is not None and (x.civilization_id, x.parent_id) not in revisions:
                raise ArchiveError('missing_revision_reference')
            ancestors, current = set(), x
            while current.parent_id is not None and (current.civilization_id,current.id) not in validated_ancestors:
                if current.id in ancestors:
                    raise ArchiveError('cyclic_revision_lineage')
                ancestors.add(current.id)
                current = revisions[x.civilization_id, current.parent_id]
            validated_ancestors.update((x.civilization_id,identity) for identity in ancestors)
            _validate_snapshot(x.inputs, x.civilization_id, x.evidence)
            check_evidence(x.evidence, x.id)
        elif isinstance(x, ArchiveBranch):
            if any((x.civilization_id, r) not in revisions for r in [x.revision_id, *x.redo]):
                raise ArchiveError('missing_branch_revision')
            if (x.fork_branch_id is None) != (x.fork_revision_id is None) or x.fork_branch_id is not None and (
                    (x.civilization_id, x.fork_branch_id) not in branches or (x.civilization_id, x.fork_revision_id) not in revisions):
                raise ArchiveError('missing_fork_reference')
        elif isinstance(x, ArchiveExperiment):
            for ctx in [x.plan.opening_revision, *[c for a in x.plan.adoptions for c in (a.source_revision, a.base_revision)]]:
                if ctx.data_store_id != 'archive:projection' or ctx.civilization_id != x.civilization_id or (ctx.civilization_id, ctx.revision_id) not in revisions or (ctx.civilization_id, ctx.branch_id) not in branches:
                    raise ArchiveError('missing_schedule_revision')
            sequences = [b.sequence for b in x.boundaries]
            if sequences != list(range(len(sequences))) or any(a.day >= b.day for a,b in zip(x.boundaries,x.boundaries[1:])):
                raise ArchiveError('invalid_boundary_order')
            if x.boundaries[0].day != x.plan.opening_day or len(set(x.checkpoint_sequences)) != len(x.checkpoint_sequences) or any(c not in sequences for c in x.checkpoint_sequences):
                raise ArchiveError('missing_checkpoint_boundary')
            if (x.origin_id is None) != (x.origin_sequence is None):
                raise ArchiveError('invalid_experiment_origin')
            if x.origin_id is not None:
                ancestors, origin = set(), x
                while origin.origin_id is not None:
                    key = (origin.civilization_id,origin.origin_id)
                    if key in ancestors or key not in experiments:
                        raise ArchiveError('cyclic_or_missing_experiment_origin')
                    ancestors.add(key)
                    origin = experiments[key]
                parent = experiments.get((x.civilization_id, x.origin_id))
                if parent is None or x.origin_id == x.id or x.origin_sequence >= len(parent.boundaries):
                    raise ArchiveError('missing_experiment_origin')
                source=parent.boundaries[x.origin_sequence]
                if (source.day != x.boundaries[0].day or digest(source.inputs) != digest(x.boundaries[0].inputs)
                        or source.conditions != x.boundaries[0].conditions):
                    raise ArchiveError('fork_opening_state_mismatch')
                if x.transition_plan is not None and x.transition_plan.random_plan is not None:
                    from poliscope_engine.stochastic import verify_fork
                    if parent.transition_plan is None or parent.transition_plan.random_plan is None:
                        raise ArchiveError('missing_random_parent')
                    verify_fork(parent.transition_plan.random_plan,x.transition_plan.random_plan)
            for b in x.boundaries:
                if b.day != b.inputs.design.effective_time.tick:
                    raise ArchiveError('boundary_time_mismatch')
                if b.sequence > 0:
                    from poliscope_engine.stochastic import check_retained
                    check_retained(None if x.transition_plan is None else x.transition_plan.random_plan,b.day,[] if b.transition is None else b.transition.draws)
                if (b.sequence > 0 and x.transition_plan is not None) and b.transition is None:
                    raise ArchiveError('missing_transition_evidence')
                if b.transition is not None:
                    from poliscope_engine.contracts.transitions import TransitionReceipt
                    from poliscope_engine.simulation import verify_receipt
                    fields=b.transition.model_dump(exclude={'draws'}) | dict(random_draws=b.transition.draws,
                        day=b.day,opening_digest=digest('projected-predecessor'),plan_digest=digest(x.transition_plan))
                    verify_receipt(TransitionReceipt(**fields,receipt_digest=digest(fields)))
                _validate_snapshot(b.inputs, x.civilization_id, b.evidence)
                check_evidence(b.evidence, f'{x.civilization_id}:{x.id}:{b.sequence}')
        else:
            selected = {'note': options.include_private_notes, 'rationale': options.include_private_rationale,
                'transcript': options.include_transcripts, 'attachment': options.include_attachments}[x.category]
            if not selected or x.revision_id not in {r.id for r in revisions.values()} or (x.status == 'available') != (x.text is not None):
                raise ArchiveError('private_payload_not_selected')
    if sorted(expected_omissions) != sorted(omissions) or len(set(omissions)) != len(omissions):
        raise ArchiveError('evidence_omissions_mismatch')
    # Every input/alternative uses approved typed simulation data, never code.
    def privacy(value):
        if isinstance(value, dict):
            if value.get('classification') == 'private' or value.get('visibility') == 'private' or value.get('rationale_ref') is not None:
                raise ArchiveError('unprojected_private_reference')
            for key, v in value.items():
                if key == 'notes' and v:
                    raise ArchiveError('unprojected_private_notes')
                privacy(v)
        elif isinstance(value, list):
            for v in value:
                privacy(v)
    for x in items:
        privacy(x.model_dump(mode='json'))


def export_archive(service, destination, options=None, *, cancelled=None, archive_id=None):
    options = options or ArchiveOptions()
    destination = Path(destination)
    if not destination.is_absolute() or destination.exists():
        raise ArchiveError('new_absolute_archive_path_required')
    if archive_id is None:
        items, omissions = project(service, options, cancelled=cancelled)
    else:
        raw = service.store.read_record(ARCHIVES,'archive-manifest',archive_id)
        if raw is None:
            raise ArchiveError('unknown_archive')
        retained = ArchiveManifest.model_validate_json(raw)
        if retained.options.evidence == 'reduced' and options.evidence == 'complete':
            raise ArchiveError('omitted_evidence_cannot_be_restored')
        items, omissions = [], []
        included = {'note':options.include_private_notes,'rationale':options.include_private_rationale,
            'transcript':options.include_transcripts,'attachment':options.include_attachments}
        for index in range(len(retained.entries)):
            _cancel(cancelled)
            item,_ = read_item(service.store,archive_id,index)
            if isinstance(item,ArchivePrivate) and not included[item.category]:
                continue
            if options.evidence == 'reduced':
                if isinstance(item,ArchiveRevision):
                    omissions.append(item.id)
                    item=item.model_copy(update={'evidence':None})
                elif isinstance(item,ArchiveExperiment):
                    omissions.extend(f'{item.civilization_id}:{item.id}:{b.sequence}' for b in item.boundaries)
                    item=item.model_copy(update={'boundaries':[b.model_copy(update={'evidence':None}) for b in item.boundaries]})
            items.append(item)
    _validate_items(items, options, omissions)
    if not 1 <= len(items) <= MAX_ENTRIES:
        raise ArchiveError('archive_entry_budget')
    redactions = [name for name, included in (
        ('private_notes',options.include_private_notes),('private_rationale',options.include_private_rationale),
        ('transcripts',options.include_transcripts),('attachments',options.include_attachments)) if not included]
    redactions += ['private_references', 'private_identifiers']
    if archive_id is not None:
        redactions = list(set(redactions) | set(retained.redactions))
    redactions.sort()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.poliscope-export-', delete=False) as stream:
            temporary = Path(stream.name)
        entries, total = [], 0
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for index, item in enumerate(items):
                _cancel(cancelled)
                raw = serialized(item).encode()
                total += len(raw)
                if len(raw) > MAX_ENTRY or total > MAX_ARCHIVE:
                    raise ArchiveError('archive_size_budget')
                name = f'data/{index:06d}.json'
                entries.append(ArchiveEntry(path=name, size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
                archive.writestr(name, raw)
            fields = dict(format='poliscope-portable', version=1, data_schema=1, options=options,
                entries=entries, redactions=redactions, omitted_evidence=omissions)
            manifest = ArchiveManifest(**fields, projection_digest=digest(fields))
            raw = manifest.model_dump_json().encode()
            if len(raw) > MAX_MANIFEST or total + len(raw) > MAX_ARCHIVE:
                raise ArchiveError('archive_size_budget')
            archive.writestr('manifest.json', raw)
        if temporary.stat().st_size > MAX_ARCHIVE:
            raise ArchiveError('archive_size_budget')
        _cancel(cancelled)
        # Publish a complete same-directory temporary file exclusively. A crash
        # before publication cannot leave a partial archive at the selected path.
        with temporary.open('rb') as source:
            os.fsync(source.fileno())
        _cancel(cancelled)
        os.link(temporary,destination)
        return summarize(manifest, items, service.registry)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _zip_directory_budget(path):
    # ZipFile eagerly loads the central directory. Check its actual header count
    # and byte budget first, including a forged EOCD count and executable prefix.
    with path.open('rb') as stream:
        if stream.read(4) != b'PK\x03\x04':
            raise ArchiveError('unsafe_archive_prefix')
        size=path.stat().st_size
        stream.seek(max(0,size-65557))
        tail=stream.read(65557)
        end=tail.rfind(b'PK\x05\x06')
        if end < 0 or len(tail)-end < 22:
            raise ArchiveError('invalid_zip_directory')
        _,disk,start_disk,disk_count,count,central_size,start,comment=struct.unpack_from('<4s4H2IH',tail,end)
        if (disk or start_disk or count != disk_count or not 1 <= count <= MAX_ENTRIES+1
                or central_size > 4*1024*1024 or len(tail)-end != 22+comment
                or start+central_size != size-(len(tail)-end)):
            raise ArchiveError('archive_directory_budget')
        stream.seek(start)
        consumed,actual=0,0
        while consumed < central_size:
            header=stream.read(46)
            if len(header)!=46 or header[:4]!=b'PK\x01\x02':
                raise ArchiveError('invalid_zip_directory')
            lengths=struct.unpack_from('<3H',header,28)
            consumed+=46+sum(lengths);actual+=1
            if consumed > central_size or actual > MAX_ENTRIES+1:
                raise ArchiveError('archive_directory_budget')
            stream.seek(sum(lengths),1)
        if actual != count:
            raise ArchiveError('archive_directory_count')


def validate_archive(path, *, cancelled=None):
    path = Path(path)
    if not path.is_absolute() or not path.is_file() or path.stat().st_size > MAX_ARCHIVE:
        raise ArchiveError('archive_size_budget')
    _zip_directory_budget(path)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [x.filename for x in infos]
            if len(infos) > MAX_ENTRIES + 1 or len(names) != len(set(names)) or 'manifest.json' not in names:
                raise ArchiveError('archive_entries_invalid')
            total = 0
            for info in infos:
                mode = info.external_attr >> 16
                if (info.orig_filename != info.filename or info.external_attr & 0x10
                        or info.filename != 'manifest.json' and not re.fullmatch(r'data/[0-9]{6}\.json',info.filename)
                        or info.is_dir() or info.flag_bits & 1 or stat.S_IFMT(mode) not in (0,stat.S_IFREG)
                        or mode & 0o111 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
                        or info.file_size > MAX_ENTRY):
                    raise ArchiveError('unsafe_archive_entry')
                total += info.file_size
                if total > MAX_ARCHIVE:
                    raise ArchiveError('archive_expansion_budget')
            def read(name):
                _cancel(cancelled)
                with archive.open(name) as stream:
                    raw = stream.read(MAX_ENTRY + 1)
                if len(raw) > MAX_ENTRY:
                    raise ArchiveError('archive_entry_budget')
                return raw
            manifest_raw = read('manifest.json')
            if len(manifest_raw) > MAX_MANIFEST:
                raise ArchiveError('archive_manifest_budget')
            manifest = ArchiveManifest.model_validate(strict_json(manifest_raw))
            if manifest.projection_digest != digest(manifest.model_dump(exclude={'projection_digest'})):
                raise ArchiveError('archive_manifest_digest')
            if names.count('manifest.json') != 1 or set(names) != {'manifest.json', *[e.path for e in manifest.entries]} or len({e.path for e in manifest.entries}) != len(manifest.entries):
                raise ArchiveError('archive_manifest_entries')
            required_redactions = {'private_references','private_identifiers'}
            for name, included in (('private_notes',manifest.options.include_private_notes),
                    ('private_rationale',manifest.options.include_private_rationale),
                    ('transcripts',manifest.options.include_transcripts),('attachments',manifest.options.include_attachments)):
                if not included: required_redactions.add(name)
            if not required_redactions <= set(manifest.redactions) or len(set(manifest.redactions)) != len(manifest.redactions):
                raise ArchiveError('archive_privacy_manifest')
            items = []
            for entry in manifest.entries:
                raw = read(entry.path)
                if len(raw) != entry.size or hashlib.sha256(raw).hexdigest() != entry.sha256:
                    raise ArchiveError('archive_entry_digest')
                items.append(archive_item_adapter.validate_json(json.dumps(strict_json(raw))))
            _validate_items(items, manifest.options, manifest.omitted_evidence)
            return manifest, items
    except (zipfile.BadZipFile, ValidationError, KeyError, RecursionError, UnicodeError) as exc:
        raise ArchiveError('unsafe_or_unreadable_archive') from exc


def summarize(manifest, items, registry=None):
    from poliscope_engine.numeric import RUNTIME_ID
    versions = [x.inputs.versions for x in items if isinstance(x, ArchiveRevision)]
    compatible = bool(versions) and registry is not None and all(
        v.model_id == registry.model[0] and v.numeric_runtime_id == RUNTIME_ID for v in versions)
    if compatible:
        for item in items:
            if isinstance(item,ArchiveRevision) and item.evidence is not None and item.evidence.saved.evaluation is not None:
                model = strict_json(item.evidence.saved.evaluation.model_json)
                if tuple(model['identity']) != registry.model or digest(model['definitions']) != digest(registry.definitions):
                    compatible = False
    return ArchiveSummary(id=manifest.projection_digest,
        revisions=sum(isinstance(x, ArchiveRevision) for x in items),
        branches=sum(isinstance(x, ArchiveBranch) for x in items),
        experiments=sum(isinstance(x, ArchiveExperiment) for x in items),
        evidence=manifest.options.evidence, execution='compatible_requires_explicit_migration' if compatible else 'unavailable',
        redactions=manifest.redactions)


def import_archive(store, path, *, registry=None, cancelled=None):
    # Complete schema, closure, path and budget validation precedes the write lock.
    manifest, items = validate_archive(path, cancelled=cancelled)
    summary = summarize(manifest, items, registry)
    blobs = RetainedBlobs(store)
    with store.transaction():
        _cancel(cancelled)
        if store.read_context(ARCHIVES) is None:
            store.add_context(ARCHIVES, '{"archive_schema":1}')
        old = store.read_record(ARCHIVES, 'archive-manifest', summary.id)
        if old is not None:
            if old != manifest.model_dump_json():
                raise ArchiveError('archive_identity_collision')
            return summary
        store.add_record(ARCHIVES, 'archive-manifest', summary.id, manifest.model_dump_json())
        for entry, item in zip(manifest.entries, items, strict=True):
            _cancel(cancelled)
            blobs.put(ARCHIVES, 'archive-item', digest([summary.id,entry.path]), item)
        store.add_record(ARCHIVES, 'archive-summary', summary.id, summary.model_dump_json())
        _cancel(cancelled)
    return summary


def list_archives(store):
    if store.in_write_transaction:
        raise ArchiveError('unconfirmed_write_in_progress')
    result = [ArchiveSummary.model_validate_json(raw) for _,raw in _page(store, ARCHIVES, 'archive-summary')]
    if len(result) > 1000:
        raise ArchiveError('archive_catalogue_budget')
    return result


def read_item(store, identity, offset):
    if store.in_write_transaction:
        raise ArchiveError('unconfirmed_write_in_progress')
    raw = store.read_record(ARCHIVES, 'archive-manifest', identity)
    if raw is None:
        raise ArchiveError('unknown_archive')
    manifest = ArchiveManifest.model_validate_json(raw)
    if type(offset) is not int or not 0 <= offset < len(manifest.entries):
        raise ArchiveError('invalid_archive_offset')
    item = archive_item_adapter.validate_json(RetainedBlobs(store).read(ARCHIVES,
        'archive-item', digest([identity,manifest.entries[offset].path])))
    return item, offset+1 if offset+1 < len(manifest.entries) else None


def display_item(item, offset=0):
    """Small text-only pages; never put an archive or retained blob on IPC."""
    from poliscope_engine.contracts.archives import ArchiveDisplay
    rows = []
    def add(label, text):
        text = str(text)
        # Long retained facts remain readable through consecutive bounded rows.
        for start in range(0, max(1,len(text)), 8192):
            rows.append(ArchiveDisplay(label=label[:512], detail=text[start:start+8192]))
    def inputs(value):
        add('Model and runtime', f'{value.versions.model_id}; {value.versions.catalog_id}; {value.versions.numeric_runtime_id}')
        add('Simulation time', f'{value.design.effective_time.calendar_id}, day {value.design.effective_time.tick}')
        for x in value.entities: add('Entity',f'{x.label} ({x.id})')
        for x in value.scopes: add('Scope',f'{x.label} ({x.id})')
        for x in value.values: add(f'{x.scope_id}: {x.property_id}', x.value.model_dump_json())
        for x in value.assumptions: add('Assumption',x.model_dump_json())
        for x in value.goals: add('Player question',x.question)
        for x in value.references: add('Source / assumption attribution',x.model_dump_json())
    def evidence(e):
        if e is None:
            add('Evidence', 'Measurement reports and calculation traces explicitly omitted; transition records remain retained')
            return
        saved=e.saved
        add('Evidence','Retained historical results with privacy projection identities; not freshly reproduced')
        if saved.report is None:
            add('Coverage','Unavailable historical accepted evidence')
            return
        for x in saved.report.measurements: add('Measurement',x.model_dump_json())
        for x in saved.report.findings: add('Finding',x.model_dump_json())
        for x in saved.report.goals: add('Goal observation',x.model_dump_json())
        for x in saved.report.traces: add('Calculation trace',x.model_dump_json())
        for x in saved.references: add('Retained attribution',x.model_dump_json())
    if isinstance(item, ArchiveRevision):
        heading=f'Revision {item.id} · {item.civilization_id} · {item.branch_id}'
        add('Parent',item.parent_id or 'Opening design')
        inputs(item.inputs)
        for x in item.alternatives: add('Original alternative',x.model_dump_json())
        add('Selected alternative',item.selected_id or 'None')
        evidence(item.evidence)
    elif isinstance(item, ArchiveBranch):
        heading=f'Branch: {item.name}'
        add('Current revision',item.revision_id)
        add('Fork origin',f'{item.fork_branch_id or "Opening branch"} / {item.fork_revision_id or "Opening revision"}')
        add('Redo history',', '.join(item.redo) or 'None')
    elif isinstance(item, ArchiveExperiment):
        heading=f'Experiment: {item.id}'
        add('Status',item.control)
        add('Past-state origin',f'{item.origin_id or "Opening experiment"}, boundary {item.origin_sequence}')
        add('Checkpoint sequences',', '.join(map(str,item.checkpoint_sequences)))
        for x in item.plan.events: add('Authored / external event',x.model_dump_json())
        for x in item.plan.adoptions: add('Approved future policy',x.model_dump_json())
        for b in item.boundaries:
            add('Confirmed boundary',f'{b.sequence}, day {b.day}')
            inputs(b.inputs)
            if b.changes is not None:add('Event and adoption outcomes',b.changes.model_dump_json())
            if b.transition is not None:
                add('Transition coverage',b.transition.coverage)
                for x in b.transition.draws:add('Recorded realization',x.model_dump_json())
                for x in b.transition.steps:add('Transition',x.model_dump_json())
                for x in b.transition.balances:add('Exact balance',x.model_dump_json())
                if b.transition.request is not None:add('Allocation request',b.transition.request.model_dump_json())
                if b.transition.allocation is not None:add('Allocation result',b.transition.allocation.model_dump_json())
                for x in b.transition.claim_owners:add('Claim ownership',x.model_dump_json())
            evidence(b.evidence)
    else:
        heading=f'Included private {item.category}'
        add('Historical revision',item.revision_id)
        add(item.status,item.text or 'No active payload available')
    if offset > len(rows):
        raise ArchiveError('invalid_detail_offset')
    return heading,rows[offset:offset+25],offset+25 if offset+25<len(rows) else None


def _validate_snapshot(inputs, civilization_id, evidence):
    """Validate safe readable contracts without resolving executable mechanisms."""
    from poliscope_engine.revisions import graph
    from poliscope_engine.contracts.accounts import AccountBatch
    from poliscope_engine.contracts.evaluation import Realization
    from poliscope_engine.contracts.boundaries import BoundaryState
    graph(inputs,civilization_id)
    if evidence is None or evidence.saved.state != 'complete':
        return
    evaluation=evidence.saved.evaluation
    for text in (evaluation.input_json,evaluation.model_json,evaluation.realization_json,evaluation.final_batch_json):
        if text is not None:strict_json(text)
    # Bind the complete retained closure to exactly these public input facts.
    BoundaryStore._check_state_evidence(ExperimentContext(data_store_id='archive:projection',
        civilization_id=civilization_id,experiment_id='archive:read'),
        BoundaryState(inputs=inputs,conditions=[]),evidence.saved)
    from poliscope_engine.contracts.archives import ArchiveModelSnapshot
    model = ArchiveModelSnapshot.model_validate_json(evaluation.model_json)
    from poliscope_engine.numeric import Unit, TimeBasis, parse
    for expression in model.graphs:
        nodes={n.id:n for n in expression.nodes}
        if len(nodes)!=len(expression.nodes) or any(ref not in nodes for ref in [*expression.outputs.values(),*expression.state.values()]):
            raise ArchiveError('invalid_expression_reference')
        pending=set(nodes);depths={}
        while pending:
            ready=[]
            for identity in pending:
                node=nodes[identity]
                refs=node.arguments if node.kind=='operator' else []
                if any(ref not in nodes for ref in refs):
                    raise ArchiveError('invalid_expression_reference')
                if all(ref in depths for ref in refs):
                    depths[identity]=1+max((depths[ref] for ref in refs),default=0)
                    if depths[identity]>32:raise ArchiveError('expression_depth_budget')
                    ready.append(identity)
            if not ready:raise ArchiveError('cyclic_expression')
            pending.difference_update(ready)
        for node in expression.nodes:
            if node.kind == "constant" and node.value_type.kind == "quantity":
                parse(node.value)
    for unit in model.units:
        Unit(unit.id,tuple(unit.dimension),unit.kind,parse(unit.scale))
    for time in model.times:
        TimeBasis(time.id,parse(time.seconds))
    Realization.model_validate_json(evaluation.realization_json)
    if evaluation.final_batch_json is not None:
        AccountBatch.model_validate_json(evaluation.final_batch_json)
