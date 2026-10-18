import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[2] / 'scripts'))
from check_gate_evidence import validate

MANIFEST = {'gates': {'G1': ['E2E-012.a'], 'G2': ['E2E-012.a', 'E2E-012.b']},
            'cases': {'E2E-012.a': {}, 'E2E-012.b': {}}}
SELECTION = {'version': 1, 'gate': 'G1', 'cases': [
    {'id': 'E2E-012.a', 'service': 'production', 'tests': ['E2E-012.a: security']} ]}


def record(*names):
    return {'results': {'cases': [{'name': n} for n in names]}}


def test_future_only_subcase_is_not_required():
    validate(SELECTION, [record('E2E-012.a: security')], MANIFEST)


@pytest.mark.parametrize('records', [[], [record('unrelated')],
    [record('E2E-012.a: security', 'E2E-012.a: security')]])
def test_unexecuted_or_duplicate_targets_fail(records):
    with pytest.raises(ValueError, match='exactly one'):
        validate(SELECTION, records, MANIFEST)


def test_omitted_mandatory_subcase_fails():
    selection = {**SELECTION, 'gate': 'G2'}
    with pytest.raises(ValueError, match='missing'):
        validate(selection, [record('E2E-012.a: security')], MANIFEST)
