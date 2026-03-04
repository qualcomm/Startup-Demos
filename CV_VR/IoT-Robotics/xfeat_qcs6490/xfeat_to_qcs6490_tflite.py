#===-- xfeat_to_qcs6490_tflite.py ----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import zipfile
import argparse
from pathlib import Path
from typing import List
import numpy as np
from PIL import Image

import torch
import torch.nn as nn

import onnx
from onnx import helper, TensorProto
import onnxruntime as ort

import qai_hub as hub  # Qualcomm AI Hub Python SDK


# ------------------------------
# Logger
# ------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


# ------------------------------
# AI Hub model saving (SDK compatibility)
# ------------------------------
def save_hub_model(model_obj, path: str) -> str:
    """
    Persist an AI Hub model to the filesystem using multiple strategies to handle SDK version differences:
    - Try in order: .save(path), .download(path), .download_to(path), hub.save_model(...)
    - If bytes/bytearray, write directly to file
    - If a string or PathLike pointing to an existing file, copy to the destination
    """
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # bytes-like
    if isinstance(model_obj, (bytes, bytearray)):
        dst.write_bytes(model_obj)
        return str(dst)

    # direct path to an existing file
    if isinstance(model_obj, (str, os.PathLike)):
        src = Path(model_obj)
        if src.exists():
            shutil.copyfile(src, dst)
            return str(dst)

    # common instance methods
    for method_name in ("save", "download", "download_to", "write_to"):
        m = getattr(model_obj, method_name, None)
        if callable(m):
            try:
                m(str(dst))
                return str(dst)
            except Exception:
                pass

    # SDK-level helper
    try:
        if hasattr(hub, "save_model"):
            hub.save_model(model_obj, str(dst))
            return str(dst)
    except Exception:
        pass

    # some SDK variants may expose bytes in blob/content/data fields
    for attr in ("blob", "content", "data"):
        b = getattr(model_obj, attr, None)
        if b is not None and isinstance(b, (bytes, bytearray)):
            dst.write_bytes(b)
            return str(dst)

    raise RuntimeError("Unable to save AI Hub model: no usable saving method/field found.")


# ------------------------------
# Calibration data utilities
# ------------------------------
def load_calib_images(calib_dir: str, H: int, W: int, max_images: int = 64) -> np.ndarray:
    p = Path(calib_dir)
    imgs: List[np.ndarray] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        for f in sorted(p.glob(ext)):
            img = Image.open(f).convert("RGB").resize((W, H))
            arr = np.asarray(img).astype(np.float32) / 255.0  # [H,W,3]
            arr = np.transpose(arr, (2, 0, 1))               # [3,H,W]
            imgs.append(arr)
            if len(imgs) >= max_images:
                break
        if len(imgs) >= max_images:
            break
    if not imgs:
        raise FileNotFoundError(f"Calibration image directory is empty: {calib_dir}")
    batch = np.stack(imgs, axis=0)  # [N,3,H,W]
    log(f"[Calib] Loaded {len(batch)} images from {calib_dir}")
    return batch


def _rand_img(H: int, W: int) -> np.ndarray:
    """Synthesize natural-image-like samples (low-frequency gradient + noise + stripes) to better match real distributions."""
    y = np.linspace(0, 1, H, dtype=np.float32)
    x = np.linspace(0, 1, W, dtype=np.float32)
    xv, yv = np.meshgrid(x, y)

    base = 0.6 * xv + 0.4 * yv
    noise = np.random.randn(H, W).astype(np.float32)
    noise = (noise - noise.min()) / (noise.max() - noise.min() + 1e-6)
    noise = 0.15 * noise
    stripes = (np.sin(2 * np.pi * (xv * 4 + np.random.rand() * 2)) * 0.5 + 0.5).astype(np.float32)
    mix = 0.6 * base + 0.2 * noise + 0.2 * stripes

    c0 = mix
    c1 = 0.7 * mix + 0.3 * (1 - mix)
    c2 = np.clip(mix + 0.1 * np.random.randn(H, W).astype(np.float32), 0, 1)
    img = np.stack([c0, c1, c2], axis=0)  # [3,H,W]
    return np.clip(img, 0.0, 1.0).astype(np.float32)


