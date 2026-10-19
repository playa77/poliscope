"""Consumer fixtures derived from request-binding requirements, before services."""
import pytest
from pydantic import ValidationError
from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest


def preview():
    return dict(revision_contract=1,
        context=dict(data_store_id='s', civilization_id='c', branch_id='b', revision_id='r'),
        changes=[dict(kind='set_values', writer_id='player', partition='design', values=[])],
        decision=dict(alternatives=[], selected_id=None, rationale_ref=None))


def apply():
    return dict(revision_contract=1, operation_id='op', preview=preview(), candidate_digest='sha256:' + '0' * 64)


def test_complete_consumer_request_roundtrip():
    request = ApplyRequest.model_validate(apply())
    assert ApplyRequest.model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize('field', ['operation_id', 'preview', 'candidate_digest'])
def test_incomplete_apply_rejected(field):
    request = apply()
    del request[field]
    with pytest.raises(ValidationError):
        ApplyRequest.model_validate(request)


def test_private_payload_not_promoted_by_rationale():
    data = preview()
    data['decision']['rationale_ref'] = dict(id='private:note', visibility='private', status='available', text='private')
    with pytest.raises(ValidationError):
        PreviewRequest.model_validate(data)


def test_unversioned_or_untyped_change_rejected():
    data = preview()
    data['changes'] = [dict(kind='execute_code', source='anything')]
    with pytest.raises(ValidationError):
        PreviewRequest.model_validate(data)
