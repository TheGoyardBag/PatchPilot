import hashlib
import json
import numpy as np
import pytest
from patchpilot.ml.features import features,FEATURE_NAMES
from patchpilot.ml.model import Ranker
from patchpilot.schemas import TestResult as Result

def test_features_are_finite():
    t=Result(status='passed',tests=3,passed=3,runner='test')
    x=features('def f(x): return x\n','def f(x): return x+1\n',t)
    assert x.shape==(len(FEATURE_NAMES),) and np.isfinite(x).all()
    assert x[3]==1

def test_empty_source_features():
    t=Result(status='runner_error',runner='test')
    assert np.isfinite(features('','def bad(:',t)).all()

def test_exported_ranker(root):
    r=Ranker(root/'artifacts/ranker.json')
    x=np.zeros((2,len(FEATURE_NAMES)),dtype=np.float32)
    assert r.score(x).shape==(2,) and np.all((r.score(x)>=0)&(r.score(x)<=1))

def test_ranker_rejects_nonfinite(root):
    r=Ranker(root/'artifacts/ranker.json')
    with pytest.raises(ValueError):r.score(np.full(len(FEATURE_NAMES),np.nan))

def test_bad_artifact(root,tmp_path):
    d=json.loads((root/'artifacts/ranker.json').read_text());d['feature_names']=[]
    p=tmp_path/'bad.json';p.write_text(json.dumps(d))
    with pytest.raises(ValueError):Ranker(p)

def test_artifact_matches_dataset(root):
    d=json.loads((root/'artifacts/ranker.json').read_text())
    assert d['metadata']['dataset_sha256']==hashlib.sha256((root/'data/candidate_features.jsonl').read_bytes()).hexdigest()

def test_group_splits_and_labels(root):
    rows=[json.loads(x) for x in (root/'data/candidate_features.jsonl').read_text().splitlines()]
    groups={s:{r['family'] for r in rows if r['split']==s} for s in ['train','validation','test']}
    assert not groups['train']&groups['test'] and not groups['train']&groups['validation'] and not groups['test']&groups['validation']
    assert len(rows)==144 and len({r['task_id'] for r in rows})==24
    for task in {r['task_id'] for r in rows}:assert any(r['label']==1 for r in rows if r['task_id']==task)
    assert all(len(r['features'])==len(FEATURE_NAMES) for r in rows)

def test_eval_has_comparisons(root):
    r=json.loads((root/'reports/model_evaluation.json').read_text())
    assert {'pairwise_mlp','logistic_regression','test_only_baseline','static_only_ablation'}<=r['evaluations']['test'].keys()
    assert r['evaluations']['test']['pairwise_mlp']['tasks']==6

def test_torch_numpy_export_equivalence(root):
    torch=pytest.importorskip('torch')
    a=json.loads((root/'artifacts/ranker.json').read_text())
    x=np.random.default_rng(3).normal(size=(9,len(FEATURE_NAMES))).astype(np.float32)
    t=torch.tensor((x-np.array(a['mean'],dtype=np.float32))/np.array(a['std'],dtype=np.float32))
    for i,l in enumerate(a['layers']):
        t=t@torch.tensor(l['weight'],dtype=torch.float32).T+torch.tensor(l['bias'],dtype=torch.float32)
        if i<len(a['layers'])-1:t=torch.relu(t)
    reference=torch.sigmoid(t[:,0]).numpy()
    np.testing.assert_allclose(reference,Ranker(root/'artifacts/ranker.json').score(x),atol=1e-6)
