from poliscope_engine.contracts.provisioning_education import ProvisioningEducationRequest, ProvisioningEducationEvaluation
from poliscope_engine.contracts.provisioning_care import ProvisioningCareRequest, ProvisioningCareEvaluation
from poliscope_engine.contracts.workbench import workbench_adapter
from poliscope_engine.contracts.exploration import exploration_adapter
"""Generate bounded runtime artifacts from canonical Pydantic schemas."""
import argparse
import json
from pathlib import Path
from poliscope_engine.contracts.comparison import comparison_adapter
from poliscope_engine.contracts.overview import overview_adapter
from poliscope_engine.contracts.workspace import workspace_adapter
from poliscope_engine.contracts.atlas import atlas_adapter
from poliscope_engine.contracts.matrix import matrix_adapter
from poliscope_engine.contracts.interview import interview_adapter
from poliscope_engine.contracts import adapter
from poliscope_engine.contracts.history import history_adapter, SavedEvidence
from poliscope_engine.contracts.packs import Pack
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.expressions import ExpressionGraph
from poliscope_engine.contracts.policies import PolicyBinding, ResolutionRule, PolicyEvaluation
from poliscope_engine.contracts.accounts import AccountBatch, AccountEvaluation
from poliscope_engine.contracts.allocations import AllocationRequest, AllocationEvaluation
from poliscope_engine.contracts.security_risk import ContinuityRequest, ContinuityEvaluation, ContinuityInterview, ContinuityEdit, ContinuityReport, ContinuityPreview, ContinuityCoverage
from poliscope_engine.contracts.meaning_identity import ParticipationRequest, ParticipationEvaluation, ParticipationInterview, ParticipationEdit, ParticipationReport, ParticipationPreview, ParticipationCoverage
from poliscope_engine.contracts.environment import EnvironmentRequest, EnvironmentEvaluation, EnvironmentInterview, EnvironmentEdit, EnvironmentReport, EnvironmentPreview, EnvironmentCoverage
from poliscope_engine.contracts.communication import CommunicationRequest, CommunicationEvaluation, CommunicationInterview, CommunicationEdit, CommunicationReport, CommunicationPreview, CommunicationCoverage
from poliscope_engine.contracts.infrastructure import InfrastructureRequest, InfrastructureEvaluation, InfrastructureInterview, InfrastructureEdit, InfrastructureReport, InfrastructurePreview, InfrastructureCoverage
from poliscope_engine.contracts.health import HealthRequest, HealthEvaluation, HealthInterview, HealthEdit, HealthReport, HealthPreview, HealthCoverage
from poliscope_engine.contracts.knowledge_culture import EducationRequest, EducationEvaluation, EducationInterview, EducationEdit, EducationReport, EducationPreview, EducationCoverage
from poliscope_engine.contracts.social_organization import CareRequest, CareEvaluation, CareInterview, CareEdit, CareReport, CarePreview, CareCoverage
from poliscope_engine.contracts.law_conflict import AdjudicationRequest, AdjudicationEvaluation, AdjudicationInterview, AdjudicationEdit, AdjudicationReport, AdjudicationPreview, AdjudicationCoverage
from poliscope_engine.contracts.governance import GovernanceRequest, GovernanceEvaluation, GovernanceInterview, GovernanceEdit, GovernanceReport, GovernancePreview, GovernanceCoverage
from poliscope_engine.contracts.economy import EconomyRequest, EconomyEvaluation, EconomyInterview, EconomyEdit, EconomyReport, EconomyPreview, EconomyCoverage
from poliscope_engine.contracts.logistics import LogisticsRequest, LogisticsEvaluation
from poliscope_engine.contracts.provisioning_economy import ProvisioningEconomyRequest, ProvisioningEconomyEvaluation
from poliscope_engine.contracts.provisioning import (ProvisioningRequest, ProvisioningEvaluation, ProvisioningInterview, ProcedureEdit, ProvisioningReport, ProvisioningPreview, ProvisioningCoverage)
from poliscope_engine.contracts.dependencies import DependencyRequest
from poliscope_engine.contracts.solvers import ExecutionRequest
from poliscope_engine.contracts.evaluation import EvaluationDesign, EvaluationResult
from poliscope_engine.contracts.content import ContentRelease
from poliscope_engine.contracts.domains import DomainModule, PairedDomainContract
from pydantic import TypeAdapter
from poliscope_engine.contracts.measurements import MeasurementReport, AcceptedEvidence, TraceQuery, CalculationTracePage, PublicEvidenceProjection
from typing import Union
from poliscope_engine.contracts.revisions import (CreateRequest, PreviewRequest, Candidate, ApplyRequest, BranchRequest, BranchState, RevisionRecord, MutationOutcome, HistoryQuery, HistoryPage)

