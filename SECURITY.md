# Security and safe-use boundaries

This is a **local, single-user development project**, not a public multi-tenant
code execution service. Do not expose it directly to the internet.

## Threat model and controls

| Risk | Implemented control | Residual limitation |
|---|---|---|
| Model requests shell/network access | Tool allowlist; no shell tool; fixed provider endpoint | Prompt instructions are not themselves a security boundary |
| Path traversal or symlink escape | Relative normalized paths, containment and symlink checks | Snapshots are assumed not to be concurrently modified by an attacker |
| Test deletion or harness edits | Only existing application Python files are editable; tests/config/harness protected | Source code can still try to interfere with the in-process test runtime |
| Stale patch | Original full-file SHA-256 must match | Human must still review semantic intent |
| Unsafe host execution | Host backend only accepts exact authored fixture contents | It is not a sandbox; repository owner controls the trusted catalog |
| Untrusted live proposal | Docker required; missing Docker fails closed | Docker shares a kernel; not equivalent to a hardened VM boundary |
| Resource exhaustion | Bounded files, tool calls, candidates, test time/output, queue, Docker resources | Overall job timer is a soft budget checked between operations |
| Credential exposure | Sensitive path exclusion, minimal subprocess environment, display masking, explicit source-sharing consent | Masking is not comprehensive DLP; remove secrets from source first |
| Unreviewed changes | Transactional versioned approval; exported diff only | Approval is not an attestation of semantic/security correctness |
| Browser injection | Text escaping / React escaping, bearer authentication, local hosts, CSP on bundled UI | No enterprise identity, TLS, tenant isolation, or hardened public deployment |

## Docker runner

Run it in a disposable VM or dedicated low-privilege host for code you do not
trust. It has no network, readonly mounts/root, non-root UID, no Linux
capabilities, no-new-privileges, PID/CPU/memory limits, and an ephemeral temp
filesystem. The code container never receives the Docker socket or model key.
Do not run the API container with a mounted Docker socket as a shortcut.

The caller needs access to the Docker daemon. That is a privileged capability
outside the sandbox; protect it accordingly. The test image only supports
standard-library Python projects. No dependency installation is attempted.

## Important honesty boundary

Application code and unittest execute in the same interpreter. A malicious patch
could monkeypatch test machinery or print a forged result. Source restrictions,
syntax validation, and a passing exit status do not eliminate that risk. Treat
test reports as evidence, not trusted attestations. A hardened service would use
stronger isolation, an out-of-process verifier, independently controlled tests,
and additional static/runtime monitoring.

No destructive remediation, git push, auto-merge, repository writeback, or remote
pull-request creation is implemented. Approved patches are only exported.

## Reporting

Report security problems privately through the repository owner's contact method
once published. Do not put secrets, real customer code, or exploit credentials in
public issues. No real security contact address is invented in this template.
