import json
from dataclasses import replace
from pathlib import Path
import pytest
from patchpilot.engine.workflow import Engine
from patchpilot.engine.graph import run_stages
from patchpilot.schemas import Proposal
from patchpilot.security import sha

def test_demo_end_to_end(settings,store,bench):
    original=(settings.root/'data/benchmarks.json').read_bytes()
    engine=Engine(settings,store)
    job=store.create('pagination','demo',bench.get('pagination')['issue']);engine.run(job['id'])
    current=store.get(job['id'])
    assert current['status']=='awaiting_review',current['error']
    result=current['result']
    assert len(result['candidates'])==6
    assert result['provider']['live_model'] is False
    assert any(c['status']=='rejected' and 'No-op' in (c['policy_error'] or '') for c in result['candidates'])
    assert result['candidates'][0]['eligible']
    assert (settings.root/'data/benchmarks.json').read_bytes()==original
    assert 'oracle' not in json.dumps(result['baseline']).lower()

def test_invalid_task_fails_cleanly(settings,store):
    engine=Engine(settings,store);job=store.create('missing','demo','oops');engine.run(job['id'])
    assert store.get(job['id'])['status']=='failed'

def test_no_unconfigured_llm_fallback(settings,store,bench):
    engine=Engine(settings,store);job=store.create('pagination','openai','fix it');engine.run(job['id'])
    current=store.get(job['id']);assert current['status']=='failed'
    assert 'explicit' in current['error'] and not current['result'].get('candidates')

def test_native_graph_order():
    result=run_stages([('a',lambda x:{'n':x['n']+1}),('b',lambda x:{'n':x['n']*2})],{'n':2})
    assert result=={'n':6}

def test_unknown_graph_backend():
    with pytest.raises(ValueError):run_stages([],{},'bad')

@pytest.mark.graph
def test_real_langgraph_adapter():
    pytest.importorskip('langgraph')
    assert run_stages([('increment',lambda x:{'n':x['n']+1})],{'n':2},'langgraph')=={'n':3}

def test_workflow_rejects_test_mutation(settings,store,workspace,bench):
    engine=Engine(settings,store);job=store.create('pagination','demo','x')
    ctx={'root':workspace,'task':{**bench.get('pagination'),'kind':'fixture','pattern':'test_public.py'},'job':job,'start':__import__('time').monotonic(),'candidates':[]}
    before=(workspace/'tests/test_public.py').read_text()
    p=Proposal(title='Bad change',rationale='Attempt to replace tests.',edits=[{'path':'tests/test_public.py','before_sha256':sha(before),'content':'# removed\n'}])
    result=engine.evaluate(ctx,p)
    assert result['status']=='rejected' and not result['eligible_for_review']

def test_candidate_deduplication(settings,store,workspace,bench):
    engine=Engine(settings,store);job=store.create('pagination','demo','x')
    task=bench.get('pagination');ctx={'root':workspace,'task':{**task,'kind':'fixture','pattern':'test_public.py'},'job':job,'start':__import__('time').monotonic(),'candidates':[]}
    code=next(c['code'] for c in task['candidates'] if c['name']=='Focused implementation')
    p=Proposal(title='Fix',rationale='Correct end index.',edits=[{'path':'src/subject.py','before_sha256':sha(task['source']),'content':code}])
    a=engine.evaluate(ctx,p);b=engine.evaluate(ctx,p)
    assert a['candidate_id']==b['candidate_id'] and len(ctx['candidates'])==1
