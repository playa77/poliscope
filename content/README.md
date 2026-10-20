# Immutable content release

`release-v1/` is a data-only, offline bundle. `inventory.json` registers every
artifact and its byte digest; `release.json` links the catalogs, archived sources
and licenses, model review dispositions, templates, editable setups, inquiry
prompts and all 38 source branches plus 115 leaves. Pack identities use canonical
semantic digests; release artifact hashes also detect byte changes.

Run `npm run content:validate` to validate and reproduce the retained build
without network access. `npm run contracts:check` checks the release and generated
canonical Python schemas/TypeScript types. To independently rebuild from the real
source, clone `playa77/society`, then run:

```sh
npm run content:build -- --society /path/to/society --output /tmp/new-content-release
```

The importer reads exactly `9ff539997dbd1bd3fa99deabcf6bc5907602df60` from Git
objects. The builder refuses an existing output directory, compares the full
source inventory with WP-025's checkpoint, and validates before writing. Identical
inputs produce identical bytes. Source text, including source AGENTS and prompts,
is archived data; it is never executed or treated as build instructions. The PDF
is inventoried by digest as optional pinned context, outside the text pack format.
Original source MIT attribution and the application's MIT notice are embedded.
The authored conventions' revision is a documented content-digest prefix rather
than a claimed Git commit; its full excerpt hash authenticates the archived text.

The twelve original qualitative interview templates are consumed by the actual
interview service. The workspace's blank and synthetic editable condition setups
also come from this validated bundle. Blank starts unanswered with no policy,
reference selection or goal. The explicitly selected historical DEC-003 excerpt
is an optional **partial qualitative setup**, available through the content API;
it is not a complete reconciled civilization or a new desktop creation mode.
Full source history, tentative options, amendments and alternatives remain in the
reference pack. Historical setup UI and domain integration retain later packages.

All source model candidates remain blocked, including unresolved units and
AR-001–006 arithmetic disputes. No numerical or procedural model is activated in
this release. An approval field in imported JSON grants no execution authority.
The host review bridge requires a code-owned approval of the entire review hash,
exact archived mechanism declaration/model/graph, evidence content hashes,
independent expected fixture hashes/identities/purposes, and registered trusted
implementations. The host must run and inspect those fixtures before approving;
the bridge never calls arbitrary fixture code. Real registry activation still
checks context, units, ownership and declarative graph constraints. Passing the
structural validator is not scientific approval; hypothetical arithmetic stays
hypothetical after trusted activation.
