from pathlib import Path
import subprocess
import shutil
import pytest
from patchpilot.security import safe_path,PolicyError,sha,validate_proposal,list_files,redact
from patchpilot.schemas import Proposal

@pytest.mark.parametrize('name',['../outside.py','/tmp/foo.py','src/../subject.py','src//subject.py','./src/subject.py','src\\subject.py','C:/x.py','.git/config','.env','a\x00.py','src/x\n.py','src/.cache/x.py','src/secret.py','src/id_rsa.py'])
def test_disallowed_paths(workspace,name):
    with pytest.raises(PolicyError):safe_path(workspace,name)

def proposal(workspace,code=None,path='src/subject.py'):
    before=(workspace/path).read_text()
    return Proposal(title='Fix boundary',rationale='Preserve the final element.',edits=[{'path':path,'before_sha256':sha(before),'content':code or before.replace('size - 1','size')}])

def test_good_patch_is_not_applied(workspace):
    before=(workspace/'src/subject.py').read_text();diff,_=validate_proposal(workspace,proposal(workspace))
    assert '-    return items[start:start + size - 1]' in diff
    assert (workspace/'src/subject.py').read_text()==before

def test_test_changes_rejected(workspace):
    with pytest.raises(PolicyError):validate_proposal(workspace,proposal(workspace,'# erased\n','tests/test_public.py'))

def test_symlink_rejected(workspace,tmp_path):
    external=tmp_path/'outside.py';external.write_text('x=1\n');(workspace/'src/link.py').symlink_to(external)
    with pytest.raises(PolicyError):safe_path(workspace,'src/link.py')
    assert 'src/link.py' not in list_files(workspace)

def test_stale_hash(workspace):
    p=proposal(workspace);p.edits[0].before_sha256='f'*64
    with pytest.raises(PolicyError,match='Stale'):validate_proposal(workspace,p)

def test_duplicate_paths(workspace):
    p=proposal(workspace);p.edits.append(p.edits[0])
    with pytest.raises(PolicyError,match='Duplicate'):validate_proposal(workspace,p)

def test_noop(workspace):
    p=proposal(workspace,(workspace/'src/subject.py').read_text())
    with pytest.raises(PolicyError,match='No-op'):validate_proposal(workspace,p)

def test_syntax_rejected(workspace):
    with pytest.raises(PolicyError,match='parse'):validate_proposal(workspace,proposal(workspace,'def bad(:\n'))

def test_line_budget(workspace):
    with pytest.raises(PolicyError,match='budget'):validate_proposal(workspace,proposal(workspace,'x=1\n'*1000))

def test_read_budget(workspace):
    (workspace/'src/large.py').write_text('x'*70000)
    with pytest.raises(PolicyError,match='limit'):safe_path(workspace,'src/large.py')

def test_only_allowed_text(workspace):
    (workspace/'src/payload.pkl').write_bytes(b'data')
    with pytest.raises(PolicyError):safe_path(workspace,'src/payload.pkl')

def test_mask_secrets():
    assert 'abcdef' not in redact('api_key=abcdef password: abcdef')
    assert '[REDACTED]' in redact('sk-'+'a'*32)

def test_diff_roundtrip(workspace,tmp_path):
    if not shutil.which('git'):pytest.skip('git CLI not installed')
    p=proposal(workspace);diff,_=validate_proposal(workspace,p)
    patch=tmp_path/'patch.diff';patch.write_text(diff)
    subprocess.run(['git','apply','--check',str(patch)],cwd=workspace,check=True,capture_output=True)
    subprocess.run(['git','apply',str(patch)],cwd=workspace,check=True,capture_output=True)
    assert (workspace/'src/subject.py').read_text()==p.edits[0].content

def test_diff_without_final_newline(workspace,tmp_path):
    if not shutil.which('git'):pytest.skip('git CLI not installed')
    (workspace/'src/subject.py').write_text('x = 1')
    p=proposal(workspace,'x = 2\n');diff,_=validate_proposal(workspace,p)
    patch=tmp_path/'patch.diff';patch.write_text(diff)
    subprocess.run(['git','apply',str(patch)],cwd=workspace,check=True,capture_output=True)
    assert (workspace/'src/subject.py').read_text()=='x = 2\n'
