import pytest
from patchpilot.store import Conflict

def ready(store):
    j=store.create('pagination','demo','Fix it')
    store.transition(j['id'],'queued','running')
    store.transition(j['id'],'running','awaiting_review',result={'candidates':[{'id':'a'*12,'eligible':True,'diff':'x'},{'id':'b'*12,'eligible':False}]})
    return store.get(j['id'])

def test_create_read_events(store):
    j=store.create('pagination','demo','Fix it')
    assert store.jobs()[0]['id']==j['id'] and store.events(j['id'])[0]['kind']=='queued'

def test_state_conflict(store):
    j=store.create('x','demo','x')
    with pytest.raises(Conflict):store.transition(j['id'],'running','approved')

def test_review_approved(store):
    j=ready(store);out=store.review(j['id'],'a'*12,'approve','Checked all cases',j['version'])
    assert out['status']=='approved' and out['reviews'][0]['note']=='Checked all cases'

def test_stale_review(store):
    j=ready(store)
    with pytest.raises(Conflict):store.review(j['id'],'a'*12,'approve','Checked',j['version']-1)

def test_double_review(store):
    j=ready(store);store.review(j['id'],'a'*12,'approve','Checked',j['version'])
    with pytest.raises(Conflict):store.review(j['id'],'a'*12,'approve','Checked',j['version'])

def test_failing_candidate_cannot_approve(store):
    j=ready(store)
    with pytest.raises(Conflict):store.review(j['id'],'b'*12,'approve','Checked',j['version'])

def test_unknown_candidate(store):
    j=ready(store)
    with pytest.raises(ValueError):store.review(j['id'],'c'*12,'approve','Checked',j['version'])

def test_reject(store):
    j=ready(store);out=store.review(j['id'],'b'*12,'reject','Not correct',j['version'])
    assert out['status']=='rejected'

def test_interrupted_jobs_marked(store):
    j=store.create('x','demo','x');store.transition(j['id'],'queued','running')
    assert store.interrupt_pending()==1 and store.get(j['id'])['status']=='interrupted'
    assert store.interrupt_pending()==0

def test_unknown_job(store):
    with pytest.raises(KeyError):store.get('none')
