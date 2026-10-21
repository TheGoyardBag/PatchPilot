"""Explicit CLI registration of local source snapshots; no remote shell or cloning."""
from __future__ import annotations
import json
from pathlib import Path
import re
import shutil
import uuid
from .security import list_files,safe_path,PolicyError

class Repositories:
    def __init__(self,state: Path):
        self.state=state
        self.path=state/"repositories.json"
    def all(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.is_file() else {}
    def get(self,ident: str) -> dict:
        entry=self.all().get(ident)
        if not entry:raise KeyError(ident)
        root=(self.state/"repos"/ident).resolve()
        if not root.is_dir():raise ValueError("Repository snapshot missing")
        return {**entry,"root":root}
    def catalog(self) -> list[dict]:
        return [{"id":k,"title":v['title'],"issue":v['issue'],"kind":"local_snapshot","family":"custom",
                 "public_tests":None,"candidate_source":"live provider; Docker required"} for k,v in self.all().items()]
    def register(self,ident: str,source: Path,issue: str,pattern: str="test_*.py") -> dict:
        if not re.fullmatch(r"repo-[a-z0-9][a-z0-9_-]{0,65}",ident):raise ValueError("Repository IDs must start with repo- and use lowercase letters, digits, hyphens, underscores")
        if not re.fullmatch(r"test_[A-Za-z0-9_*]+\.py",pattern):raise ValueError("Invalid test pattern")
        if not issue.strip() or len(issue)>10000:raise ValueError("Issue text must contain 1–10000 characters")
        source=source.resolve()
        if not source.is_dir():raise ValueError("Repository path does not exist")
        if not (source/"tests").is_dir():raise ValueError("A stdlib unittest tests/ directory is required")
        entries=self.all()
        if ident in entries:raise ValueError("Snapshot ID already exists; register a new ID to refresh")
        files=list_files(source,401)
        if len(files)>400:raise ValueError("Snapshot exceeds the 400-file budget; use a smaller project")
        if not any(f.startswith("tests/") and f.endswith(".py") for f in files):raise ValueError("No readable Python tests")
        if sum(safe_path(source,f).stat().st_size for f in files)>5_000_000:raise ValueError("Snapshot exceeds 5 MB budget")
        dest=self.state/"repos"/ident
        if dest.exists():raise ValueError("Destination already exists")
        dest.mkdir(parents=True)
        try:
            for fn in files:
                target=dest/fn;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(safe_path(source,fn).read_bytes())
            entries[ident]={"title":source.name,"issue":issue,"pattern":pattern,"files":len(files)}
            self.state.mkdir(parents=True,exist_ok=True)
            tmp=self.path.with_suffix(".tmp");tmp.write_text(json.dumps(entries,indent=2));tmp.replace(self.path)
        except Exception:
            shutil.rmtree(dest,ignore_errors=True);raise
        return {"id": ident, **entries[ident]}
