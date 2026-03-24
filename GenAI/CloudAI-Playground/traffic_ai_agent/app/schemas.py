#===--schemas.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===---------------------------------------------===//

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal

Phase = Literal["NS", "EW"]


class LaneState(BaseModel):
    queue: float = Field(ge=0.0, le=1.0)
    flow: float = Field(ge=0.0, le=1.0)


class IngestRequest(BaseModel):
    intersection_id: str
    timestamp: int
    lanes: Dict[Phase, LaneState]
    current_phase: Phase


class Constraints(BaseModel):
    green_min: int = 20
    green_max: int = 60
    delta_max: int = 10
    max_step_change: int = 5  # Max seconds change per step (anti-oscillation / smoothing)


class CurrentPlan(BaseModel):
    NS_green: int = 30
    EW_green: int = 30


class DecideRequest(BaseModel):
    intersection_id: str
    constraints: Constraints = Constraints()
    current_plan: CurrentPlan = CurrentPlan()


class Action(BaseModel):
    next_phase: Phase
    green_sec: int
    yellow_sec: int = 3
    all_red_sec: int = 1


class DecideResponse(BaseModel):
    decision_id: str
    intersection_id: str
    ts: int
    action: Action
    delta: Dict[str, int]
    reason_codes: List[str]
    confidence: float


class ExplainRequest(BaseModel):
    intersection_id: str
    origin: str = "A"
    destination: str = "C"
    user_query: str = "Explain the signal decision and recommended route for this step."


class RouteOption(BaseModel):
    route_id: Literal["direct", "via_B"]
    segments: List[str]
    cost: float


class ExplainResponse(BaseModel):
    explanation: str
    chosen_route: str
    routes: List[RouteOption]


class StateResponse(BaseModel):
    intersection_id: str
    latest: Optional[IngestRequest]
    window_seconds: int
    points: List[Dict]  # time-series points (simplified)
    trend: Dict[str, str]
    events: List[str]
    last_decisions: List[Dict]
``