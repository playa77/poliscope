"""WP-055 cumulative workflows over actual services and existing independent oracles.

This composes accepted component workflows, preserving their literal expected
answers and negative/fault cases. It adds gate selection identities, not new model
mechanisms or scientific validity. Packaged/UI and live-provider checks remain
separate required evidence, never replaced by these engine cases.
"""
import sqlite3
import stat
import pytest
import test_archives as archives
import test_boundaries as boundaries
import test_experiments as experiments
import test_fault_audit as faults
import test_recovery as recovery
import test_reports as reports
import test_stochastic as stochastic
import test_timeline as timeline
import test_uncertainty as uncertainty
import test_uncertainty_service as uncertainty_service
from test_boundaries import running
from test_timeline import approved
from test_uncertainty_service import system

CASES = {
    'E2E-006.c disk-full across actual revision timeline archive and recovery paths': 'fault:full',
    'E2E-006.c read-only across actual revision timeline archive and recovery paths': 'fault:readonly',
    'E2E-007 mixed rates authored events named stochastic draws crashes and checkpoint replay': 'dynamic',
    'E2E-009 approved future deltas conflicts disruptions and retrospective forks preserve state': 'adoptions',
    'E2E-010.b actual sensitivity capacity repeated variables common cause and qualified gaps': 'uncertainty',
    'E2E-011 ordinary reduced archives historical privacy and Markdown CSV round trip': 'archives',
    'E2E-012.c archive paths types hashes bounds and interrupted import reject transactionally': 'hostile-archive',
    'E2E-015.b timeline evidence and completed outcomes survive eviction checkpoint changes and reopen': 'timeline-evidence',
    'E2E-015.c absent mechanisms legacy schemas model migration and interrupted restore preserve originals': 'historical',
}


@pytest.mark.parametrize('scenario', CASES.values(), ids=CASES.keys())
def test_offline_gate(tmp_path, monkeypatch, request, scenario):
    def space(name):
        path = tmp_path / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    if scenario.startswith('fault:'):
        fault = scenario.split(':')[1]
        code = sqlite3.SQLITE_FULL if fault == 'full' else sqlite3.SQLITE_READONLY
        faults.test_design_save_failure_retains_history_then_exact_retry_succeeds(space('design'), fault, code)
        faults.test_timeline_save_failure_never_publishes_candidate(request.getfixturevalue('running'), fault, code)
        with monkeypatch.context() as patch:
            archives.test_import_write_failure_and_cancellation_roll_back_everything(space('archive'), patch)
        with monkeypatch.context() as patch:
            recovery.test_backup_failure_does_not_remove_existing_destination_or_history(space('backup'), patch)
    elif scenario == 'dynamic':
        timeline.test_year_fast_forward_keeps_daily_shortage_and_all_multirate_boundaries()
        experiments.test_mixed_rates_event_conflict_and_checkpoint_replay_keep_intermediate_history(space('mixed'))
        stochastic.test_reopen_continuation_and_unrelated_module_insertion(space('named'))
        with monkeypatch.context() as patch:
            stochastic.test_actual_transition_atomic_retention_shared_consumers_and_cold_retry(space('shared'), patch)
        for committed in (False, True):
            stochastic.test_random_evidence_real_process_crash_is_atomic(space('crash-' + str(committed)), committed)
        experiments.test_random_forks_keep_realized_past_and_explicit_future_seed_policy(space('forks'))
    elif scenario == 'adoptions':
        accepted = request.getfixturevalue('approved')
        timeline.test_disjoint_approved_deltas_compose_and_conflict_is_atomic(accepted)
        timeline.test_future_policy_preserves_past_dynamic_inputs_and_pending_cases(accepted)
        timeline.test_same_day_event_can_satisfy_only_an_already_approved_precondition(accepted)
        boundaries.test_actual_same_day_event_adoption_conflict_gap_survive_reopen(accepted, tmp_path)
        experiments.test_retrospective_fork_preserves_stocks_pending_work_and_original_history(space('fork'))
        experiments.test_retrospective_future_event_edit_does_not_rewrite_parent(space('future'))
    elif scenario == 'uncertainty':
        uncertainty.test_same_variable_cancels_before_interval_propagation()
        uncertainty.test_joint_common_cause_shortage_is_one_quarter_not_independent_seven_sixteenths()
        uncertainty.test_unresolved_factorization_never_multiplies_marginals()
        selected = request.getfixturevalue('system')
        uncertainty_service.test_actual_analysis_pins_revision_types_time_provenance_and_digest(selected)
        uncertainty_service.test_sensitivity_calls_actual_preview_without_committing_and_retains_explicit_choices(selected)
        uncertainty_service.test_resource_capacity_independent_feasible_infeasible_oracle_and_no_writes(selected)
        uncertainty_service.test_goals_cannot_enter_capacity_problem(selected)
    elif scenario == 'archives':
        archives.test_real_roundtrip_branches_evidence_reopen_no_model_or_cache(space('ordinary'))
        archives.test_reduced_explicit_omissions_and_distinct_collision_identity(space('reduced'))
        reports.test_exact_python_measurements_and_unavailable_values(space('reports'))
        reports.test_history_privacy_notes_subtypes_and_keys(space('private'))
        reports.test_imported_historical_reports_no_runtime_and_reduced_evidence(space('imported'))
    elif scenario == 'hostile-archive':
        for i, name in enumerate(['../escape', '/absolute', 'data\\escape', 'x.py', 'C:/bad']):
            archives.test_unsafe_paths_leave_destination_untouched(space('path-' + str(i)), name)
        for i, mode in enumerate([stat.S_IFLNK | 0o777, stat.S_IFREG | 0o755, stat.S_IFDIR | 0o755]):
            archives.test_entry_types_rejected(space('mode-' + str(i)), mode)
        archives.test_digest_corruption_duplicate_names_duplicate_keys_and_unknown_schema(space('integrity'))
        with monkeypatch.context() as patch:
            archives.test_size_and_count_budgets_are_enforced_before_mutation(space('bounds'), patch)
        with monkeypatch.context() as patch:
            archives.test_import_write_failure_and_cancellation_roll_back_everything(space('transaction'), patch)
    elif scenario == 'timeline-evidence':
        experiments.test_continuous_checkpoint_resume_and_model_free_recorded_replay(space('replay'))
        experiments.test_cache_eviction_and_checkpoint_spacing_preserve_all_explanations(space('cache'))
        boundaries.test_cache_eviction_detached_reads_and_reopen_preserve_all_evidence(request.getfixturevalue('running'), tmp_path)
    else:
        recovery.test_absent_mechanism_archive_is_inspectable_but_not_executable(space('absent'))
        recovery.test_explicit_schema_upgrade_preserves_history_and_backup(space('legacy'))
        recovery.test_interrupted_schema_ddl_rolls_back_and_keeps_backup(space('interrupted'))
        recovery.test_new_model_branch_never_rewrites_source_and_replays(space('migration'))
        recovery.test_snapshot_restore_replays_and_retains_evidence_after_cache_deletion(space('restore'))
        recovery.test_backup_restore_does_not_resurrect_deleted_private_payloads(space('private'))
