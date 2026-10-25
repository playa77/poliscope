"""Reviewed transition proposals, shared finite reduction and durable confirmation.

No default social dynamics, hidden priority, aggregate skipping or code loading.
Each private candidate is recomputed by the boundary-store validator before its
single commit. Missing models remain retained coverage gaps beside supported work.
"""
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from decimal import localcontext
from typing import Callable
from pydantic import TypeAdapter
from poliscope_engine.contracts.base import Identifier

from poliscope_engine.accounts import AccountBook, AccountError
from poliscope_engine.allocations import allocate, encoded
from poliscope_engine.boundaries import BoundaryStore, BoundaryError, outcome
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.contracts.allocations import AllocationRequest
from poliscope_engine.contracts.boundaries import BoundaryCandidate, ConfirmBoundary
from poliscope_engine.contracts.transitions import (
    TransitionPlan, TransitionProposal, TransitionInvocation, TransitionStep,
    TransitionReceipt, AccountBalanceWitness, ChunkProgress, TransitionClaimOwner, TransitionReadView)
from poliscope_engine.contracts.world import PartitionValueDTO, EffectiveTime
from poliscope_engine.domains.conformance import stage_transition
from poliscope_engine.evaluation import evaluate
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.explanation import retain
from poliscope_engine.measurements import observe
from poliscope_engine.mechanisms import MechanismError
from poliscope_engine.numeric import parse, AccountPolicy, exact, context
from poliscope_engine.revisions import graph
from poliscope_engine.policies import resolve
from poliscope_engine.timeline import boundaries, stage_changes

REDUCER_ID = 'atomic-transitions-v1'
ACCOUNT_OWNER = 'shared_accounts'


class TransitionError(ValueError):
    pass


class TransitionUnresolved(ValueError):
    """A selected callback explicitly cannot compute; no proposed writes survive."""


@dataclass(frozen=True)
class TransitionAdapter:
    """Application-owned callbacks registered as Implementation(phase='transition').

    propose(invocation) -> TransitionProposal
    resolve(invocation_with_actuals, proposal) -> list[PartitionValueDTO]
    validate(invocation_with_actuals, proposal, writes, complete_closing_inputs) -> None
    The registry's declaration/fixture/review gates remain mandatory. This is not
    a Python sandbox or a way for source content to grant execution authority.
    """
    propose: Callable
    resolve: Callable
    validate: Callable

    def __post_init__(self):
        if not all(callable(f) for f in (self.propose, self.resolve, self.validate)):
            raise TransitionError('invalid_transition_adapter')

    def __call__(self, invocation):
        return self.propose(invocation)


def _pure(callback, *args):
    results = []
    for _ in range(2):
        supplied = deepcopy(args)
        before = digest(supplied)
        with localcontext(context()):
            result = callback(*supplied)
        if digest(supplied) != before:
            raise TransitionError('mutated_transition_inputs')
        results.append(deepcopy(result))
    if digest(results[0]) != digest(results[1]):
        raise TransitionError('nondeterministic_transition')
    return results[0]


def _physical_view(inputs, definition=None, *, mechanisms, civilization_id):
    partitions = (['conditions', 'design', 'assumptions', 'dynamic_state', 'observations']
                  if definition is None else [p for p in definition.read_partitions if p != 'goals'])
    return TransitionReadView(versions=inputs.versions, effective_time=inputs.design.effective_time,
        entities=inputs.entities, scopes=inputs.scopes, relationships=inputs.relationships,
        values=[v for v in inputs.values if v.partition in partitions],
        policies=resolve(inputs.design.policies, graph=graph(inputs, civilization_id), mechanisms=mechanisms,
            rules=inputs.design.policy_rules) if 'design' in partitions else None,
        assumptions=inputs.assumptions if 'assumptions' in partitions else None, read_partitions=partitions)


