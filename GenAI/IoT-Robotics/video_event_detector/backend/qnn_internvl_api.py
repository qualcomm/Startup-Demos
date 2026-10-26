#===--qnn_internvl_api.py-------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env python3
"""HTTP API for InternVL3 multimodal inference via qnn_multimodal_persistent_runner."""

import argparse
import atexit
import json
import re
import subprocess
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image

STATUS_LINE_RE = re.compile(r"^(OK|ERR) (\d+)$")
IMAGE_HEIGHT = 448
IMAGE_WIDTH = 448
IMAGE_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGE_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class RunnerClient:
    def __init__(self, command):
        self._process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, bufsize=0
        )
        self._lock = threading.Lock()
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError("runner exited before READY")
            if line == b"READY\n":
                break

    @property
    def pid(self):
        return self._process.pid

    def is_alive(self):
        return self._process.poll() is None

    def close(self):
        if self._process.poll() is None:
            try:
                self._process.stdin.write(b"QUIT\n")
                self._process.stdin.flush()
            except OSError:
                pass
            self._process.terminate()
            self._process.wait(timeout=5)

    def generate(self, prompt, system_prompt, seq_len, image_paths, continue_conversation):
        if not prompt:
            raise ValueError("prompt must not be empty")
        if seq_len <= 0:
            raise ValueError("seq_len must be greater than zero")
        if not self.is_alive():
            raise RuntimeError("persistent multimodal runner is not running")

        prompt_bytes = prompt.encode("utf-8")
        system_bytes = system_prompt.encode("utf-8")
        header = (
            f"{len(prompt_bytes)} {len(system_bytes)} {seq_len} "
            f"{len(image_paths)} {1 if continue_conversation else 0}\n"
        )

        with self._lock:
            self._process.stdin.write(header.encode("ascii"))
            self._process.stdin.write(prompt_bytes)
            self._process.stdin.write(system_bytes)
            for image_path in image_paths:
                image_path_bytes = image_path.encode("utf-8")
                self._process.stdin.write(f"{len(image_path_bytes)}\n".encode("ascii"))
                self._process.stdin.write(image_path_bytes)
            self._process.stdin.flush()

            while True:
                status_line = self._process.stdout.readline().decode("utf-8").strip()
                if not status_line:
                    continue
                match = STATUS_LINE_RE.match(status_line)
                if match:
                    break
            status, size = match.group(1), int(match.group(2))
            payload = b""
            while len(payload) < size:
                payload += self._process.stdout.read(size - len(payload))

        text = payload.decode("utf-8")
        if status == "ERR":
            raise RuntimeError(text)
        return text


def preprocess_image(path):
    with Image.open(path) as image:
        resized = image.convert("RGB").resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.Resampling.BICUBIC)
    image_array = np.asarray(resized, dtype=np.float32) / 255.0
    normalized = (image_array - IMAGE_MEAN) / IMAGE_STD
    return np.ascontiguousarray(np.transpose(normalized, (2, 0, 1))[np.newaxis, ...], dtype=np.float32)


def prepare_images(image_paths):
    if not image_paths:
        return None, []
    temp_dir = tempfile.TemporaryDirectory(prefix="internvl-")
    raw_paths = []
    for index, image_path in enumerate(image_paths):
        array = preprocess_image(image_path)
        raw_path = Path(temp_dir.name) / f"img_{index}.raw"
        array.tofile(raw_path)
        raw_paths.append(str(raw_path))
    return temp_dir, raw_paths


def normalize_image_paths(payload):
    image_path = payload.get("image_path")
    image_paths = payload.get("image_paths")
    if image_path is not None and image_paths is not None:
        raise ValueError("provide either image_path or image_paths, not both")
    if image_path is not None:
        if not isinstance(image_path, str) or not image_path:
            raise ValueError("image_path must be a non-empty string")
        return [image_path]
    if image_paths is None:
        return []
    if not isinstance(image_paths, list) or any(
        not isinstance(path, str) or not path for path in image_paths
    ):
        raise ValueError("image_paths must be a list of non-empty strings")
    return image_paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--runner-binary", required=True)
    parser.add_argument("--decoder-path", required=True)
    parser.add_argument("--tok-embedding-path", required=True)
    parser.add_argument("--encoder-path", required=True)
    parser.add_argument("--tokenizer-path", required=True)
    parser.add_argument("--decoder-model-version", default="internvl3")
    parser.add_argument("--eval-mode", type=int, default=1)
    parser.add_argument("--seq-len", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--system-prompt", default="")
    args = parser.parse_args()

    command = [
        args.runner_binary,
        "--stdio_server",
        "--decoder_path",
        args.decoder_path,
        "--tok_embedding_path",
        args.tok_embedding_path,
        "--encoder_path",
        args.encoder_path,
        "--tokenizer_path",
        args.tokenizer_path,
        "--decoder_model_version",
        args.decoder_model_version,
        "--eval_mode",
        str(args.eval_mode),
        "--seq_len",
        str(args.seq_len),
        "--temperature",
        str(args.temperature),
    ]
    if args.system_prompt:
        command.extend(["--system_prompt", args.system_prompt])

    client = RunnerClient(command)
    atexit.register(client.close)
    default_seq_len = args.seq_len
    default_system_prompt = args.system_prompt

    class Handler(BaseHTTPRequestHandler):
        def _write_json(self, status_code, payload):
            body = json.dumps(payload).encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/healthz":
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found", "path": self.path})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "runner_alive": client.is_alive(),
                    "runner_pid": client.pid,
                },
            )

        def do_POST(self):
            if self.path != "/generate":
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found", "path": self.path})
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(content_length) or b"{}")
                prompt = payload.get("prompt", "")
                if not isinstance(prompt, str):
                    raise ValueError("prompt must be a string")
                system_prompt = payload.get("system_prompt", default_system_prompt)
                if not isinstance(system_prompt, str):
                    raise ValueError("system_prompt must be a string")
                seq_len = int(payload.get("seq_len", default_seq_len))
                image_paths = normalize_image_paths(payload)
                continue_conversation = bool(payload.get("continue_conversation", False))
            except json.JSONDecodeError as error:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": f"invalid json: {error}"})
                return
            except ValueError as error:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return

            temp_dir = None
            try:
                temp_dir, raw_paths = prepare_images(image_paths)
                response = client.generate(
                    prompt,
                    system_prompt,
                    seq_len,
                    raw_paths,
                    continue_conversation,
                )
                self._write_json(HTTPStatus.OK, {"response": response})
            except Exception as error:
                self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            finally:
                if temp_dir is not None:
                    temp_dir.cleanup()

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"status": "listening", "host": args.host, "port": args.port}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
