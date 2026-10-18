import json
from pathlib import Path
import pytest


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv('POLISCOPE_USER_DATA', str(tmp_path))
    return tmp_path


@pytest.fixture
def synthetic():
    return json.loads((Path(__file__).parents[1] / 'fixtures/synthetic.json').read_text())
