"""Offline retained-data reports. No evaluator, PRNG, provider or renderer arithmetic.

The archive projection supplies the same all-history privacy policy and validated
closure for native and imported histories. Every untrusted Markdown string lives
inside a dynamically fenced code block. CSV text is reversibly apostrophe encoded.
"""
import csv
import io
import os
from pathlib import Path
import re
import tempfile
from poliscope_engine.archives import export_archive, validate_archive, ArchiveError
from poliscope_engine.contracts.archives import ArchiveRevision, ArchiveExperiment, ArchiveBranch, ArchivePrivate
from poliscope_engine.contracts.reports import ReportRequest, ReportReply
from poliscope_engine.comparison import difference, retained
from poliscope_engine.evaluation.identity import serialized

MAX_REPORT = 512 * 1024 * 1024
CHUNK = 65536
COLUMNS = ('report_schema', 'record_type', 'civilization_id', 'branch_id', 'revision_id',
    'experiment_id', 'sequence', 'day', 'scope_id', 'indicator_id', 'definition_version', 'partition', 'value_id',
    'calendar_id', 'tick', 'coverage', 'value_kind', 'value', 'unit_id', 'time_basis_id',
    'denominator_scope_id', 'reason', 'world_schema', 'model_id', 'catalog_id', 'numeric_runtime_id',
    'model_digest', 'physical_output_digest', 'report_digest', 'trace_refs', 'source_refs',
    'assumption_refs', 'distribution_json', 'distribution_runtime', 'consumer_refs', 'dependence', 'comparison_revision',
    'projection_digest')
NUMERIC = {'report_schema', 'sequence', 'day', 'tick', 'world_schema', 'value'}


def csv_text(value):
    """Encode *all* nonempty text, including leading apostrophe/control characters.

    Consumers remove exactly one leading apostrophe. Quantities never use this
    function: a validated Decimal string stays verbatim, including its sign.
    """
    return '' if value is None or value == '' else "'" + str(value)


def csv_line(row):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\r\n')
    writer.writerow([str(row.get(k, '')) if k in NUMERIC and row.get(k) is not None
                     else csv_text(row.get(k)) for k in COLUMNS])
    return stream.getvalue()


def block(value):
    text = value if isinstance(value, str) else serialized(value)
    # Neither raw HTML, Markdown links/images, nor embedded fences can escape.
    fence = '`' * max(3, max((len(m) + 1 for m in re.findall(r'`+', text)), default=3))
    return f'{fence}text\n{text}\n{fence}\n\n'


def snapshots(items):
    for item in items:
        if isinstance(item, ArchiveRevision):
            yield dict(civilization_id=item.civilization_id, branch_id=item.branch_id,
                revision_id=item.id), item.inputs, item.evidence
        elif isinstance(item, ArchiveExperiment):
            for boundary in item.boundaries:
                yield dict(civilization_id=item.civilization_id, experiment_id=item.id,
                    sequence=boundary.sequence, day=boundary.day), boundary.inputs, boundary.evidence


