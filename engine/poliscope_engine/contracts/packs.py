"""Version-one data-only pack declarations; parsing never registers code."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .evidence import SourceRef, AssumptionRef, Text
from .world import WorldValue

GameID = Annotated[str, Field(max_length=256, pattern=r'^[a-z][a-z0-9_.-]*:[a-zA-Z0-9_./-]+$')]
Digest = Annotated[str, Field(pattern=r'^sha256:[0-9a-f]{64}$')]
Commit = Annotated[str, Field(pattern=r'^[0-9a-f]{40}$')]
Refs = Annotated[list[GameID], Field(max_length=100)]
Path = Annotated[str, Field(min_length=1, max_length=256, pattern=r'^[a-zA-Z0-9_./-]+$')]


class Identity(Contract):
    id: Identifier
    version: Identifier


class PackIdentities(Contract):
    application: Identity
    schema_identity: Identity
    catalog: Identity
    model: Identity
    numeric: Identity


class Dependency(Contract):
    id: GameID
    version: Identifier
    digest: Digest


class Manifest(Contract):
    format_version: Literal[1]
    id: GameID
    version: Identifier
    identities: PackIdentities
    engine_versions: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    dependencies: Annotated[list[Dependency], Field(max_length=100)]
    files: Annotated[dict[Path, Digest], Field(max_length=500)]


class ArchivedFile(Contract):
    path: Path
    text: Annotated[str, Field(max_length=131072)]


class License(Contract):
    id: Identifier
    file: Path
    digest: Digest


class ArchivedSource(Contract):
    reference: SourceRef
    commit: Commit
    excerpt_file: Path
    license_digest: Digest


class Assumption(Contract):
    reference: AssumptionRef
    validity_limits: Text


class ParameterDeclaration(Contract):
    scope_id: Identifier
    value: WorldValue
    validity_limits: Text


class MeasurementDeclaration(Contract):
    scope_id: Identifier
    unit_id: Identifier
    time_basis_id: Identifier
    interpretation: Text
    coverage_limits: Text


class Definition(Contract):
    id: GameID
    version: Identifier
    kind: Literal['domain', 'branch', 'question', 'option', 'mechanism', 'parameter', 'measurement', 'fixture']
    parent_ref: GameID | None
    original_text: Annotated[str, Field(min_length=1, max_length=131072)]
    source_decision_id: Identifier | None
    source_refs: Refs
    assumption_refs: Refs
    supersedes_refs: Refs
    mechanism_refs: Refs
    variable_refs: Refs
    origin: Literal['authored', 'imported', 'player_proposed', 'ai_proposed']
    modeling: Literal['numerical', 'procedural', 'qualitative', 'partial', 'unsupported']
    evidence: Literal['unreviewed', 'hypothetical', 'supported', 'disputed']
    historical_status: Literal['adopted', 'alternative', 'amended', 'superseded', 'provenance', 'unspecified']
    parameter: ParameterDeclaration | None = None
    measurement: MeasurementDeclaration | None = None


class UncertainVariable(Contract):
    id: GameID
    version: Identifier
    scope_id: Identifier
    form: Literal['point', 'bounded_range', 'distribution', 'qualitative', 'unspecified']
    definition: Text
    distribution_ref: GameID | None
    source_refs: Refs


class Distribution(Contract):
    id: GameID
    version: Identifier
    kind: Literal['marginal', 'joint', 'conditional']
    variable_refs: Annotated[list[GameID], Field(min_length=1, max_length=100)]
    conditioning_refs: Refs
    definition: Text
    sampling_rule_ref: GameID | None


class Dependence(Contract):
    id: GameID
    version: Identifier
    variable_refs: Annotated[list[GameID], Field(min_length=2, max_length=100)]
    kind: Literal['joint', 'conditional', 'common_cause', 'independent', 'unresolved']
    definition_ref: GameID | None
    rationale: Text


class Pack(Contract):
    manifest: Manifest
    files: Annotated[list[ArchivedFile], Field(max_length=500)]
    licenses: Annotated[list[License], Field(max_length=100)]
    sources: Annotated[list[ArchivedSource], Field(max_length=500)]
    assumptions: Annotated[list[Assumption], Field(max_length=500)]
    definitions: Annotated[list[Definition], Field(max_length=2000)]
    variables: Annotated[list[UncertainVariable], Field(max_length=500)]
    distributions: Annotated[list[Distribution], Field(max_length=500)]
    dependence: Annotated[list[Dependence], Field(max_length=500)]
