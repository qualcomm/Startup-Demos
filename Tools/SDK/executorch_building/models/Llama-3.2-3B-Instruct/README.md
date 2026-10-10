# Llama-3.2-3B-Instruct on Qualcomm

Text generation model. Requires manual download from HuggingFace.

## Prerequisites

- **Host:** x86_64 Ubuntu, Python 3.10+, **64GB+ RAM**
- **Target:** aarch64 Qualcomm board (QCS9075/QCS8275) with Ubuntu 24.04, NPU access via FastRPC

## Step 1: Host Setup (one-time) — **[Host]**

Clones ExecuTorch, applies patch, downloads QAIRT SDK, installs deps.

```bash
cd <workspace>
bash executorch_building/common/setup_host.sh
bash executorch_building/common/build_host.sh
```

## Step 2: Download Raw Model — **[Host]**

Download from https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct and place at:

```bash
raw_model/Llama-3.2-3B-Instruct/
```

## Step 3: Export — **[Host]**

Exports model artifacts from the downloaded checkpoint.

```bash
bash executorch_building/models/Llama-3.2-3B-Instruct/export.sh
```

## Step 4: Transfer to Target — **[Host → Target]**

Copy the following from the host to the target board at `<workspace>/`:

- `executorch_building/` → `<workspace>/executorch_building/`
- `artifacts/Llama-3.2-3B-Instruct/` → `<workspace>/artifacts/Llama-3.2-3B-Instruct/`
- `raw_model/Llama-3.2-3B-Instruct/original/tokenizer.model` → `<workspace>/raw_model/Llama-3.2-3B-Instruct/original/tokenizer.model`

## Step 5: Target Setup (one-time) — **[Target]**

Run on the target board. Installs QAIRT board packages, clones ExecuTorch, then builds natively. Log out and back in after first run for fastrpc group membership.

```bash
cd <workspace>
bash executorch_building/common/setup_target.sh
bash executorch_building/common/build_target.sh
```

## Step 6: Package (one-time) — **[Target]**

Collects build outputs and artifacts into `deploy/Llama-3.2-3B-Instruct/`.

```bash
bash executorch_building/models/Llama-3.2-3B-Instruct/package.sh
```

## Step 7: Run — **[Target]**

Starts the HTTP API on port 8081.

```bash
bash executorch_building/models/Llama-3.2-3B-Instruct/run.sh
```

## Step 8: Test — **[Target]**

Run on the target board (or any machine that can reach it). Sends a test prompt to the running API.

```bash
bash executorch_building/models/Llama-3.2-3B-Instruct/test.sh
```