def _bindings(plan, inputs, batch, units):
    accounts = {a.id: a for a in batch.accounts}
    values = {v.id: v for v in inputs.values}
    if {b.account_id for b in plan.account_bindings} != set(accounts):
        raise TransitionError('incomplete_account_state_bindings')
    results = {a.account_id: a for a in AccountBook(batch, units).evaluate().accounts}
    owners = {(o.entity_id, o.property_id, o.partition): o.writer_id for o in inputs.owners}
    entity_kinds = {e.id: e.entity_kind for e in inputs.entities}
    if any(c.claimant_id not in entity_kinds for c in batch.claims):
        raise TransitionError('unknown_transition_claimant')
    seen = set()
    for binding in plan.account_bindings:
        row, account = values.get(binding.value_id), accounts[binding.account_id]
        if row is None:
            raise TransitionError('unknown_account_state')
        key = row.entity_id, row.property_id, row.partition
        if (key in seen or row.partition != 'dynamic_state' or row.entity_id != account.id
                or entity_kinds.get(account.id) != 'account' or owners.get(key) != ACCOUNT_OWNER):
            raise TransitionError('noncanonical_account_state')
        seen.add(key)
        if (row.value.kind != 'quantity' or row.value.unit_id != account.unit_id
                or row.scope_id != account.scope_id
                or row.value.time_basis_id != (None if account.kind == 'stock' else account.period_id)
                or row.value.denominator_scope_id is not None
                or Fraction(parse(row.value.value)) != Fraction(parse(results[account.id].closing))):
            raise TransitionError('account_state_mismatch')
    static = inputs.design.execution.batch
    if static is not None and set(accounts) & {a.id for a in static.accounts}:
        raise TransitionError('static_transition_account_overlap')


def validate_opening_book(plan, inputs, mechanisms):
    plan = TransitionPlan.model_validate_json(plan.model_dump_json())
    if plan.instances:
        if mechanisms is None:
            raise TransitionError('transition_runtime_unavailable')
        entities = {e.id for e in inputs.entities}
        scopes = {s.id for s in inputs.scopes}
        for instance in plan.instances:
            mechanisms.definition(instance.mechanism_id, instance.mechanism_version)
            if instance.entity_id not in entities or instance.scope_id not in scopes:
                raise TransitionError('unknown_transition_instance_context')
    if plan.opening is not None:
        if mechanisms is None:
            raise TransitionError('transition_runtime_unavailable')
        _bindings(plan, inputs, plan.opening.batch, mechanisms.units)
        if any(a.period_id is not None and a.period_id not in {t.id for t in mechanisms.times}
               for a in plan.opening.batch.accounts):
            raise TransitionError('unknown_transition_period')
        allocate(plan.opening, mechanisms.units)  # validate procedure/claims without publishing


def _carry_book(request, batch, owners, units):
    """Roll confirmed closings forward; archive past postings in their receipts.

    Requested in the new active frame means outstanding demand. Original demand
    and prior fulfillment remain explicit for owned claims, while immutable parent
    receipts retain every old posting, claim and reservation. No capacity renews.
    """
    result = AccountBook(batch, units).evaluate()
    remaining = {c.claim_id: c.unmet for c in result.claims if Fraction(c.unmet)}
    actual = {c.claim_id: Fraction(c.actual) for c in result.claims}
    pending = set(remaining)
    closing = {a.account_id: a.closing for a in result.accounts}
    reservations = []
    for reservation in batch.reservations:
        fulfilled = sum((Fraction(p.amount) for p in batch.postings
                         if p.reservation_id == reservation.id), Fraction())
        held = Fraction(reservation.amount) - fulfilled
        if held:
            if reservation.claim_id not in pending:
                raise TransitionError('orphaned_pending_reservation')
            reservations.append(reservation.model_copy(update={'amount': encoded(held)}))
    active = AccountBatch.model_validate(batch.model_dump() | dict(
        accounts=[a.model_copy(update={'opening': closing[a.id]}) for a in batch.accounts],
        postings=[], claims=[c.model_copy(update={'requested': remaining[c.id]}) for c in batch.claims if c.id in pending],
        reservations=reservations))
    carried = {cid: owner.model_copy(update={'fulfilled_prior': encoded(
        Fraction(owner.fulfilled_prior) + actual[cid])}) for cid, owner in owners.items() if cid in pending}
    updated = AllocationRequest.model_validate(request.model_dump() | dict(batch=active,
        choices=[c for c in request.choices if c.claim_id in pending],
        claim_order=[cid for cid in request.claim_order if cid in pending]))
    return updated, carried


