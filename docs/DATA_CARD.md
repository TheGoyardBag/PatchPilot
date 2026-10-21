# Data card: original repair-fixture corpus

## Source and permitted use

All 24 functions, issue descriptions, public tests, held-out oracle tests, and
144 candidate proposals were authored for this MIT-licensed repository. There is
no scraped private code and no third-party benchmark redistribution. Regenerate
with `scripts/make_benchmarks.py`.

Each task contains six proposals: a focused implementation, a commented alternate,
a partial adjustment, an example-specific lookup, an early constant return, and
the original source. Order is deterministically shuffled per task. Those labels
are for inspection only; the ranker does not receive proposal names or positions.
The oracle is included for reproducibility, but not copied into runtime agent
workspaces or sent through the API.

## Measurement

`scripts/build_dataset.py` constructs disposable workspaces and executes both
public and oracle suites for each candidate. It records 288 test processes and
888 individual test cases for the current corpus. A positive label means all
public and oracle cases passed; this is not a proof of full semantic correctness.
An unchanged proposal is ineligible for review even if tests pass.

`candidate_features.jsonl` includes measured labels plus metadata needed to split
and audit the data. `features()` receives only original/proposed source, public
results, and touched-file count. Labels, titles, identities, and families are not
features. File hashes tie the dataset to its corpus and the model to its training
data.

## Split

- Train: slicing, strings, collections, parsing, boundaries (15 tasks, 90 candidates).
- Validation: arithmetic (3 tasks, 18 candidates).
- Test: statistics, ordering (6 tasks, 36 candidates).

This keeps every candidate for a task and every task in a family together.
Validation determines early stopping. Test labels are only used to report final
metrics. The held-out test is small and was authored with knowledge of the task
mechanics; it is not equivalent to an independently collected real-world test set.

## Major limitations

Candidate structure is conspicuously artificial. Lookup-table patches use more
constants and string literals; that gives static features a useful but potentially
non-generalizable shortcut. The static-only baseline matching the full model is
a warning, not evidence that runtime verification is unnecessary. All examples
are small Python functions; real repositories, dependencies, concurrency, security
properties, and natural-language ambiguity are not represented adequately.

Before claiming realistic repair performance, collect naturally generated patches
from consented repositories, keep repository-level and temporal holdouts, evaluate
against independently maintained tests, and report failed/abstained cases.
