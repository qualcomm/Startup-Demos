# InternVL3-1B on Qualcomm

Multimodal vision+language model. Auto-downloaded from HuggingFace during export.

## Prerequisites

- **Host:** x86_64 Ubuntu, Python 3.10+, **16GB+ RAM**
- **Target:** aarch64 Qualcomm board (QCS9075/QCS8275) with Ubuntu 24.04, NPU access via FastRPC

## Step 1: Host Setup (one-time) — **[Host]**

Clones ExecuTorch, applies patch, downloads QAIRT SDK, installs deps.

```bash
cd <workspace>
bash executorch_building/common/setup_host.sh
bash executorch_building/common/build_host.sh
```

## Step 2: Export — **[Host]**

Exports model artifacts. Model is auto-downloaded from HuggingFace.

```bash
bash executorch_building/models/internvl3_1b/export.sh
```

## Step 3: Transfer to Target — **[Host → Target]**

Copy the following from the host to the target board at `<workspace>/`:

- `executorch_building/` → `<workspace>/executorch_building/`
- `artifacts/internvl3_1b/` → `<workspace>/artifacts/internvl3_1b/`

## Step 4: Target Setup (one-time) — **[Target]**

Run on the target board. Installs QAIRT board packages, clones ExecuTorch, then builds natively. Log out and back in after first run for fastrpc group membership.

```bash
cd <workspace>
bash executorch_building/common/setup_target.sh
bash executorch_building/common/build_target.sh
```

## Step 5: Package (one-time) — **[Target]**

Collects build outputs and artifacts into `deploy/internvl3_1b/`.

```bash
bash executorch_building/models/internvl3_1b/package.sh
```

## Step 6: Run — **[Target]**

Starts the HTTP API on port 8080.

```bash
bash executorch_building/models/internvl3_1b/run.sh
```

## Step 7: Test — **[Target]**

Run on the target board (or any machine that can reach it). Sends a test request with an image.

```bash
bash executorch_building/models/internvl3_1b/test.sh
```
