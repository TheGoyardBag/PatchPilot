# Portfolio and interview guide

Use wording only for the components you have run, understood, and extended.

## Accurate starting description

> Built a Python repair workbench with a FastAPI backend and interactive review UI,
> integrating bounded LLM tool-calling, disposable test workspaces, a PyTorch-trained
> patch-ranking model, and versioned human approval with unified-diff export.

When discussing the included experiment:

> Compared a pairwise neural ranker with logistic and heuristic baselines on 144
> authored candidate patches across 24 tasks, using bug-family-disjoint splits and
> separate evaluation tests; documented the small-data and synthetic-distribution
> limitations rather than claiming production or SWE-bench performance.

Do not claim a validated Next.js deployment, real-world autonomous repair rate,
SWE-bench score, live Docker sandbox assurance, or production users from this
initial delivery. The provider integration is implemented, but paid live calls
were not performed here. The offline proposer uses authored examples.

## Interview questions worth preparing for

- Why are test-passing patches not necessarily correct?
- Which features are available at selection time, and which would leak labels?
- Why split by bug family instead of candidate row?
- Does the neural model beat logistic regression? What does the ablation reveal?
- How are source hashes used to reject stale proposals?
- What can prompt injection influence, and what is enforced outside the prompt?
- Why is a Docker container not a perfect security boundary?
- How could untrusted Python interfere with the test harness?
- What happens if the server restarts or two reviews race?
- Which integration tests are mocked, and what live validation remains?

## High-value next work

Run live provider trials on consented small repositories. Add independently
maintained regression cases. Collect natural candidate patches, expand holdouts,
measure review effort, and compare the deployed model to the simpler baseline.
A useful contribution would be reducing false-positive approvals on partial fixes,
not merely making the dashboard more elaborate.
