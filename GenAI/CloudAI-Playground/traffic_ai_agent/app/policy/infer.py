#===--infer.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-------------------------------------------===//

import os
import numpy as np
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
            "policy_model.npz",   # Semgrep-safe checkpoint
        )
        _POLICY = PolicyInfer(ckpt_path)
    return _POLICY


def _load_checkpoint_npz(ckpt_path: str) -> dict:
    """
    Load checkpoint WITHOUT pickle (Semgrep-safe):
    - numpy .npz with allow_pickle=False
    - meta keys: __meta_in_dim, __meta_hidden, __meta_delta_max
    - weight keys: match model.state_dict() keys
    """
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(
            f"Policy checkpoint not found: {ckpt_path}\n"
            f"Please run train_policy.py to generate policy_model.npz."
        )

    data = np.load(ckpt_path, allow_pickle=False)

    def _get_meta_int(key: str) -> int:
        if key not in data:
            raise KeyError(f"Missing meta key in checkpoint: {key}")
        v = data[key]
        # stored as shape (1,) int array
        return int(v.reshape(-1)[0])

    in_dim = _get_meta_int("__meta_in_dim")
    hidden = _get_meta_int("__meta_hidden")
    delta_max = _get_meta_int("__meta_delta_max")

    # Collect weights
    weights = {}
    for k in data.files:
        if k.startswith("__meta_"):
            continue
        arr = data[k]
        # Convert numpy -> torch tensor (CPU)
        weights[k] = torch.from_numpy(arr)

    return {
        "in_dim": in_dim,
        "hidden": hidden,
        "delta_max": delta_max,
        "model_state": weights,
    }


# -------------------------------------------------
# Core inference class
# -------------------------------------------------
class PolicyInfer:
    def __init__(self, ckpt_path: str):
        ckpt = _load_checkpoint_npz(ckpt_path)
        self.delta_max = int(ckpt["delta_max"])
        self.model = PolicyMLP(
            in_dim=int(ckpt["in_dim"]),
            hidden=int(ckpt["hidden"]),
        )

        # load_state_dict expects tensors with correct dtypes/shapes
        # If training saved float32 (default), this will match.
        self.model.load_state_dict(ckpt["model_state"], strict=True)
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