def measurement_rows(items, query, projection):
    for context, inputs, closure in snapshots(items):
        saved = closure.saved if closure else None
        report = saved.report if saved else None
        evaluation = saved.evaluation if saved else None
        base = dict(report_schema=1, **context, **inputs.versions.model_dump(),
            projection_digest=projection, model_digest=evaluation.identities.model_digest if evaluation else '',
            physical_output_digest=report.physical_output_digest if report else '',
            report_digest=report.report_digest if report else '')
        for value in inputs.values:
            if query.scope_id is not None and value.scope_id != query.scope_id:
                continue
            row = dict(base, record_type='time_series_state' if 'experiment_id' in context else 'input_value',
                scope_id=value.scope_id, indicator_id=value.property_id, value_id=value.id,
                partition=value.partition, value_kind=value.value.kind,
                coverage='missing_input' if value.value.kind == 'unknown' else 'retained_input',
                calendar_id=value.effective_time.calendar_id, tick=value.effective_time.tick,
                source_refs=serialized(value.provenance.source_refs), assumption_refs=serialized(value.provenance.assumption_refs),
                reason='Retained input/state; not a calculated indicator')
            if value.value.kind == 'quantity':
                row.update(value=value.value.value, unit_id=value.value.unit_id,
                    time_basis_id=value.value.time_basis_id,denominator_scope_id=value.value.denominator_scope_id)
            else:
                row['reason'] += '; ' + serialized(value.value)
            yield row
        if report is None:
            yield dict(base, record_type='evidence_unavailable', coverage='unavailable',
                reason='Retained result/trace unavailable; no recomputation performed')
            continue
        observations = {o.indicator_id: o for o in report.measurements}
        definitions = {d.id: d for d in report.definitions}
        for identity in sorted(definitions.keys() | observations.keys()):
            observation, definition = observations.get(identity), definitions.get(identity)
            scope = observation.scope_id if observation else definition.scope_id
            if query.scope_id is not None and scope != query.scope_id:
                continue
            row = dict(base, record_type='time_series' if 'experiment_id' in context else 'measurement',
                indicator_id=identity, definition_version=definition.version if definition else '',
                scope_id=scope, coverage=observation.status if observation else 'unavailable',
                reason=observation.reason if observation else 'Retained observation unavailable',
                unit_id=definition.unit_id if definition else '',
                time_basis_id=definition.time_basis_id if definition else '',
                denominator_scope_id=definition.denominator_scope_id if definition else '')
            if observation:
                value = observation.value
                row.update(calendar_id=observation.effective_time.calendar_id, tick=observation.effective_time.tick,
                    value_kind=value.kind, trace_refs=serialized(observation.trace_refs),
                    source_refs=serialized(observation.source_refs), assumption_refs=serialized(observation.assumption_refs))
                if value.kind == 'quantity':
                    row.update(value=value.value, unit_id=value.unit_id,
                        time_basis_id=value.time_basis_id, denominator_scope_id=value.denominator_scope_id)
                else:
                    # No untrusted text ever occupies an unescaped numeric column.
                    row['reason'] += '; ' + serialized(value)
            yield row
    # Declared laws are data, never inferred frequencies or fresh samples.
    for item in items:
        if not isinstance(item, ArchiveExperiment) or item.transition_plan is None:
            continue
        plan = item.transition_plan.random_plan
        if plan is None:
            continue
        for draw in plan.draws:
            if query.scope_id is not None and draw.key.scope_id != query.scope_id:
                continue
            yield dict(report_schema=1, record_type='distribution', civilization_id=item.civilization_id,
                experiment_id=item.id, day=draw.day, scope_id=draw.key.scope_id,
                indicator_id=draw.variable_id, coverage='declared', value_kind='distribution',
                distribution_json=serialized(draw.distribution), dependence=draw.dependence,
                source_refs=serialized(draw.source_refs), assumption_refs=serialized(draw.assumption_refs),
                reason='Explicit model law; not a measured outcome; see plan for shared-variable references',
                projection_digest=projection, **item.boundaries[0].inputs.versions.model_dump(),
                distribution_runtime=serialized(plan.runtime),
                consumer_refs=serialized([r for r in plan.references if r.variable_id==draw.variable_id]))


