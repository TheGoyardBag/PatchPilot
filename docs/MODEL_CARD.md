# Model card: pairwise patch ranker

**Intended use:** order candidate repairs for human inspection, after public tests.
**Not intended:** certify correctness, grant approval, detect every malicious patch,
or report real-world autonomous issue-resolution accuracy.

## Architecture and training

A 22 → 24 → 12 → 1 multilayer perceptron with ReLU activations is trained in PyTorch
on CPU. Training standardization parameters come from the training split only.
The objective combines pairwise softplus ranking loss within each task with a
smaller binary-cross-entropy term. AdamW, fixed seed 17, validation-only early
stopping, and explicit family-disjoint splits make the experiment reproducible.

Numeric weights and normalization arrays are exported to `artifacts/ranker.json`.
Runtime inference uses NumPy and is tested against PyTorch to absolute tolerance
1e-6. The JSON format avoids loading a pickle. Scores are sigmoid-transformed for
display but **are not calibrated probabilities**.

## Evaluation

See `reports/model_evaluation.json` for exact outputs and baselines. The current
held-out set has only six tasks. The neural, logistic, and static-only models all
rank an oracle-passing patch first on 6/6 tasks; the smallest-passing-patch selector
does so on 4/6, and a public-test-only selector with fixed tie order on 2/6.
There is no demonstrated neural-model advantage over logistic regression here.
The simpler baseline even has better candidate AUC on this corpus.

Metrics use only changed candidates passing all public tests as review-eligible.
Candidate AUC is computed over all authored proposals, while top-1 and reciprocal
rank use the eligible subset. “Correct” in reports means passing the available
oracle suite, not mathematical or security correctness.

An empirical task bootstrap is recorded, but it can return a degenerate interval
when all six tasks succeed. It must not be presented as evidence of certainty.

## Failure modes

- A partial fix can pass public tests and receive a high score.
- Small authored examples do not reflect natural model-generated diffs.
- Static patterns may dominate the learned decision.
- Tests and source share a Python process; hostile code could try to forge results.
- Proposed source may introduce semantic or security bugs absent from the tests.
- Model scores must never replace inspection or independently maintained tests.

## Extending the experiment

Collect real candidate sets with permission. Benchmark unseen repositories and
bug types, hold out future issues, keep test/label provenance, and compare the
learned model to strong simple selectors. Measure whether ranking changes the
human-reviewed repair success rate rather than only offline classification AUC.
