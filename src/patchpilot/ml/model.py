"""Safe JSON artifact + NumPy inference for a network trained with PyTorch."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from .features import FEATURE_NAMES

class Ranker:
    def __init__(self,path: Path):
        value=json.loads(path.read_text())
        if value.get("feature_names")!=FEATURE_NAMES or value.get("format")!="patchpilot-mlp-v1":
            raise ValueError("Incompatible ranker artifact")
        self.metadata=value["metadata"]
        self.mean=np.asarray(value["mean"],dtype=np.float32)
        self.std=np.asarray(value["std"],dtype=np.float32)
        if self.mean.shape!=(len(FEATURE_NAMES),) or self.std.shape!=self.mean.shape or np.any(self.std<=0):
            raise ValueError("Invalid normalization parameters")
        self.layers=[]
        width=len(FEATURE_NAMES)
        for layer in value["layers"]:
            w=np.asarray(layer["weight"],dtype=np.float32);b=np.asarray(layer["bias"],dtype=np.float32)
            if w.ndim!=2 or w.shape[1]!=width or b.shape!=(w.shape[0],) or not np.isfinite(w).all() or not np.isfinite(b).all():
                raise ValueError("Invalid network parameters")
            self.layers.append((w,b));width=w.shape[0]
        if not self.layers or width!=1: raise ValueError("Ranker must return one score")
    def score(self,x: np.ndarray) -> np.ndarray:
        x=np.asarray(x,dtype=np.float32)
        if x.shape[-1]!=len(FEATURE_NAMES) or not np.isfinite(x).all(): raise ValueError("Invalid feature vector")
        out=(x-self.mean)/self.std
        for i,(w,b) in enumerate(self.layers):
            out=out@w.T+b
            if i<len(self.layers)-1:out=np.maximum(out,0)
        # A bounded ranking score, NOT a calibrated probability of correctness.
        return (1/(1+np.exp(-np.clip(out[...,0],-30,30)))).astype(np.float32)
