#===--context.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===---------------------------------------------===//

from typing import List, Dict


def _trend_label(delta: float) -> str:
    if delta > 0.15:
        return "increasing_fast"
    if delta > 0.05:
        return "increasing"
    if delta < -0.15:
        return "decreasing_fast"
    if delta < -0.05:
        return "decreasing"
    return "stable"


def build_context(points: List[dict]) -> Dict:
    """
    points: list of ingest payloads within sliding window.
    Each point format:
      {
        "lanes": {"NS":{"queue":..,"flow":..}, "EW":{...}},
        "events": [... optional ...],
        ...
      }
    """
    if not points:
        return {"trend": {"NS": "unknown", "EW": "unknown"}, "events": ["no_data"]}

    ns_q = [p["lanes"]["NS"]["queue"] for p in points]
    ew_q = [p["lanes"]["EW"]["queue"] for p in points]
    ns_f = [p["lanes"]["NS"]["flow"] for p in points]
    ew_f = [p["lanes"]["EW"]["flow"] for p in points]

    trend = {
        "NS": _trend_label(ns_q[-1] - ns_q[0]),
        "EW": _trend_label(ew_q[-1] - ew_q[0]),
    }

    events = []

    # Include replay-injected events if present.
    last_events = points[-1].get("events", [])
    if last_events:
        events.extend(last_events)

    # Congestion / underutilization hints
    if ns_q[-1] > 0.7 and trend["NS"].startswith("increasing"):
        events.append("NS_congestion_rising")
    if ew_q[-1] > 0.7 and trend["EW"].startswith("increasing"):
        events.append("EW_congestion_rising")
    if ns_q[-1] < 0.25:
        events.append("NS_underutilized_or_clear")
    if ew_q[-1] < 0.25:
        events.append("EW_underutilized_or_clear")

    # Flow hints
    if ns_f[-1] > 0.7:
        events.append("NS_flow_high")
    if ew_f[-1] > 0.7:
        events.append("EW_flow_high")

    if not events:
        events = ["no_significant_event"]

    return {"trend": trend, "events": events}