def comparison_rows(items, query, projection):
    revisions = {(x.civilization_id,x.id):x for x in items if isinstance(x,ArchiveRevision)}
    for right in revisions.values():
        left = revisions.get((right.civilization_id,right.parent_id))
        if not left:
            continue
        ls, rs = left.evidence, right.evidence
        if not ls or not rs:
            continue
        ls, rs = ls.saved, rs.saved
        identities = {d.id for s in (ls,rs) if s.report for d in s.report.definitions}
        for identity in sorted(identities):
            result = difference(identity, retained(ls,identity), retained(rs,identity),left,right,ls.evaluation,rs.evaluation)
            observation = result.right.observation or result.left.observation
            if query.scope_id is not None and (not observation or observation.scope_id != query.scope_id):
                continue
            row = dict(report_schema=1, record_type='comparison', civilization_id=right.civilization_id,
                branch_id=right.branch_id, revision_id=right.id, comparison_revision=left.id,
                indicator_id=identity, scope_id=observation.scope_id if observation else '',
                coverage='known' if result.delta else 'unavailable', value_kind='quantity' if result.delta else 'unknown',
                reason='Right minus parent; compatible retained observations' if result.delta else '; '.join(result.reasons),
                projection_digest=projection, **right.inputs.versions.model_dump(),
                definition_version=result.right.definition.version if result.right.definition else '',
                model_digest=rs.evaluation.identities.model_digest if rs.evaluation else '',
                physical_output_digest=rs.report.physical_output_digest if rs.report else '',
                report_digest=rs.report.report_digest if rs.report else '',
                trace_refs=serialized(observation.trace_refs) if observation else '',
                source_refs=serialized(observation.source_refs) if observation else '',
                assumption_refs=serialized(observation.assumption_refs) if observation else '')
            if result.delta:
                row.update(value=result.delta.value,unit_id=result.delta.unit_id,
                    time_basis_id=result.delta.time_basis_id,denominator_scope_id=result.delta.denominator_scope_id,
                    calendar_id=observation.effective_time.calendar_id,tick=observation.effective_time.tick)
            yield row


def markdown(items, query, manifest):
    yield '# Poliscope inquiry report\n\n'
    yield ('Retained historical data, not freshly reproduced. This deterministic report '
        'contains no AI explanation. A question or expectation is a player hypothesis; '
        'a saved calculation is a model result; a source descriptor is historical attribution, '
        'not confirmation of the model. No overall score or ranking is assigned.\n\n')
    yield '## Export privacy and interpretation\n\n'
    yield block(dict(report_schema=1,projection_digest=manifest.projection_digest,
        scope_id=query.scope_id,privacy=manifest.options,redactions=manifest.redactions,
        omitted_evidence=manifest.omitted_evidence))
    yield ('Identities describe the privacy projection. Private references are redacted. '
        'Missing/unmodeled values remain unavailable, never zero. Time series do not '
        'imply comparability across times, units or model versions.\n\n')
    for item in items:
        if isinstance(item, ArchiveBranch):
            yield '## Branch lineage\n\n'
            yield block(item)
        elif isinstance(item, ArchiveRevision):
            yield '## Design revision and original choices\n\n'
            yield block(dict(civilization=item.civilization_id,revision=item.id,parent=item.parent_id,
                branch=item.branch_id,selected=item.selected_id))
            yield '### Alternatives — approved design content\n\n'
            if not item.alternatives:
                yield 'No recorded alternatives.\n\n'
            for alternative in item.alternatives:
                yield block(alternative)
            yield '### Inquiry — player questions and targets\n\n'
            yield block(item.inputs.goals)
        elif isinstance(item, ArchivePrivate):
            yield '## Optional private material — explicitly included\n\n'
            yield ('Private notes may record inquiry, expectation, observation or model gaps; '
                'these statements are not calculated findings. Older portable histories may have an unavailable note subtype.\n\n')
            yield block(item)
        elif isinstance(item, ArchiveExperiment):
            yield '## Experiment — schedule, alternatives and declared stochastic laws\n\n'
            yield block(dict(civilization=item.civilization_id,experiment=item.id,plan=item.plan,
                transition_plan=item.transition_plan,origin=item.origin_id,origin_sequence=item.origin_sequence,
                control=item.control,checkpoints=item.checkpoint_sequences))
            for boundary in item.boundaries:
                yield '### Confirmed boundary and transition observations\n\n'
                yield block(dict(sequence=boundary.sequence,day=boundary.day,conditions=boundary.conditions,
                    changes=boundary.changes,transition=boundary.transition))
    for context, inputs, closure in snapshots(items):
        yield '## Saved calculation and unresolved coverage\n\n'
        yield block(dict(context=context,versions=inputs.versions))
        yield '### Authored inputs, state and selected policies\n\n'
        yield block(inputs.values)
        yield block(inputs.design.policies)
        yield '### Model assumptions — not historical facts\n\n'
        yield block(inputs.assumptions)
        if not closure or not closure.saved.report:
            yield 'Retained result/trace unavailable. No substitute runtime was invoked.\n\n'
            continue
        saved = closure.saved
        report = saved.report
        yield block(dict(coverage=report.coverage,sufficient=report.sufficient,
            physical_output_digest=report.physical_output_digest,report_digest=report.report_digest))
        yield '### Observations — saved Python calculations\n\n'
        definitions = {d.id:d for d in report.definitions}
        selected = [m for m in report.measurements if query.scope_id is None or m.scope_id == query.scope_id]
        if not selected:
            yield 'No retained indicators in this selection. Authored state above is not an indicator result.\n\n'
        for observation in selected:
            definition = definitions.get(observation.indicator_id)
            yield '#### Measurement and interpretation\n\n'
            lines = [f'Indicator: {definition.name if definition else observation.indicator_id}',
                f'Scope: {observation.scope_id}',
                f'Time: {observation.effective_time.calendar_id}, tick {observation.effective_time.tick}',
                f'Coverage: {observation.status}', f'Reason: {observation.reason}']
            if observation.value.kind == 'quantity':
                v = observation.value
                lines += [f'Value: {v.value}', f'Unit: {v.unit_id}',
                    f'Time basis: {v.time_basis_id or "not applicable"}',
                    f'Denominator scope: {v.denominator_scope_id or "not applicable"}']
            else:
                lines += ['Value: '+serialized(observation.value)]
            if definition:
                lines += ['Interpretation: '+definition.interpretation]
            yield block('\n'.join(lines))
            yield block(dict(observation=observation,definition=definition))
        yield '### Findings and player target observations\n\n'
        yield block([f for f in report.findings if query.scope_id is None or f.scope_id == query.scope_id])
        yield block(report.goals)
        yield '### Sources and assumption descriptors — retained attribution\n\n'
        yield block(saved.references)
        yield '### Calculation traces — retained explanation closure\n\n'
        yield block(report.traces)
    yield '## Parent revision comparisons\n\n'
    yield 'Differences use the same compatibility checks as the application. No automatic unit conversion.\n\n'
    for row in comparison_rows(items,query,manifest.projection_digest):
        yield block(row)


