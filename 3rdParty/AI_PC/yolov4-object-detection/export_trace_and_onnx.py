#===--export_trace_and_onnx.py-------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import torch
import numpy as np

from tool.darknet2pytorch import Darknet

# ----------------- user config -----------------
cfg_file = "/path-to-folder/yolov4.cfg"
weight_file = "/path-to-folder/yolov4.weights"

trace_out = "/path-to-folder/yolov4_traced.pt"
onnx_out = "/path-to-folder/yolov4.onnx"

inference_size = 832
opset_version = 11
use_cuda = False
# ------------------------------------------------

device = torch.device("cuda" if (use_cuda and torch.cuda.is_available()) else "cpu")
print("Device:", device)

# Build model architecture and load darknet weights directly (NO torch.load here)
print("Building model from cfg:", cfg_file)
model = Darknet(cfg_file)

print("Loading darknet weights:", weight_file)
model.load_weights(weight_file)

model.to(device)
model.eval()

# inspect raw output once
dummy = torch.randn(1, 3, inference_size, inference_size, device=device)
with torch.no_grad():
    raw_out = model(dummy)

# helper to print structure
def print_structure(obj, prefix=""):
    if isinstance(obj, torch.Tensor):
        print(f"{prefix}Tensor shape={tuple(obj.shape)} dtype={obj.dtype}")
    elif isinstance(obj, (list, tuple)):
        print(f"{prefix}{type(obj).__name__} len={len(obj)}")
        for i, e in enumerate(obj):
            print_structure(e, prefix + f"  [{i}]: ")
    elif isinstance(obj, dict):
        print(f"{prefix}dict keys={list(obj.keys())}")
        for k, v in obj.items():
            print_structure(v, prefix + f"  [{k}]: ")
    else:
        print(f"{prefix}Other: {type(obj)}")

print("\n=== Model raw output structure ===")
print_structure(raw_out)
print("==================================\n")

# flatten nested structures into list of tensors, preserving order
def flatten_tensors(obj):
    out = []
    if isinstance(obj, torch.Tensor):
        out.append(obj)
    elif isinstance(obj, (list, tuple)):
        for e in obj:
            out += flatten_tensors(e)
    elif isinstance(obj, dict):
        for k in sorted(obj.keys()):
            out += flatten_tensors(obj[k])
    return out

# normalize a tensor to shape [B, N, C]
def normalize_to_B_N_C(t, B):
    if not isinstance(t, torch.Tensor):
        t = torch.as_tensor(t, device=device)
    t = t.to(device)
    if t.dtype != torch.float32:
        t = t.float()

    d = t.dim()
    if d == 4:
        # two possibilities:
        # 1) shape like [B, N, 1, C] -> last dim small (C small, e.g., 4)
        # 2) shape like [B, C, H, W] -> conv feature map
        last = t.shape[-1]
        if last <= 16:
            B_, a, b, c = t.shape
            return t.reshape(B_, -1, c)
        else:
            B_, C, H, W = t.shape
            return t.permute(0, 2, 3, 1).contiguous().view(B_, -1, C)
    elif d == 3:
        return t if t.shape[0] == B else t.unsqueeze(0)
    elif d == 2:
        return t.unsqueeze(1) if t.shape[0] == B else t.unsqueeze(0)
    elif d == 1:
        return t.unsqueeze(0).unsqueeze(0)
    else:
        try:
            B_ = t.shape[0]
            rest = int(np.prod(t.shape[1:]))
            return t.view(B_, rest, 1)
        except Exception:
            return torch.zeros(B, 0, 1, device=device)

# wrapper module for export
class ExportWrapper(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        outs = self.model(x)
        tensors = flatten_tensors(outs)  # list of tensors
        B = x.shape[0]
        normed = [normalize_to_B_N_C(t, B) for t in tensors]

        if len(normed) == 0:
            return torch.zeros(B, 0, 1, device=x.device)

        # decide concat axis:
        N_vals = [int(t.shape[1]) for t in normed]
        # if all N same -> concat on channels (dim=2)
        if all(n == N_vals[0] for n in N_vals):
            out = torch.cat(normed, dim=2)  # [B, N, sumC]
        else:
            out = torch.cat(normed, dim=1)  # [B, total_preds, C_maybe_diff]
        return out

# instantiate wrapper and test
wrapper = ExportWrapper(model).to(device)
wrapper.eval()

with torch.no_grad():
    try:
        out_nontraced = wrapper(dummy)
        print("Wrapper (non-traced) output shape:", tuple(out_nontraced.shape))
    except Exception as e:
        print("ERROR running wrapper(dummy) BEFORE tracing:", e)
        raise

# Trace and save
print("Tracing to TorchScript (strict=False)...")
with torch.no_grad():
    traced = torch.jit.trace(wrapper, dummy, strict=False)
    try:
        out_traced = traced(dummy)
        print("Traced output shape:", tuple(out_traced.shape))
    except Exception as e:
        print("Warning: traced(dummy) raised:", e)

    traced.save(trace_out)
    print("Saved traced model to:", trace_out)

# Try ONNX export (from traced)
print("Attempting ONNX export to:", onnx_out)
try:
    torch.onnx.export(
        traced,
        dummy,
        onnx_out,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["images"],
        output_names=["detections"],
        dynamic_axes={"images": {0: "batch_size"}, "detections": {0: "batch_size"}},
        verbose=False,
    )
    print("ONNX export succeeded:", onnx_out)
except Exception as e:
    print("ONNX export failed with error:")
    print(e)

print("Done.")