def balance_witnesses(batch, accounts=None):
    """Independent rational oracle; no tolerance, Decimal summation or allocator reuse."""
    closing = None if accounts is None else {a.account_id: Fraction(parse(a.closing)) for a in accounts.accounts}
    if closing is not None and set(closing) != {a.id for a in batch.accounts}:
        raise TransitionError('exact_transition_balance_failure')
    witnesses = []
    for account in sorted(batch.accounts, key=lambda a: a.id):
        inflow = sum((Fraction(parse(p.amount)) for p in batch.postings if p.destination_id == account.id), Fraction())
        outflow = sum((Fraction(parse(p.amount)) for p in batch.postings if p.source_id == account.id), Fraction())
        expected = Fraction(parse(account.opening)) + inflow - outflow
        actual = expected if closing is None else closing[account.id]
        if expected != actual or actual < 0:
            raise TransitionError('exact_transition_balance_failure')
        AccountPolicy(parse(account.quantum), parse(account.maximum), 'reject').count(exact(actual))
        witnesses.append(AccountBalanceWitness(account_id=account.id, unit_id=account.unit_id,
            scope_id=account.scope_id, period_id=account.period_id, opening=account.opening, inflow=encoded(inflow),
            outflow=encoded(outflow), closing=encoded(actual)))
    return witnesses


def verify_receipt(receipt):
    receipt = TransitionReceipt.model_validate_json(receipt.model_dump_json())
    if receipt.receipt_digest != digest(receipt.model_dump(exclude={'receipt_digest'})):
        raise TransitionError('transition_receipt_digest_mismatch')
    for witness in receipt.balances:
        if (Fraction(parse(witness.opening)) + Fraction(parse(witness.inflow)) - Fraction(parse(witness.outflow))
                != Fraction(parse(witness.closing)) or Fraction(parse(witness.closing)) < 0):
            raise TransitionError('exact_transition_balance_failure')
    if len({s.instance_id for s in receipt.steps}) != len(receipt.steps):
        raise TransitionError('duplicate_transition_step')
    unresolved_book = receipt.request is not None and (receipt.allocation is None or receipt.allocation.status == 'unresolved')
    coverage = ('unresolved' if unresolved_book or any(s.status == 'unresolved' for s in receipt.steps) else
                'partial' if any(s.status == 'coverage_gap' for s in receipt.steps) else 'complete')
    if receipt.coverage != coverage:
        raise TransitionError('transition_coverage_mismatch')
    if receipt.request is None:
        if receipt.allocation is not None or receipt.balances or receipt.claim_owners:
            raise TransitionError('transition_receipt_book_mismatch')
    else:
        if receipt.allocation is not None and digest(receipt.allocation.request) != digest(receipt.request):
            raise TransitionError('transition_receipt_book_mismatch')
        batch = receipt.request.batch if receipt.allocation is None else receipt.allocation.batch
        witnesses = balance_witnesses(batch, None if receipt.allocation is None else receipt.allocation.accounts)
        if digest(witnesses) != digest(receipt.balances):
            raise TransitionError('transition_witness_mismatch')
        owners = {o.claim_id: o for o in receipt.claim_owners}
        if len(owners) != len(receipt.claim_owners) or not set(owners) <= {c.id for c in batch.claims}:
            raise TransitionError('invalid_transition_claim_ownership')
        if any(o.choice.claim_id != o.claim_id for o in owners.values()):
            raise TransitionError('invalid_transition_claim_ownership')
        requested = {c.id: Fraction(parse(c.requested)) for c in receipt.request.batch.claims}
        if any(Fraction(parse(o.original_requested)) != Fraction(parse(o.fulfilled_prior)) + requested[o.claim_id]
               for o in owners.values()):
            raise TransitionError('pending_claim_fulfillment_mismatch')
        if any(owners.get(cid) is None or owners[cid].instance_id != s.instance_id
               for s in receipt.steps for cid in [*s.claim_ids, *s.refined_claim_ids]):
            raise TransitionError('invalid_transition_claim_ownership')
    return receipt


