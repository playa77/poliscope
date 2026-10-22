"""Pure health prerequisites; finite care time is not delivered treatment."""
from poliscope_engine.contracts.health import HealthRequest, HealthEvaluation, HealthResult
from poliscope_engine.domains.service_capacity import evaluate_prerequisites


def evaluate_health(request, *, graph, mechanisms, units):
    return evaluate_prerequisites(request, graph=graph, mechanisms=mechanisms, units=units,
        request_type=HealthRequest, evaluation_type=HealthEvaluation,
        result_type=HealthResult, domain='health', participant_kinds=('care',))
