"""Read-only GitHub issue import. No repository cloning or writes."""
from __future__ import annotations
import re
import httpx

def fetch_issue(repository: str,number: int,token: str="",client: httpx.Client | None=None) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository) or any(p in {'.','..'} for p in repository.split('/')):
        raise ValueError("Expected owner/repository, not a URL")
    if number<1:raise ValueError("Issue number must be positive")
    headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"PatchPilot-portfolio"}
    if token:headers['Authorization']='Bearer '+token
    own=client is None;client=client or httpx.Client(timeout=15,follow_redirects=False,trust_env=False)
    try:
        response=client.get(f"https://api.github.com/repos/{repository}/issues/{number}",headers=headers)
        if response.status_code!=200:raise ValueError(f"GitHub issue request returned HTTP {response.status_code}")
        data=response.json()
        if 'pull_request' in data:raise ValueError("This number refers to a pull request, not an issue")
        return {"title":str(data.get('title',''))[:300],"body":str(data.get('body') or '')[:9500],
                "number":number,"repository":repository,"url":f"https://github.com/{repository}/issues/{number}",
                "untrusted":True}
    finally:
        if own:client.close()
