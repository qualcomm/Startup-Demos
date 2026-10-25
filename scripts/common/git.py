#===--git.py---------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Authenticated, bounded Git subprocesses shared by repository automation."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from .errors import GitCommandError
from .sanitizer import TokenSanitizer

__all__ = ["GitCommandError", "GitRunner", "TokenSanitizer"]


class GitRunner:
    """Run Git commands with optional askpass auth, redacted logs, and a timeout."""

    def __init__(
        self,
        working_directory: Path,
        token: str,
        timeout_seconds: float,
        sanitizer: TokenSanitizer,
        token_env_name: str = "COMMON_GITHUB_TOKEN",
        error_type: type[Exception] = GitCommandError,
        credential_directory: Path | None = None,
    ) -> None:
        if not token_env_name.isidentifier():
            raise ValueError("token_env_name must be a valid environment variable name")
        self.working_directory = working_directory
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.sanitizer = sanitizer
        self.token_env_name = token_env_name
        self.error_type = error_type
        self.credential_directory = credential_directory or working_directory
        self.askpass_path = self.credential_directory / ".git-askpass-common.sh"

    def __enter__(self) -> GitRunner:
        self.working_directory.mkdir(parents=True, exist_ok=True)
        self.credential_directory.mkdir(parents=True, exist_ok=True)
        self.askpass_path.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  *Username*) printf '%s\\n' 'x-access-token' ;;\n"
            f"  *Password*) printf '%s\\n' \"${self.token_env_name}\" ;;\n"
            "  *) printf '\\n' ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.askpass_path.chmod(0o700)
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        try:
            self.askpass_path.unlink(missing_ok=True)
        except OSError as error:
            logging.warning("Failed to remove temporary Git askpass helper: %s", error)

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        try:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            process.wait()

    def run(
        self,
        args: list[str],
        cwd: Path | None = None,
        authenticated: bool = False,
        allow_failure: bool = False,
        auth_token: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if authenticated:
            token = auth_token or self.token
            self.sanitizer.add(token)
            env["GIT_ASKPASS"] = str(self.askpass_path)
            env["GIT_TERMINAL_PROMPT"] = "0"
            env[self.token_env_name] = token
        else:
            env.pop(self.token_env_name, None)

        safe_command = self.sanitizer.clean(" ".join(args))
        if authenticated and args and Path(args[0]).name == "git":
            args = [args[0], "-c", "credential.helper=", *args[1:]]
        command_cwd = cwd or self.working_directory
        started_at = time.monotonic()
        logging.debug("Starting Git command (cwd=%s): %s", command_cwd, safe_command)
        process = subprocess.Popen(
            args,
            cwd=str(command_cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            start_new_session=os.name != "nt",
        )
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def stream_output(pipe, chunks: list[str], stream_name: str) -> None:
            for line in pipe:
                chunks.append(line)
                logging.debug("Git %s: %s", stream_name, self.sanitizer.clean(line.rstrip()))
            pipe.close()

        stdout_thread = threading.Thread(target=stream_output, args=(process.stdout, stdout_chunks, "stdout"), daemon=True)
        stderr_thread = threading.Thread(target=stream_output, args=(process.stderr, stderr_chunks, "stderr"), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        try:
            return_code = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as error:
            self._stop_process(process)
            stdout_thread.join()
            stderr_thread.join()
            elapsed = time.monotonic() - started_at
            logging.error(
                "Git command timed out after %.1f seconds (limit=%s, cwd=%s): %s",
                elapsed,
                self.timeout_seconds,
                command_cwd,
                safe_command,
            )
            raise subprocess.TimeoutExpired(
                args,
                self.timeout_seconds,
                output=self.sanitizer.clean("".join(stdout_chunks)),
                stderr=self.sanitizer.clean("".join(stderr_chunks)),
            ) from error

        stdout_thread.join()
        stderr_thread.join()
        elapsed = time.monotonic() - started_at
        stdout = self.sanitizer.clean("".join(stdout_chunks))
        stderr = self.sanitizer.clean("".join(stderr_chunks))
        logging.debug("Git command finished in %.2f seconds (exit=%s): %s", elapsed, return_code, safe_command)
        completed = subprocess.CompletedProcess(args, return_code, stdout, stderr)
        if return_code != 0 and not allow_failure:
            raise self.error_type(f"Git command failed ({return_code}): {safe_command}\n{stderr.strip()}")
        return completed