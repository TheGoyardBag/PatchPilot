import time
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from patchpilot.api import create_app

@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:yield c
@pytest.fixture
def auth(settings):return {'Authorization':'Bearer '+settings.token}

def wait(client,auth,ident):
    for _ in range(160):
        j=client.get('/api/jobs/'+ident,headers=auth).json()
        if j['status'] not in {'queued','running'}:return j
        time.sleep(.025)
    pytest.fail('Job did not complete')

def test_auth_required(client):
    assert client.get('/api/tasks').status_code==401
    assert client.get('/health').json()['status']=='ok'

def test_bad_auth(client):assert client.get('/api/tasks',headers={'Authorization':'Bearer nope'}).status_code==401

def test_api_catalog(client,auth):
    tasks=client.get('/api/tasks',headers=auth).json()
    assert len(tasks)==24 and 'oracle' not in str(tasks) and 'candidates' not in tasks[0]

def test_no_secrets_config(client,auth,settings):
    r=client.get('/api/config',headers=auth)
    assert settings.token not in r.text and not r.json()['live_provider_enabled']

def test_full_review_export(client,auth):
    r=client.post('/api/jobs',headers=auth,json={'task_id':'pagination'})
    assert r.status_code==202
    j=wait(client,auth,r.json()['id']);assert j['status']=='awaiting_review',j.get('error')
    assert client.get(f"/api/jobs/{j['id']}/patch",headers=auth).status_code==409
    candidate=next(c for c in j['result']['candidates'] if c['title']=='Focused implementation')
    review={'candidate_id':candidate['id'],'decision':'approve','note':'Checked final-page boundaries','version':j['version']}
    assert client.post(f"/api/jobs/{j['id']}/review",headers=auth,json=review).status_code==200
    patch=client.get(f"/api/jobs/{j['id']}/patch",headers=auth)
    assert patch.status_code==200 and '--- a/src/subject.py' in patch.text
    assert client.post(f"/api/jobs/{j['id']}/review",headers=auth,json=review).status_code==409

def test_fail_cannot_be_approved(client,auth):
    created=client.post('/api/jobs',headers=auth,json={'task_id':'pagination'}).json();j=wait(client,auth,created['id'])
    candidate=next(c for c in j['result']['candidates'] if not c['eligible'])
    res=client.post(f"/api/jobs/{j['id']}/review",headers=auth,json={'candidate_id':candidate['id'],'decision':'approve','note':'Try approval','version':j['version']})
    assert res.status_code==409

def test_live_requires_consent(client,auth):
    r=client.post('/api/jobs',headers=auth,json={'task_id':'pagination','provider':'openai'})
    assert r.status_code==400

def test_live_requires_configuration(client,auth):
    r=client.post('/api/jobs',headers=auth,json={'task_id':'pagination','provider':'openai','consent_external':True})
    assert r.status_code==409

def test_unknown_task(client,auth):assert client.post('/api/jobs',headers=auth,json={'task_id':'missing'}).status_code==404

def test_unknown_job(client,auth):assert client.get('/api/jobs/none',headers=auth).status_code==404

def test_schema_rejects_arbitrary_commands(client,auth):
    r=client.post('/api/jobs',headers=auth,json={'task_id':'pagination','command':'echo ignored'})
    assert r.status_code==422

def test_events_and_stream(client,auth):
    j=client.post('/api/jobs',headers=auth,json={'task_id':'tail'}).json();wait(client,auth,j['id'])
    events=client.get(f"/api/jobs/{j['id']}/events",headers=auth).json()
    assert events[-1]['kind']=='awaiting_review'
    r=client.get(f"/api/jobs/{j['id']}/stream",headers=auth)
    assert 'event: complete' in r.text and 'text/event-stream' in r.headers['content-type']

def test_cross_origin_write_denied(client,auth):
    r=client.post('/api/jobs',headers={**auth,'Origin':'https://other.example'},json={'task_id':'pagination'})
    assert r.status_code==403

def test_bad_host_denied(client,auth):
    assert client.get('/api/tasks',headers={**auth,'host':'attacker.example'}).status_code==400

def test_static_security_headers(client):
    r=client.get('/')
    assert r.status_code==200 and 'PatchPilot' in r.text
    assert r.headers['X-Frame-Options']=='DENY'
    assert client.get('/static/app.js').status_code==200

def test_metrics_endpoint(client,auth):
    r=client.get('/api/metrics',headers=auth)
    assert r.status_code==200 and r.json()['split_unit']=='Entire bug family'

def test_weak_server_token(settings):
    with pytest.raises(RuntimeError):create_app(replace(settings,token='weak'))
