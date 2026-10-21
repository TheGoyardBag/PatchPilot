import json
import pytest
import httpx
from patchpilot.engine.provider import OpenAIProvider,ProviderError,BudgetExceeded,TOOLS

def output_call(name='list_files',args=None):return {'type':'function_call','name':name,'arguments':json.dumps(args or {}),'call_id':'call-1','id':'fc-1'}
def mock_client(handler):return httpx.Client(transport=httpx.MockTransport(handler))

def test_live_provider_protocol_with_mock():
    requests=[];calls=[];events=[]
    def handler(req):
        body=json.loads(req.content);requests.append(body)
        out=[output_call()] if len(requests)==1 else [{'type':'message','content':[{'type':'output_text','text':'Inspection finished.'}]}]
        return httpx.Response(200,json={'output':out,'usage':{'input_tokens':20,'output_tokens':5}})
    with mock_client(handler) as client:
        p=OpenAIProvider('fake-key','test-model',client=client)
        result=p.run('fix it',{},lambda name,args:calls.append(name) or {'files':[]},lambda k,v:events.append(k))
    assert result['live_model'] and result['tools']==1 and result['usage']['input_tokens']==40
    assert calls==['list_files'] and requests[0]['store'] is False and requests[0]['parallel_tool_calls'] is False
    assert any(x.get('type')=='function_call_output' for x in requests[1]['input'])

def test_unknown_tool_never_executes():
    requests=[];calls=[]
    def handler(req):
        requests.append(json.loads(req.content))
        return httpx.Response(200,json={'output':[output_call('shell',{'command':'ignored'})] if len(requests)==1 else []})
    with mock_client(handler) as client:
        OpenAIProvider('k','m',client=client).run('i',{},lambda *x:calls.append(x),lambda *x:None)
    assert not calls
    assert 'denied' in requests[1]['input'][-1]['output']

def test_invalid_arguments_return_tool_error():
    count=[0]
    def handler(req):
        count[0]+=1
        call=output_call();call['arguments']='not-json'
        return httpx.Response(200,json={'output':[call] if count[0]==1 else []})
    with mock_client(handler) as client:
        r=OpenAIProvider('k','m',client=client).run('i',{},lambda *x:pytest.fail('must not execute'),lambda *x:None)
    assert r['tools']==1

def test_model_turn_budget():
    with mock_client(lambda req:httpx.Response(200,json={'output':[output_call()]})) as client:
        with pytest.raises(BudgetExceeded):OpenAIProvider('k','m',max_turns=1,client=client).run('i',{},lambda *x:{},lambda *x:None)

def test_tool_budget():
    with mock_client(lambda req:httpx.Response(200,json={'output':[output_call(),output_call()]})) as client:
        with pytest.raises(BudgetExceeded):OpenAIProvider('k','m',max_tools=1,client=client).run('i',{},lambda *x:{},lambda *x:None)

def test_context_budget():
    with mock_client(lambda req:pytest.fail('no network call')) as client:
        with pytest.raises(BudgetExceeded):OpenAIProvider('k','m',max_input_chars=2,client=client).run('i',{},lambda *x:{},lambda *x:None)

@pytest.mark.parametrize('status',[401,429,500])
def test_http_failures_explicit(status):
    with mock_client(lambda req:httpx.Response(status,json={'error':'secret provider error'})) as client:
        with pytest.raises(ProviderError,match=f'HTTP {status}'):
            OpenAIProvider('k','m',client=client).run('i',{},lambda *x:{},lambda *x:None)

def test_missing_credentials():
    with pytest.raises(ProviderError):OpenAIProvider('','')

def test_tool_schema_strictness():
    for t in TOOLS:
        assert t['strict'] and t['parameters']['additionalProperties'] is False
        assert set(t['parameters']['required'])==set(t['parameters']['properties'])

def test_incomplete_response_rejected():
    with mock_client(lambda req:httpx.Response(200,json={'status':'incomplete','output':[]})) as client:
        with pytest.raises(ProviderError):OpenAIProvider('k','m',client=client).run('i',{},lambda *x:{},lambda *x:None)