def build_synthetic_calib(H: int, W: int, count: int = 64) -> np.ndarray:
    arrs = [_rand_img(H, W) for _ in range(count)]
    batch = np.stack(arrs, axis=0)
    log(f"[Calib] Built synthetic calibration set: {batch.shape}")
    return batch


# ------------------------------
# Build XFeat via torch.hub (using official pretrained weights)
# ------------------------------
def build_xfeat_via_hub():
    # use entry defined in hubconf.py: 'XFeat'
    model = torch.hub.load('verlab/accelerated_features', 'XFeat',
                           pretrained=True, source='github')
    model.eval()
    return model


# ------------------------------
# Replace InstanceNorm2d with decomposed module (PyTorch layer, before TorchScript)
# ------------------------------
class InstanceNormDecomposed(nn.Module):
    """
    Re-implement InstanceNorm2d using primitive ops to avoid exporting onnx::InstanceNormalization.
    """
    def __init__(self, num_channels, eps=1e-5, affine=True):
        super().__init__()
        self.eps = float(eps)
        self.affine = bool(affine)
        if self.affine:
            self.weight = nn.Parameter(torch.ones(num_channels))
            self.bias = nn.Parameter(torch.zeros(num_channels))
        else:
            self.register_parameter("weight", None)
            self.register_parameter("bias", None)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mean = x.mean(dim=(2, 3), keepdim=True)
        var = ((x - mean) ** 2).mean(dim=(2, 3), keepdim=True)
        xhat = (x - mean) / torch.sqrt(var + self.eps)
        if self.affine:
            w = self.weight.view(1, -1, 1, 1)
            b = self.bias.view(1, -1, 1, 1)
            return xhat * w + b
        return xhat


def replace_instancenorm2d(module: nn.Module) -> None:
    """
    Recursively replace nn.InstanceNorm2d with InstanceNormDecomposed.
    Must be called before TorchScript tracing.
    """
    for name, child in module.named_children():
        if isinstance(child, nn.InstanceNorm2d):
            repl = InstanceNormDecomposed(child.num_features, eps=child.eps, affine=child.affine)
            if child.affine:
                with torch.no_grad():
                    repl.weight.copy_(child.weight)
                    repl.bias.copy_(child.bias)
            setattr(module, name, repl)
        else:
            replace_instancenorm2d(child)


# ------------------------------
# Export wrapper (convert variable-length keypoints/desc into fixed tensors)
# ------------------------------
class XFeatExportDense(nn.Module):
    """
    Emit dense maps with fixed tensors; no top-k / variable-length / keypoint selection:
      - heatmap:     [1, 1, H_out, W_out]      (if head returns [1,H,W], auto expand to 4D)
      - descriptors: [1, D, H_out, W_out]
      - reliability: [1, 1, H_out, W_out] (if absent, return an all-ones tensor or use heat as placeholder)
    """
    def __init__(self, xf: nn.Module, use_zero_reliability_fallback: bool = True):
        super().__init__()
        self.xf = xf
        self.use_zero_reliability_fallback = use_zero_reliability_fallback

    @staticmethod
    def _to_4d(t: torch.Tensor) -> torch.Tensor:
        # Convert 2D/3D/4D into [N=1, C, H, W]
        if t.dim() == 4:
            return t
        if t.dim() == 3:
            return t.unsqueeze(0)
        if t.dim() == 2:
            return t.unsqueeze(0).unsqueeze(0)
        raise RuntimeError(f"Unsupported dense output tensor rank: dim={t.dim()}, shape={tuple(t.shape)}")

    @staticmethod
    def _pick_first_existing(d: dict, keys: List[str]):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    def forward(self, x: torch.Tensor):
        # Call the core network directly, not detectAndCompute / detectAndComputeDense
        core = getattr(self.xf, "net", None)
        if core is None or not isinstance(core, nn.Module):
            raise RuntimeError("No 'net' module found inside XFeat; cannot emit dense maps.")

        out = core(x)  # expect dict or (heat, desc, reli)

        # Parse outputs (tolerate variant key names)
        if isinstance(out, dict):
            heat = self._pick_first_existing(out, ["heatmap", "K", "scores", "heat"])
            desc = self._pick_first_existing(out, ["descriptors", "F", "desc"])
            reli = self._pick_first_existing(out, ["reliability", "R", "conf"])
        elif isinstance(out, (tuple, list)):
            if len(out) < 2:
                raise RuntimeError("xfeat.net(x) returned too few outputs; need at least heat and desc.")
            heat, desc = out[0], out[1]
            reli = out[2] if len(out) >= 3 else None
        else:
            raise RuntimeError("Unknown output type from xfeat.net(x); expected dict or (heat, desc, reli).")

        if heat is None or desc is None:
            raise RuntimeError("Cannot infer heat/desc from xfeat.net(x); print model output keys/shapes and adjust the wrapper.")

        # Normalize shapes to 4D
        heat = self._to_4d(heat).contiguous()
        desc = self._to_4d(desc).contiguous()
        if reli is not None:
            reli = self._to_4d(reli).contiguous()
        else:
            if self.use_zero_reliability_fallback:
                N, _, H, W = heat.shape
                reli = torch.ones((N, 1, H, W), dtype=heat.dtype, device=heat.device)
            else:
                reli = heat  # use heat as placeholder

        # Slice unconditionally to remove trace-time conditional branches
        heat = heat[:1]
        desc = desc[:1]
        reli = reli[:1]

        return heat, desc, reli

