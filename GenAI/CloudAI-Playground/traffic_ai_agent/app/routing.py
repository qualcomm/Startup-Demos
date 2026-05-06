#===--routing.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===---------------------------------------------===//

from typing import Dict, Optional


def compute_edge_cost(base_time: float, queue: float, flow: float, wq=60.0, wf=20.0) -> float:
    return base_time + wq * queue + wf * flow


def two_route_compare(latest_A: dict, latest_B: Optional[dict] = None) -> Dict:
    lanesA = latest_A["lanes"]
    A_q = max(lanesA["NS"]["queue"], lanesA["EW"]["queue"])
    A_f = max(lanesA["NS"]["flow"], lanesA["EW"]["flow"])

    # If real B data exists, use it; otherwise use a synthesized fallback estimate.
    if latest_B:
        lanesB = latest_B["lanes"]
        B_q = max(lanesB["NS"]["queue"], lanesB["EW"]["queue"])
        B_f = max(lanesB["NS"]["flow"], lanesB["EW"]["flow"])
    else:
        # Fallback estimation (simple heuristic)
        B_q = min(1.0, 0.5 * lanesA["EW"]["queue"] + 0.2 * (1.0 - lanesA["NS"]["queue"]))
        B_f = min(1.0, 0.5 * lanesA["EW"]["flow"] + 0.2 * (1.0 - lanesA["NS"]["flow"]))

    base_AC = 30.0
    base_AB = 20.0
    base_BC = 25.0

    direct_cost = compute_edge_cost(base_AC, queue=A_q, flow=A_f)
    via_cost = compute_edge_cost(base_AB, queue=A_q, flow=A_f) + compute_edge_cost(base_BC, queue=B_q, flow=B_f)

    chosen = "via_B" if via_cost < direct_cost else "direct"

    return {
        "routes": [
            {"route_id": "direct", "segments": ["A-C"], "cost": round(direct_cost, 1)},
            {"route_id": "via_B", "segments": ["A-B", "B-C"], "cost": round(via_cost, 1)},
        ],
        "chosen": chosen,
    }
