#===-----------------------vital_simulator.py--------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===------------------------------------------------------------------------===//

import time
import math
import random
from typing import Dict


class VitalSimulator:
    """
    Generates near-realistic vitals:
      - Heart rate varies smoothly + noise
      - SpO2 normally 95-99 with occasional dips
      - Temperature normally 36.5-37.5 with fever scenario
    """

    def __init__(self):
        self.t0 = time.time()
        self.base_hr = 78
        self.fever = False
        self.spo2_dip = False

    def set_scenario(self, fever: bool = False, spo2_dip: bool = False):
        self.fever = fever
        self.spo2_dip = spo2_dip

    def get_vitals(self) -> Dict[str, float]:
        t = time.time() - self.t0

        # HR: smooth variation (sinusoid) + small random noise
        hr_wave = 6 * math.sin(2 * math.pi * (t / 60.0))   # 1 minute cycle
        hr_noise = random.uniform(-2.0, 2.0)
        heart_rate = max(45, min(130, self.base_hr + hr_wave + hr_noise))

        # SpO2: normal 96-99, dip scenario 88-93 for sustained period
        if self.spo2_dip:
            spo2 = random.uniform(88.0, 93.0)
        else:
            spo2 = random.uniform(96.0, 99.0)

        # Temperature
        if self.fever:
            temperature = random.uniform(37.8, 39.2)
        else:
            temperature = random.uniform(36.5, 37.4)

        return {
            "heart_rate": round(heart_rate, 1),
            "spo2": round(spo2, 1),
            "temperature": round(temperature, 1),
            "timestamp": int(time.time()),
        }
