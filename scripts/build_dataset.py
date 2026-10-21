"""Execute every authored candidate against public and separate oracle tests."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from patchpilot.benchmarks import Benchmarks
from patchpilot.engine.runner import TestRunner
from patchpilot.ml.features import features,FEATURE_NAMES

TRAIN={"slicing","strings","collections","parsing","boundaries"}
VAL={"arithmetic"}
TEST={"statistics","ordering"}

def main():
    p=argparse.ArgumentParser();p.add_argument("--workers",type=int,default=4);args=p.parse_args()
    catalog=Benchmarks(ROOT/"data/benchmarks.json")
    pairs=[(task,idx,c) for task in catalog.tasks.values() for idx,c in enumerate(task["candidates"])]
    started=time.monotonic()
    def execute(pair):
        task,idx,c=pair
        with tempfile.TemporaryDirectory(prefix="patchpilot-data-") as d:
            root=Path(d);catalog.materialize(task["id"],root,code=c["code"],oracle=True)
            assert catalog.verify(task["id"],root,oracle=True),"Never execute unverified code on host"
            runner=TestRunner()
            public=runner.run(root,"test_public.py",trusted_fixture=True)
            oracle=runner.run(root,"test_oracle.py",trusted_fixture=True)
        split="train" if task["family"] in TRAIN else "validation" if task["family"] in VAL else "test"
        return {"task_id":task["id"],"family":task["family"],"candidate_index":idx,"split":split,
                "features":features(task["source"],c["code"],public).tolist(),
                "label":int(public.eligible and oracle.eligible),
                "eligible":bool(public.eligible and task["source"]!=c["code"]),
                "public_passed":public.passed,"public_total":public.tests,
                "oracle_passed":oracle.passed,"oracle_total":oracle.tests,
                "candidate_sha256":hashlib.sha256(c["code"].encode()).hexdigest()}
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,8))) as pool:
        rows=list(pool.map(execute,pairs))
    text="".join(json.dumps(r,sort_keys=True)+"\n" for r in rows)
    (ROOT/"data/candidate_features.jsonl").write_text(text)
    manifest={"provenance":"Original authored repair fixtures and candidate patches; no LLM outputs",
              "tasks":len(catalog.tasks),"candidates":len(rows),"test_processes":2*len(rows),
              "executed_test_cases":sum(r['public_total']+r['oracle_total'] for r in rows),
              "feature_names":FEATURE_NAMES,"sha256":hashlib.sha256(text.encode()).hexdigest(),
              "corpus_sha256":hashlib.sha256((ROOT/"data/benchmarks.json").read_bytes()).hexdigest(),
              "split_families":{"train":sorted(TRAIN),"validation":sorted(VAL),"test":sorted(TEST)},
              "elapsed_s":round(time.monotonic()-started,2),"runner":"trusted-demo (not an untrusted-code sandbox)"}
    (ROOT/"data/dataset_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))

if __name__=="__main__":main()
