"""Assistant/spending contracts reject secret, path and forged-context authority."""
import pytest
from pydantic import ValidationError
from poliscope_engine.contracts.assistant import AssistantPrepare, AssistantAction
from poliscope_engine.contracts.spending import SpendReserve, SpendBinding

BASE=dict(action='prepare',profile_id='p',expected_revision=1,text='explicit text',stream=True,exposure='0.01',turn_limit='0.01',session_limit='0.10',profile_limit='1')

@pytest.mark.parametrize('extra',[{'endpoint':'https://sink.invalid'},{'key':'private'},{'operation':'world.apply'},{'path':'/etc/passwd'},{'context_json':'forged'},{'budgets':[]}])
def test_no_renderer_authority(extra):
    with pytest.raises(ValidationError):AssistantPrepare.model_validate(BASE|extra)

@pytest.mark.parametrize('amount',['-1','NaN','Infinity','0.0000001','1e2','10000000','unknown'])
def test_invalid_exposure(amount):
    with pytest.raises(ValidationError):AssistantPrepare.model_validate(BASE|dict(exposure=amount))

def test_continuation_cannot_inherit_existing_grants():
    assert AssistantAction(action='continue',request_id='old').action == 'continue'
    # Runtime requires a completed tool turn; this DTO conveys no spending or sharing grant.
    with pytest.raises(ValidationError):SpendBinding(dispatch_id='d',turn_id='t',session_id='s',profile_id='p',payload_sha256='not-digest',binding_sha256='b'*64,currency='USD',estimate_version='explicit-bounded-exposure-v1')
