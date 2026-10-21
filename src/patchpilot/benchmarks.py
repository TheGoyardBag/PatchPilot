from __future__ import annotations
import json
from pathlib import Path
from .security import sha

def suite_source(cases: list) -> str:
    lines=["import unittest", "from subject import solve", "", "class Cases(unittest.TestCase):"]
    for i,(args,expected) in enumerate(cases):
        lines.extend([f"    def test_case_{i:03}(self):",f"        self.assertEqual(solve(*{args!r}), {expected!r})",""])
    return "\n".join(lines)+"\n"

class Benchmarks:
    def __init__(self,path: Path):
        self.path=path
        content=json.loads(path.read_text())
        self.tasks={t["id"]:t for t in content["tasks"]}
    def get(self,ident: str) -> dict:
        if ident not in self.tasks: raise KeyError(ident)
        return self.tasks[ident]
    def catalog(self) -> list[dict]:
        return [{"id":t["id"],"title":t["title"],"issue":t["issue"],"family":t["family"],"kind":"authored_fixture",
                 "public_tests":len(t["public"]),"candidate_source":"curated examples, not LLM output"} for t in self.tasks.values()]
    def materialize(self,ident: str,root: Path,code: str | None=None,oracle: bool=False):
        t=self.get(ident)
        (root/"src").mkdir(parents=True,exist_ok=True);(root/"tests").mkdir(parents=True,exist_ok=True)
        (root/"src/subject.py").write_text(code if code is not None else t["source"])
        (root/"tests/test_public.py").write_text(suite_source(t["public"]))
        (root/"README.md").write_text(t["title"]+"\n\n"+t["issue"]+"\n")
        if oracle: (root/"tests/test_oracle.py").write_text(suite_source(t["oracle"]))
    def verify(self,ident: str,root: Path,*,oracle: bool=False) -> bool:
        """Host runner is allowed only for exact, authored corpus contents."""
        t=self.get(ident)
        expected={"src/subject.py","tests/test_public.py","README.md"}
        if oracle: expected.add("tests/test_oracle.py")
        actual=set()
        for p in root.rglob("*"):
            if p.is_symlink(): return False
            if p.is_file(): actual.add(p.relative_to(root).as_posix())
        if actual!=expected: return False
        try:
            if (root/"src/subject.py").read_text() not in {t["source"],*(c["code"] for c in t["candidates"])}: return False
            if (root/"tests/test_public.py").read_text()!=suite_source(t["public"]): return False
            if (root/"README.md").read_text()!=t["title"]+"\n\n"+t["issue"]+"\n": return False
            if oracle and (root/"tests/test_oracle.py").read_text()!=suite_source(t["oracle"]): return False
            return True
        except (OSError,UnicodeError): return False
