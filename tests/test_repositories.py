import json
import httpx
import pytest
from patchpilot.repositories import Repositories
from patchpilot.engine.github import fetch_issue

def test_snapshot_no_credentials(workspace,settings):
    (workspace/'.env').write_text('API_KEY=private')
    r=Repositories(settings.state);v=r.register('repo-example',workspace,'Fix the bug')
    snapshot=r.get('repo-example')
    assert v['files']==3 and not (snapshot['root']/'.env').exists()
    assert r.catalog()[0]['kind']=='local_snapshot'

def test_snapshot_cannot_overwrite(workspace,settings):
    r=Repositories(settings.state);r.register('repo-example',workspace,'Fix it')
    with pytest.raises(ValueError):r.register('repo-example',workspace,'Again')

@pytest.mark.parametrize('name',['../../a','normal','repo-../bad','repo-X'])
def test_snapshot_ids(workspace,settings,name):
    with pytest.raises(ValueError):Repositories(settings.state).register(name,workspace,'Fix it')

def test_github_read_only_mock():
    requests=[]
    def handler(req):
        requests.append(req);return httpx.Response(200,json={'title':'Bug','body':'Details'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        issue=fetch_issue('owner/project',42,'fake-token',client)
    assert issue['untrusted'] and issue['title']=='Bug'
    assert requests[0].method=='GET' and requests[0].url.host=='api.github.com'

def test_github_rejects_pr():
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'pull_request':{}}))) as client:
        with pytest.raises(ValueError,match='pull request'):fetch_issue('o/r',1,client=client)

@pytest.mark.parametrize('repo',['https://github.com/o/r','../repo','owner/../repo','owner/repo?token=x'])
def test_github_repo_validation(repo):
    with pytest.raises(ValueError):fetch_issue(repo,1)

def test_github_http_failure():
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(404))) as client:
        with pytest.raises(ValueError,match='404'):fetch_issue('o/r',1,client=client)
