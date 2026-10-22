"""Education prerequisites over the shared service capacity evaluator."""
from poliscope_engine.contracts.knowledge_culture import EducationRequest, EducationEvaluation, EducationResult
from poliscope_engine.domains.service_capacity import evaluate_prerequisites


def evaluate_education(request, *, graph, mechanisms, units):
    return evaluate_prerequisites(request, graph=graph, mechanisms=mechanisms, units=units,
        request_type=EducationRequest, evaluation_type=EducationEvaluation,
        result_type=EducationResult, domain='education', participant_kinds=('training',))
