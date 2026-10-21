import pytest
from patchpilot.engine.retrieval import CodeIndex,tokens
from patchpilot.security import PolicyError,sha

def test_index_symbols(workspace):
    i=CodeIndex(workspace)
    assert i.symbols['src/subject.py'][0]['name']=='solve'
    assert len(i.listing()['files'])==3

def test_search_returns_evidence(workspace):
    found=CodeIndex(workspace).search('page size items')
    assert found and found[0]['path']=='src/subject.py'
    assert all(r['untrusted'] for r in found)

def test_blank_search(workspace):assert CodeIndex(workspace).search('')==[]

def test_read_returns_precondition(workspace):
    r=CodeIndex(workspace).read('src/subject.py',1,3)
    assert r['sha256']==sha((workspace/'src/subject.py').read_text()) and '1:' in r['content']

@pytest.mark.parametrize('start,end',[(0,1),(3,1),(1,200)])
def test_read_limits(workspace,start,end):
    with pytest.raises(PolicyError):CodeIndex(workspace).read('src/subject.py',start,end)

def test_tokenization():assert tokens('readFile snake_case 123')==['read','file','snake','case']

def test_secret_path_not_indexed(workspace):
    (workspace/'.env').write_text('x=secret');(workspace/'src/credentials.py').write_text('x=secret')
    i=CodeIndex(workspace)
    assert '.env' not in i.files and 'src/credentials.py' not in i.files
