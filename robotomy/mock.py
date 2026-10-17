"""Synthetic integration fixture; deliberately not a Lobotomy simulator.

Never use these outcomes to infer the real game's rules or player performance.
Only this adapter owns transitions; the executor does not choose a strategy.
"""
from copy import deepcopy


def initial_state():
    return {"tick": 0, "energy": 0, "worker": {"id": "fixture-worker", "health": 100}}


def observe(state):
    return {
        "environment": "synthetic_fixture", "real_game": False,
        "notice": "Integration fixture only. No Lobotomy gameplay or rules are represented.",
        **deepcopy(state),
        "actions": {
            "work": "Issue one synthetic work order.",
            "rest": "Issue one synthetic rest order.",
            "wait": "Advance one synthetic tick without a work order.",
        },
    }


def step(state, action):
    if action not in {"work", "rest", "wait"}:
        raise ValueError("Unknown fixture action")
    result = deepcopy(state)
    result["tick"] += 1
    if action == "work":
        if result["worker"]["health"] <= 0:
            raise ValueError("Synthetic worker is unavailable")
        result["energy"] += 10
        result["worker"]["health"] = max(0, result["worker"]["health"] - 20)
    elif action == "rest" and result["worker"]["health"] > 0:
        result["worker"]["health"] = min(100, result["worker"]["health"] + 15)
    return result
