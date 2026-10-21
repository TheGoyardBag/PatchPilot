# Live-mode setup and limitations

1. Review SECURITY.md. Use a dedicated disposable Linux VM for untrusted code.
2. Build `patchpilot-runner:local` from `sandbox/Dockerfile`.
3. Verify Docker with `PATCHPILOT_DOCKER_TESTS=1 pytest -q -m docker`.
4. Set `PATCHPILOT_RUNNER=docker`, `PATCHPILOT_ALLOW_EXTERNAL_LLM=1`,
   `OPENAI_API_KEY`, and an explicit tool-capable `OPENAI_MODEL` accessible to you.
5. Restart FastAPI. Source sharing still requires a per-request consent flag.
6. Try one small fixture, inspect the complete tool trace, then use a registered
   repository snapshot. Read every exported patch before applying it.

The proposer uses the Responses API with strict function schemas, no parallel tool
calls, and `store=false` at the application API level. This flag is not a blanket
promise about the provider's contractual retention or training policies; review
your provider account's actual settings and terms before sharing sensitive code.

Allowed tools: list files, search code, read a bounded file range, submit a patch
and receive public test results. No shell, package manager, Git write, or generic
HTTP tool is available to the model. The model can revise a proposal after test
feedback, within six candidate submissions, tool/turn/output/context budgets,
and per-call deadlines. A limit-exhausted run with tested proposals is visibly
marked. Other provider failures fail explicitly; no authored demo output is
substituted for a failed model call.

Costs depend on the model selected and the excerpts read. Token usage is recorded
when available. No dollar estimate or guaranteed latency is fabricated.

Live provider calls, the Docker image, and real GitHub network import were not
executed in the creation environment. Their protocols, policy checks, and failure
paths have unit tests. Validate them before describing live repair performance.
