"""Two retained synthetic worlds: a regional reserve of 200 then 250 kg."""
import json
import sys
from pathlib import Path
from overview_fixture import registry, seed, inputs
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest

if __name__ == '__main__':
    with Store(Path(sys.argv[1])) as store:
        service = Revisions(store, registry=registry())
        root = seed(service).context
        data = inputs().model_dump()
        data['design']['execution']['batch']['accounts'][-1]['opening'] = '250'
        request = PreviewRequest(revision_contract=1, context=root, changes=[dict(kind='replace_inputs', inputs=data)],
            decision=dict(alternatives=[], selected_id=None, rationale_ref=None))
        candidate = service.preview(request)
        head = service.apply(ApplyRequest(revision_contract=1, operation_id='reserve:250', preview=request, candidate_digest=candidate.candidate_digest)).context
        print(json.dumps(dict(root=root.revision_id, head=head.revision_id)))
