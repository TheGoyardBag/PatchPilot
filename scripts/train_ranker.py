"""Pairwise patch ranking with family-disjoint train/validation/test splits.

Early stopping uses validation loss only. Test results are reported after training.
All features are public-test or static-diff features; oracle results provide labels.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
from torch import nn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from patchpilot.ml.features import FEATURE_NAMES
from patchpilot.ml.model import Ranker

SEED=17

def ranking_metrics(rows,scores):
    groups={}
    for i,r in enumerate(rows):groups.setdefault(r['task_id'],[]).append(i)
    successes=[];rr=[];public_only_errors=0
    for ids in groups.values():
        eligible=[i for i in ids if rows[i]['eligible']]
        order=sorted(eligible,key=lambda i:(-float(scores[i]),rows[i]['candidate_index']))
        successes.append(int(bool(order) and rows[order[0]]['label']==1))
        rank=next((j+1 for j,i in enumerate(order) if rows[i]['label']==1),None)
        rr.append(1/rank if rank else 0)
        public_only_errors+=sum(rows[i]['label']==0 for i in eligible)
    labels=[r['label'] for r in rows]
    return {'tasks':len(groups),'top1_correct':sum(successes),'top1_accuracy':float(np.mean(successes)),
            'mean_reciprocal_rank':float(np.mean(rr)),
            'candidate_auc':float(roc_auc_score(labels,scores)) if len(set(labels))>1 else None,
            'public_passing_but_oracle_failing_candidates':int(public_only_errors)}

def main():
    start=time.monotonic();torch.set_num_threads(1);torch.manual_seed(SEED);np.random.seed(SEED)
    torch.use_deterministic_algorithms(True)
    raw=(ROOT/'data/candidate_features.jsonl').read_bytes()
    rows=[json.loads(s) for s in raw.decode().splitlines()]
    by={s:[r for r in rows if r['split']==s] for s in ('train','validation','test')}
    families={s:{r['family'] for r in v} for s,v in by.items()}
    assert not families['train'] & (families['validation']|families['test'])
    assert not families['validation'] & families['test']
    arrays={s:np.asarray([r['features'] for r in v],dtype=np.float32) for s,v in by.items()}
    labels={s:np.asarray([r['label'] for r in v],dtype=np.float32) for s,v in by.items()}
    mean=arrays['train'].mean(axis=0);std=arrays['train'].std(axis=0);std[std<1e-6]=1
    tensors={s:torch.tensor((v-mean)/std) for s,v in arrays.items()}
    model=nn.Sequential(nn.Linear(len(FEATURE_NAMES),24),nn.ReLU(),nn.Linear(24,12),nn.ReLU(),nn.Linear(12,1))
    optimizer=torch.optim.AdamW(model.parameters(),lr=0.008,weight_decay=0.02)
    train_y=torch.tensor(labels['train']);val_y=torch.tensor(labels['validation'])
    positives=[];negatives=[]
    for task in sorted({r['task_id'] for r in by['train']}):
        ids=[i for i,r in enumerate(by['train']) if r['task_id']==task]
        for a in ids:
            for b in ids:
                if train_y[a]==1 and train_y[b]==0:positives.append(a);negatives.append(b)
    pos=torch.tensor(positives);neg=torch.tensor(negatives)
    best=float('inf');best_epoch=0;state=None;history=[]
    for epoch in range(1,401):
        model.train();optimizer.zero_grad();logits=model(tensors['train']).squeeze(-1)
        pairwise=torch.nn.functional.softplus(-(logits[pos]-logits[neg])).mean()
        loss=pairwise+0.3*nn.functional.binary_cross_entropy_with_logits(logits,train_y)
        loss.backward();optimizer.step();model.eval()
        with torch.no_grad():
            val_logits=model(tensors['validation']).squeeze(-1)
            val_loss=nn.functional.binary_cross_entropy_with_logits(val_logits,val_y).item()
        history.append({'epoch':epoch,'train_loss':float(loss.item()),'validation_bce':val_loss})
        if val_loss<best-1e-5:best=val_loss;best_epoch=epoch;state=copy.deepcopy(model.state_dict())
        if epoch-best_epoch>=40:break
    model.load_state_dict(state);model.eval()
    artifact={'format':'patchpilot-mlp-v1','feature_names':FEATURE_NAMES,'mean':mean.tolist(),'std':std.tolist(),
              'layers':[{'weight':layer.weight.detach().numpy().tolist(),'bias':layer.bias.detach().numpy().tolist()} for layer in model if isinstance(layer,nn.Linear)],
              'metadata':{'seed':SEED,'architecture':[len(FEATURE_NAMES),24,12,1],'best_epoch':best_epoch,
                          'dataset_sha256':hashlib.sha256(raw).hexdigest(),'training_candidates':len(by['train']),
                          'score_semantics':'Uncalibrated ranking score; not probability of repair correctness',
                          'provenance':'Original authored candidate patches, not natural LLM patch distribution'}}
    path=ROOT/'artifacts/ranker.json';path.write_text(json.dumps(artifact,indent=2)+'\n')
    ranker=Ranker(path)
    scores={s:ranker.score(x) for s,x in arrays.items()}
    with torch.no_grad():ref=torch.sigmoid(model(tensors['test']).squeeze(-1)).numpy()
    assert np.allclose(ref,scores['test'],atol=1e-6),'NumPy export must match trained network'
    lr=LogisticRegression(C=0.3,max_iter=500,random_state=SEED).fit((arrays['train']-mean)/std,labels['train'])
    # Ablation: train again without any public-test features, not just masking inference.
    no_test=LogisticRegression(C=0.3,max_iter=500,random_state=SEED).fit(((arrays['train']-mean)/std)[:,4:],labels['train'])
    report={'dataset':'24 original repair tasks / 144 authored candidates','seed':SEED,'split_unit':'Entire bug family',
            'selection_gate':'Only changed patches with all public tests passing are eligible',
            'early_stopping':'Validation BCE; test labels never used to select weights or threshold',
            'best_epoch':best_epoch,'epochs_run':len(history),'numpy_torch_max_abs_error':float(np.max(abs(ref-scores['test']))),
            'evaluations':{},'training_seconds':round(time.monotonic()-start,3),
            'limitations':['Small authored benchmark; no SWE-bench or live LLM resolution claims.',
                           'Authored overfit patches have recognizable artifacts; generalization is unproven.',
                           'Only six test tasks; point estimates have high uncertainty.',
                           'Full public test success is necessary, not sufficient, for semantic correctness.']}
    for s in by:
        x=arrays[s]
        report['evaluations'][s]={
            'pairwise_mlp':ranking_metrics(by[s],scores[s]),
            'logistic_regression':ranking_metrics(by[s],lr.predict_proba((x-mean)/std)[:,1]),
            'static_only_ablation':ranking_metrics(by[s],no_test.predict_proba(((x-mean)/std)[:,4:])[:,1]),
            'test_only_baseline':ranking_metrics(by[s],x[:,0]),
            'smallest_passing_patch':ranking_metrics(by[s],-x[:,4]-x[:,5])}
    # Task-level bootstrap uncertainty, not candidate-level resampling.
    test=by['test'];results=[]
    for task in sorted({r['task_id'] for r in test}):
        ids=[i for i,r in enumerate(test) if r['task_id']==task and r['eligible']]
        pick=max(ids,key=lambda i:float(scores['test'][i])) if ids else None
        results.append(int(pick is not None and test[pick]['label']==1))
    rng=np.random.default_rng(SEED);boot=rng.choice(results,size=(2000,len(results)),replace=True).mean(axis=1)
    report['test_top1_bootstrap_95_percent_interval']=np.quantile(boot,[.025,.975]).tolist()
    report['uncertainty_note']='A small empirical bootstrap can be degenerate when all tasks succeed. It does not establish a narrow population confidence interval.'
    (ROOT/'reports/model_evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'reports/training_history.json').write_text(json.dumps(history,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
