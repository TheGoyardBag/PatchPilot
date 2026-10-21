"""Selection-time features only: public tests and source-change structure.

No oracle result, candidate title, task ID, split, or family is accepted here.
"""
from __future__ import annotations
import ast
from collections import Counter
import difflib
import math
import re
import numpy as np
from ..schemas import TestResult

FEATURE_NAMES=["public_pass_fraction","public_error_fraction","public_test_count_log",
               "public_complete_pass","added_lines_log","deleted_lines_log","changed_fraction",
               "ast_nodes_log","ast_node_delta","constant_fraction","string_literal_chars_log",
               "numeric_literals_log","dict_entries_log","bare_constant_returns",
               "branches_log","loops_log","calls_log","repr_calls","functions_removed",
               "token_overlap","source_changed","file_count_log"]

def facts(source: str) -> dict:
    try: tree=ast.parse(source)
    except (SyntaxError,RecursionError): return {"nodes":1,"syntax":False}
    nodes=list(ast.walk(tree)); c=Counter(type(n).__name__ for n in nodes)
    return {"syntax":True,"nodes":len(nodes),"constants":c["Constant"],
            "string_chars":sum(len(n.value) for n in nodes if isinstance(n,ast.Constant) and isinstance(n.value,str)),
            "numeric":sum(isinstance(n,ast.Constant) and type(n.value) in (int,float) for n in nodes),
            "dict_entries":sum(len(n.keys) for n in nodes if isinstance(n,ast.Dict)),
            "bare_returns":sum(isinstance(n,ast.Return) and isinstance(n.value,ast.Constant) for n in nodes),
            "branches":c["If"]+c["IfExp"],"loops":c["For"]+c["While"]+c["comprehension"],
            "calls":c["Call"],"repr_calls":sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="repr" for n in nodes),
            "functions":c["FunctionDef"]+c["AsyncFunctionDef"]}

def features(before: str,after: str,tests: TestResult,file_count: int=1) -> np.ndarray:
    old,new=facts(before),facts(after)
    changes=list(difflib.ndiff(before.splitlines(),after.splitlines()))
    added=sum(l.startswith("+ ") for l in changes);deleted=sum(l.startswith("- ") for l in changes)
    a=set(re.findall(r"[A-Za-z_]\w*",before));b=set(re.findall(r"[A-Za-z_]\w*",after))
    n=max(1,tests.tests);nodes=max(1,new.get("nodes",1))
    vals=[tests.passed/n,tests.errors/n,math.log1p(tests.tests),float(tests.eligible),
          math.log1p(added),math.log1p(deleted),(added+deleted)/max(1,len(before.splitlines())),
          math.log1p(nodes),(nodes-old["nodes"])/max(1,old["nodes"]),new.get("constants",0)/nodes,
          math.log1p(new.get("string_chars",0)),math.log1p(new.get("numeric",0)),
          math.log1p(new.get("dict_entries",0)),new.get("bare_returns",0),
          math.log1p(new.get("branches",0)),math.log1p(new.get("loops",0)),math.log1p(new.get("calls",0)),
          new.get("repr_calls",0),max(0,old.get("functions",0)-new.get("functions",0)),
          len(a&b)/max(1,len(a|b)),float(before!=after),math.log1p(file_count)]
    return np.asarray(vals,dtype=np.float32)
