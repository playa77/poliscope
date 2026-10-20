"""G2 production engine selection, composed from independently inspected oracles.

These call real Store/Revisions services. UI assertions live in packaged specs;
this selection cannot establish the cumulative native or handoff prerequisites.
"""
import pytest
import test_headless_slice as slice
import test_expressions as expressions
import test_mechanism_registry as mechanisms

CASES = {
    'E2E-002.b target observations leave allocation unchanged': 'targets',
    'E2E-003.a finite stock labor loss reservation import access and precision': 'accounts',
    'E2E-004.a canonical overlap and unresolved policies are order invariant': 'overlap',
    'E2E-005 stale tampered duplicate lost reply status cross context and retained futures': 'retries',
    'E2E-012.b trusted registry bounded expressions units operators and state writes': 'attacks',
    'E2E-015.a retained closure survives cache eviction and absent runtime': 'retained',
}

@pytest.mark.parametrize('scenario', CASES.values(), ids=CASES.keys())
def test_offline_gate(tmp_path, scenario):
    if scenario in ('targets', 'retained'):
        slice.test_complete_headless_workflow_and_retained_futures(tmp_path)
    elif scenario == 'accounts':
        slice.test_complete_headless_workflow_and_retained_futures(tmp_path / 'finite')
        for case in ('missing', 'qualitative', 'access-unknown', 'labor', 'quantum-remainder', 'precision', 'precision-boundary'):
            slice.test_visible_gaps_and_precision_rejection(tmp_path / case, case)
        for case in ('scope', 'physical-budget', 'dated-source', 'stock-budget'):
            slice.test_period_allowance_does_not_erase_other_requirement_guards(tmp_path / case, case)
    elif scenario == 'overlap':
        slice.test_overlap_and_policy_conflicts_are_order_invariant(tmp_path)
    elif scenario == 'retries':
        slice.test_stale_tampered_conflicting_and_lost_reply(tmp_path / 'retry')
        slice.test_complete_headless_workflow_and_retained_futures(tmp_path / 'future')
    else:
        expressions.test_size_depth_and_executable_payload_bounds()
        expressions.test_unused_nodes_cannot_hide_invalid_operators()
        expressions.test_graph_output_types_and_transition_ownership_cannot_be_bypassed()
        expressions.test_invalid_graphs_fail_before_execution(
            lambda nodes: nodes[1]['value_type'].update(unit_id='missing'), 'unknown_unit')
        mechanisms.test_graph_content_never_resolves_to_trusted_python_by_same_name()
        mechanisms.test_trusted_implementation_version_and_phase_cannot_be_substituted()
