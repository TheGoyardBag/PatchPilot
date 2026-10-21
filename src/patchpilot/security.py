"""Path and patch policy. These checks are NOT a Python sandbox."""
from __future__ import annotations
import ast
import difflib
import hashlib
from pathlib import Path, PurePosixPath
import re
from .schemas import Proposal

class PolicyError(ValueError):
    pass

DENIED_PARTS = {".git", ".env", ".ssh", ".aws", "node_modules", ".venv", "venv", "__pycache__", ".patchpilot"}
DENIED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".db", ".pt", ".pkl"}
READ_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".yaml", ".yml", ".cfg", ".ini"}
SECRET_NAME = re.compile(r"(^|[._-])(credentials|secrets?|tokens?|id_rsa)([._-]|$)", re.I)

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def safe_path(root: Path, name: str, *, editable: bool = False) -> Path:
    if not name or "\\" in name or "\x00" in name or re.search(r"[\r\n\t]", name):
        raise PolicyError("Invalid path characters")
    raw = PurePosixPath(name)
    if raw.is_absolute() or any(p in {".", "..", ""} for p in name.split("/")):
        raise PolicyError("Only normalized relative paths are permitted")
    if any(p in DENIED_PARTS or p.startswith(".") for p in raw.parts):
        raise PolicyError("Hidden, dependency, or credential paths are not permitted")
    if ":" in name or any(SECRET_NAME.search(p) for p in raw.parts):
        raise PolicyError("Credential or drive paths are not permitted")
    root = root.resolve()
    target = root
    for part in raw.parts:
        target = target / part
        if target.is_symlink():
            raise PolicyError("Symlinks are not permitted")
    try:
        target.resolve().relative_to(root)
    except ValueError as exc:
        raise PolicyError("Path escapes workspace") from exc
    if not target.is_file():
        raise PolicyError("Only existing regular files may be accessed")
    if target.suffix.lower() in DENIED_SUFFIXES or target.suffix.lower() not in READ_SUFFIXES:
        raise PolicyError("Unsupported file type")
    if target.stat().st_size > 65536:
        raise PolicyError("File exceeds 64 KiB limit")
    if editable:
        if target.suffix != ".py" or any(p.lower() in {"tests", "test", "scripts", "sandbox"} for p in raw.parts):
            raise PolicyError("Only application Python source may be edited")
        if target.name.startswith("test_") or target.name.endswith("_test.py") or target.name in {"conftest.py", "setup.py", "harness.py"}:
            raise PolicyError("Tests, configuration, and execution harness are immutable")
    return target

def list_files(root: Path, limit: int = 400) -> list[str]:
    found = []
    # Do not recurse into sensitive or dependency trees at all.
    import os
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in DENIED_PARTS and not (Path(base)/d).is_symlink())
        for fn in sorted(files):
            name = (Path(base)/fn).relative_to(root).as_posix()
            try:
                safe_path(root, name)
            except PolicyError:
                continue
            found.append(name)
            if len(found) >= limit:
                return found
    return found

def validate_proposal(root: Path, proposal: Proposal) -> tuple[str, dict[str, str]]:
    seen = set()
    diff = []
    originals = {}
    total = 0
    for edit in proposal.edits:
        if edit.path in seen:
            raise PolicyError("Duplicate edit path")
        seen.add(edit.path)
        path = safe_path(root, edit.path, editable=True)
        before = path.read_text(encoding="utf-8")
        if sha(before) != edit.before_sha256:
            raise PolicyError("Stale source hash; read the current file before editing")
        if before == edit.content:
            raise PolicyError("No-op edit")
        if "\x00" in edit.content:
            raise PolicyError("NUL byte in source")
        try:
            ast.parse(edit.content)
        except (SyntaxError, RecursionError) as exc:
            raise PolicyError(f"Proposed source does not parse: {type(exc).__name__}") from exc
        lines = list(difflib.unified_diff(before.splitlines(True), edit.content.splitlines(True),
                                        fromfile=f"a/{edit.path}", tofile=f"b/{edit.path}"))
        total += sum(1 for l in lines if l[:1] in {"+", "-"} and not l.startswith(("+++", "---")))
        diff.extend(line if line.endswith("\n") else line+"\n\\ No newline at end of file\n" for line in lines)
        originals[edit.path] = before
    if total > 800 or sum(len(e.content.encode()) for e in proposal.edits) > 100000:
        raise PolicyError("Patch exceeds change budget")
    return "".join(diff), originals

def redact(text: str) -> str:
    # Best-effort display masking, not a DLP guarantee. Source sharing is explicit opt-in.
    text = re.sub(r"(?i)(api[_-]?key|password|secret|authorization)(\s*[:=]\s*)([^\s,;]+)", r"\1\2[REDACTED]", text)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,})\b", "[REDACTED]", text)
    return text
