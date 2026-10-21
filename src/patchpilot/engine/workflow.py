from __future__ import annotations
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Callable
import numpy as np
from ..benchmarks import Benchmarks
from ..config import Settings
from ..ml.features import features,FEATURE_NAMES
from ..ml.model import Ranker
from ..repositories import Repositories
from ..schemas import Proposal,TestResult
from ..security import PolicyError,sha,validate_proposal,redact,list_files,safe_path
from ..store import Store
from .graph import run_stages
from .provider import OpenAIProvider,ProviderError,BudgetExceeded
from .retrieval import CodeIndex
from .runner import TestRunner

class Engine:
    def __init__(self,settings: Settings,store: Store,provider_factory=OpenAIProvider):
        self.settings,self.store=settings,store
        self.bench=Benchmarks(settings.root/'data/benchmarks.json')
        self.repos=Repositories(settings.state)
        self.ranker=Ranker(settings.root/'artifacts/ranker.json')
        self.provider_factory=provider_factory
        self.runner=TestRunner(settings.runner,settings.runner_image,settings.test_timeout_s)

    def catalog(self):return self.bench.catalog()+self.repos.catalog()
    def task(self,ident: str) -> dict:
        if ident in self.bench.tasks:return {**self.bench.get(ident),'pattern':'test_public.py','kind':'fixture'}
        return {**self.repos.get(ident),'id':ident,'kind':'repo'}

    def run(self,ident: str,orchestrator: str='native'):
        job=self.store.get(ident);self.store.transition(ident,'queued','running')
        start=time.monotonic()
        try:
            task=self.task(job['task_id'])
            with tempfile.TemporaryDirectory(prefix='patchpilot-job-') as d:
                root=Path(d)/'base';root.mkdir()
                if task['kind']=='fixture':self.bench.materialize(task['id'],root)
                else:
                    for path in list_files(task['root']):
                        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True)
                        dest.write_bytes(safe_path(task['root'],path).read_bytes())
                context={'root':root,'task':task,'job':job,'candidates':[],'start':start}
                run_stages([('inspect',self.inspect),('generate',self.generate),('rank',self.rank)],context,orchestrator)
        except Exception as exc:
            # Provider failures never masquerade as live model-generated patches.
            self.store.transition(ident,'running','failed',error=redact(f'{type(exc).__name__}: {str(exc)[:1000]}'))

    def emit(self,ctx,kind,payload):self.store.event(ctx['job']['id'],kind,payload)

    def trusted(self,ctx,root):
        return ctx['task']['kind']=='fixture' and self.bench.verify(ctx['task']['id'],root)

    def inspect(self,ctx):
        idx=CodeIndex(ctx['root']);ctx['index']=idx
        self.emit(ctx,'inspect',{'message':'Indexed allowed source files and Python symbols','files':len(idx.files)})
        baseline=self.runner.run(ctx['root'],ctx['task']['pattern'],trusted_fixture=self.trusted(ctx,ctx['root']))
        ctx['baseline']=baseline
        self.emit(ctx,'baseline',{'message':'Baseline tests executed','tests':baseline.model_dump()})
        if baseline.status in {'runner_error','timeout','output_limit'}:
            raise RuntimeError('Baseline execution could not produce a usable test result; inspect the runner')
        self.emit(ctx,'retrieval',{'message':'Issue-relevant source candidates','matches':idx.search(ctx['job']['issue'])})
        return ctx

    def evaluate(self,ctx,proposal: Proposal) -> dict:
        if len(ctx['candidates'])>=6:raise ValueError('Candidate budget reached')
        if time.monotonic()-ctx['start']>self.settings.job_timeout_s:raise BudgetExceeded('Total job time budget reached')
        key=sha(json.dumps([e.model_dump() for e in proposal.edits],sort_keys=True))[:12]
        existing=next((x for x in ctx['candidates'] if x['id']==key),None)
        if existing:return self.feedback(existing)
        candidate={'id':key,'title':proposal.title,'rationale':proposal.rationale,'eligible':False,'score':None,
                   'diff':'','test_result':None,'status':'rejected','policy_error':None,'features':None}
        try:
            diff,originals=validate_proposal(ctx['root'],proposal);candidate['diff']=diff
            self.emit(ctx,'candidate',{'message':f'Evaluating candidate: {proposal.title}','candidate_id':key})
            with tempfile.TemporaryDirectory(prefix='patchpilot-patch-') as d:
                sandbox=Path(d)/'repo';shutil.copytree(ctx['root'],sandbox)
                for edit in proposal.edits:(sandbox/edit.path).write_text(edit.content)
                result=self.runner.run(sandbox,ctx['task']['pattern'],trusted_fixture=self.trusted(ctx,sandbox))
            before='\n'.join(originals[e.path] for e in proposal.edits)
            after='\n'.join(e.content for e in proposal.edits)
            vector=features(before,after,result,len(proposal.edits))
            candidate.update(status='tested',eligible=result.eligible,score=float(self.ranker.score(vector)),
                             test_result=result.model_dump(),features=dict(zip(FEATURE_NAMES,vector.astype(float).tolist())))
        except (ValueError,PolicyError) as exc:
            candidate['policy_error']=str(exc)
        ctx['candidates'].append(candidate)
        self.emit(ctx,'candidate_result',{'candidate_id':key,'eligible':candidate['eligible'],
                                        'policy_error':candidate['policy_error'],'score':candidate['score']})
        return self.feedback(candidate)

    @staticmethod
    def feedback(c):
        return {'candidate_id':c['id'],'status':c['status'],'public_tests':c['test_result'],
                'policy_error':c['policy_error'],'eligible_for_review':c['eligible'],
                'note':'Public test success is not proof of correctness. No oracle results are exposed.'}

    def generate(self,ctx):
        job=ctx['job'];task=ctx['task']
        if job['provider']=='demo':
            if task['kind']!='fixture':raise ValueError('Demo candidates exist only for bundled fixtures')
            self.emit(ctx,'provider',{'message':'Replaying authored candidate proposals; no LLM is used in demo mode'})
            for c in task['candidates']:
                proposal=Proposal.model_validate({'title':c['name'],'rationale':'Authored benchmark proposal. Compare observed tests and the diff before deciding.',
                    'edits':[{'path':'src/subject.py','before_sha256':sha(task['source']),'content':c['code']}]})
                self.evaluate(ctx,proposal)
            ctx['provider']={'provider':'demo','live_model':False,'notes':['Candidate proposals are authored fixtures, not AI-generated. ML ranking and tests run locally.']}
        else:
            if not self.settings.allow_external_llm or self.settings.runner!='docker':
                raise ProviderError('Live LLM runs require explicit source-sharing consent configuration and Docker')
            provider=self.provider_factory(self.settings.api_key,self.settings.model,
                    max_turns=self.settings.max_llm_turns,max_tools=self.settings.max_tool_calls,
                    timeout_s=self.settings.job_timeout_s)
            def tool(name,args):
                self.emit(ctx,'tool',{'name':name,'message':f'Agent requested {name}'})
                if name=='list_files':
                    if args:raise ValueError('list_files takes no arguments')
                    return ctx['index'].listing()
                if name=='search_code':
                    if set(args)!={'query'} or not isinstance(args['query'],str):raise ValueError('Expected query string')
                    return {'matches':ctx['index'].search(args['query'])}
                if name=='read_file':return ctx['index'].read(**args)
                if name=='submit_candidate':return self.evaluate(ctx,Proposal.model_validate(args))
                raise ValueError('Unknown tool')
            try:
                ctx['provider']=provider.run(job['issue'],ctx['baseline'].model_dump(),tool,lambda kind,p:self.emit(ctx,kind,p))
            except BudgetExceeded as exc:
                # Preserve actually tested proposals, visibly marking the truncated run.
                if not ctx['candidates']:raise
                ctx['provider']={'provider':'openai','model':self.settings.model,'live_model':True,'budget_exhausted':True,'notes':[str(exc)]}
        return ctx

    def rank(self,ctx):
        candidates=sorted(ctx['candidates'],key=lambda c:(not c['eligible'],-(c['score'] if c['score'] is not None else -1),c['id']))
        result={'baseline':ctx['baseline'].model_dump(),'candidates':candidates,'provider':ctx['provider'],
                'ranker':self.ranker.metadata,'elapsed_s':round(time.monotonic()-ctx['start'],3),
                'runner':self.settings.runner,'limitations':['Ranking scores are uncalibrated.','Public tests are not a correctness proof.',
                  'Approval records a review; it does not push, merge, or modify your original repository.']}
        if not candidates:raise RuntimeError('No patch candidates were produced')
        self.emit(ctx,'ranked',{'message':'Candidates ranked; waiting for human review','count':len(candidates),
                              'eligible':sum(c['eligible'] for c in candidates)})
        self.store.transition(ctx['job']['id'],'running','awaiting_review',result=result)
        return ctx
