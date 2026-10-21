import os
from pathlib import Path
import pytest
from patchpilot.engine.runner import TestRunner as Runner,RunnerUnavailable

def test_host_refuses_unknown_code(workspace):
    with pytest.raises(RunnerUnavailable):Runner().run(workspace)

def test_baseline_failure(workspace,bench):
    result=Runner().run(workspace,trusted_fixture=bench.verify('pagination',workspace))
    assert result.tests==3 and result.passed==1 and result.failed==2
    assert not result.eligible

def test_fixed_fixture_passes(workspace,bench):
    task=bench.get('pagination');code=next(c['code'] for c in task['candidates'] if c['name']=='Focused implementation')
    (workspace/'src/subject.py').write_text(code)
    r=Runner().run(workspace,trusted_fixture=bench.verify('pagination',workspace))
    assert r.eligible and r.tests==3

def test_fixture_tampering_denied(workspace,bench):
    (workspace/'tests/test_public.py').write_text('print("forged")\n')
    assert not bench.verify('pagination',workspace)

def test_fixture_extra_file_denied(workspace,bench):
    (workspace/'src/extra.py').write_text('x=1\n')
    assert not bench.verify('pagination',workspace)

def test_timeout_of_known_test(workspace):
    (workspace/'src/subject.py').write_text('while True:\n    pass\n')
    r=Runner(timeout_s=.15).run(workspace,trusted_fixture=True)
    assert r.status=='timeout'

def test_bounded_output_of_known_test(workspace):
    (workspace/'src/subject.py').write_text("print('x'*20000)\n")
    r=Runner(output_limit=3000).run(workspace,trusted_fixture=True)
    assert r.status=='output_limit' and len(r.output)<4000

def test_empty_suite_not_success(workspace):
    (workspace/'tests/test_public.py').write_text('import unittest\n')
    r=Runner().run(workspace,trusted_fixture=True)
    assert not r.eligible and r.tests==0

def test_skipping_not_success(workspace):
    (workspace/'tests/test_public.py').write_text("import unittest\nclass T(unittest.TestCase):\n @unittest.skip('skip')\n def test_skip(self): pass\n")
    r=Runner().run(workspace,trusted_fixture=True)
    assert not r.eligible and r.skipped==1

def test_docker_controls(workspace):
    cmd=Runner('docker').docker_command(workspace,'test_public.py','patchpilot-test')
    for flag in ['--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--pids-limit=64','--memory=256m','--cpus=1','--user=65532:65532']:assert flag in cmd
    assert 'readonly' in ' '.join(cmd) and not any('docker.sock' in x for x in cmd)

def test_missing_docker_fails_closed(workspace,monkeypatch):
    monkeypatch.setattr('patchpilot.engine.runner.shutil.which',lambda _:None)
    with pytest.raises(RunnerUnavailable):Runner('docker').run(workspace)

@pytest.mark.parametrize('pattern',['../test.py','foo.py','test_*.py;ls','/test_a.py'])
def test_invalid_pattern(workspace,pattern):
    with pytest.raises(ValueError):Runner().run(workspace,pattern,trusted_fixture=True)

@pytest.mark.docker
def test_real_docker_runner(workspace,bench):
    if os.environ.get('PATCHPILOT_DOCKER_TESTS')!='1':pytest.skip('Docker execution explicitly disabled in this environment')
    r=Runner('docker',timeout_s=30).run(workspace)
    assert r.tests==3 and r.failed==2 and r.runner=='docker'
