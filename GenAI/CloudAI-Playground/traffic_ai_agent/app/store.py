#===--store.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-------------------------------------------===//

import time
from collections import deque
from typing import Dict, Optional, List

class InMemoryStore:
    def __init__(self, window_seconds: int = 600, max_decisions: int = 20):
        self.window_seconds = window_seconds
        self.latest = {}            # intersection_id -> latest ingest dict
        self.series = {}            # intersection_id -> deque(points)
        self.decisions = {}         # intersection_id -> deque(decisions)
        self.max_decisions = max_decisions

    def ingest(self, intersection_id: str, payload: dict):
        self.latest[intersection_id] = payload
        if intersection_id not in self.series:
            self.series[intersection_id] = deque()
        dq = self.series[intersection_id]
        dq.append(payload)

        # purge old
        cutoff = int(time.time()) - self.window_seconds
        while dq and dq[0]["timestamp"] < cutoff:
            dq.popleft()

    def get_latest(self, intersection_id: str) -> Optional[dict]:
        return self.latest.get(intersection_id)

    def get_series(self, intersection_id: str) -> List[dict]:
        dq = self.series.get(intersection_id)
        return list(dq) if dq else []

    def add_decision(self, intersection_id: str, decision: dict):
        if intersection_id not in self.decisions:
            self.decisions[intersection_id] = deque(maxlen=self.max_decisions)
        self.decisions[intersection_id].append(decision)

    def get_decisions(self, intersection_id: str) -> List[dict]:
        dq = self.decisions.get(intersection_id)
        return list(dq) if dq else []
