#===--internvl.py---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

import atexit
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib import error, request

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "internvl" / "deploy"
START_SCRIPT = ROOT / "backend" / "start_target_internvl_api.sh"

API_HOST = os.environ.get("INTERNVL_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("INTERNVL_API_PORT", "8080"))
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
DEFAULT_SEQ_LEN = int(os.environ.get("INTERNVL_SEQ_LEN", "1024"))
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("INTERNVL_TIMEOUT_SECONDS", "90"))
API_READY_TIMEOUT_SECONDS = float(os.environ.get("INTERNVL_API_READY_TIMEOUT_SECONDS", "30"))

_PROCESS_LOCK = threading.Lock()
_API_PROCESS: subprocess.Popen[str] | None = None
_API_LOG_HANDLE = None
_API_LOG_PATH: Path | None = None


def _api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def _is_api_healthy() -> bool:
    try:
        with request.urlopen(_api_url("/healthz"), timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and payload.get("status") == "ok"
    except Exception:
        return False


def _cleanup_process() -> None:
    global _API_LOG_HANDLE, _API_LOG_PATH, _API_PROCESS

    if _API_PROCESS is None or _API_PROCESS.poll() is not None:
        if _API_LOG_HANDLE is not None:
            _API_LOG_HANDLE.close()
            _API_LOG_HANDLE = None
        return

    _API_PROCESS.terminate()
    try:
        _API_PROCESS.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _API_PROCESS.kill()
        _API_PROCESS.wait(timeout=5)
    finally:
        if _API_LOG_HANDLE is not None:
            _API_LOG_HANDLE.close()
            _API_LOG_HANDLE = None
        _API_LOG_PATH = None
        _API_PROCESS = None


atexit.register(_cleanup_process)


def _read_process_output() -> str:
    if _API_LOG_PATH is None or not _API_LOG_PATH.exists():
        return ""
    return _API_LOG_PATH.read_text(encoding="utf-8", errors="replace").strip()


def _ensure_api_running() -> None:
    global _API_LOG_HANDLE, _API_LOG_PATH, _API_PROCESS

    if _is_api_healthy():
        return

    with _PROCESS_LOCK:
        if _is_api_healthy():
            return

        if _API_PROCESS is None or _API_PROCESS.poll() is not None:
            if not START_SCRIPT.exists():
                raise FileNotFoundError(f"InternVL API start script not found: {START_SCRIPT}")
            if not MODEL_DIR.exists():
                raise FileNotFoundError(
                    "InternVL deploy directory not found. Copy the contents of deploy/internvl3_1b "
                    f"into {MODEL_DIR}."
                )

            process_env = os.environ.copy()
            process_env["PYTHON_EXECUTABLE"] = sys.executable
            process_env.setdefault("INTERNVL_MODEL_DIR", str(MODEL_DIR))
            log_file = tempfile.NamedTemporaryFile(
                mode="w",
                prefix="internvl-api-",
                suffix=".log",
                delete=False,
            )
            _API_LOG_HANDLE = log_file
            _API_LOG_PATH = Path(log_file.name)

            _API_PROCESS = subprocess.Popen(
                ["bash", str(START_SCRIPT)],
                cwd=str(MODEL_DIR),
                env=process_env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )

        deadline = time.monotonic() + API_READY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if _API_PROCESS is not None and _API_PROCESS.poll() is not None:
                details = _read_process_output() or "InternVL API exited before becoming ready."
                raise RuntimeError(details)
            if _is_api_healthy():
                return
            time.sleep(0.5)

        raise RuntimeError("InternVL API did not become ready in time.")


def _save_frame_as_jpeg(frame: np.ndarray) -> Path:
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected an HxWx3 frame array.")

    rgb_frame = np.ascontiguousarray(frame[:, :, ::-1])
    image = Image.fromarray(rgb_frame, mode="RGB")

    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    path = Path(handle.name)
    handle.close()
    image.save(path, format="JPEG", quality=90)
    return path


def _post_generate(payload: dict[str, object]) -> str:
    _ensure_api_running()

    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        _api_url("/generate"),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(message) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach InternVL API: {exc}") from exc

    model_response = response_payload.get("response")
    if not isinstance(model_response, str) or not model_response.strip():
        raise RuntimeError(f"InternVL API returned an invalid response: {response_payload}")
    return model_response.strip()


def run_internvl_frame(frame: np.ndarray, prompt: str) -> str:
    image_path = _save_frame_as_jpeg(frame)
    try:
        return _post_generate({
            "prompt": prompt,
            "image_path": str(image_path),
            "seq_len": DEFAULT_SEQ_LEN,
        })
    finally:
        image_path.unlink(missing_ok=True)
