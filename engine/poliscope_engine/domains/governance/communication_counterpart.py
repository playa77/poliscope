"""Reviewed opaque host bindings for the actual DOM-03/09 counterpart."""
from decimal import Decimal
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.contracts.governance_communication import GovernanceCommunicationRequest
from poliscope_engine.mechanisms import MechanismRegistry, Implementation
from poliscope_engine.numeric import TimeBasis, RUNTIME_ID
from .communication import evaluate_pair, validate_context, binding, MODEL
from ..provisioning.context import digest


FIXTURE = ('synthetic:governance-communication', 'v1')
SOURCE = 'authored:governance-communication-v1'
CATALOG_ID = 'authored:governance-communication-catalog-v1'
CONTEXT = 'gc:context'
WORK = 'gc:administration-book'
BOOK = 'gc:administration-book-in'
CANDIDATE = 'gc:candidate'


def definitions():
    import json
    from pathlib import Path
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    return tuple(MechanismDefinition.model_validate(d) for d in json.loads(
        Path(__file__).with_name('communication-counterpart-v1.json').read_text()))


def policy_registry(*, units, reviews):
    """Fixed policy declaration; resolution uses the normal reviewed gate."""
    def no_execution(*args, **kwargs):
        fail('policy_callback_not_executable')
    return MechanismRegistry(model=MODEL, units=units,
        times=(TimeBasis('day:0', Decimal(86400)),), source_ids=[SOURCE],
        fixture_ids=[FIXTURE], definitions=definitions(), reviews=reviews,
        implementations=[Implementation('authored:gc-policy', 'v1', 'static', no_execution)])


def host_registry(request, *, graph, units, reviews):
    from poliscope_engine.domains.law_conflict.health_counterpart import definitions as ah_definitions
    from poliscope_engine.domains.law_conflict.education_counterpart import definitions as ae_definitions
    from poliscope_engine.domains.law_conflict.care_counterpart import definitions as ac_definitions
    from poliscope_engine.domains.governance.continuity_counterpart import definitions as gk_definitions
    from poliscope_engine.domains.governance.participation_counterpart import definitions as gp_definitions
    """Create a private immutable request binding. Reviews are explicit host input.

    Registering declarations never activates them. Normal MechanismRegistry review,
    context and fixture checks still apply. This host is not public IPC support.
    """
    from poliscope_engine.domains.economy.infrastructure_counterpart import definitions as economy_infrastructure_definitions
    from ..provisioning.counterpart import education_definitions, continuity_definitions, infrastructure_definitions, definitions as economy_definitions, care_definitions, health_definitions, environment_definitions
    from ..economy.governance_counterpart import definitions as governance_definitions
    from ..economy.adjudication_counterpart import definitions as adjudication_definitions
    from ..economy.care_counterpart import definitions as economy_care_definitions
    from .adjudication_counterpart import definitions as governance_adjudication_definitions
    from .education_counterpart import definitions as governance_education_definitions
    mechanisms = policy_registry(units=units, reviews=reviews)
    from poliscope_engine.domains.economy.health_counterpart import definitions as economy_health_definitions
    from poliscope_engine.domains.economy.education_counterpart import definitions as economy_education_definitions
    request = GovernanceCommunicationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    encoded = request.model_dump_json()
    context = binding(request, graph, units, mechanisms)

    def current():
        return GovernanceCommunicationRequest.model_validate_json(encoded)

    def evaluate():
        return evaluate_pair(current(), graph=graph, units=units, mechanisms=mechanisms)

    def work(port, inputs):
        if port != WORK or inputs[CONTEXT].kind != 'label' or inputs[CONTEXT].value != context:
            fail('stale_counterpart_context')
        from poliscope_engine.domains.governance import evaluate_governance
        result = evaluate_governance(current().governance, graph=graph, units=units, mechanisms=mechanisms)
        if result.status != 'resolved':
            return dict(kind='unknown', reason='Unresolved decision prerequisites; no staged book')
        return dict(kind='label', value=digest(dict(context=context,
            governance=result.model_dump(mode='json'))))

    def communication(port, inputs):
        expected = work(WORK, {CONTEXT: LabelValue(kind='label', value=context)})
        if (port != CANDIDATE or inputs[BOOK].kind != 'label'
                or expected['kind'] != 'label' or inputs[BOOK].value != expected['value']):
            fail('stale_counterpart_book')
        result = evaluate()
        if result.candidate is None:
            return dict(kind='unknown', reason='Unresolved communication; no complete candidate')
        return dict(kind='label', value=digest(result.model_dump(mode='json')))

    return MechanismRegistry(model=MODEL, units=units,
        times=(TimeBasis('day:0', Decimal(86400)),), source_ids=['authored:adjudication-health-v1', 'authored:adjudication-education-v1', 'authored:adjudication-care-v1', 'authored:governance-continuity-v1', 'authored:governance-participation-v1', SOURCE, 'authored:governance-education-v1', 'authored:governance-adjudication-v1', 'authored:economy-adjudication-v1', 'authored:economy-infrastructure-v1', 'authored:economy-health-v1', 'authored:economy-education-v1', 'authored:economy-care-v1', 'authored:economy-governance-v1', 'authored:provisioning-education-v1', 'authored:provisioning-environment-v1', 'authored:provisioning-continuity-v1', 'authored:provisioning-infrastructure-v1', 'authored:provisioning-health-v1', 'authored:provisioning-economy-v1', 'authored:provisioning-care-v1'],
        fixture_ids=[('synthetic:adjudication-health', 'v1'), ('synthetic:adjudication-education', 'v1'), ('synthetic:adjudication-care', 'v1'), ('synthetic:governance-continuity', 'v1'), ('synthetic:governance-participation', 'v1'), FIXTURE, ('synthetic:governance-education', 'v1'), ('synthetic:governance-adjudication', 'v1'), ('synthetic:economy-adjudication', 'v1'), ('synthetic:economy-infrastructure', 'v1'), ('synthetic:economy-health', 'v1'), ('synthetic:economy-education', 'v1'), ('synthetic:economy-care', 'v1'), ('synthetic:economy-governance', 'v1'), ('synthetic:provisioning-education', 'v1'), ('synthetic:provisioning-environment', 'v1'), ('synthetic:provisioning-continuity', 'v1'), ('synthetic:provisioning-infrastructure', 'v1'), ('synthetic:provisioning-health', 'v1'), ('synthetic:provisioning-economy', 'v1'), ('synthetic:provisioning-care', 'v1')],
        definitions=(*ah_definitions(), *ae_definitions(), *ac_definitions(), *gk_definitions(), *gp_definitions(), *definitions(), *governance_education_definitions(), *governance_adjudication_definitions(), *adjudication_definitions(), *economy_infrastructure_definitions(), *economy_health_definitions(), *economy_education_definitions(), *economy_care_definitions(), *governance_definitions(), *environment_definitions(), *continuity_definitions(), *infrastructure_definitions(), *health_definitions(), *education_definitions(), *economy_definitions(), *care_definitions()), reviews=reviews,
        implementations=[Implementation('authored:gc-administration', 'v1', 'static', work),
                         Implementation('authored:gc-communication', 'v1', 'static', communication),
                         *mechanisms.implementations])


