# Start here

1. Read the mode distinction in README: offline authored candidates vs live LLM
   generation. Both use real test execution and the learned ranker.
2. Create a virtual environment and run `python -m pip install -e ".[dev]"`.
3. Run `python scripts/setup.py`, then `python -m patchpilot.cli serve`.
4. Open http://127.0.0.1:8000 and enter your local token.
5. Run **Pagination drops the last item**. Review the candidate diffs, public test
   logs, and ranking features. Passing public tests does not prove correctness.
6. Write a review note, approve a passing candidate, and export its diff.
7. Read `reports/VALIDATION.md`, `docs/MODEL_CARD.md`, and `docs/ARCHITECTURE.md`.
8. Run the tests yourself, then follow `docs/PUBLISH.md` to publish the source.

Do not upload `.patchpilot/`, `.env`, personal repositories, credentials,
`node_modules/`, `.venv/`, or private source. Nothing in this delivery has been
pushed to GitHub or deployed to a cloud account.
