# Data-only pack boundary

`PackArchive` accepts at most 8 MiB of UTF-8 JSON in format 1, rejects duplicate
JSON keys, and returns detached Pydantic snapshots. It never reads archive paths,
extracts files, imports modules, evaluates formulas, or activates mechanisms.
Files are bounded inline UTF-8 text (binary/ZIP import is a later boundary), with
canonical relative paths and exact SHA-256 inventory, source excerpt and license
closure. A pack's digest covers canonical sorted-key JSON, including metadata.
Callers with a pinned archive digest must supply `expected_digest`; internal file
hashes alone do not authenticate an edited manifest or attest a license's validity.

Game IDs are namespaced; source decision IDs are citation text, never primary
keys. Compound questions use explicit parent links; options retain full original
text and historical status. History carries no selected player answer. Sources
pin full Git commits and licenses; supersession/parent graphs cannot cycle.
References close within each pack; dependencies are separate version/digest-pinned
archives, not an implicit cross-pack ID lookup or executable plugin mechanism.

`compatibility` checks a supplied dependency closure, exact app/schema/catalog/
model/numeric identities, allowed engine versions, and the caller's trusted
mechanism ID/version registry. This is an availability report, not registration,
scientific certification, or execution. Missing code does not prevent historical
inspection. An evidence label alone cannot satisfy trusted code availability.
Qualitative definitions remain qualitative even when historically adopted.
Supported format-1 archives remain structurally readable regardless of installed
numeric runtime; references and digests must still validate.

Uncertain variables have stable versioned identities and scopes. Repeated
references preserve one identity. Marginal/joint/conditional definitions and
common causes are retained as data. Every pair of uncertain variables requires
an explicit dependence declaration, including `unresolved`; no separate streams
or missing edges imply independence. Ambiguous pair declarations are rejected.
Missing sampling rules and unresolved dependence block execution availability.
This package provides no random sampler, propagation, numerical mechanism,
production corpus, player defaults, persistent publication, or import UI.