def run_bound_case(case, *, request, units, reviews):
    """Common conformance using a fresh host bound to the actual case world.

    The fixed context input remains authored by the caller. A stale context from
    another request/world cannot become a successful case by reusing callbacks.
    """
    from poliscope_engine.contracts.revisions import RevisionInputs
    from poliscope_engine.domains import conformance_catalog, ConformanceError
    from poliscope_engine.domains.conformance import run_case
    from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration
    from poliscope_engine.world.membership import WorldGraph
    mechanisms = policy_registry(units=units, reviews=reviews)
    inputs = RevisionInputs.model_validate_json(case.inputs.model_dump_json())
    if (inputs.versions.model_id != MODEL[0]
            or inputs.versions.numeric_runtime_id != RUNTIME_ID
            or inputs.versions.catalog_id != CATALOG_ID):
        raise ConformanceError('counterpart_version_mismatch')
    civs = [e.id for e in inputs.entities if e.entity_kind == 'civilization']
    if len(civs) != 1:
        fail('counterpart_civilization_identity')
    world = WorldRegistry(civs[0], entities=inputs.entities, scopes=inputs.scopes,
        values=inputs.values, owners=[StateOwner(**o.model_dump()) for o in inputs.owners],
        populations=[PopulationDeclaration(**p.model_dump()) for p in inputs.populations])
    graph = WorldGraph(world, inputs.relationships)
    contexts = [f.value for f in inputs.design.execution.dependencies.fixed_inputs
                if (f.consumer.instance_id, f.consumer.port_id) == ('work', CONTEXT)]
    if contexts != [LabelValue(kind='label', value=binding(request, graph, units, mechanisms))]:
        raise ConformanceError('stale_counterpart_context')
    registry = host_registry(request, graph=graph, units=units, reviews=reviews)
    catalog = conformance_catalog()
    return run_case(case, catalog=catalog, mechanisms=registry,
        branch_ids=[c.branch_id for m in catalog.modules for c in m.coverage])