# ------------------------------
# TorchScript trace
# ------------------------------
def to_torchscript(wrapper: nn.Module, input_shape=(1, 3, 480, 640)) -> torch.jit.ScriptModule:
    dummy = torch.randn(*input_shape)
    with torch.no_grad():
        ts = torch.jit.trace(wrapper, dummy)
    ts.eval()
    return ts


# ------------------------------
# AI Hub compile: TorchScript -> ONNX (cloud)
# Returns (hub.Model or None, error_message or "")
# ------------------------------
def aihub_compile_ts_to_onnx(ts_model, device_name: str, input_shape, job_name="xfeat_compile_to_onnx"):
    try:
        device = hub.Device(device_name)
        job = hub.submit_compile_job(
            model=ts_model,
            device=device,
            input_specs=dict(images=(input_shape, "float32")),
            options="--target_runtime onnx"
        )
        # Safely access job id/url to avoid SDK variant issues
        job_id = getattr(job, "id", None) or getattr(job, "job_id", None)
        job_url = getattr(job, "url", None)
        if job_id:
            log(f"[AI Hub] Scheduled compile job ({job_id}). Waiting...")
        elif job_url:
            log(f"[AI Hub] Scheduled compile job. See: {job_url}  (Waiting...)")
        else:
            log("[AI Hub] Scheduled compile job. Waiting...")

        job.wait()
        model = job.get_target_model()
        if model is None:
            return None, "AI Hub compile returned no model (failed remotely)."
        log("[AI Hub] Compile job completed.")
        return model, "", job_id
    except Exception as e:
        return None, f"AI Hub compile failed: {e}", job_id

# ------------------------------
# unzip onnx model file
# ------------------------------
def unzip_onnx_model(zip_path: str, job_id: str, target_path: str):
    # Check if a zip exists and unzip it
    zip_path = Path(zip_path + ".onnx.zip")
    onnx_raw_path = Path(target_path) / "xfeat_from_aihub.onnx"
    data_raw_path = Path(target_path) / "model.data"

    if zip_path.exists():
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_path)
        print(f"[AI Hub] Unzipped: {zip_path}")

        # Extracted folder is named model.onnx
        extracted_dir = Path(target_path) / f"job_{job_id}_optimized_onnx"
        model_onnx_path = extracted_dir / "model.onnx"
        model_data_path = extracted_dir / "model.data"

        # Move and rename model.onnx
        if model_onnx_path.exists():
            shutil.move(str(model_onnx_path), str(onnx_raw_path))
            print(f"[AI Hub] model.onnx moved and renamed to: {onnx_raw_path}")
        else:
            print(f"[Warn] model.onnx not found at {extracted_dir}")

        # Move model.data
        if model_data_path.exists():
            shutil.move(str(model_data_path), str(data_raw_path))
            print(f"[AI Hub] model.data moved to: {data_raw_path}")
        else:
            print(f"[Warn] model.data not found at {extracted_dir}")
    else:
        print(f"[Warn] Expected zip file does not exist: {zip_path}")


