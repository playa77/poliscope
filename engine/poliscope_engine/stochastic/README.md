# Named realization contract v1

WP-035 supplies explicit probability data and stateless sampling for the trusted
transition host. It never samples a source interval, chooses a distribution,
loads model code, calls a provider, or uses the process random generator.
`RandomPlan` is optional in a frozen `TransitionPlan`; its absence preserves
existing v1 plan, request and receipt identities. Empty draw receipts also retain
their original v1 identity. Updated generated schemas/types describe the additive
fields for consumers of stochastic histories.

Each selected `DrawSpec` declares its stable uncertain-variable ID, effective
simulation day, full named key, explicit distribution, source references and
nonempty dependence-assumption references. Supported distributions are rational
Bernoulli, inclusive nonnegative integer uniform and ordered weighted categorical.
Parameters/weights are exact bounded integers, not floats; categorical ordering is
semantic. Invalid probabilities, duplicate support, unknown distributions,
undeclared dependence and source intervals fail before experiment creation. Other
continuous or conditional models require a future version, not an approximation.
A model needing a joint realization can declare categorical joint-state labels
and reference that same variable from its dependent mechanisms. Separate streams
require an explicit independence assumption; stream separation proves no empirical
independence. No native scientific stochastic mechanism is activated here.

The key has mechanism definition/version, stable mechanism instance AND entity,
scope, purpose, stable event ID, named draw and explicit index. An index is local
to a named draw, never a position in a global event list. Duplicate full keys and
variable IDs are rejected. The actual experiment instances and their schedules
must match the declared owners and all consumers. Different events/days require
different event identities. An `event` variable is passed only at its declared
boundary. An explicitly `persistent` variable is reused at later boundaries, with
the same original identity and realized value. All references to a shared variable
receive one realization. Private proposal, resolution and invariant callbacks get
detached typed realized values, not an implicit draw capability.

The portable runtime identity is:

- RNG: `hmac-sha256-counter-v1`.
- Key encoding: `named-draw-json-v1`.
- Sampling: `exact-discrete-rejection-v1`.

The seed is exactly 32 bytes encoded as 64 lowercase hexadecimal characters.
For each draw, HMAC-SHA256 uses those bytes as its key. The message is the UTF-8
encoding of the JSON object `{counter, key, runtime}`, with sorted object keys,
compact separators, literal Unicode (`ensure_ascii=False`), no Unicode
normalization, and the complete typed key/runtime objects. The local counter
starts at zero for every named draw. It has no dependency on execution ordering,
thread/experiment IDs, wall clocks, Python hashes, unrelated models, variable
presentation IDs, distributions or earlier draws. A parameter comparison can
therefore use the same underlying block while declaring different distributions.

Interpret the 32-byte block as an unsigned big-endian integer. For support size
N, reject integers at or above `2**256 - (2**256 % N)`, then take modulo N.
Bernoulli succeeds below its numerator; integer uniform adds its lower bound;
categorical selects the first cumulative-weight interval containing the integer.
Rejection increments only this named draw's local counter, bounded to 128 tries.
Failure is explicit and cannot commit a boundary. This avoids modulo bias and
platform floating-point differences. Sampling uses standard SHA256/HMAC and
integer operations, so its runtime version is independent of the host's Python
patch version; the experiment also preserves its existing model/numeric identity.

`realize(plan, day)` returns stable variable-ID order. An optional checkpoint
runs before every available draw; the reducer charges its existing operation
quota and cancellation checks there. A receipt retains seed, full specification,
all runtime versions, value, accepted block and rejection count. The whole receipt
is included in the canonical confirmed state and stored atomically with closing
results, due/authored events, evidence and operation outcome. A rejected private
candidate, cancellation or pre-COMMIT crash retains none of those new results.

`verify_draw` resamples only under an exactly supported runtime and rejects a
changed value/block. `check_retained` checks the frozen plan binding without
executing sampling. Historical reads and completed operation retries use that
data-only route and continue to work without current sampling/model providers.
Unknown runtime strings can be read, but a new execution or exact reproduction
request reports `historical_random_runtime_unavailable`. Readability is not an
exact reproduction claim. Transition confirmation recomputes the full candidate,
so rehashing a substituted realization cannot authorize it.

`fork_plan(parent, policy='preserve')` retains seed, runtime, keys, specs and
references for paired comparison. `new_realization` requires a supplied different
seed. Both retain parent digest/seed and policy; `verify_fork` binds them to the
actual parent and rejects identity substitutions. Parents remain immutable. This
is the realization policy provider for WP-036; it does not create a retrospective
experiment, select checkpoints or claim full timeline replay orchestration.

`tests/engine/test_stochastic.py` includes a fixed HMAC known answer, an independent
message/integer oracle, UTF-8 field separation, distribution boundaries and
rejection, instance/purpose/event isolation, persistent/shared values, actual
SQLite transition/reopen/continuation, authored/no-hazard paths, cold retries,
forged receipts and actual subprocess crashes on both sides of COMMIT.
The manual `Stochastic contract portability` workflow runs these same tests on
native Windows x64 and Linux x64. A Linux run does not certify Windows; CI/manual
native results must be recorded separately. AI and diagram/layout randomness are
outside this contract.
