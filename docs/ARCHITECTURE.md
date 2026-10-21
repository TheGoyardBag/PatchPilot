# Architecture

## Request and review lifecycle

```text
local UI / Next.js UI
        | bearer-authenticated HTTP
        v
FastAPI -> SQLite queued job -> bounded local worker
                                  |
                         snapshot + code index
                                  |
                           baseline public tests
                                  |
                  +---------------+----------------+
                  |                                |
          authored-fixture replay        optional live Responses tool loop
                  |                       list/search/read/submit tools
                  +---------------+----------------+
                                  |
                  source hash + file policy + AST validation
                                  |
                  isolated candidate copy -> public tests
                                  |
                  public-test/static features -> trained ranker
                                  |
                      eligible first, descending ML score
                                  |
               await human review -> audited approval/rejection
                                  |
                         export approved unified diff
```

The original snapshot is never edited. Candidate workspaces are temporary and
removed after test execution. The SQLite record retains the diff, results,
features, event history, provider provenance, and human review.

## Execution boundaries

`trusted-demo` is a subprocess runner, **not a security sandbox**. The application
permits it only when every workspace file matches the authored fixture catalog.
Registered or model-generated source requires the Docker runner. There is no
automatic downgrade to host execution.

Docker receives a readonly workspace and a baked-in test harness. It runs
non-root, without network, with a readonly root filesystem, no capabilities,
no-new-privileges, a small `/tmp`, CPU/memory/PID limits, and a wall-clock/output
budget. The Docker client runs outside the code-execution container. Its socket,
provider key, and original repository are not mounted into that container.

These are meaningful restrictions, not a claim of complete containment against a
hostile kernel exploit. See the threat model before processing unknown code.

## What the model sees

The proposer can list allowed files, search text, read capped line ranges, and
submit full replacement contents for existing application `.py` files. It cannot
execute shell commands, modify tests/configuration, install packages, or publish
changes. The current version deliberately trades breadth for inspectability.

The ranker sees public test outcomes and static change features. Oracle results
are used by offline training/evaluation only. A candidate title such as “Focused
implementation” is displayed to a human but never passed to the ranker.

## Persistence and recovery

SQLite uses WAL and transactional review updates. Reviews include the job's
expected version; stale or duplicate approvals fail. On server restart, queued or
running jobs become `interrupted`. This is explicit failure handling, not durable
resumable execution. SSE publishes event records; the Next.js client uses polling.
The shipped application is single-process, single-user. A production deployment
would need a durable queue, object storage, external workers, and tenant isolation.

## Why not train a large code model?

The learned component scores competing repairs using observable evidence. That
makes the ML problem small enough to reproduce on a CPU and easy to evaluate
independently of a paid LLM. It is not a learned source-code generator. The MLP is
compared to logistic regression and nonlearned selectors rather than assumed to
be best because it is neural.

## Implemented extension points

- `OpenAIProvider`: strict tool schemas with the Responses API.
- `TestRunner`: explicit trusted-demo and Docker backends.
- `run_stages`: native stages or an optional real LangGraph adapter.
- `Repositories`: local snapshots; no network cloning.
- `fetch_issue`: a read-only GitHub issue importer.

## Documentation used

- Responses function calling: https://developers.openai.com/api/docs/guides/function-calling
- LangGraph StateGraph: https://docs.langchain.com/oss/python/langgraph/graph-api
- Docker resource constraints: https://docs.docker.com/engine/containers/resource_constraints/
- Docker default seccomp: https://docs.docker.com/engine/security/seccomp/
- GitHub issue API: https://docs.github.com/en/rest/issues/issues#get-an-issue
- SWE-bench evaluation context: https://www.swebench.com/SWE-bench/

The linked benchmark is contextual only. This repository does not bundle its
problems, run its harness, or report a SWE-bench score.