# ------------------------------
# ONNX fixes: decompose InstanceNormalization & remove trivial Unsqueeze
# ------------------------------
def decompose_instance_norm(onnx_in_path: str, onnx_out_path: str, eps_default: float = 1e-5) -> str:
    """
    Decompose onnx::InstanceNormalization into primitive ops for runtimes (e.g., TFLite) that lack support.
    """
    m = onnx.load(onnx_in_path)
    g = m.graph
    mutated = False
    new_nodes = []
    uniq = 0
    for n in g.node:
        if n.op_type == "InstanceNormalization":
            mutated = True
            uniq += 1
            x, scale, bias = n.input
            y = n.output[0]
            eps_attr = next((a for a in n.attribute if a.name == "epsilon"), None)
            eps = eps_attr.f if eps_attr else eps_default

            # generate unique constant/intermediate names to avoid collisions when names are empty
            axes = helper.make_node("Constant", inputs=[], outputs=[f"IN_axes_{uniq}"],
                                    value=helper.make_tensor("", TensorProto.INT64, [2], [2, 3]))
            shp = helper.make_node("Constant", inputs=[], outputs=[f"IN_shp_{uniq}"],
                                   value=helper.make_tensor("", TensorProto.INT64, [4], [1, -1, 1, 1]))
            epsC = helper.make_node("Constant", inputs=[], outputs=[f"IN_eps_{uniq}"],
                                    value=helper.make_tensor("", TensorProto.FLOAT, [1], [eps]))

            mean = helper.make_node("ReduceMean", inputs=[x, axes.output[0]], outputs=[f"IN_mean_{uniq}"], keepdims=1)
            sub = helper.make_node("Sub", inputs=[x, mean.output[0]], outputs=[f"IN_xmu_{uniq}"])
            sqr = helper.make_node("Mul", inputs=[sub.output[0], sub.output[0]], outputs=[f"IN_sq_{uniq}"])
            var = helper.make_node("ReduceMean", inputs=[sqr.output[0], axes.output[0]], outputs=[f"IN_var_{uniq}"], keepdims=1)
            vpe = helper.make_node("Add", inputs=[var.output[0], epsC.output[0]], outputs=[f"IN_vpe_{uniq}"])
            std = helper.make_node("Sqrt", inputs=[vpe.output[0]], outputs=[f"IN_std_{uniq}"])
            norm = helper.make_node("Div", inputs=[sub.output[0], std.output[0]], outputs=[f"IN_norm_{uniq}"])

            rshS = helper.make_node("Reshape", inputs=[scale, shp.output[0]], outputs=[f"IN_scale4d_{uniq}"])
            rshB = helper.make_node("Reshape", inputs=[bias, shp.output[0]], outputs=[f"IN_bias4d_{uniq}"])
            mulS = helper.make_node("Mul", inputs=[norm.output[0], rshS.output[0]], outputs=[f"IN_mulS_{uniq}"])
            addB = helper.make_node("Add", inputs=[mulS.output[0], rshB.output[0]], outputs=[y])

            new_nodes.extend([axes, shp, epsC, mean, sub, sqr, var, vpe, std, norm, rshS, rshB, mulS, addB])
        else:
            new_nodes.append(n)

    if mutated:
        g.ClearField("node")
        g.node.extend(new_nodes)
        onnx.checker.check_model(m)
        onnx.save(m, onnx_out_path)
        log(f"[FixONNX] Decomposed InstanceNormalization -> {onnx_out_path}")
        return onnx_out_path
    else:
        if onnx_in_path != onnx_out_path:
            onnx.save(m, onnx_out_path)
        log("[FixONNX] No InstanceNormalization found; pass-through.")
        return onnx_out_path


