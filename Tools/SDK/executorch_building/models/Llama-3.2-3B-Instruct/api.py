#===--api.py--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env python3
"""HTTP API for Llama inference via qnn_llama_persistent_runner."""

import argparse
import atexit
import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATUS_LINE_RE = re.compile(r"^(OK|ERR) (\d+)$")


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

    def close(self):
        if self._process.poll() is None:
            try:
                self._process.stdin.write(b"QUIT\n")
                self._process.stdin.flush()
            except OSError:
                pass
            self._process.terminate()
            self._process.wait(timeout=5)

    def generate(self, prompt, system_prompt, seq_len):
        prompt_bytes = prompt.encode("utf-8")
        system_bytes = system_prompt.encode("utf-8")
        header = f"{len(prompt_bytes)} {len(system_bytes)} {seq_len}\n"

        with self._lock:
            self._process.stdin.write(header.encode("ascii"))
            self._process.stdin.write(prompt_bytes)
            self._process.stdin.write(system_bytes)
            self._process.stdin.flush()

            while True:
                status_line = self._process.stdout.readline().decode("utf-8").strip()
                if not status_line:
                    continue
                m = STATUS_LINE_RE.match(status_line)
                if m:
                    break
            status, size = m.group(1), int(m.group(2))
            payload = b""
            while len(payload) < size:
                payload += self._process.stdout.read(size - len(payload))

        text = payload.decode("utf-8")
        if status == "ERR":
            raise RuntimeError(text)
        return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--runner-binary", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--tokenizer-path", required=True)
    parser.add_argument("--decoder-model-version", default="qwen3")
    parser.add_argument("--eval-mode", type=int, default=0)
    parser.add_argument("--seq-len", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--system-prompt", default="")
    args = parser.parse_args()

    cmd = [
        args.runner_binary, "--stdio_server",
        "--model_path", args.model_path,
        "--tokenizer_path", args.tokenizer_path,
        "--decoder_model_version", args.decoder_model_version,
        "--eval_mode", str(args.eval_mode),
        "--seq_len", str(args.seq_len),
        "--temperature", str(args.temperature),
    ]
    if args.system_prompt:
        cmd.extend(["--system_prompt", args.system_prompt])

    client = RunnerClient(cmd)
    atexit.register(client.close)

    default_seq_len = args.seq_len
    default_system_prompt = args.system_prompt

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            prompt = req.get("prompt", "")
            system_prompt = req.get("system_prompt", default_system_prompt)
            seq_len = int(req.get("seq_len", default_seq_len))

            try:
                response = client.generate(prompt, system_prompt, seq_len)
                body = json.dumps({"response": response}).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *a):
            pass

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"status": "listening", "host": args.host, "port": args.port}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