def export_report(service, destination, query, *, cancelled=None):
    query = ReportRequest.model_validate_json(query.model_dump_json())
    destination = Path(destination)
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise ArchiveError('new_absolute_report_path_required')
    # Reuse the fully validated native/imported privacy projection, not a second
    # interpretation of private stores or an enumeration of arbitrary files.
    temporary = None
    with tempfile.TemporaryDirectory(prefix='poliscope-report-') as scratch:
        archive = Path(scratch)/'projection.poliscope'
        export_archive(service,archive,query.options,cancelled=cancelled,archive_id=query.archive_id)
        manifest, items = validate_archive(archive,cancelled=cancelled)
        if query.scope_id is not None and not any(s.id == query.scope_id for _,i,_ in snapshots(items) for s in i.scopes):
            raise ArchiveError('unknown_report_scope')
        rows = 0
        size = 0
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.poliscope-report-',delete=False) as stream:
                temporary = Path(stream.name)
                if query.format == 'markdown':
                    chunks = markdown(items,query,manifest)
                else:
                    def csv_chunks():
                        nonlocal rows
                        yield ','.join(COLUMNS)+'\r\n'
                        for row in measurement_rows(items,query,manifest.projection_digest):
                            rows += 1
                            yield csv_line(row)
                        for row in comparison_rows(items,query,manifest.projection_digest):
                            rows += 1
                            yield csv_line(row)
                    chunks = csv_chunks()
                for chunk in chunks:
                    raw = chunk.encode('utf-8')
                    for offset in range(0,len(raw),CHUNK):
                        if cancelled is not None and cancelled():
                            raise ArchiveError('report_cancelled')
                        part = raw[offset:offset+CHUNK]
                        size += len(part)
                        if size > MAX_REPORT:
                            raise ArchiveError('report_size_budget')
                        stream.write(part)
                stream.flush()
                os.fsync(stream.fileno())
            # Exclusive atomic publication; timeout/failure leaves no partial file.
            os.link(temporary,destination)
            return ReportReply(status='complete',format=query.format,rows=rows,bytes_written=size,
                projection_digest=manifest.projection_digest,redactions=manifest.redactions)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