def remove_trivial_unsqueeze(onnx_in_path: str, onnx_out_path: str) -> str:
    """
    Remove Unsqueeze nodes (axes in {0,1}) that are immediately consumed by Reshape/Concat/Transpose.
    """
    m = onnx.load(onnx_in_path)
    g = m.graph

    consumers = {}
    for n in g.node:
        for i in n.input:
            consumers.setdefault(i, []).append(n)

    keep = []
    bypass = {}
    mutated = False

    for n in g.node:
        if n.op_type == "Unsqueeze":
            axes_attr = next((a for a in n.attribute if a.name == "axes"), None)
            if axes_attr and set(axes_attr.ints).issubset({0, 1}):
                out0 = n.output[0]
                ok = all(all(c.op_type in ("Reshape", "Concat", "Transpose") for c in consumers.get(out0, [])))
                if ok:
                    bypass[out0] = n.input[0]
                    mutated = True
                    continue
        keep.append(n)

    if mutated:
        for n in keep:
            for i, inp in enumerate(n.input):
                if inp in bypass:
                    n.input[i] = bypass[inp]
        g.ClearField("node")
        g.node.extend(keep)
        onnx.checker.check_model(m)
        onnx.save(m, onnx_out_path)
        log(f"[FixONNX] Removed trivial Unsqueeze -> {onnx_out_path}")
        return onnx_out_path
    else:
        if onnx_in_path != onnx_out_path:
            onnx.save(m, onnx_out_path)
        log("[FixONNX] No trivial Unsqueeze pattern; pass-through.")
        return onnx_out_path


# ------------------------------
# AI Hub: Quantize (W8A8) & Compile to TFLite
# ------------------------------
def aihub_quantize_and_compile_tflite(onnx_model_or_path, device_name: str,
                                      calib_np_batch: np.ndarray,
                                      out_dir: str, job_prefix: str = "xfeat") -> str:
    device = hub.Device(device_name)

    log("[AI Hub] Submitting quantize job (INT8)...")
    calib_list = [im[np.newaxis, ...] for im in calib_np_batch]  # (1,3,H,W)
    quant_job = hub.submit_quantize_job(
        model=onnx_model_or_path,
        calibration_data={"images": calib_list},
        weights_dtype=hub.QuantizeDtype.INT8,
        activations_dtype=hub.QuantizeDtype.INT8
    )
    quant_job.wait()
    q_onnx = quant_job.get_target_model()
    if q_onnx is None:
        raise RuntimeError("Quantize job returned no model.")

    log("[AI Hub] Submitting compile job to TFLite...")
    compile_job = hub.submit_compile_job(
        model=q_onnx,
        device=device,
        options="--target_runtime tflite"
    )
    compile_job.wait()
    tflite_model = compile_job.get_target_model()
    if tflite_model is None:
        raise RuntimeError("Compile-to-TFLite job returned no model.")

    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)
    tfl_path = out_dir_p / f"{job_prefix}_quant_int8.tflite"
    save_hub_model(tflite_model, tfl_path)
    log(f"[AI Hub] Completed. TFLite saved to: {tfl_path}")
    return (str(tfl_path), tflite_model)


def aihub_compile_fp32_tflite(onnx_model_or_path, device_name: str,
                              out_dir: str, job_prefix: str = "xfeat_fp32") -> str:
    device = hub.Device(device_name)
    log("[AI Hub] Submitting compile job to FP32 TFLite...")
    job = hub.submit_compile_job(
        model=onnx_model_or_path,
        device=device,
        options="--target_runtime tflite"
    )
    job.wait()
    tflite_model = job.get_target_model()
    if tflite_model is None:
        raise RuntimeError("Compile-to-TFLite job returned no model.")

    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)
    tfl_path = out_dir_p / f"{job_prefix}.tflite"
    save_hub_model(tflite_model, tfl_path)
    log(f"[AI Hub] Completed. FP32 TFLite saved to: {tfl_path}")
    return (str(tfl_path), tflite_model)

def aihub_profile_and_inference_tflite(tflite_model, device_name: str, height, width, calib_count):
    device = hub.Device(device_name)

    log("[AI Hub] Submitting Profile job ...")
    prof_job = hub.submit_profile_job(
        model=tflite_model,
        device=device,
        options="--compute_unit npu"
    )
    prof_job.wait()
    log("[AI Hub] Profile done.")

    log("[AI Hub] Submitting Inference job ...")
    arrs = [_rand_img(height, width) for _ in range(calib_count)]
    inference_batch = np.stack(arrs, axis=0)
    log(f"[AI Hub] Built inference test set: {inference_batch.shape}")

    dataset_dict = {"images": [im[np.newaxis, ...] for im in inference_batch]}

    infer_job = hub.submit_inference_job(
        model=tflite_model,
        device=device,
        inputs=dataset_dict
    )
    infer_job.wait()
    log("[AI Hub] Inference done.")

