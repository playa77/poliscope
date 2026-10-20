# Offline society corpus importer

Run from the repository root after frozen installation:

```sh
uv run --frozen python scripts/import_society.py /path/to/society /path/to/new-output
```

The local repository must contain commit
`9ff539997dbd1bd3fa99deabcf6bc5907602df60`. Only that immutable tree is read, with
Git replacement objects disabled; HEAD, dirty files, hooks and source programs
are not used. A missing revision fails rather than substituting a newer source.
The importer is bounded to 4 MiB of source blobs and flat regular non-executable
files. It writes to a new output directory, refusing to overwrite existing work.
It performs no network access, sandbox mutation or model activation.

`reference-pack.json` passes the existing production format-1 PackArchive digest,
license, namespace, reference and graph checks. `inventory.json` accounts for all
files/map leaves/ledger decisions, original option labels, compound rounds,
tentative choices, explicit lineage and source coverage gaps. Source-only runtime
identities prevent confusing this candidate with an installed executable catalog.
The PDF essay is inventoried by hash as optional binary context; format 1 archives
UTF-8 text only. Source AGENTS/prompts are archived text, never instructions to
execute. The root MIT notice is retained; external works are not fetched.

The reviewed inventory and arithmetic dispositions are in
[the package record](../../../docs/roadmap/execution/WP-025.md) and
[the source review](../../../docs/roadmap/execution/society/review.md).
WP-026 owns production content build, validation, curated gameplay exposure and
reviewed model activation. This CLI produces an import candidate only. Original
branch prose is archived, including unnumbered discussions; structured interview
extraction covers the exhaustive numbered ledger, not invented unseen choices.
