"""Bounded lexical code retrieval with AST symbol summaries; no remote embeddings."""
from __future__ import annotations
import ast
import math
from pathlib import Path
import re
from collections import Counter
from ..security import list_files, safe_path, sha, redact, PolicyError

def tokens(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return re.findall(r"[a-z][a-z0-9]*", text.lower().replace("_", " "))

class CodeIndex:
    def __init__(self, root: Path):
        self.root = root
        self.files = list_files(root)
        self.docs = {}
        self.symbols = {}
        for name in self.files:
            text = safe_path(root, name).read_text(encoding="utf-8", errors="replace")
            self.docs[name] = text
            if name.endswith(".py"):
                try:
                    tree = ast.parse(text)
                    self.symbols[name] = [{"name": n.name, "line": n.lineno, "kind": type(n).__name__}
                                          for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))][:60]
                except SyntaxError:
                    self.symbols[name] = []
        self.counts = {name: Counter(tokens(name + " " + text)) for name, text in self.docs.items()}
        self.avg_len = max(1, sum(sum(c.values()) for c in self.counts.values()) / max(len(self.counts), 1))

    def listing(self) -> dict:
        return {"files": [{"path": p, "symbols": self.symbols.get(p, [])} for p in self.files], "limit": 400}

    def read(self, path: str, start_line: int = 1, end_line: int = 120) -> dict:
        if start_line < 1 or end_line < start_line or end_line-start_line >= 160:
            raise PolicyError("Read at most 160 lines, using positive inclusive line numbers")
        target = safe_path(self.root, path)
        text = target.read_text(encoding="utf-8")
        lines = text.splitlines()
        excerpt = "\n".join(f"{i+1:4}: {lines[i]}" for i in range(start_line-1, min(end_line, len(lines))))
        return {"path": path, "sha256": sha(text), "start_line": start_line, "end_line": min(end_line,len(lines)),
                "total_lines": len(lines), "content": redact(excerpt), "untrusted": True}

    def search(self, query: str, limit: int = 6) -> list[dict]:
        terms = tokens(query[:1000])[:30]
        if not terms:
            return []
        scored = []
        n = len(self.docs)
        for name, count in self.counts.items():
            length = sum(count.values())
            score = 0.0
            for term in set(terms):
                df = sum(term in c for c in self.counts.values())
                idf = math.log(1 + (n-df+0.5)/(df+0.5))
                freq = count[term]
                score += idf * (freq*2.2)/(freq+1.2*(0.25+0.75*length/self.avg_len)) if freq else 0
            if score:
                text_lines = self.docs[name].splitlines()
                best = next((i for i, l in enumerate(text_lines) if set(tokens(l)) & set(terms)), 0)
                scored.append({"path": name, "score": round(score,4), "start_line": best+1,
                               "excerpt": redact("\n".join(text_lines[max(0,best-1):best+5])), "untrusted": True})
        return sorted(scored, key=lambda r: (-r["score"],r["path"]))[:max(1,min(limit,10))]