class TransitionReducer:
    def __init__(self, revisions, *, catalog):
        self.revisions, self.mechanisms, self.catalog = revisions, revisions.registry, catalog
        self.store = BoundaryStore(revisions, validator=self.validate, validator_id=REDUCER_ID)

    def _reduce(self, opening, experiment, due, *, cancelled=None):
        if self.mechanisms is None or experiment.transition_plan is None:
            raise TransitionError('transition_runtime_or_plan_unavailable')
        plan = experiment.transition_plan
        spent = 0
        def checkpoint(cost=1):
            nonlocal spent
            if cancelled is not None and cancelled():
                raise BoundaryError('boundary_cancelled')
            spent += cost
            if spent > plan.operation_limit:
                raise TransitionError('transition_operation_quota')
        checkpoint()
        inputs = opening.state.inputs.model_copy(deep=True)
        changes, facts = stage_changes(experiment.plan, due.day, inputs.design.policies,
            {(c.scope_id, c.condition_id): c.value for c in opening.state.conditions},
            read_revision=self.revisions.read)
        inputs = inputs.model_copy(update={'design': inputs.design.model_copy(update={
            'policies': changes.policies, 'effective_time': EffectiveTime(tick=due.day, calendar_id=experiment.plan.calendar.id)})})
        world = graph(inputs, experiment.context.civilization_id).registry
        branches = [c.branch_id for m in self.catalog.modules for c in m.coverage]
        self.catalog.validate(world=world, mechanisms=self.mechanisms, branch_ids=branches)
        instances = {i.id: i for i in inputs.design.execution.dependencies.instances}
        static_ids = set(instances)
        if set(instances) & {i.id for i in plan.instances}:
            raise TransitionError('duplicate_transition_instance')
        instances.update({i.id: i for i in plan.instances})
        if not set(due.mechanism_ids) <= set(plan.instance_order):
            raise TransitionError('transition_schedule_mismatch')
        previous = opening.state.transition
        if previous is not None:
            verify_receipt(previous)
            if previous.plan_digest != digest(plan):
                raise TransitionError('transition_plan_changed')
        base = plan.opening
        claim_owners = {} if previous is None else {c.claim_id: c for c in previous.claim_owners}
        if previous is not None and previous.request is not None:
            base, claim_owners = _carry_book(previous.request,
                previous.allocation.batch if previous.allocation else previous.request.batch,
                claim_owners, self.mechanisms.units)
        elif base is not None:
            base, claim_owners = _carry_book(base, base.batch, {}, self.mechanisms.units)
        if base is not None:
            _bindings(plan, opening.state.inputs, base.batch, self.mechanisms.units)
        proposals, adapters, invocations, steps = {}, {}, {}, {}
        prior_unmet = {} if base is None else {c.claim_id: Fraction(c.unmet)
            for c in AccountBook(base.batch, self.mechanisms.units).evaluate().claims}
        new_claims, new_choices, new_order = [], [], []
        unknown_model, staged_evaluation = False, None
        for identity in plan.instance_order:
            if identity not in due.mechanism_ids:
                continue
            checkpoint()
            instance = instances.get(identity)
            if instance is None:
                raise TransitionError('unknown_due_instance')
            definition = self.mechanisms.definition(instance.mechanism_id, instance.mechanism_version)
            def step(status, reason, claim_ids=(), writes=(), refs=()):
                return TransitionStep(instance_id=identity, domain=definition.domain, status=status,
                    reason=reason, claim_ids=list(claim_ids), changes=list(writes),
                    source_refs=sorted(set(refs) | set(definition.source_refs)),
                    assumption_refs=list(definition.assumption_refs), transition_class=None)
            module = next((m for m in self.catalog.modules if m.domain == definition.domain), None)
            hook = None if module is None else next((h for h in module.transitions if
                (h.mechanism.id, h.mechanism.version, h.entity_id, h.scope_id, h.status) ==
                (definition.id, definition.version, instance.entity_id, instance.scope_id, 'proposal_only')), None)
            if definition.support.transition is None or hook is None:
                steps[identity] = step('coverage_gap', 'missing_transition_model')
                continue
            if 'goals' in definition.read_partitions:
                raise TransitionError('goal_partition_not_physical_input')
            self.mechanisms.activate(definition.id, definition.version, phase='transition', world=world,
                entity_id=instance.entity_id, scope_id=instance.scope_id)
            if definition.preconditions:
                if identity not in static_ids:
                    steps[identity] = step('unresolved', 'transition_preconditions_unbound')
                    unknown_model = True
                    continue
                if staged_evaluation is None:
                    staged_evaluation = evaluate(graph(inputs, experiment.context.civilization_id), inputs.design,
                        inputs.assumptions, self.mechanisms.model, registry=self.mechanisms)
                statuses = [o.status for o in staged_evaluation.observations
                            if o.node[0] == 'output' and o.node[1] == identity]
                if statuses and all(s == 'not_applicable' for s in statuses):
                    steps[identity] = step('not_applicable', 'declared_precondition_not_applicable')
                    continue
                if not statuses or any(s not in ('known', 'partial') for s in statuses):
                    steps[identity] = step('unresolved', 'declared_precondition_unresolved')
                    unknown_model = True
                    continue
            procedure = definition.support.transition
            if procedure.kind != 'trusted_python':
                steps[identity] = step('coverage_gap', 'transition_adapter_unavailable')
                continue
            callback = next(i.callback for i in self.mechanisms.implementations if i.key ==
                (procedure.implementation.id, procedure.implementation.version, 'transition'))
            if not isinstance(callback, TransitionAdapter):
                steps[identity] = step('coverage_gap', 'transition_adapter_unavailable')
                continue
            invocation = TransitionInvocation(inputs=_physical_view(inputs, definition,
                mechanisms=self.mechanisms, civilization_id=experiment.context.civilization_id), instance=instance,
                opening_day=opening.record.day, day=due.day, allocation=None, claim_ids=[],
                pending_claims=[o for cid, o in claim_owners.items()
                                if o.instance_id == identity and prior_unmet.get(cid, 0)],
                conditions=[dict(scope_id=s, condition_id=c, value=v) for (s, c), v in sorted(facts.items())])
            try:
                proposed = _pure(callback, invocation)
                proposal = TransitionProposal.model_validate_json(proposed.model_dump_json())
            except TransitionUnresolved as error:
                steps[identity] = step('unresolved', 'model_unresolved')
                unknown_model = True
                continue
            allowed_sources = set(definition.source_refs)
            allowed_sources.update(ref for v in invocation.inputs.values for ref in v.provenance.source_refs)
            allowed_sources.update(ref for owner in invocation.pending_claims for ref in owner.choice.source_refs)
            if not set(proposal.source_refs) <= allowed_sources & self.mechanisms.source_ids:
                raise TransitionError('unknown_transition_provenance')
            local_ids = [d.claim.id for d in proposal.demands]
            if len(local_ids) != len(set(local_ids)):
                raise TransitionError('duplicate_transition_demand')
            refined = []
            for refinement in proposal.refinements:
                checkpoint()
                owner = claim_owners.get(refinement.claim_id)
                if (proposal.status != 'ready' or owner is None or owner.instance_id != identity
                        or not prior_unmet.get(refinement.claim_id, 0)
                        or refinement.claim_id in refined):
                    raise TransitionError('foreign_or_closed_pending_refinement')
                old, new = owner.choice, refinement.replacement
                immutable = {'access', 'funding_known', 'source_refs'}
                if (refinement.expected_digest != digest(old)
                        or digest(old.model_dump(exclude=immutable)) != digest(new.model_dump(exclude=immutable))
                        or (old.access != new.access and old.access != 'unknown')
                        or (old.funding_known and not new.funding_known)
                        or not set(old.source_refs) <= set(new.source_refs) <= allowed_sources & self.mechanisms.source_ids):
                    raise TransitionError('invalid_pending_refinement')
                claim_owners[owner.claim_id] = owner.model_copy(update={'choice': new})
                refined.append(owner.claim_id)
            ids = [cid for cid, owner in claim_owners.items()
                   if owner.instance_id == identity and prior_unmet.get(cid, 0)]
            for demand in proposal.demands:
                checkpoint()
                if base is None:
                    raise TransitionError('transition_book_required')
                if demand.claim.claimant_id != instance.entity_id:
                    raise TransitionError('foreign_transition_claimant')
                if (demand.choice.mechanism_ref != definition.id or
                        not set([*demand.claim.source_refs, *demand.choice.source_refs]) <= allowed_sources & self.mechanisms.source_ids):
                    raise TransitionError('foreign_transition_demand_provenance')
                cid = digest(dict(transition=identity, day=due.day, claim=demand.claim.id))
                ids.append(cid)
                new_claims.append(demand.claim.model_copy(update={'id': cid}))
                selected_choice = demand.choice.model_copy(update={'claim_id': cid,
                    **({'access': 'unknown'} if proposal.status == 'unresolved' else {})})
                new_choices.append(selected_choice)
                claim_owners[cid] = TransitionClaimOwner(instance_id=identity, claim_id=cid, choice=selected_choice,
                    original_requested=encoded(Fraction(parse(demand.claim.requested))), fulfilled_prior='0')
                new_order.append(cid)
            proposals[identity], adapters[identity] = proposal, callback
            if proposal.status == 'unresolved' and not proposal.demands:
                unknown_model = True
            invocations[identity] = invocation.model_copy(update={'claim_ids': ids})
            steps[identity] = step('unresolved', proposal.reason, ids, refs=proposal.source_refs)
            steps[identity] = steps[identity].model_copy(update={'transition_class': proposal.transition_class})
            steps[identity] = steps[identity].model_copy(update={'refined_claim_ids': refined})
        checkpoint(len(new_claims))
        request, allocation, balances = None, None, []
        if base is not None:
            initial = AccountBook(base.batch, self.mechanisms.units).evaluate()
            unmet = {c.claim_id: Fraction(c.unmet) for c in initial.claims}
            # Fulfilled historical claims remain inspectable, but cannot acquire
            # more resources or introduce a false current allocation feedback edge.
            old_choices = []
            opening_terms = {} if plan.opening is None else {c.claim_id: c for c in plan.opening.choices}
            for choice in base.choices:
                owner = claim_owners.get(choice.claim_id)
                original = opening_terms.get(choice.claim_id, choice) if owner is None else owner.choice
                if not unmet[choice.claim_id]:
                    original = original.model_copy(update={'access': 'denied', 'access_limit': '0',
                        'funding_known': True, 'requirements': [], 'outputs': [], 'loss_per_unit': '0'})
                elif owner is not None and (owner.instance_id not in proposals or
                        proposals[owner.instance_id].status == 'unresolved'):
                    original = original.model_copy(update={'access': 'unknown'})
                old_choices.append(original)
            if unknown_model:
                # An unresolved selected model with no known footprint cannot be
                # silently treated as zero demand. Preserve the book and allow
                # independently resource-free effects; no default winner exists.
                old_choices = [c.model_copy(update={'access': 'unknown'}) for c in old_choices]
                new_choices = [c.model_copy(update={'access': 'unknown'}) for c in new_choices]
            order = ([*base.claim_order, *new_order] if plan.carry_priority == 'existing_first'
                     else [*new_order, *base.claim_order])
            request = AllocationRequest.model_validate(base.model_dump() | dict(
                batch=base.batch.model_copy(update={'claims': [*base.batch.claims, *new_claims]}),
                choices=[*old_choices, *new_choices], claim_order=order))
            checkpoint(len(request.batch.postings) + len(request.batch.claims))
            try:
                allocation = allocate(request, self.mechanisms.units)
            except AccountError as error:
                if error.code != 'coupled_allocation_requires_solver':
                    raise
                # Preserve the complete pending request, without pretending a
                # single pass solved allocation feedback or consuming anything.
            batch = allocation.batch if allocation else request.batch
            accounts = allocation.accounts if allocation else AccountBook(batch, self.mechanisms.units).evaluate()
            balances = balance_witnesses(batch, accounts)
            closing_values = {a.account_id: a.closing for a in accounts.accounts}
            values = {v.id: v for v in inputs.values}
            book_writes = []
            for binding in plan.account_bindings:
                row = values[binding.value_id]
                book_writes.append(row.model_copy(update={'value': row.value.model_copy(update={
                    'value': closing_values[binding.account_id]}), 'effective_time': inputs.design.effective_time}))
            world = world.with_values(writer_id=ACCOUNT_OWNER, partition='dynamic_state', changes=book_writes)
            inputs = inputs.model_copy(update={'values': list(world.values)})
        checkpoint()
        written = {b.value_id for b in plan.account_bindings}
        written_slots = {(v.entity_id, v.property_id, v.scope_id, v.partition)
                         for v in inputs.values if v.id in written}
        writes_by_instance = {}
        for identity, proposal in proposals.items():
            checkpoint()
            owned_ids = set(invocations[identity].claim_ids)
            ordered_ids = [] if request is None else [cid for cid in request.claim_order if cid in owned_ids]
            invocation = invocations[identity].model_copy(update={'allocation': allocation, 'claim_ids': ordered_ids})
            invocations[identity] = invocation
            steps[identity] = steps[identity].model_copy(update={'claim_ids': ordered_ids})
            if proposal.status == 'unresolved' or (invocation.claim_ids and (allocation is None or allocation.status == 'unresolved')):
                steps[identity] = steps[identity].model_copy(update={'reason':
                    'allocation_feedback_requires_solver' if invocation.claim_ids and allocation is None else
                    'unresolved_finite_allocation' if invocation.claim_ids else proposal.reason})
                continue
            try:
                raw = _pure(adapters[identity].resolve, invocation, proposal)
            except TransitionUnresolved:
                # Resource spending cannot survive a failed post-allocation model.
                raise TransitionError('unresolved_after_allocation')
            writes = [PartitionValueDTO.model_validate_json(w.model_dump_json()) for w in raw]
            if len(writes) > 100:
                raise TransitionError('transition_write_limit')
            for write in writes:
                slot = write.entity_id, write.property_id, write.scope_id, write.partition
                if write.id in written or slot in written_slots or write.effective_time != inputs.design.effective_time:
                    raise TransitionError('conflicting_or_mistimed_transition_write')
                written.add(write.id)
                written_slots.add(slot)
            instance = invocation.instance
            definition = self.mechanisms.definition(instance.mechanism_id, instance.mechanism_version)
            world = stage_transition(catalog=self.catalog, mechanisms=self.mechanisms, world=world,
                module_domain=definition.domain, mechanism=(definition.id, definition.version),
                entity_id=instance.entity_id, scope_id=instance.scope_id, changes=writes)
            writes_by_instance[identity] = writes
            steps[identity] = steps[identity].model_copy(update={'status': 'applied', 'changes': writes, 'reason': 'validated_actual_allocation'})
        closing = inputs.model_copy(update={'values': list(world.values)})
        for identity, writes in writes_by_instance.items():
            checkpoint()
            closing_view = _physical_view(closing, mechanisms=self.mechanisms,
                civilization_id=experiment.context.civilization_id)
            if _pure(adapters[identity].validate, invocations[identity], proposals[identity], writes, closing_view) is not None:
                raise TransitionError('invalid_model_validation_result')
        checkpoint()
        result = evaluate(graph(closing, experiment.context.civilization_id), closing.design,
            closing.assumptions, self.mechanisms.model, registry=self.mechanisms)
        if any(o.status == 'solver_failure' for o in result.observations):
            raise TransitionError('closing_solver_failure')
        evidence = retain(result, observe(result, closing.measurements, closing.goals), closing.references)
        checkpoint()
        unresolved_book = request is not None and (allocation is None or allocation.status == 'unresolved')
        coverage = ('unresolved' if unresolved_book or any(s.status == 'unresolved' for s in steps.values()) else
                    'partial' if any(s.status == 'coverage_gap' for s in steps.values()) else 'complete')
        payload = dict(transition_contract=1, reducer_id=REDUCER_ID, opening_digest=opening.record.boundary_digest,
            plan_digest=digest(plan), day=due.day, request=request, allocation=allocation,
            steps=sorted(steps.values(), key=lambda s: s.instance_id), balances=balances,
            claim_owners=sorted(claim_owners.values(), key=lambda c: c.claim_id), coverage=coverage)
        receipt = TransitionReceipt(**payload, receipt_digest=digest(payload))
        return BoundaryCandidate(inputs=closing, evidence=evidence, transition=receipt)

    def preview(self, expected, day, *, cancelled=None):
        opening = self.store.read(expected.context)
        if outcome(opening.record) != expected:
            raise BoundaryError('stale_boundary')
        _, experiment = self.store._experiment(expected.context)
        if day <= opening.record.day:
            raise TransitionError('past_target_requires_fork')
        due = next(boundaries(experiment.plan, day, after_day=opening.record.day))
        if due.day != day:
            raise TransitionError('skipped_required_boundary')
        return self._reduce(opening, experiment, due, cancelled=cancelled)

    def validate(self, validation):
        self._validate_cancellable(validation, None)

    def advance_boundary(self, expected, day, *, operation_id, cancelled=None):
        TypeAdapter(Identifier).validate_python(operation_id, strict=True)
        # Recover a completed boundary before requiring executable models. A saved
        # candidate reconstructs the exact request, whose operation binding must
        # still match; a reused ID never authorizes a different payload.
        try:
            saved = self.store.read(expected.context, expected.sequence + 1)
        except BoundaryError as error:
            if str(error) != 'unknown_confirmed_boundary':
                raise
        else:
            if saved.record.parent_digest == expected.boundary_digest:
                replay = ConfirmBoundary(boundary_contract=1, expected=expected, operation_id=operation_id,
                    candidate=BoundaryCandidate(inputs=saved.state.inputs, evidence=saved.evidence, transition=saved.state.transition))
                old = self.store.status(replay)
                if old is not None:
                    if saved.record.day != day:
                        raise TransitionError('operation_id_bound_to_different_boundary')
                    return old
        candidate = self.preview(expected, day, cancelled=cancelled)
        request = ConfirmBoundary(boundary_contract=1, expected=expected, operation_id=operation_id, candidate=candidate)
        # Carry cancellation into the validation recomputation as well as writes.
        previous = self.store.validator
        self.store.validator = lambda check: self._validate_cancellable(check, cancelled)
        try:
            return self.store.confirm(request, cancelled=cancelled)
        finally:
            self.store.validator = previous

    def _validate_cancellable(self, validation, cancelled):
        _, experiment = self.store._experiment(validation.opening.record.context)
        expected = self._reduce(validation.opening, experiment, validation.due, cancelled=cancelled)
        if (digest(expected.inputs) != digest(validation.closing.inputs) or digest(expected.evidence) != digest(validation.evidence)
                or digest(expected.transition) != digest(validation.closing.transition)):
            raise TransitionError('transition_candidate_mismatch')

    def run_chunk(self, expected, target_day, *, operation_prefix, max_boundaries, cancelled=None, progress=None):
        TypeAdapter(Identifier).validate_python(operation_prefix, strict=True)
        if type(max_boundaries) is not int or not 1 <= max_boundaries <= 1000:
            raise TransitionError('invalid_chunk_quota')
        _, experiment = self.store._experiment(expected.context)
        if outcome(self.store.read(expected.context).record) != expected:
            raise BoundaryError('stale_boundary')
        current, completed = expected, 0
        coverage = 'not_assessed'
        def event(status):
            nonlocal coverage
            saved = self.store.read(current.context, current.sequence)
            observed = 'not_assessed' if saved.state.transition is None else saved.state.transition.coverage
            rank = {'not_assessed': -1, 'complete': 0, 'partial': 1, 'unresolved': 2}
            if rank[observed] > rank[coverage]:
                coverage = observed
            return ChunkProgress(day=current.day, sequence=current.sequence, boundary_digest=current.boundary_digest,
                completed=completed, status=status, coverage=coverage)
        for due in boundaries(experiment.plan, target_day, after_day=expected.day):
            if completed == max_boundaries:
                break
            try:
                current = self.advance_boundary(current, due.day,
                    operation_id=digest(dict(prefix=operation_prefix, opening_digest=current.boundary_digest, day=due.day)),
                    cancelled=cancelled)
            except BoundaryError as error:
                if str(error) != 'boundary_cancelled':
                    raise
                return event('cancelled')
            completed += 1
            report = event('confirmed')
            if progress is not None:
                progress(report)
        return event('complete' if current.day == target_day else 'quota')
