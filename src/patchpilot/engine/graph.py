"""Optional orchestration adapter using the real LangGraph StateGraph API.

The default workflow needs no LangGraph dependency. This adapter runs the same
stage functions; it deliberately does not claim durable process recovery.
"""
from typing import TypedDict,Any,Callable

class State(TypedDict,total=False):
    payload: dict[str,Any]

def run_stages(stages: list[tuple[str,Callable]],payload: dict,backend: str="native") -> dict:
    if backend=="native":
        for _,fn in stages:payload=fn(payload)
        return payload
    if backend!="langgraph":raise ValueError("Unknown orchestration backend")
    try:from langgraph.graph import StateGraph,START,END
    except ImportError as exc:raise RuntimeError("Install .[graph] before selecting LangGraph") from exc
    graph=StateGraph(State)
    for name,fn in stages:
        def node(state,fn=fn):return {"payload":fn(state['payload'])}
        graph.add_node(name,node)
    for i,(name,_) in enumerate(stages):
        graph.add_edge(START if i==0 else stages[i-1][0],name)
    graph.add_edge(stages[-1][0],END)
    return graph.compile().invoke({'payload':payload})['payload']
