from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
from .config import Settings
from .store import Store

def main():
    p=argparse.ArgumentParser(prog='patchpilot',description='A local, evidence-first AI repair lab')
    sub=p.add_subparsers(dest='command',required=True)
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8000)
    run=sub.add_parser('run');run.add_argument('task');run.add_argument('--provider',choices=['demo','openai'],default='demo');run.add_argument('--consent-source-sharing',action='store_true');run.add_argument('--graph',action='store_true')
    sub.add_parser('tasks')
    reg=sub.add_parser('register');reg.add_argument('id');reg.add_argument('path',type=Path);reg.add_argument('--issue-file',required=True,type=Path);reg.add_argument('--pattern',default='test_*.py')
    gh=sub.add_parser('github-issue');gh.add_argument('repository');gh.add_argument('number',type=int);gh.add_argument('--out',type=Path,required=True)
    args=p.parse_args();settings=Settings.from_env()
    try:
        if args.command=='serve':
            import uvicorn
            from .api import create_app
            uvicorn.run(create_app(settings),host='127.0.0.1',port=args.port)
        elif args.command=='tasks':
            from .benchmarks import Benchmarks
            print(json.dumps(Benchmarks(settings.root/'data/benchmarks.json').catalog(),indent=2))
        elif args.command=='register':
            from .repositories import Repositories
            print(json.dumps(Repositories(settings.state).register(args.id,args.path,args.issue_file.read_text(),args.pattern),indent=2))
        elif args.command=='github-issue':
            from .engine.github import fetch_issue
            issue=fetch_issue(args.repository,args.number,os.environ.get('GITHUB_TOKEN',''))
            args.out.write_text(issue['title']+'\n\n'+issue['body']+'\n')
            print(f'Wrote untrusted issue text to {args.out}. No code cloned or executed.')
        elif args.command=='run':
            from .engine.workflow import Engine
            if args.provider=='openai' and not args.consent_source_sharing:raise ValueError('Pass --consent-source-sharing to allow selected source excerpts to reach the model provider')
            store=Store(settings.state/'patchpilot.sqlite3');engine=Engine(settings,store)
            task=engine.task(args.task);job=store.create(args.task,args.provider,task['issue'])
            engine.run(job['id'],'langgraph' if args.graph else 'native')
            result=store.get(job['id']);print(json.dumps(result,indent=2))
            return 0 if result['status']=='awaiting_review' else 1
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        p.exit(2,f'Error: {exc}\n')
    return 0

if __name__=='__main__':sys.exit(main())
