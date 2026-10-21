# Validation report — PatchPilot 0.1.0

This report distinguishes source implementation from exercised integrations. It
is not a production readiness, security certification, or real-world repair score.

## Executed here

| Check | Observed result |
|---|---|
| Python automated tests | **128 passed, 2 skipped**, 0 failed |
| Python statement coverage | **92.67%** (872 / 941 statements) |
| JavaScript helper unit tests | **12 passed** |
| Chromium UI interaction checks | **13 passed**, 0 recorded JS errors |
| Python editable install | Built and installed successfully using already available dependencies |
| Python compile checks | Source and scripts compile successfully |
| TypeScript syntax | 4 files transpile with 0 syntax diagnostics; **not a dependency typecheck or Next build** |
| Dataset construction | 24 tasks, 144 authored candidate patches, **288 executed test processes / 888 test cases** |
| Neural model | Seeded CPU PyTorch training completed; numeric JSON artifact included |
| Export correctness | PyTorch / NumPy prediction max absolute difference: 5.96e-08 |
| Command-line workflow | Actual pagination fixture ran to review state with current trained artifact |

Coverage is Python **statement** coverage under `src/patchpilot`; the separate
isolated `harness.py` is omitted from coverage collection and exercised through
subprocess tests. Training scripts, JavaScript, and optional frontend are not
included in the Python coverage denominator. Some test cases deliberately mock
external provider protocols; unit-test count does not imply live integrations.

### Browser methodology

The managed Chromium instance blocks direct navigation to all URLs. The test
therefore injects the actual bundled HTML/CSS/JavaScript and connects its fetch
requests to a real loopback FastAPI process through a Python transport bridge.
It covers login behavior, the catalog, executing fixture tests, event content,
diff/test/feature views, rejection safeguards, human review, export, model metrics,
and a 390-pixel layout check. It uses buffered SSE and shimmed session storage.
It **does not validate ordinary browser networking, streaming timing, persistent
session storage, or the effective browser CSP**. It does not exercise Next.js.
The same script defaults to ordinary browser navigation on unrestricted machines.

The screenshot in `docs/dashboard.png` was captured from that real UI, not from
an image generator or a nonfunctional mockup.

## Deliberately not claimed

- The Docker command and safeguards are implemented and unit tested, but a Docker
  CLI/daemon was unavailable. The marked live Docker test is skipped.
- LangGraph is optional and was not installed; its real-adapter test is skipped.
- OpenAI Responses and GitHub issue adapters are tested with mocked HTTP
  exchanges. No paid model request or account interaction was made.
- npm/pip network registries were unavailable. The independent Next.js source
  was syntax checked only; dependency typecheck/build must run on your machine.
- GitHub Actions and image recipes are included but have not run remotely here.
- No cloud infrastructure was provisioned; no GitHub repository was created.
- Windows and other Python versions are CI targets, not locally executed claims.

## Interpreting the ML result

The held-out split contains only **six small authored tasks**. Neural, logistic,
and static-only ranking each selected a passing-oracle patch in all six. The
neural model **does not demonstrate an advantage over logistic regression**.
The fixed-tie public-test baseline selected 2/6; smallest-passing-patch selected
4/6. Authored candidate patterns make this distribution much easier than natural
agent-generated patches. Do not market these numbers as autonomous repair
accuracy, a SWE-bench result, or proof that a patch is safe.

## Evidence and reproduction

- `pytest.log` / `pytest.xml`: Python results and explicit skip reasons.
- `coverage.json`: machine-readable statement coverage.
- `javascript-tests.log`: Node test-runner output.
- `browser_validation.json`: exact browser scope and checks.
- `typescript_syntax.json`: exact syntax-only scope.
- `dataset_build.log`, `model_train.log`, `model_evaluation.json`,
  `training_history.json`: measured experiment outputs.
- `release_validation.json`: environment and summary.
- `archive_validation.json`: fresh extraction checks passed (Python, Node, compile, CLI repair).

Commands used:

```bash
python -m pip install -e . --no-deps --no-build-isolation
pytest -q --cov=patchpilot --cov-report=json:reports/coverage.json
node --test tests/web.test.mjs
python -m compileall -q src scripts
PATCHPILOT_BROWSER_BRIDGE=1 CHROMIUM_PATH=/usr/bin/chromium python scripts/browser_smoke.py
```

`--no-deps` was used only because the required libraries already existed in the
validation environment. Use the normal install in README on your machine.
