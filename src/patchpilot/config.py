"""Local-first configuration. Network providers and untrusted execution are opt-in."""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Source checkout is the supported distribution: artifacts/data live beside pyproject.toml.

@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    state: Path = ROOT / ".patchpilot"
    token: str = ""
    runner: str = "trusted-demo"
    model: str = ""
    api_key: str = ""
    allow_external_llm: bool = False
    max_jobs: int = 2
    max_tool_calls: int = 16
    max_llm_turns: int = 10
    max_candidates: int = 4
    job_timeout_s: int = 180
    test_timeout_s: int = 15
    runner_image: str = "patchpilot-runner:local"

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.environ.get("PATCHPILOT_ROOT", str(ROOT))).resolve()
        state = Path(os.environ.get("PATCHPILOT_STATE", str(root / ".patchpilot"))).resolve()
        token = os.environ.get("PATCHPILOT_TOKEN", "")
        if not token and (state / "token").is_file():
            token = (state / "token").read_text().strip()
        runner = os.environ.get("PATCHPILOT_RUNNER", "trusted-demo")
        if runner not in {"trusted-demo", "docker"}:
            raise ValueError("PATCHPILOT_RUNNER must be trusted-demo or docker")
        return cls(root=root, state=state, token=token, runner=runner,
                   model=os.environ.get("OPENAI_MODEL", ""),
                   api_key=os.environ.get("OPENAI_API_KEY", ""),
                   allow_external_llm=os.environ.get("PATCHPILOT_ALLOW_EXTERNAL_LLM") == "1",
                   runner_image=os.environ.get("PATCHPILOT_RUNNER_IMAGE", "patchpilot-runner:local"))
