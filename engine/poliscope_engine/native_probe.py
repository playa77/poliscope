"""Offline bundled-runtime known answers; touches only a fresh temporary store."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory


def check():
    from poliscope_engine.numeric import context, parse, RUNTIME_ID
    from decimal import localcontext
    from poliscope_engine.contracts.stochastic import DrawSpec
    from poliscope_engine.stochastic import sample, verify_draw, RUNTIME
    from poliscope_engine.workspace import dispatch, registry, select
    from poliscope_engine.storage import Store
    from poliscope_engine.revisions import Revisions
    from poliscope_engine.archives import export_archive, validate_archive, import_archive, read_item
    from poliscope_engine.contracts.archives import ArchiveRevision

    def require(value):
        if not value:
            raise ValueError('native_known_answer_failed')

    with localcontext(context()):
        require(parse('0.1') + parse('0.2') == parse('0.3'))
        require(parse('1') / parse('7') == parse('0.1428571428571428571428571429'))
    spec = DrawSpec.model_validate(dict(variable_id='hazard-a', day=1,
        key=dict(mechanism_id='synthetic:model/infrastructure', mechanism_version='v1',
            instance_id='a', entity_id='service-a', scope_id='local',
            purpose='synthetic:hazard', event_id='storm:1', draw_name='occurs', index=0),
        distribution=dict(kind='bernoulli', numerator=1, denominator=3),
        dependence='declared_independent', source_refs=['synthetic:source'],
        assumption_refs=['synthetic:probability']))
    draw = sample('01' * 32, RUNTIME, spec)
    require(draw.accepted_block == 'bd6e1bf82d2ab5a84aa71be3a07f299e5110d9b459628e28aacb1d708cdd93f6')
    require(draw.value == 'true' and draw.rejected_blocks == 0)
    verify_draw(draw)
    with TemporaryDirectory(prefix='poliscope-native-') as temporary:
        directory = Path(temporary)
        options = dict(name='Synthetic native probe', setup='blank', scope_name='Home', population='17', land_area='2.50')
        with Store(directory / 'store') as store:
            service = Revisions(store, registry=registry())
            state = dispatch(service, 'create', options, 'native-probe')
            require(dispatch(service, 'create', options, 'native-probe') == state)
            evidence = service.evidence(state.context).model_dump_json()
            archive = directory / 'roundtrip.poliscope'
            export_archive(service, archive)
            _, items = validate_archive(archive)
            retained = next(item for item in items if isinstance(item, ArchiveRevision))
            require(retained.inputs == service.read(state.context).inputs)
        with Store(directory / 'imported') as target:
            imported = import_archive(target, archive)
            require(import_archive(target, archive) == imported)
            loaded, _ = read_item(target, imported.id, items.index(retained))
            require(loaded == retained)
        with Store(directory / 'store') as store:
            cold = Revisions(store, registry=None)
            require(select(cold, dict(civilization_id=state.context.civilization_id,
                branch_id='main', revision_id=None)) == state)
            require(cold.evidence(state.context).model_dump_json() == evidence)
            require(dispatch(cold, 'create', options, 'native-probe') == state)
    return dict(probe_version=1, status='passed', application='0.1.0',
        numeric_runtime=RUNTIME_ID, random_runtime=RUNTIME.model_dump(),
        checks=['decimal-known-answers', 'named-draw-known-answer', 'sqlite-cold-replay', 'archive-roundtrip'])


def main():
    try:
        result = check()
    except Exception:
        print('{"probe_version":1,"status":"failed"}')
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0
