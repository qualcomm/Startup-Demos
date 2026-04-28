#===--replay_sender_dual.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===--------------------------------------------------------===//

import json
import time
import random
import requests

API_BASE = "http://localhost:9000"
FILE_PATH = "data/replay_dual.jsonl"

SLEEP_SEC_PER_LINE = 0.5

# Increase these values if you want the difference to be visually obvious.
NOISE_SCALE = 0.06   # Small random noise (avoids perfectly periodic waves)
DRIFT_SCALE = 0.015  # Slow drift (baseline gradually changes)
EVENT_PROB = 0.12    # Event probability (0.10~0.20 is usually noticeable)
SHOCK_Q = 0.25       # Queue shock magnitude for events
SHOCK_F = 0.20       # Flow shock magnitude for events


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def post_ingest(payload: dict) -> None:
    r = requests.post(f"{API_BASE}/ingest", json=payload, timeout=10)
    r.raise_for_status()


def inject_noise_and_drift(payload: dict, drift: dict) -> dict:
    """Add noise + slow drift so the waveform is not perfectly periodic."""
    for d in ["NS", "EW"]:
        q = payload["lanes"][d]["queue"]
        f = payload["lanes"][d]["flow"]

        q = q + random.uniform(-NOISE_SCALE, NOISE_SCALE) + drift[d]["q"]
        f = f + random.uniform(-NOISE_SCALE, NOISE_SCALE) + drift[d]["f"]

        payload["lanes"][d]["queue"] = clamp01(q)
        payload["lanes"][d]["flow"] = clamp01(f)

    return payload


def maybe_inject_event(payload: dict) -> dict:
    """Random event injection so the LLM has something new to explain each time."""
    events = []

    if random.random() < EVENT_PROB:
        evt = random.choice(["ACCIDENT_NS", "ACCIDENT_EW", "RAIN", "PEAK_HOUR"])
        events.append(evt)

        if evt == "ACCIDENT_NS":
            payload["lanes"]["NS"]["queue"] = clamp01(payload["lanes"]["NS"]["queue"] + SHOCK_Q)
            payload["lanes"]["NS"]["flow"] = clamp01(payload["lanes"]["NS"]["flow"] - SHOCK_F)

        elif evt == "ACCIDENT_EW":
            payload["lanes"]["EW"]["queue"] = clamp01(payload["lanes"]["EW"]["queue"] + SHOCK_Q)
            payload["lanes"]["EW"]["flow"] = clamp01(payload["lanes"]["EW"]["flow"] - SHOCK_F)

        elif evt == "RAIN":
            payload["lanes"]["NS"]["flow"] = clamp01(payload["lanes"]["NS"]["flow"] * 0.75)
            payload["lanes"]["EW"]["flow"] = clamp01(payload["lanes"]["EW"]["flow"] * 0.75)

        elif evt == "PEAK_HOUR":
            payload["lanes"]["NS"]["queue"] = clamp01(payload["lanes"]["NS"]["queue"] + 0.18)
            payload["lanes"]["EW"]["queue"] = clamp01(payload["lanes"]["EW"]["queue"] + 0.18)

    payload["events"] = events
    return payload


def main() -> None:
    print(f"[replay] looping forever: {FILE_PATH} -> {API_BASE}/ingest")

    # Per-intersection slow drift state (helps produce visible trend changes)
    drift = {
        "A": {"NS": {"q": 0.0, "f": 0.0}, "EW": {"q": 0.0, "f": 0.0}},
        "B": {"NS": {"q": 0.0, "f": 0.0}, "EW": {"q": 0.0, "f": 0.0}},
    }

    last_A = None

    while True:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                payload = json.loads(line)
                iid = payload["intersection_id"]

                # Key point: overwrite timestamp to "now" so the sliding window does not purge everything.
                payload["timestamp"] = int(time.time())

                # Update drift occasionally so baseline shifts over time.
                if random.random() < 0.15:
                    for d in ["NS", "EW"]:
                        drift[iid][d]["q"] = clamp01(
                            drift[iid][d]["q"] + random.uniform(-DRIFT_SCALE, DRIFT_SCALE)
                        ) - 0.5
                        drift[iid][d]["f"] = clamp01(
                            drift[iid][d]["f"] + random.uniform(-DRIFT_SCALE, DRIFT_SCALE)
                        ) - 0.5

                    # Shrink drift into a small range.
                    for d in ["NS", "EW"]:
                        drift[iid][d]["q"] *= 0.02
                        drift[iid][d]["f"] *= 0.02

                payload = inject_noise_and_drift(payload, drift[iid])
                payload = maybe_inject_event(payload)

                # A -> B causal effect: if A's EW is congested, B's NS queue/flow becomes heavier.
                if iid == "B" and last_A:
                    if last_A["lanes"]["EW"]["queue"] > 0.75:
                        payload["lanes"]["NS"]["queue"] = clamp01(payload["lanes"]["NS"]["queue"] + 0.10)
                        payload["lanes"]["NS"]["flow"] = clamp01(payload["lanes"]["NS"]["flow"] + 0.08)

                post_ingest(payload)

                if iid == "A":
                    last_A = payload

                nsq = payload["lanes"]["NS"]["queue"]
                ewq = payload["lanes"]["EW"]["queue"]
                ph = payload["current_phase"]
                ev = payload.get("events", [])

                print(f"[ingest] {iid} phase={ph} NS_q={nsq:.2f} EW_q={ewq:.2f} events={ev}")
                time.sleep(SLEEP_SEC_PER_LINE)

        time.sleep(1.0)


if __name__ == "__main__":
    main()