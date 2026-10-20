"""Deterministic, nonactivating import of an immutable society Git snapshot.

Source text is data. No checkout hooks, source programs, PDF renderers or model
callbacks run. The format-specific parser fails closed rather than guessing at
new ledger layouts. Release artifact build/activation is a separate boundary.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess

from poliscope_engine.packs import PackArchive, digest

REPOSITORY = 'playa77/society'
REVISION = '9ff539997dbd1bd3fa99deabcf6bc5907602df60'
MAP = '00_broad_structure.md'
LEDGER = '06_global_decision_ledger.md'
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAINTENANCE = {'DEC-018', 'DEC-023', 'DEC-024'}
# Explicit source linkage, not chronological replacement of entire earlier decisions.
SUPERSEDES = {'DEC-003': ['DEC-002.2']}
AMENDS = {
    'DEC-001': ['01-1-1_food-agriculture-log.md'],
    'DEC-002': ['01-1-2_energy-log.md', '01-1-3_materials-manufacturing-log.md'],
    'DEC-003': ['01-1-3_materials-manufacturing-log.md', '01-1-1_food-agriculture-log.md'],
    'DEC-005': ['01-1-2_energy-log.md'],
    'DEC-019': ['DEC-007'], 'DEC-020': ['DEC-015', '01-2-2_storage-supply-chains-log.md'],
    'DEC-021': ['01-2-3_allocation-mechanisms-log.md'],
    'DEC-022': ['01-1-authority-arbitration-spec.md', 'DEC-008'],
}


class CorpusError(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def snapshot(repository: Path) -> dict[str, bytes]:
    """Read pinned Git objects, unaffected by checkout edits or checkout filters."""
    def git(*args):
        return subprocess.check_output(['git', '--no-replace-objects', '-C', str(repository), *args], stderr=subprocess.PIPE)
    try:
        entries = git('ls-tree', '-rz', '--full-tree', REVISION).split(b'\0')
        files = {}
        total = 0
        for entry in entries:
            if not entry:
                continue
            meta, raw_path = entry.split(b'\t', 1)
            mode, kind, oid = meta.split()
            name = raw_path.decode('utf-8')
            if mode != b'100644' or kind != b'blob' or not re.fullmatch(r'[a-zA-Z0-9_.-]+', name):
                raise CorpusError('unsupported_source_entry')
            size = int(git('cat-file', '-s', oid.decode()))
            total += size
            if total > MAX_SOURCE_BYTES:
                raise CorpusError('source_size')
            files[name] = git('cat-file', 'blob', oid.decode())
        return files
    except (subprocess.CalledProcessError, UnicodeError) as error:
        raise CorpusError('pinned_revision_unavailable') from error


def _definition(identity, kind, text, source, *, parent=None, decision=None, status='unspecified', supersedes=()):
    return dict(id='society:' + identity, version=REVISION, kind=kind, parent_ref=parent,
                original_text=text, source_decision_id=decision, source_refs=[source],
                assumption_refs=[], supersedes_refs=['society:' + item for item in supersedes],
                mechanism_refs=[], variable_refs=[], origin='imported', modeling='unsupported',
                evidence='unreviewed', historical_status=status)


def _field(text, name):
    match = re.search(r'^\*\*' + re.escape(name) + r':\*\*\s*(.*?)(?=^\*\*[^\n]+:\*\*|\Z)', text, re.M | re.S)
    if not match:
        raise CorpusError('missing_ledger_field:' + name)
    return match.group(1).strip()


def _map(text, source):
    definitions, domains = [], []
    current = None
    for line in text.splitlines():
        if line == '---':
            break  # Structural notes are archived context, not map branches.
        match = re.fullmatch(r'## ([IVX]+)\. (.+)', line)
        if match:
            number = len(domains) + 1
            identity = f'domain/{number:02}'
            current = {'id': 'society:' + identity, 'roman': match[1], 'title': match[2], 'branches': []}
            domains.append(current)
            definitions.append(_definition(identity, 'domain', line, source))
        elif line.startswith('- **') and current is not None:
            match = re.fullmatch(r'- \*\*(.+)\*\*: (.+)', line)
            if not match:
                raise CorpusError('invalid_map_branch')
            branch_number = len(current['branches']) + 1
            identity = f'domain/{len(domains):02}/{branch_number}'
            leaves = match[2].split(' · ')
            branch = {'id': 'society:' + identity, 'title': match[1], 'leaves': []}
            current['branches'].append(branch)
            definitions.append(_definition(identity, 'branch', line, source, parent=current['id']))
            for index, leaf in enumerate(leaves, 1):
                leaf_id = f'{identity}/{index}'
                branch['leaves'].append({'id': 'society:' + leaf_id, 'title': leaf})
                definitions.append(_definition(leaf_id, 'branch', leaf, source, parent=branch['id']))
    if len(domains) != 12:
        raise CorpusError('twelve_domains_required')
    return definitions, domains


# Option labels repeat in DEC-021; the parent round is part of their identity.
OPTION = re.compile(r'^\s*- \*\*(DEC-\d{3}-alt-[A-Z0-9]+(?:\.\d+)?)(?: \((ownership|rule|class)\))?\s+—', re.M)
ROUND = re.compile(r'^- \*\*(?:Round \d+ —[^\n]+|Review-machinery round[^\n]+|Propagation round[^\n]+)\*\*\s*$', re.M)


def _ledger(text, source):
    register = text.split('## B.', 1)[0]
    starts = list(re.finditer(r'^### (DEC-\d{3}) — (.+)$', register, re.M))
    definitions, decisions = [], []
    for index, start in enumerate(starts):
        identity = start[1]
        body = register[start.start():starts[index + 1].start() if index + 1 < len(starts) else len(register)].rstrip()
        body = body.split('\n### Session-level meta-decision ', 1)[0].rstrip()
        question, choices, decision = (_field(body, field) for field in ('Question', 'Choices presented (all preserved)', 'Decision'))
        status = 'provenance' if identity in MAINTENANCE else 'adopted'
        rounds = list(ROUND.finditer(choices))
        # Single/bundled questions retain the joint choice set. Explicit rounds
        # become separate questions under a structural decision container.
        if rounds:
            definitions.append(_definition(identity, 'branch', body, source, decision=identity, status=status))
            groups = [(f'{identity}/round/{n + 1}', choices[m.start():rounds[n + 1].start() if n + 1 < len(rounds) else len(choices)])
                      for n, m in enumerate(rounds)]
            if choices[:rounds[0].start()].strip():
                groups.insert(0, (f'{identity}/round/0', choices[:rounds[0].start()]))
        else:
            groups = [(identity, choices)]
        option_ids, option_statuses = [], []
        for group_id, group in groups:
            group_status = 'provenance' if identity == 'DEC-022' and group_id.endswith('/round/2') else status
            definitions.append(_definition(group_id, 'question', question + '\n\n' + group, source,
                                           parent='society:' + identity if rounds else None,
                                           decision=identity, status=group_status,
                                           supersedes=SUPERSEDES.get(identity, ()) if not rounds else ()))
            options = list(OPTION.finditer(group))
            if not options:
                raise CorpusError('missing_options:' + group_id)
            for n, option in enumerate(options):
                if not option[1].startswith(identity + '-alt-'):
                    raise CorpusError('foreign_option')
                option_text = group[option.start():options[n + 1].start() if n + 1 < len(options) else len(group)].strip()
                label = re.sub(r'\s+', ' ', option_text)
                chosen = '[CHOSEN]' in label or '[CHOSEN tentatively]' in label
                tentative = '[CHOSEN tentatively]' in label
                if not chosen and '[NOT CHOSEN]' not in label:
                    raise CorpusError('missing_option_status:' + option[1])
                option_id = group_id + '/option/' + option[1].split('-alt-')[1]
                option_ids.append('society:' + option_id)
                option_statuses.append({'id': 'society:' + option_id,
                                        'source_label': option[1], 'qualifier': option[2],
                                        'status': 'chosen_tentatively' if tentative else ('chosen' if chosen else 'not_chosen')})
                definitions.append(_definition(option_id, 'option', option_text, source,
                                               parent='society:' + group_id, decision=option[1],
                                               status='provenance' if group_status == 'provenance' else ('unspecified' if tentative else ('adopted' if chosen else 'alternative'))))
        # Preserve DEC-002's explicit recorded findings/sub-decisions, without
        # inventing choice sets for findings that were never questions.
        if identity == 'DEC-002':
            section = _field(body, 'Sub-decisions produced by running the balance sheet (same session)')
            subs = list(re.finditer(r'^- \*\*(DEC-002\.[123]) —', section, re.M))
            if len(subs) != 3:
                raise CorpusError('missing_subdecisions')
            for n, sub in enumerate(subs):
                subtext = section[sub.start():subs[n + 1].start() if n + 1 < len(subs) else len(section)].strip()
                definitions.append(_definition(sub[1], 'branch', subtext, source, parent='society:DEC-002',
                                               decision=sub[1], status='superseded' if sub[1] == 'DEC-002.2' else 'unspecified'))
        decisions.append({'id': identity, 'title': start[2], 'classification': 'provenance' if identity in MAINTENANCE else 'reference_design',
                          'question': question, 'recorded_decision': decision, 'option_ids': option_ids,
                          'option_statuses': option_statuses,
                          'round_ids': [row[0] for row in groups], 'supersedes': list(SUPERSEDES.get(identity, ())),
                          'amends': list(AMENDS.get(identity, ())), 'source_excerpt_digest': digest(body.encode()),
                          'source_lines': [text[:start.start()].count('\n') + 1,
                                           text[:start.start() + len(body)].count('\n') + 1],
                          'model_status': 'unsupported', 'evidence_status': 'unreviewed'})
    if [row['id'] for row in decisions] != [f'DEC-{n:03}' for n in range(1, 25)]:
        raise CorpusError('unexpected_decision_register')
    return definitions, decisions


@dataclass(frozen=True)
class ImportResult:
    archive: PackArchive
    report: dict


def _transform(files: dict[str, bytes]) -> ImportResult:
    """Transform supplied bytes; caller must authenticate them against Git objects.

    Tests use synthetic bytes; only snapshot() establishes the pinned repository
    identity. No schema/model review is implied by successful transformation.
    """
    if sum(len(data) for data in files.values()) > MAX_SOURCE_BYTES:
        raise CorpusError('source_size')
    if 'LICENSE' not in files:
        raise CorpusError('license_unavailable')
    license_text = files['LICENSE'].decode('utf-8')
    if not license_text.startswith('MIT License\n') or 'Copyright (c) 2026 playa77' not in license_text or 'Permission is hereby granted' not in license_text:
        raise CorpusError('license_requires_review')
    texts = {}
    for name, data in sorted(files.items()):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name):
            raise CorpusError('unsafe_source_path')
        if name.endswith('.md') or name == 'LICENSE':
            texts[name] = data.decode('utf-8')
        elif name != '02_AI-Essay.pdf':
            raise CorpusError('unclassified_source_file:' + name)
    if MAP not in texts or LEDGER not in texts or '02_AI-Essay.pdf' not in files:
        raise CorpusError('source_inventory_incomplete')
    archived = [{'path': name, 'text': text} for name, text in texts.items()]
    license_digest = digest(files['LICENSE'])
    sources, source_ids = [], {}
    for name in texts:
        source_id = 'society:source/' + name
        source_ids[name] = source_id
        sources.append(dict(reference=dict(id=source_id, repository_id=REPOSITORY, document_id=name,
                                           revision_id=REVISION, location='complete UTF-8 document; pinned snapshot',
                                           excerpt_digest=digest(files[name]), license_id='society-mit',
                                           historical_status='unknown', supersedes_refs=[]),
                            commit=REVISION, excerpt_file=name, license_digest=license_digest))
    definitions, domains = _map(texts[MAP], source_ids[MAP])
    ledger_definitions, decisions = _ledger(texts[LEDGER], source_ids[LEDGER])
    definitions.extend(ledger_definitions)
    meta = re.search(r'^### Session-level meta-decision (DEC-SYS-001) —[^\n]+\n.*?(?=^### |\Z)', texts[LEDGER], re.M | re.S)
    if meta is None:
        raise CorpusError('missing_system_decision')
    definitions.append(_definition('DEC-SYS-001', 'branch', meta[0].rstrip(), source_ids[LEDGER],
                                   decision='DEC-SYS-001', status='provenance'))
    identities = {key: {'id': 'society-source-only-' + key, 'version': 'v1'}
                  for key in ('application', 'schema_identity', 'model', 'numeric')}
    identities['catalog'] = {'id': 'society-reference', 'version': REVISION}
    pack = dict(manifest=dict(format_version=1, id='society:reference', version=REVISION,
                             identities=identities, engine_versions=['v1'], dependencies=[],
                             files={name: digest(files[name]) for name in texts}),
                files=archived, licenses=[dict(id='society-mit', file='LICENSE', digest=license_digest)],
                sources=sources, definitions=definitions, assumptions=[], variables=[], distributions=[], dependence=[])
    archive = PackArchive(canonical(pack))
    document_rows = []
    for name, data in sorted(files.items()):
        branch_match = re.fullmatch(r'(\d{2})-(\d+)-(\d+)_[a-z-]+-(full|log)\.md', name)
        if name == '02_AI-Essay.pdf':
            role = 'essay_context_binary'
        elif name == MAP:
            role = 'classification_map'
        elif name == LEDGER:
            role = 'decision_history'
        elif branch_match:
            role = 'branch_' + branch_match[4]
        elif name.startswith('01-'):
            role = 'integration_model_candidates'
        elif name == 'LICENSE':
            role = 'license'
        else:
            role = 'project_provenance'
        document_rows.append({'path': name, 'digest': digest(data), 'bytes': len(data), 'role': role,
                              'archived': name in texts,
                              'map_leaf_id': f'society:domain/{branch_match[1]}/{branch_match[2]}/{branch_match[3]}' if branch_match else None})
    leaves = {leaf['id']: leaf for domain in domains for branch in domain['branches'] for leaf in branch['leaves']}
    for leaf_id, leaf in leaves.items():
        leaf['documents'] = [row['path'] for row in document_rows if row['map_leaf_id'] == leaf_id]
        leaf['coverage'] = 'source_design_only' if leaf['documents'] else 'map_only'
    if any(row['map_leaf_id'] is not None and row['map_leaf_id'] not in leaves for row in document_rows):
        raise CorpusError('branch_outside_map')
    ledger = texts[LEDGER]
    index_text = ledger.split('## B.', 1)[1].split('## C.', 1)[0]
    alternate_index = re.findall(r'^- \*\*(DEC-[^*]+)\*\*', index_text, re.M)
    changelog = re.findall(r'^- \*\*(CL-\d{3})[^*]*\*\*', ledger.split('## C.', 1)[1], re.M)
    unindexed = []
    for decision in decisions:
        for option in decision['option_statuses']:
            if option['status'] != 'not_chosen':
                continue
            canonical_label = option['source_label'] + (f" ({option['qualifier']})" if option['qualifier'] else '')
            legacy_label = option['source_label'].replace('-alt-', '-')
            if not any(label.startswith(prefix + ':') or label.startswith(prefix + ' (')
                       for prefix in (canonical_label, legacy_label) for label in alternate_index):
                unindexed.append(option['id'])
    report = dict(format_version=1, repository=REPOSITORY, revision=REVISION,
                  license={'id': 'society-mit', 'spdx': 'MIT', 'digest': license_digest,
                           'redistribution': 'repository notice permits documentation redistribution with retained notice'},
                  archive_digest=archive.digest, files=document_rows, domains=domains, decisions=decisions,
                  system_decisions=[{'id': 'DEC-SYS-001', 'classification': 'provenance',
                                     'source_excerpt_digest': digest(meta[0].rstrip().encode())}],
                  preserved_alternative_index_labels=alternate_index,
                  unindexed_alternatives=unindexed,
                  changelog_ids=changelog,
                  content_layers={'reference_design': [d['id'] for d in decisions if d['classification'] == 'reference_design'],
                                  'provenance': [d['id'] for d in decisions if d['classification'] == 'provenance'],
                                  'evidence_claims': [{'source': row['path'], 'status': 'unreviewed'} for row in document_rows if row['role'].startswith(('branch_', 'integration_'))],
                                  'model_candidates': [{'source': row['path'], 'status': 'unsupported'} for row in document_rows if row['role'].startswith(('branch_', 'integration_'))],
                                  'selected_player_policies': [], 'activated_mechanisms': []},
                  limitations=['All imported quantities and causal claims require model/evidence review.',
                               'No player selection, executable mechanism, numerical parameter or default setup is created.',
                               'PDF essay inventoried by digest as optional context; format-1 archives support text only.',
                               'External citations are source claims; third-party works are not fetched or relicensed.'])
    return ImportResult(archive, report)


def import_repository(repository: Path) -> ImportResult:
    """Public production entry: immutable source identity is established by Git."""
    return _transform(snapshot(repository))
