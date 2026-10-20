"""Deterministic release assembly from authenticated source import results."""
from poliscope_engine.contracts.content import ContentRelease
from poliscope_engine.corpus import canonical, REVISION
from poliscope_engine.packs import PackArchive, digest
from poliscope_engine.content import Release


def build(reference, report, notice, source_review):
    # This is host-authored build code. Source instructions remain archived text.
    from poliscope_engine.interviews import TOPICS, PROCEDURES, BENEFITS, COSTS, LIMIT, definition
    artifacts = {'society.pack.json': canonical(reference.pack.model_dump(mode='json')),
                 'society.inventory.json': canonical(report), 'source-review.md': source_review}
    templates, definitions, inquiries = [], [], []
    for index, (title, prose, labels) in enumerate(TOPICS, 1):
        qid = 'interview:domain-' + str(index)
        rows = [definition(qid, 'question', None, title + '. ' + prose)]
        rows.extend(definition(qid + '/option-' + str(n), 'option', qid,
                              label + '. ' + PROCEDURES[index - 1][n - 1]) for n, label in enumerate(labels, 1))
        for row in rows:
            definitions.append(row.model_copy(update={'source_refs': ['interview:source/conventions']}))
        templates.append(dict(domain_ref=f'society:domain/{index:02}', question=definitions[-4], options=definitions[-3:],
                              labels=list(labels), mechanisms=list(PROCEDURES[index - 1]), benefits=list(BENEFITS),
                              costs=list(COSTS), coverage=LIMIT))
        inquiries.append(dict(id=f'interview:inquiry/{index}', domain_refs=[f'society:domain/{index:02}'],
            prompt=f'{title}: What do you expect from an alternative? Identify its assumptions, missing capacities, affected groups and evidence. Compare the retained observation with your expectation; an unknown result is not zero.'))
    convention = ('Original synthetic qualitative templates authored for Poliscope.\n'
        'One substantive question, visible scope, three cards with mechanisms, benefits and costs.\n'
        'Show origin, sources and model gaps; allow clarification, deferral and player alternatives.\n'
        'Select drafts, preview first, Apply explicitly. Preserve all original alternatives and rationale.\n'
        'No civic default, hidden grading, numerical social benefit or fabricated model.\n')
    files = {'LICENSE': notice.decode(), 'conventions.md': convention}
    authored = dict(manifest=dict(format_version=1, id='interview:catalog', version='v1',
        identities={key: dict(id='interview-' + key, version='v1') for key in ('application', 'schema_identity', 'catalog', 'model', 'numeric')},
        engine_versions=['v1'], dependencies=[], files={p: digest(t.encode()) for p, t in files.items()}),
        files=[dict(path=p, text=t) for p, t in files.items()],
        licenses=[dict(id='poliscope-mit', file='LICENSE', digest=digest(notice))],
        sources=[dict(reference=dict(id='interview:source/conventions', repository_id='playa77/poliscope',
            document_id='conventions.md', revision_id='0' * 40, location='complete authored conventions v1',
            excerpt_digest=digest(convention.encode()), license_id='poliscope-mit', historical_status='unknown', supersedes_refs=[]),
            commit='0' * 40, excerpt_file='conventions.md', license_digest=digest(notice))],
        definitions=[d.model_dump(mode='json') for d in definitions], assumptions=[], variables=[], distributions=[], dependence=[])
    # Authored document identity is its content hash (first 40 hex digits), not a
    # fabricated Git revision. SourceRef revision and archive commit agree.
    authored['sources'][0]['commit'] = digest(convention.encode())[7:47]
    authored['sources'][0]['reference']['revision_id'] = authored['sources'][0]['commit']
    authored['sources'][0]['reference']['location'] += '; revision is a content digest prefix, not a Git commit'
    authored_archive = PackArchive(canonical(authored))
    artifacts['interview.pack.json'] = canonical(authored_archive.pack.model_dump(mode='json'))
    reviews = []
    for index, candidate in enumerate(report['content_layers']['model_candidates'], 1):
        source = 'society:source/' + candidate['source']
        reviews.append(dict(id=f'interview:review/source-{index}', candidate_refs=['society:domain/01'],
            mechanism_ref=None, mechanism_version=None, mechanism_artifact=None, declaration_digest=None, graph_digest=None, model=None,
            disposition='blocked', operational_definition='Source design/model candidate in ' + candidate['source'],
            formula_or_procedure='Preserve original source text. No trusted numerical procedure approved.',
            denominator_time_scope='Unresolved: require explicit units, population denominator, spatial scope and time basis before activation.',
            basis='unresolved', uncertainty='Source ranges are not calibrated probability laws; joint dependence unresolved.',
            evidence_refs=[source], evidence_digests={source: next(s.reference.excerpt_digest for s in reference.pack.sources if s.reference.id == source)}, fixtures=[], invariants='Require independently derived dimensional, conservation and boundedness cases.',
            validity_limits='Historical design only; source-review.md records AR-001–006 and unresolved empirical inputs.',
            unsupported_extrapolation='No social outcomes, feasibility, behavior or default civic policy may be inferred.',
            review_notes='Blocked pending operational model, evidence and independent fixture review. Import/schema success is not approval.'))
    coverage = []
    for domain in report['domains']:
        for branch in domain['branches']:
            coverage.append(dict(branch_ref=branch['id'], source_status='source_design_only' if any(l['documents'] for l in branch['leaves']) else 'map_only',
                model_status='unsupported', reason='Classification with original source wording; no reviewed executable branch model.'))
            coverage.extend(dict(branch_ref=leaf['id'], source_status=leaf['coverage'], model_status='unsupported',
                reason='Source design needs independent model/evidence review.' if leaf['documents'] else 'Map title only: detailed source content and numerical model are missing.') for leaf in branch['leaves'])
    ledger_source = 'society:source/06_global_decision_ledger.md'
    # A bounded historical excerpt avoids guessing a globally reconciled state
    # from partially amended older choices. Full ledger remains in the archive.
    decision = next(d for d in report['decisions'] if d['id'] == 'DEC-003')
    historical = [o['id'] for o in decision['option_statuses'] if o['status'] == 'chosen']
    setups = [dict(id='blank', name='Unanswered starting conditions', kind='neutral',
        description='Editable conditions; no selected policies, goals or reference choices.', population=None, land_area=None,
        selected_option_refs=[], goals=[], source_refs=[], limitations='Unknown conditions remain unknown; no numerical social model.'),
        dict(id='reference:small-settlement', name='Synthetic small settlement (editable conditions only)', kind='synthetic',
        description='Original illustrative population and land; no civic arrangement is selected.', population='100', land_area='10',
        selected_option_refs=[], goals=[], source_refs=['interview:source/conventions'], limitations='Not a calibrated or historical society.'),
        dict(id='reference:society-dec-003', name='Historical DEC-003 design excerpt (qualitative)', kind='historical',
        description='Explicitly selected source design excerpt at ' + REVISION + '; retains the original DEC-003 choice.',
        population=None, land_area=None, selected_option_refs=historical, goals=[], source_refs=[ledger_source],
        limitations='Partial reference setup, not a reconciled civilization or executable model. Earlier partly amended choices are not auto-selected. No numerical parameters or worldview is imposed.')]
    metadata = ContentRelease.model_validate(dict(format_version=1, id='interview:release', version='v1',
        artifacts=[dict(path=p, digest=digest(b)) for p, b in sorted(artifacts.items())],
        catalogs=[dict(artifact='society.pack.json', pack_digest=reference.digest, role='reference'),
                  dict(artifact='interview.pack.json', pack_digest=authored_archive.digest, role='authored')],
        reviews=reviews, activated_review_refs=[], templates=templates, setups=setups, inquiries=inquiries, coverage=coverage))
    manifest = canonical(metadata.model_dump(mode='json'))
    Release(manifest, artifacts)
    return {'release.json': manifest, **artifacts}
