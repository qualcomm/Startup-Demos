#===--main.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===------------------------------------------===//

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import time

from .store import InMemoryStore
from .policy import decide_next
from .context import build_context
from .routing import two_route_compare
from .llm_agent import call_llm, call_llm_stream  # call_llm may be unused, kept for compatibility

app = FastAPI()
store = InMemoryStore(window_seconds=600)

# Auto-decision interval per intersection (seconds)
AUTO_DECIDE_INTERVAL_SEC = 4.0
_last_decide_ts = {"A": 0.0, "B": 0.0}

# Default constraints / plan for demo (so decisions exist even without pressing UI buttons)
DEFAULT_CONSTRAINTS = {"green_min": 20, "green_max": 60, "delta_max": 10, "max_step_change": 5}
DEFAULT_PLAN = {"NS_green": 30, "EW_green": 30, "yellow_sec": 3, "all_red_sec": 1}


# =======================
# Schemas
# =======================
class IngestRequest(BaseModel):
    intersection_id: str
    timestamp: int
    lanes: dict
    current_phase: str


class DecideRequest(BaseModel):
    intersection_id: str
    constraints: dict
    current_plan: dict


class ExplainRequest(BaseModel):
    intersection_id: str
    user_query: str
    origin: str
    destination: str


# =======================
# Closed-loop: apply previous decision to new state
# =======================
def apply_previous_decision(payload: dict, prev_decision: dict) -> dict:
    """
    Simulate how the previous signal decision impacts the next incoming state,
    so that charts and metrics reflect closed-loop behavior.

    prev_decision format (from policy/infer.py) example:
      {
        "next_phase": "NS" / "EW",
        "green_sec": ...,
        "delta": {"green_sec": ...},
        ...
      }
    """
    if not prev_decision:
        return payload

    phase = prev_decision.get("next_phase")
    delta = float(prev_decision.get("delta", {}).get("green_sec", 0))

    # delta > 0: more green for that phase → queue drops faster, flow increases
    # delta < 0: less green for that phase → queue drops slower, flow decreases
    def scale_queue(q, s): return max(0.0, min(1.0, q * s))
    def scale_flow(f, s): return max(0.0, min(1.0, f * s))

    if phase == "NS":
        payload["lanes"]["NS"]["queue"] = scale_queue(payload["lanes"]["NS"]["queue"], 1.0 - 0.02 * max(delta, 0))
        payload["lanes"]["NS"]["flow"] = scale_flow(payload["lanes"]["NS"]["flow"], 1.0 + 0.02 * max(delta, 0))
        payload["lanes"]["EW"]["queue"] = scale_queue(payload["lanes"]["EW"]["queue"], 1.0 + 0.01 * max(delta, 0))
        payload["lanes"]["EW"]["flow"] = scale_flow(payload["lanes"]["EW"]["flow"], 1.0 - 0.01 * max(delta, 0))

    elif phase == "EW":
        payload["lanes"]["EW"]["queue"] = scale_queue(payload["lanes"]["EW"]["queue"], 1.0 - 0.02 * max(delta, 0))
        payload["lanes"]["EW"]["flow"] = scale_flow(payload["lanes"]["EW"]["flow"], 1.0 + 0.02 * max(delta, 0))
        payload["lanes"]["NS"]["queue"] = scale_queue(payload["lanes"]["NS"]["queue"], 1.0 + 0.01 * max(delta, 0))
        payload["lanes"]["NS"]["flow"] = scale_flow(payload["lanes"]["NS"]["flow"], 1.0 - 0.01 * max(delta, 0))

    # Update current_phase so it looks like real control switching (for visualization)
    payload["current_phase"] = phase or payload["current_phase"]

    return payload


# =======================
# Basic Endpoints
# =======================
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ingest")
def ingest(req: IngestRequest):
    payload = req.dict()
    iid = payload["intersection_id"]

    # 1) Closed-loop: apply previous decision to this new state
    prev = store.get_decisions(iid)
    if prev:
        payload = apply_previous_decision(payload, prev[-1])

    # 2) Store the state
    store.ingest(iid, payload)

    # 3) Auto-decide: generate a decision every N seconds (otherwise recent_decisions stays empty)
    now = time.time()
    if now - _last_decide_ts.get(iid, 0.0) >= AUTO_DECIDE_INTERVAL_SEC:
        decision = decide_next(payload, DEFAULT_CONSTRAINTS, DEFAULT_PLAN)
        store.add_decision(iid, decision)
        _last_decide_ts[iid] = now

    return {"ok": True}


@app.get("/state")
def state(intersection_id: str):
    latest = store.get_latest(intersection_id)
    if not latest:
        raise HTTPException(404, "no data")

    points = store.get_series(intersection_id)
    decisions = store.get_decisions(intersection_id)
    ctx = build_context(points)

    return {
        "intersection_id": intersection_id,
        "latest": latest,
        "window_seconds": store.window_seconds,
        "points": points,
        "trend": ctx["trend"],
        "events": ctx["events"],
        "last_decisions": decisions,
    }


@app.post("/decide")
def decide(req: DecideRequest):
    latest = store.get_latest(req.intersection_id)
    if not latest:
        raise HTTPException(404, "no data")

    decision = decide_next(latest, req.constraints, req.current_plan)
    store.add_decision(req.intersection_id, decision)
    return decision


# =======================
# Explain (STREAMING ✅)
# =======================
@app.post("/explain_stream")
def explain_stream(req: ExplainRequest):
    latest = store.get_latest(req.intersection_id)
    if not latest:
        raise HTTPException(404, "no data")

    points = store.get_series(req.intersection_id)
    ctx = build_context(points)

    decisions = store.get_decisions(req.intersection_id)
    recent_decisions = decisions[-3:] if len(decisions) > 3 else decisions

    routing = two_route_compare(latest, store.get_latest("B"))

    llm_input = {
        "intersection_id": req.intersection_id,
        "time_window_seconds": store.window_seconds,
        "trend": ctx["trend"],
        "events": ctx["events"],
        "latest_state": {
            "current_phase": latest["current_phase"],
            "lanes": latest["lanes"],
        },
        "recent_decisions": recent_decisions,
        "routing": routing,
        "user_query": req.user_query,
        "origin": req.origin,
        "destination": req.destination,
    }

    def gen():
        meta = {"type": "meta", "routing": routing}
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        for token in call_llm_stream(llm_input):
            chunk = {"type": "token", "content": token}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")