# ------------------------------
# Main
# ------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calib_mode", type=str, choices=["dir", "random", "none"], default="random",
                    help="dir: use image folder; random: synthetic calibration; none: no quantization (FP32 TFLite)")
    ap.add_argument("--calib_dir", type=str, default="")
    ap.add_argument("--calib_count", type=int, default=64, help="number of synthetic samples when mode=random")
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--device_name", type=str, default="QCS6490 (Proxy)")
    ap.add_argument("--workdir", type=str, default="./xfeat_qai-hub_model")
    args = ap.parse_args()

    H, W = args.height, args.width
    WDIR = Path(args.workdir)
    WDIR.mkdir(parents=True, exist_ok=True)

    xfeat = build_xfeat_via_hub()

    core = getattr(xfeat, "net", None)
    if core is None or not isinstance(core, nn.Module):
        raise RuntimeError("The 'net' inside XFeat was not found or is not an nn.Module.")

    # Decompose InstanceNorm first (critical before quant/HTP)
    replace_instancenorm2d(core)

    # Guard: if any sparse APIs are used by mistake, fail fast to ensure we use the dense wrapper
    def _guard_detectAndCompute(*args, **kwargs):
        raise RuntimeError("detectAndCompute() should not be called; ensure the Dense wrapper is used.")
    for name in ("detectAndCompute", "detectAndComputeDense"):
        if hasattr(xfeat, name):
            setattr(xfeat, name, _guard_detectAndCompute)

    # Use Dense wrapper
    wrapper = XFeatExportDense(xfeat).eval()
    print(f"[Wrapper] Using {wrapper.__class__.__name__}")

    # TorchScript trace (fixed 1x3xHxW)
    ts = to_torchscript(wrapper, input_shape=(1, 3, H, W))

    # Prepare output paths
    onnx_raw_path = str(WDIR / "xfeat_from_aihub.onnx")

    # Single cloud TorchScript->ONNX attempt; fall back to local Dynamo on failure
    onnx_model = None
    err = ""

    log("[AI Hub] Trying TorchScript -> ONNX compile in the cloud ...")
    onnx_model, err, job_id = aihub_compile_ts_to_onnx(
        ts_model=ts,
        device_name=args.device_name,
        input_shape=(1, 3, H, W),
    )

    if onnx_model is not None:
        save_hub_model(onnx_model, onnx_raw_path)
        print(f"[AI Hub] Saved ONNX from Hub: {onnx_raw_path}")
    else:
        if err:
            print(f"[Warn] AI Hub compile failed: {err}")
        else:
            print("[Warn] AI Hub compile failed: Unknown error")


    target_path = str(WDIR)
    unzip_onnx_model(onnx_raw_path, job_id, target_path)

    # Local ONNX fixes
    onnx_noIN_path = str(Path(WDIR) / "xfeat_no_instance_norm.onnx")
    onnx_noIN_path = decompose_instance_norm(onnx_raw_path, onnx_noIN_path)

    onnx_clean_path = str(Path(WDIR) / "xfeat_clean.onnx")
    onnx_clean_path = remove_trivial_unsqueeze(onnx_noIN_path, onnx_clean_path)

    # Quantize (or skip) -> TFLite
    out_dir = str(Path(WDIR) / "out")
    if args.calib_mode == "none":
        # No quantization: compile to FP32 TFLite (typically runs on CPU/GPU)
        tfl_path, tflite_model = aihub_compile_fp32_tflite(onnx.load(onnx_clean_path),
                                             args.device_name, out_dir, job_prefix="xfeat_fp32")
    else:
        # Prepare calibration data
        if args.calib_mode == "dir":
            if not args.calib_dir:
                raise ValueError("--calib_dir not specified (calib_mode=dir)")
            calib = load_calib_images(args.calib_dir, H, W, max_images=args.calib_count)
        else:
            calib = build_synthetic_calib(H, W, count=args.calib_count)

        tfl_path, tflite_model = aihub_quantize_and_compile_tflite(onnx.load(onnx_clean_path),
                                                     args.device_name, calib, out_dir, job_prefix="xfeat")

    aihub_profile_and_inference_tflite(tflite_model, args.device_name, args.height, args.width, args.calib_count)

    log("[Done] Pipeline finished successfully.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n[Abort] Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        log(f"\n[Error] {e}")
        sys.exit(1)