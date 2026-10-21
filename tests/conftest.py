from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from patchpilot.config import Settings
from patchpilot.benchmarks import Benchmarks
from patchpilot.store import Store

@pytest.fixture
def root():return ROOT
@pytest.fixture
def settings(tmp_path):return Settings(root=ROOT,state=tmp_path/'state',token='test-only-'+'a'*40)
@pytest.fixture
def bench():return Benchmarks(ROOT/'data/benchmarks.json')
@pytest.fixture
def workspace(tmp_path,bench):
    p=tmp_path/'repo';bench.materialize('pagination',p);return p
@pytest.fixture
def store(settings):return Store(settings.state/'test.sqlite3')
