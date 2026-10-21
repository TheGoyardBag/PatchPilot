"""CLI argument plumbing, real fixture runs, and explicit source-sharing consent."""
import json
import sys
from pathlib import Path
import pytest
from patchpilot import cli
from patchpilot.config import Settings


def invoke(monkeypatch, root, tmp_path, *args):
    monkeypatch.setenv('PATCHPILOT_ROOT', str(root))
    monkeypatch.setenv('PATCHPILOT_STATE', str(tmp_path / 'state'))
    monkeypatch.setattr(sys, 'argv', ['patchpilot', *args])
    return cli.main()


def test_cli_lists_authored_tasks(monkeypatch, root, tmp_path, capsys):
    assert invoke(monkeypatch, root, tmp_path, 'tasks') == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 24 and any(x['id'] == 'pagination' for x in rows)


def test_cli_executes_fixture_job(monkeypatch, root, tmp_path, capsys):
    assert invoke(monkeypatch, root, tmp_path, 'run', 'pagination') == 0
    job = json.loads(capsys.readouterr().out)
    assert job['status'] == 'awaiting_review'
    assert job['result']['provider']['live_model'] is False


def test_cli_live_mode_requires_consent(monkeypatch, root, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        invoke(monkeypatch, root, tmp_path, 'run', 'pagination', '--provider', 'openai')
    assert exc.value.code == 2
    assert 'consent-source-sharing' in capsys.readouterr().err


def test_cli_unknown_task_is_nonzero(monkeypatch, root, tmp_path):
    with pytest.raises(SystemExit) as exc:
        invoke(monkeypatch, root, tmp_path, 'run', 'not-a-task')
    assert exc.value.code == 2


def test_cli_register_snapshot(monkeypatch, root, tmp_path, workspace, capsys):
    issue = tmp_path / 'issue.txt'
    issue.write_text('Fix the pagination endpoint boundary.')
    assert invoke(monkeypatch, root, tmp_path, 'register', 'repo-example', str(workspace), '--issue-file', str(issue)) == 0
    assert 'repo-example' in capsys.readouterr().out


def test_cli_github_read_adapter(monkeypatch, root, tmp_path, capsys):
    import patchpilot.engine.github
    monkeypatch.setattr(patchpilot.engine.github, 'fetch_issue', lambda *args: {'title': 'A bug', 'body': 'Reproduction.'})
    out = tmp_path / 'issue.txt'
    assert invoke(monkeypatch, root, tmp_path, 'github-issue', 'owner/repo', '3', '--out', str(out)) == 0
    assert out.read_text() == 'A bug\n\nReproduction.\n'
    assert 'No code cloned' in capsys.readouterr().out


def test_cli_serve_invokes_loopback_only(monkeypatch, root, tmp_path):
    import uvicorn
    called = {}
    monkeypatch.setenv('PATCHPILOT_TOKEN', 'test-token-' + 's' * 40)
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kwargs: called.update(kwargs))
    assert invoke(monkeypatch, root, tmp_path, 'serve', '--port', '8123') == 0
    assert called == {'host': '127.0.0.1', 'port': 8123}


def test_settings_reads_local_token(monkeypatch, root, tmp_path):
    state = tmp_path / 'settings-state'
    state.mkdir()
    (state / 'token').write_text('local-token-value\n')
    monkeypatch.setenv('PATCHPILOT_ROOT', str(root))
    monkeypatch.setenv('PATCHPILOT_STATE', str(state))
    monkeypatch.delenv('PATCHPILOT_TOKEN', raising=False)
    assert Settings.from_env().token == 'local-token-value'


def test_settings_rejects_unknown_runner(monkeypatch):
    monkeypatch.setenv('PATCHPILOT_RUNNER', 'unsafe-shell')
    with pytest.raises(ValueError, match='RUNNER'):
        Settings.from_env()
