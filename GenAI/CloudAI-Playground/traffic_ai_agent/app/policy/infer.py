#===--infer.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-------------------------------------------===//

import os
import torch
from .model import PolicyMLP

# -------------------------------------------------
# Singleton policy inferencer (load once)
# -------------------------------------------------

_POLICY = None


def _get_policy() -> "PolicyInfer":
    global _POLICY
    if _POLICY is None:
        ckpt_path = os.path.join(
            os.path.dirname(__file__),
            "policy_model.pt",
        )
        _POLICY = PolicyInfer(ckpt_path)
    return _POLICY


# -------------------------------------------------
# Core inference class 
# -------------------------------------------------

class PolicyInfer:
    def __init__(self, ckpt_path: str):
        ckpt = torch.load(ckpt_path, map_location="cpu")
        self.delta_max = int(ckpt["delta_max"])
        self.model = PolicyMLP(
            in_dim=ckpt["in_dim"],
            hidden=ckpt["hidden"],
        )
        self.model.load_state_dict(ckpt["model_state"])
        self.model.eval()

    def predict_delta(
        self,
        ns_q: float,
        ew_q: float,
        ns_f: float,
        ew_f: float,
        current_phase: str,
    ) -> float:
        phase_is_ns = 1.0 if current_phase == "NS" else 0.0
        x = torch.tensor(
            [[ns_q, ew_q, ns_f, ew_f, phase_is_ns, 1.0 - phase_is_ns]],
            dtype=torch.float32,
        )
        with torch.no_grad():
            delta = float(self.model(x).item())

        return float(max(-self.delta_max, min(self.delta_max, delta)))


# -------------------------------------------------
# ✅ Public API for app.main (decide_next)
# -------------------------------------------------

def decide_next(latest: dict, constraints: dict, current_plan: dict) -> dict:
    """
    Service-level policy decision wrapper.
    This is what app.main imports and calls.
    """
    policy = _get_policy()

    lanes = latest["lanes"]
    ns_q = lanes["NS"]["queue"]
    ew_q = lanes["EW"]["queue"]
    ns_f = lanes["NS"]["flow"]
    ew_f = lanes["EW"]["flow"]
    current_phase = latest["current_phase"]

    delta = policy.predict_delta(
        ns_q=ns_q,
        ew_q=ew_q,
        ns_f=ns_f,
        ew_f=ew_f,
        current_phase=current_phase,
    )

    # apply delta to current plan
    base_green = current_plan.get(f"{current_phase}_green", 30)
    new_green = int(base_green + delta)

    # clamp with constraints
    green_min = constraints.get("green_min", 20)
    green_max = constraints.get("green_max", 60)
    new_green = max(green_min, min(green_max, new_green))

    decision = {
        "next_phase": current_phase,
        "green_sec": new_green,
        "yellow_sec": current_plan.get("yellow_sec", 3),
        "all_red_sec": current_plan.get("all_red_sec", 1),
        "delta": {
            "green_sec": new_green - base_green,
        },
        "reason_codes": ["POLICY_MODEL"],
        "confidence": 0.7,
    }

    return decision
