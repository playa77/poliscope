"""Read retained results without numerical callbacks or writes; targets are ephemeral."""
import math
from decimal import Decimal
from poliscope_engine.contracts.overview import (OverviewQuery, OverviewPage, IndicatorRow,
    ConditionRow, AccountRow, FindingRow, PolicyRow, GoalRow, ReferenceRow, TraceRow,
    TargetQuery, TargetReply, ChartQuery, ChartReply, ChartPoint, CommitmentRow)
from poliscope_engine.contracts.measurements import PlayerGoal, TraceQuery
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.explanation import trace_page, TEMPLATES
from poliscope_engine.measurements import observe


def selected(service, context, scope):
    record = service.read(context)
    if scope not in {s.id for s in record.inputs.scopes}:
        raise ValueError('unknown_scope')
    return record, service.evidence(context)


def page(service, data):
    query = OverviewQuery.model_validate(data)
    record, saved = selected(service, query.context, query.scope_id)
    report, evaluation = saved.report, saved.evaluation
    prefix = digest(dict(query=query.model_dump(exclude={'cursor'}), evidence=saved.closure_digest))
    rows = []
    collection = query.collection
    if collection == 'conditions':
        owners = {(o.entity_id, o.property_id, o.partition): o.writer_id for o in record.inputs.owners}
        rows = [ConditionRow(kind='condition', id=v.id, condition=v,
            writer_id=owners.get((v.entity_id, v.property_id, v.partition)))
            for v in record.inputs.values if v.partition == 'conditions' or (v.partition == 'design' and v.property_id.startswith('world:relationship:'))]
    elif collection == 'policies':
        rows = [PolicyRow(kind='policy', id=p.id, policy=p) for p in record.inputs.design.policies]
        labels = {e.id: e.label for e in record.inputs.entities}
        rows += [CommitmentRow(kind='commitment', id=v.id, label=labels.get(v.entity_id, 'Qualitative commitment'), condition=v) for v in record.inputs.values
            if v.partition == 'design' and v.property_id == 'interview:commitment']
    elif report is not None:
        if collection == 'indicators':
            definitions = {d.id: d for d in report.definitions}
            rows = [IndicatorRow(kind='indicator', id=o.indicator_id,
                definition=definitions[o.indicator_id], observation=o, tone=(
                    'gray' if o.status != 'known' else 'neutral' if o.diagnostic == 'neutral' else
                    'green' if o.diagnostic == 'within_named_thresholds' else
                    'red' if any(f.indicator_id == o.indicator_id and f.template_id == 'named_diagnostic:v1' and
                        f.category in ('physical_shortage', 'selected_policy_breach', 'institutional_gap') for f in report.findings) else 'orange'))
                for o in report.measurements]
        elif collection == 'findings':
            rows = [FindingRow(kind='finding', id=f.id, finding=f,
                message=TEMPLATES.get(f.template_id, 'Retained finding; authored template unavailable.')) for f in report.findings]
        elif collection == 'accounts' and evaluation is not None and evaluation.accounts is not None:
            batch = AccountBatch.model_validate_json(evaluation.final_batch_json)
            definitions = {a.id: a for a in batch.accounts}
            refs = {m.node[1]: t.id for t in report.traces for m in t.members if m.node[0] == 'account_result'}
            rows = [AccountRow(kind='account', id=a.account_id, definition=definitions[a.account_id],
                result=a, trace_refs=[refs[a.account_id]] if a.account_id in refs else []) for a in evaluation.accounts.accounts]
        elif collection == 'goals':
            goals = {g.id: g for g in report.goal_definitions}
            rows = [GoalRow(kind='goal', id=g.goal_id, definition=goals[g.goal_id], observation=g) for g in report.goals]
        elif collection == 'references':
            rows = [ReferenceRow(kind='reference', id=r.id, reference=r) for r in saved.references]
        elif collection == 'traces':
            inner_cursor = None
            if query.cursor is not None:
                outer, inner_cursor = query.cursor.split('|', 1)
                if outer != prefix:
                    raise ValueError('invalid_trace_context_cursor')
            result = trace_page(report, TraceQuery(report_digest=report.report_digest, root_id=query.item_id,
                cursor=inner_cursor, limit=10))
            rows = [TraceRow(kind='trace', id=t.id, trace=t) for t in result.items]
    # Trace roots intentionally retain dependencies at other scopes. References
    # and goals are revision-wide, with their own explicit scope if applicable.
    if collection not in ('traces', 'references', 'goals') and not query.all_scopes:
        def scope(row):
            return (row.condition.scope_id if row.kind in ('condition', 'commitment') else row.finding.scope_id if row.kind == 'finding'
                else row.policy.scope_id if row.kind == 'policy' else row.definition.scope_id)
        rows = [r for r in rows if scope(r) in (None, query.scope_id)]
    if collection != 'traces' and query.item_id is not None:
        rows = [r for r in rows if r.id == query.item_id]
        if not rows:
            raise ValueError('unknown_overview_item')
    end = 0
    if collection == 'traces' and report is not None:
        items = rows
        cursor = prefix + '|' + result.next_cursor if result.next_cursor else None
    else:
        rows.sort(key=lambda r: r.id)
        if query.cursor is not None:
            bound, offset = query.cursor.rsplit(':', 1)
            end = int(offset)
            if bound != prefix or str(end) != offset or not 0 < end < len(rows):
                raise ValueError('invalid_overview_cursor')
        items = []
        for row in rows[end:end + 25]:
            if len(serialized([*items, row]).encode()) > 800000:
                if not items:
                    raise ValueError('overview_item_requires_chunking')
                break
            items.append(row)
            end += 1
        cursor = prefix + ':' + str(end) if end < len(rows) else None
    reply = OverviewPage(overview_contract=1, query=query, versions=record.inputs.versions,
        effective_time=record.inputs.design.effective_time, evidence_state=saved.state,
        report_digest=report.report_digest if report else None,
        physical_output_digest=report.physical_output_digest if report else None,
        coverage=report.coverage if report else 'unmodeled', items=items, next_cursor=cursor)
    if len(reply.model_dump_json().encode()) > 1000000:
        raise ValueError('overview_page_requires_chunking')
    return reply


