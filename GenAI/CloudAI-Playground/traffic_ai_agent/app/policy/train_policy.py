#===--train_policy.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===--------------------------------------------------===//

import random
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from model import PolicyMLP

def teacher_delta(ns_q, ew_q, ns_f, ew_f, phase_is_ns, delta_max=10):
    # queue dominates, flow secondary
    delta = (ns_q - ew_q) * 12.0 + (ns_f - ew_f) * 4.0
    # if current phase already NS, reduce tendency to keep boosting it
    if phase_is_ns:
        delta *= 0.6
    # clip
    delta = max(-delta_max, min(delta_max, delta))
    return float(delta)

class SynthDataset(Dataset):
    def __init__(self, n=30000, delta_max=10):
        self.x = []
        self.y = []
        for _ in range(n):
            ns_q = random.random()
            ew_q = random.random()
            ns_f = random.random()
            ew_f = random.random()
            phase_is_ns = random.randint(0, 1)  # 1 NS green, 0 EW green
            x = [ns_q, ew_q, ns_f, ew_f, float(phase_is_ns), float(1 - phase_is_ns)]
            y = [teacher_delta(ns_q, ew_q, ns_f, ew_f, phase_is_ns, delta_max)]
            self.x.append(x)
            self.y.append(y)
        self.x = torch.tensor(self.x, dtype=torch.float32)
        self.y = torch.tensor(self.y, dtype=torch.float32)

    def __len__(self):
        return self.x.shape[0]
    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]

def main():
    delta_max = 10
    ds = SynthDataset(n=40000, delta_max=delta_max)
    dl = DataLoader(ds, batch_size=256, shuffle=True)

    model = PolicyMLP(in_dim=6, hidden=32)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    model.train()
    for epoch in range(10):
        total = 0.0
        for x, y in dl:
            pred = model(x)
            loss = loss_fn(pred, y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item()
        print(f"epoch {epoch+1:02d} loss={total/len(dl):.6f}")

    torch.save({
        "model_state": model.state_dict(),
        "in_dim": 6,
        "hidden": 32,
        "delta_max": delta_max
    }, "policy_model.pt")

    print("Saved policy_model.pt")

if __name__ == "__main__":
    main()