ROOT = Path(__file__).resolve().parents[1]

def ts(schema):
    if '$ref' in schema:
        return schema['$ref'].rsplit('/', 1)[1]
    if 'const' in schema:
        return json.dumps(schema['const'])
    if 'enum' in schema:
        return ' | '.join(json.dumps(v) for v in schema['enum'])
    for union in ('anyOf', 'oneOf'):
        if union in schema:
            return ' | '.join(ts(v) for v in schema[union])
    kind = schema.get('type')
    if kind == 'object':
        if not schema.get('properties') and len(schema.get('patternProperties', {})) == 1:
            return '{ [key: string]: ' + ts(next(iter(schema['patternProperties'].values()))) + ' }'
        if not schema.get('properties') and isinstance(schema.get('additionalProperties'), dict):
            return '{ [key: string]: ' + ts(schema['additionalProperties']) + ' }'
        return '{ ' + '; '.join(json.dumps(k) + ('' if k in schema.get('required', []) else '?') + ': ' + ts(v) for k, v in schema.get('properties', {}).items()) + ' }'
    if kind == 'array':
        if 'prefixItems' in schema:
            return '[' + ', '.join(ts(v) for v in schema['prefixItems']) + ']'
        return '(' + ts(schema['items']) + ')[]'
    return {'string': 'string', 'integer': 'number', 'null': 'null', 'boolean': 'boolean'}[kind]