def target(service, data):
    query = TargetQuery.model_validate(data)
    _, saved = selected(service, query.context, query.scope_id)
    if saved.report is None or saved.evaluation is None or not any(
            d.id == query.indicator_id and d.scope_id == query.scope_id for d in saved.report.definitions):
        raise ValueError('unknown_target_indicator')
    # observe uses stored inputs and model metadata only, never an implementation
    # callback or revision mutation. The ephemeral report is never persisted.
    goal = PlayerGoal(id='session:target', kind='comparison', question='Session target',
        indicator_id=query.indicator_id, operation=query.operation, threshold=query.threshold)
    result = observe(saved.evaluation, saved.report.definitions, [goal])
    return TargetReply(overview_contract=1, query=query, report_digest=saved.report.report_digest,
        physical_output_digest=result.physical_output_digest, observation=result.goals[0])


def chart(service, data):
    query = ChartQuery.model_validate(data)
    _, saved = selected(service, query.context, query.scope_id)
    if saved.report is None:
        raise ValueError('unavailable_chart')
    definitions = {d.id: d for d in saved.report.definitions}
    chosen = definitions.get(query.indicator_id)
    if chosen is None or chosen.scope_id != query.scope_id:
        raise ValueError('unknown_chart_indicator')
    # Compare only definitions explicitly sharing procedure, name, units and time.
    # Never sum across overlapping memberships or infer an aggregate.
    points = []
    for row in saved.report.measurements:
        definition = definitions[row.indicator_id]
        fields = ('name', 'procedure', 'unit_id', 'time_basis_id', 'denominator_scope_id', 'version')
        if any(getattr(definition, f) != getattr(chosen, f) for f in fields) or row.value.kind != 'quantity':
            continue
        exact = row.value.value
        approximate = float(exact)
        points.append(ChartPoint(label=row.indicator_id, exact=exact,
            approximate=repr(approximate) if math.isfinite(approximate) and (approximate != 0 or Decimal(exact) == 0) else None))
    if len(points) > 100:
        raise ValueError('chart_distribution_limit')
    return ChartReply(overview_contract=1, query=query, unit_id=chosen.unit_id,
        time_basis_id=chosen.time_basis_id, points=points)
