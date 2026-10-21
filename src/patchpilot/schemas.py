from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Edit(StrictModel):
    path: str = Field(min_length=1, max_length=240)
    before_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content: str = Field(max_length=65536)

class Proposal(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=4000)
    edits: list[Edit] = Field(min_length=1, max_length=4)

class JobRequest(StrictModel):
    task_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    provider: str = Field(default="demo", pattern=r"^(demo|openai)$")
    issue: str | None = Field(default=None, max_length=10000)
    consent_external: bool = False

class ReviewRequest(StrictModel):
    candidate_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    decision: str = Field(pattern=r"^(approve|reject)$")
    note: str = Field(min_length=3, max_length=2000)
    version: int = Field(ge=0)

class TestResult(StrictModel):
    status: str
    tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_s: float = 0
    output: str = ""
    failures: list[dict] = Field(default_factory=list)
    runner: str
    exit_code: int | None = None

    @property
    def eligible(self) -> bool:
        return self.status == "passed" and self.tests > 0 and self.passed == self.tests

class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