def artifacts():
    schema = adapter.json_schema()
    types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in schema['$defs'].items())
    types += '\nexport type WireMessage = ' + ts(schema) + ';\n'
    tools = {name: value['properties']['params'] for name, value in schema['$defs'].items() if name.endswith('Request') and 'params' in value.get('properties', {})}
    history = history_adapter.json_schema()
    history_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    history_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in history['$defs'].items())
    pack_schema = Pack.model_json_schema()
    pack_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    pack_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in pack_schema['$defs'].items())
    pack_types += '\nexport type Pack = ' + ts(pack_schema) + ';\n'
    mechanism_schema = MechanismDefinition.model_json_schema()
    mechanism_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    mechanism_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in mechanism_schema['$defs'].items())
    mechanism_types += '\nexport type MechanismDefinition = ' + ts(mechanism_schema) + ';\n'
    mechanism_fixtures = json.loads((ROOT / 'contracts/mechanism-fixtures.json').read_text())
    for fixture in mechanism_fixtures:
        MechanismDefinition.model_validate(fixture)
    fixture_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    fixture_types += 'import type { MechanismDefinition } from "./mechanism";\n'
    fixture_types += 'export const mechanismFixtures = ' + json.dumps(mechanism_fixtures, indent=2) + ' satisfies MechanismDefinition[];\n'
    expression_schema = ExpressionGraph.model_json_schema()
    expression_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    expression_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in expression_schema['$defs'].items())
    expression_types += '\nexport type ExpressionGraph = ' + ts(expression_schema) + ';\n'
    policy_schema = TypeAdapter(Union[PolicyBinding, ResolutionRule, PolicyEvaluation]).json_schema()
    policy_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    policy_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in policy_schema['$defs'].items()) + '\n'
    account_schema = TypeAdapter(Union[AccountBatch, AccountEvaluation]).json_schema()
    account_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    account_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in account_schema['$defs'].items()) + '\n'
    allocation_schema = TypeAdapter(Union[AllocationRequest, AllocationEvaluation]).json_schema()
    allocation_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    allocation_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in allocation_schema['$defs'].items()) + '\n'
    dependency_schema = DependencyRequest.model_json_schema()
    dependency_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    dependency_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in dependency_schema['$defs'].items())
    dependency_types += '\nexport type DependencyRequest = ' + ts(dependency_schema) + ';\n'
    solver_schema = ExecutionRequest.model_json_schema()
    solver_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    solver_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in solver_schema['$defs'].items())
    solver_types += '\nexport type ExecutionRequest = ' + ts(solver_schema) + ';\n'
    evaluation_schema = TypeAdapter(Union[EvaluationDesign, EvaluationResult]).json_schema()
    evaluation_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    evaluation_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in evaluation_schema['$defs'].items()) + '\n'
    measurement_schema = TypeAdapter(Union[MeasurementReport, AcceptedEvidence, TraceQuery, CalculationTracePage, PublicEvidenceProjection]).json_schema()
    measurement_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    measurement_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in measurement_schema['$defs'].items()) + '\n'
    revision_schema = TypeAdapter(Union[CreateRequest, PreviewRequest, Candidate, ApplyRequest, BranchRequest, BranchState, RevisionRecord, MutationOutcome, HistoryQuery, HistoryPage]).json_schema()
    revision_types = '// Generated by scripts/generate_contracts.py; do not edit.\n'
    revision_types += '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in revision_schema['$defs'].items()) + '\n'
    workspace_schema = workspace_adapter.json_schema()
    workspace_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in workspace_schema['$defs'].items()) + '\n'
    workbench_schema = workbench_adapter.json_schema()
    workbench_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in workbench_schema['$defs'].items()) + '\n'
    exploration_schema = exploration_adapter.json_schema()
    exploration_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in exploration_schema['$defs'].items()) + '\n'
    matrix_schema = matrix_adapter.json_schema()
    matrix_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in matrix_schema['$defs'].items()) + '\n'
    atlas_schema = atlas_adapter.json_schema()
    atlas_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in atlas_schema['$defs'].items()) + '\n'
    interview_schema = interview_adapter.json_schema()
    interview_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in interview_schema['$defs'].items()) + '\n'
    overview_schema = overview_adapter.json_schema()
    overview_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in overview_schema['$defs'].items()) + '\n'
    comparison_schema = comparison_adapter.json_schema()
    comparison_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in comparison_schema['$defs'].items()) + '\n'
    content_schema = ContentRelease.model_json_schema()
    content_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in content_schema['$defs'].items()) + '\nexport type ContentRelease = ' + ts(content_schema) + ';\n'
    domain_schema = TypeAdapter(Union[DomainModule, PairedDomainContract]).json_schema()
    domain_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in domain_schema['$defs'].items()) + '\n'
    logistics_schema = TypeAdapter(Union[LogisticsRequest, LogisticsEvaluation]).json_schema()
    logistics_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in logistics_schema['$defs'].items()) + '\n'
    provisioning_schema = TypeAdapter(Union[ProvisioningRequest, ProvisioningEvaluation, ProvisioningInterview, ProcedureEdit, ProvisioningReport, ProvisioningPreview, ProvisioningCoverage]).json_schema()
    provisioning_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in provisioning_schema['$defs'].items()) + '\n'
    education_pair_schema = TypeAdapter(Union[ProvisioningEducationRequest, ProvisioningEducationEvaluation]).json_schema()
    education_pair_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in education_pair_schema['$defs'].items()) + '\n'
    care_pair_schema = TypeAdapter(Union[ProvisioningCareRequest, ProvisioningCareEvaluation]).json_schema()
    care_pair_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in care_pair_schema['$defs'].items()) + '\n'
    paired_schema = TypeAdapter(Union[ProvisioningEconomyRequest, ProvisioningEconomyEvaluation]).json_schema()
    paired_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in paired_schema['$defs'].items()) + '\n'
    economy_schema = TypeAdapter(Union[EconomyRequest, EconomyEvaluation, EconomyInterview, EconomyEdit, EconomyReport, EconomyPreview, EconomyCoverage]).json_schema()
    economy_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in economy_schema['$defs'].items()) + '\n'
    law_schema = TypeAdapter(Union[AdjudicationRequest, AdjudicationEvaluation, AdjudicationInterview, AdjudicationEdit, AdjudicationReport, AdjudicationPreview, AdjudicationCoverage]).json_schema()
    law_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in law_schema['$defs'].items()) + '\n'
    governance_schema = TypeAdapter(Union[GovernanceRequest, GovernanceEvaluation, GovernanceInterview, GovernanceEdit, GovernanceReport, GovernancePreview, GovernanceCoverage]).json_schema()
    governance_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in governance_schema['$defs'].items()) + '\n'
    care_schema = TypeAdapter(Union[CareRequest, CareEvaluation, CareInterview, CareEdit, CareReport, CarePreview, CareCoverage]).json_schema()
    care_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in care_schema['$defs'].items()) + '\n'
    education_schema = TypeAdapter(Union[EducationRequest, EducationEvaluation, EducationInterview, EducationEdit, EducationReport, EducationPreview, EducationCoverage]).json_schema()
    education_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in education_schema['$defs'].items()) + '\n'
    health_schema = TypeAdapter(Union[HealthRequest, HealthEvaluation, HealthInterview, HealthEdit, HealthReport, HealthPreview, HealthCoverage]).json_schema()
    health_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in health_schema['$defs'].items()) + '\n'
    infrastructure_schema = TypeAdapter(Union[InfrastructureRequest, InfrastructureEvaluation, InfrastructureInterview, InfrastructureEdit, InfrastructureReport, InfrastructurePreview, InfrastructureCoverage]).json_schema()
    infrastructure_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in infrastructure_schema['$defs'].items()) + '\n'
    communication_schema = TypeAdapter(Union[CommunicationRequest, CommunicationEvaluation, CommunicationInterview, CommunicationEdit, CommunicationReport, CommunicationPreview, CommunicationCoverage]).json_schema()
    communication_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in communication_schema['$defs'].items()) + '\n'
    environment_schema = TypeAdapter(Union[EnvironmentRequest, EnvironmentEvaluation, EnvironmentInterview, EnvironmentEdit, EnvironmentReport, EnvironmentPreview, EnvironmentCoverage]).json_schema()
    environment_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in environment_schema['$defs'].items()) + '\n'
    participation_schema = TypeAdapter(Union[ParticipationRequest, ParticipationEvaluation, ParticipationInterview, ParticipationEdit, ParticipationReport, ParticipationPreview, ParticipationCoverage]).json_schema()
    participation_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in participation_schema['$defs'].items()) + '\n'
    continuity_schema = TypeAdapter(Union[ContinuityRequest, ContinuityEvaluation, ContinuityInterview, ContinuityEdit, ContinuityReport, ContinuityPreview, ContinuityCoverage]).json_schema()
    continuity_types = '// Generated by scripts/generate_contracts.py; do not edit.\n' + '\n'.join('export type ' + k + ' = ' + ts(v) + ';' for k, v in continuity_schema['$defs'].items()) + '\n'
    return {'provisioning-education.schema.json': education_pair_schema, 'provisioning-education.ts': education_pair_types, 'provisioning-care.schema.json': care_pair_schema, 'provisioning-care.ts': care_pair_types, 'provisioning-economy.schema.json': paired_schema, 'provisioning-economy.ts': paired_types, 'security-risk.schema.json': continuity_schema, 'security-risk.ts': continuity_types, 'meaning-identity.schema.json': participation_schema, 'meaning-identity.ts': participation_types, 'environment.schema.json': environment_schema, 'environment.ts': environment_types, 'communication.schema.json': communication_schema, 'communication.ts': communication_types, 'infrastructure.schema.json': infrastructure_schema, 'infrastructure.ts': infrastructure_types, 'health.schema.json': health_schema, 'health.ts': health_types, 'knowledge-culture.schema.json': education_schema, 'knowledge-culture.ts': education_types, 'social-organization.schema.json': care_schema, 'social-organization.ts': care_types, 'law-conflict.schema.json': law_schema, 'law-conflict.ts': law_types, 'governance.schema.json': governance_schema, 'governance.ts': governance_types, 'economy.schema.json': economy_schema, 'economy.ts': economy_types, 'provisioning.schema.json': provisioning_schema, 'provisioning.ts': provisioning_types, 'logistics.schema.json': logistics_schema, 'logistics.ts': logistics_types, 'workbench.schema.json': workbench_schema, 'workbench.ts': workbench_types, 'exploration.schema.json': exploration_schema, 'exploration.ts': exploration_types, 'matrix.schema.json': matrix_schema, 'matrix.ts': matrix_types, 'atlas.schema.json': atlas_schema, 'atlas.ts': atlas_types, 'domain.schema.json': domain_schema, 'domain.ts': domain_types, 'content.schema.json': content_schema, 'content.ts': content_types, 'comparison.schema.json': comparison_schema, 'comparison.ts': comparison_types, 'overview.schema.json': overview_schema, 'overview.ts': overview_types, 'interview.schema.json': interview_schema, 'interview.ts': interview_types, 'workspace.schema.json': workspace_schema, 'workspace.ts': workspace_types, 'revision.schema.json': revision_schema, 'revision.ts': revision_types, 'measurement.schema.json': measurement_schema, 'measurement.ts': measurement_types, 'evaluation.schema.json': evaluation_schema, 'evaluation.ts': evaluation_types, 'solver.schema.json': solver_schema, 'solver.ts': solver_types, 'dependency.schema.json': dependency_schema, 'dependency.ts': dependency_types, 'allocation.schema.json': allocation_schema, 'allocation.ts': allocation_types, 'account.schema.json': account_schema, 'account.ts': account_types, 'policy.schema.json': policy_schema, 'policy.ts': policy_types, 'expression.schema.json': expression_schema, 'expression.ts': expression_types, 'mechanism-fixtures.ts': fixture_types, 'mechanism.schema.json': mechanism_schema, 'mechanism.ts': mechanism_types, 'pack.schema.json': pack_schema, 'pack.ts': pack_types, 'wire.schema.json': schema, 'wire.ts': types, 'tool-inputs.json': {'$defs': schema['$defs'], 'inputs': tools}, 'history.schema.json': history, 'saved-evidence.schema.json': SavedEvidence.model_json_schema(), 'history.ts': history_types + '\n'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    from poliscope_engine.content import load_release
    load_release(ROOT / 'content/release-v1')
    outputs = artifacts()
    fixtures = ['fixtures.json', 'mechanism-fixtures.json']
    allowed = {*outputs, 'inventory.json', 'README.md', *fixtures}
    actual = {str(p.relative_to(ROOT / 'contracts')) for p in (ROOT / 'contracts').rglob('*') if p.is_file()}
    if actual - allowed:
        raise SystemExit(f'Unregistered contract artifacts: {sorted(actual - allowed)}')
    outputs['inventory.json'] = {'version': 1, 'status': 'runtime-wire-v1', 'files': sorted([*outputs, *fixtures])}
    for name, value in outputs.items():
        text = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True) + '\n'
        path = ROOT / 'contracts' / name
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f'Contract drift: {name}')
        else:
            path.write_text(text)

if __name__ == '__main__':
    main()
