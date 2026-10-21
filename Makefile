.PHONY: setup run test dataset train frontend sandbox
setup:
	python scripts/setup.py
run:
	python -m patchpilot.cli serve
test:
	python -m pytest -q
	node --test tests/web.test.mjs
dataset:
	python scripts/make_benchmarks.py
	python scripts/build_dataset.py
train:
	python scripts/train_ranker.py
frontend:
	cd frontend && npm install && npm run typecheck && npm run build
sandbox:
	docker build -f sandbox/Dockerfile -t patchpilot-runner:local .
