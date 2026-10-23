"""Trusted host binding for the real finite DOM-01/12 conformance path.

Label ports carry opaque digests, never stock quantities or execution authority.
The consumer revalidates/recomputes the canonical book bound to this host; no
mutable staging cache or caller-supplied serialized book is accepted.
"""
from poliscope_engine.domains.economy.care_counterpart import definitions as economy_care_definitions
import json
from pathlib import Path

from poliscope_engine.accounts import fail
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.contracts.provisioning_continuity import ProvisioningContinuityRequest
from poliscope_engine.mechanisms import MechanismRegistry, Implementation
from poliscope_engine.numeric import TimeBasis, RUNTIME_ID
from decimal import Decimal
from .continuity import evaluate_pair, validate_context, binding, MODEL
from .context import digest

from poliscope_engine.domains.economy.governance_counterpart import definitions as governance_definitions
from poliscope_engine.domains.economy.adjudication_counterpart import definitions as adjudication_definitions

FIXTURE = ('synthetic:provisioning-continuity', 'v1')
SOURCE = 'authored:provisioning-continuity-v1'
CATALOG_ID = 'authored:provisioning-continuity-catalog-v1'
CONTEXT = 'continuity-pair:context'
WORK = 'continuity-pair:work-book'
BOOK = 'continuity-pair:work-book-in'
CANDIDATE = 'continuity-pair:candidate'


from .counterpart import definitions as economy_definitions, health_definitions, care_definitions, education_definitions, infrastructure_definitions, environment_definitions


def other_definitions():
    return (*environment_definitions(), *economy_definitions(), *health_definitions(), *care_definitions(), *education_definitions(), *infrastructure_definitions())


def definitions():
    data = json.loads(Path(__file__).with_name('continuity-counterpart-v1.json').read_text())
    return tuple(MechanismDefinition.model_validate(d) for d in data)


def host_registry(request, *, graph, units, reviews):
    from poliscope_engine.domains.governance.education_counterpart import definitions as ge_definitions
    from poliscope_engine.domains.governance.adjudication_counterpart import definitions as ga_definitions
    from poliscope_engine.domains.economy.infrastructure_counterpart import definitions as economy_infrastructure_definitions
    from poliscope_engine.domains.economy.health_counterpart import definitions as economy_health_definitions
    """Create a private immutable request binding. Reviews are explicit host input.

    Registering declarations never activates them. Normal MechanismRegistry review,
    context and fixture checks still apply. This host is not public IPC support.
    """
    from poliscope_engine.domains.economy.education_counterpart import definitions as economy_education_definitions
    request = ProvisioningContinuityRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    encoded = request.model_dump_json()
    context = binding(request, graph, units)

    def current():
        return ProvisioningContinuityRequest.model_validate_json(encoded)

    def evaluate():
        return evaluate_pair(current(), graph=graph, units=units)

    def work(port, inputs):
        if port != WORK or inputs[CONTEXT].kind != 'label' or inputs[CONTEXT].value != context:
            fail('stale_counterpart_context')
        from poliscope_engine.domains.security_risk import evaluate_continuity
        result = evaluate_continuity(current().continuity, graph=graph, units=units)
        if result.status != 'resolved':
            return dict(kind='unknown', reason='Unresolved response-slot reach; no prerequisite evidence')
        return dict(kind='label', value=digest(dict(context=context,
            continuity=result.model_dump(mode='json'))))

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
        times=(TimeBasis('day:0', Decimal(86400)),), source_ids=['authored:governance-education-v1', 'authored:governance-adjudication-v1', SOURCE, 'authored:economy-infrastructure-v1', 'authored:economy-health-v1', 'authored:economy-education-v1', 'authored:economy-care-v1', 'authored:economy-adjudication-v1', 'authored:economy-governance-v1', 'authored:provisioning-environment-v1', 'authored:provisioning-infrastructure-v1', 'authored:provisioning-economy-v1', 'authored:provisioning-health-v1', 'authored:provisioning-care-v1', 'authored:provisioning-education-v1'],
        fixture_ids=[('synthetic:governance-education', 'v1'), ('synthetic:governance-adjudication', 'v1'), FIXTURE, ('synthetic:economy-infrastructure', 'v1'), ('synthetic:economy-health', 'v1'), ('synthetic:economy-education', 'v1'), ('synthetic:economy-care', 'v1'), ('synthetic:economy-adjudication', 'v1'), ('synthetic:economy-governance', 'v1'), ('synthetic:provisioning-environment', 'v1'), ('synthetic:provisioning-infrastructure', 'v1'), ('synthetic:provisioning-economy', 'v1'), ('synthetic:provisioning-health', 'v1'), ('synthetic:provisioning-care', 'v1'), ('synthetic:provisioning-education', 'v1')],
        definitions=(*ge_definitions(), *ga_definitions(), *definitions(), *economy_infrastructure_definitions(), *economy_health_definitions(), *economy_education_definitions(), *economy_care_definitions(), *adjudication_definitions(), *governance_definitions(), *other_definitions()), reviews=reviews,
        implementations=[Implementation('authored:continuity-pair-work', 'v1', 'static', work),
                         Implementation('authored:continuity-pair-provisioning', 'v1', 'static', provisioning)])


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
    if contexts != [LabelValue(kind='label', value=binding(request, graph, units))]:
        raise ConformanceError('stale_counterpart_context')
    registry = host_registry(request, graph=graph, units=units, reviews=reviews)
    catalog = conformance_catalog()
    return run_case(case, catalog=catalog, mechanisms=registry,
        branch_ids=[c.branch_id for m in catalog.modules for c in m.coverage])
