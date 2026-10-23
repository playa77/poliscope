"""Explicit reviewed host bindings for the real DOM-01/07 counterpart."""
from decimal import Decimal
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.contracts.provisioning_health import ProvisioningHealthRequest
from poliscope_engine.mechanisms import MechanismRegistry, Implementation
from poliscope_engine.numeric import TimeBasis, RUNTIME_ID
from .health import evaluate_pair, validate_context, binding, MODEL
from .context import digest
from .counterpart import continuity_definitions, infrastructure_definitions, health_definitions as definitions, definitions as economy_definitions, care_definitions, education_definitions, environment_definitions

FIXTURE = ('synthetic:provisioning-health', 'v1')
SOURCE = 'authored:provisioning-health-v1'
CATALOG_ID = 'authored:provisioning-health-catalog-v1'
CONTEXT = 'health-pair:context'
WORK = 'health-pair:work-book'
BOOK = 'health-pair:work-book-in'
CANDIDATE = 'health-pair:candidate'


def policy_registry(*, units, reviews):
    """Fixed policy declaration; resolution uses the normal reviewed gate."""
    def no_execution(*args, **kwargs):
        fail('policy_callback_not_executable')
    return MechanismRegistry(model=MODEL, units=units,
        times=(TimeBasis('day:0', Decimal(86400)),), source_ids=[SOURCE],
        fixture_ids=[FIXTURE], definitions=definitions(), reviews=reviews,
        implementations=[Implementation('authored:health-policy', 'v1', 'static', no_execution)])


def host_registry(request, *, graph, units, reviews):
    """Create a private immutable request binding. Reviews are explicit host input.

    Registering declarations never activates them. Normal MechanismRegistry review,
    context and fixture checks still apply. This host is not public IPC support.
    """
    mechanisms = policy_registry(units=units, reviews=reviews)
    request = ProvisioningHealthRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    encoded = request.model_dump_json()
    context = binding(request, graph, units, mechanisms)

    def current():
        return ProvisioningHealthRequest.model_validate_json(encoded)

    def evaluate():
        return evaluate_pair(current(), graph=graph, units=units, mechanisms=mechanisms)

    def work(port, inputs):
        if port != WORK or inputs[CONTEXT].kind != 'label' or inputs[CONTEXT].value != context:
            fail('stale_counterpart_context')
        from poliscope_engine.domains.health import evaluate_health
        result = evaluate_health(current().health, graph=graph, units=units, mechanisms=mechanisms)
        if result.status != 'resolved':
            return dict(kind='unknown', reason='Unresolved health prerequisites; no staged book')
        return dict(kind='label', value=digest(dict(context=context,
            health=result.model_dump(mode='json'))))

    def provisioning(port, inputs):
        expected = work(WORK, {CONTEXT: LabelValue(kind='label', value=context)})
        if (port != CANDIDATE or inputs[BOOK].kind != 'label'
                or expected['kind'] != 'label' or inputs[BOOK].value != expected['value']):
            fail('stale_counterpart_book')
        result = evaluate()
        if result.batch is None:
            return dict(kind='unknown', reason='Unresolved provisioning; no complete candidate')
        return dict(kind='label', value=digest(result.model_dump(mode='json')))

    return MechanismRegistry(model=MODEL, units=units,
        times=(TimeBasis('day:0', Decimal(86400)),), source_ids=[SOURCE, 'authored:provisioning-environment-v1', 'authored:provisioning-continuity-v1', 'authored:provisioning-infrastructure-v1', 'authored:provisioning-education-v1', 'authored:provisioning-economy-v1', 'authored:provisioning-care-v1'],
        fixture_ids=[FIXTURE, ('synthetic:provisioning-environment', 'v1'), ('synthetic:provisioning-continuity', 'v1'), ('synthetic:provisioning-infrastructure', 'v1'), ('synthetic:provisioning-education', 'v1'), ('synthetic:provisioning-economy', 'v1'), ('synthetic:provisioning-care', 'v1')],
        definitions=(*definitions(), *environment_definitions(), *continuity_definitions(), *infrastructure_definitions(), *education_definitions(), *economy_definitions(), *care_definitions()), reviews=reviews,
        implementations=[Implementation('authored:health-work', 'v1', 'static', work),
                         Implementation('authored:health-provisioning', 'v1', 'static', provisioning),
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
