#===-------------------------main.py--------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from arduino.app_utils import *
import os
import re
import time
import tempfile
import subprocess
import threading
from pathlib import Path

import wave
import struct
import math

# ----------------------------
# Paths / Config
# ----------------------------
BASE_DIR = Path("/app/python")
MODEL_DIR = BASE_DIR / "model"

WHISPER_BIN = MODEL_DIR / "whisper-cli"
MODEL_FILE = MODEL_DIR / "ggml-tiny.en.bin"

SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = "S16_LE"

# Increase if you want more speaking time
CHUNK_SECONDS = 4

# Optional user override:
#   export ALSA_DEVICE=plughw:0,0
ALSA_DEVICE = os.getenv("ALSA_DEVICE", "").strip()

DEBUG = True
COUNTDOWN_SECONDS = 5
MIN_WAV_BYTES = 5000
RMS_THRESHOLD = 200
IGNORE_REPEAT_SECONDS = 1.0

OPEN_PATTERNS = [
    r"\bopen\b",
    r"\bopen\s+gate\b",
    r"\bopen\s+the\s+gate\b",
]
CLOSE_PATTERNS = [
    r"\bclose\b",
    r"\bclose\s+gate\b",
    r"\bclose\s+the\s+gate\b",
]

last_detected_cmd = "NONE"
_last_cmd_time = 0.0
_last_cmd_value = None


def banner(msg: str):
    print("\n" + "=" * 70, flush=True)
    print(msg, flush=True)
    print("=" * 70, flush=True)


def run_cmd(cmd, env=None, cwd=None):
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=cwd,
    )
    return proc.returncode, (proc.stdout or "").strip()


# ----------------------------
# MIC detection (NO WRONG EXIT)
# ----------------------------
CARD_DEV_RE = re.compile(r"card\s+(?P<card>\d+)\s*:\s*.*?device\s+(?P<dev>\d+)\s*:", re.IGNORECASE)

def infer_first_plughw(arecord_l_output: str):
    for ln in (arecord_l_output or "").splitlines():
        m = CARD_DEV_RE.search(ln.strip())
        if m:
            return f"plughw:{m.group('card')},{m.group('dev')}"
    return None


def verify_can_record_quick(device_str: str | None):
    test_wav = Path("/tmp/mic_test.wav")
    try:
        cmd = ["arecord"]
        if device_str:
            cmd += ["-D", device_str]
        cmd += ["-f", FORMAT, "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-d", "1", str(test_wav)]
        rc, out = run_cmd(cmd)
        return (rc == 0), " ".join(cmd), out
    finally:
        if test_wav.exists():
            test_wav.unlink()


def ensure_mic_connected_or_continue():
    global ALSA_DEVICE

    rc, out = run_cmd(["arecord", "-l"])
    banner("CONNECTED CAPTURE DEVICES (arecord -l)")
    print(out, flush=True)

    if rc != 0:
        banner("arecord -l FAILED")
        print("Audio capture stack not working.", flush=True)
        raise SystemExit(1)

    # Auto-select first capture device if ALSA_DEVICE not set
    if not ALSA_DEVICE:
        inferred = infer_first_plughw(out)
        if inferred:
            ALSA_DEVICE = inferred
            banner("AUTO-SELECTED CAPTURE DEVICE")
            print(f"Using inferred ALSA_DEVICE: {ALSA_DEVICE}", flush=True)
        else:
            banner("Could not parse device line; using DEFAULT capture device")
            print("Continuing with default ALSA capture device (no -D).", flush=True)

    else:
        banner("USING ALSA_DEVICE FROM ENV")
        print(f"ALSA_DEVICE={ALSA_DEVICE}", flush=True)

    # Quick record test
    device_for_test = ALSA_DEVICE if ALSA_DEVICE else None
    ok, cmd_str, out2 = verify_can_record_quick(device_for_test)
    if ok:
        banner("MIC RECORD TEST PASSED")
        print(f"Test command: {cmd_str}", flush=True)
        return

    # If forced device failed, fallback to default (do NOT exit)
    if device_for_test:
        banner("MIC TEST FAILED WITH FORCED DEVICE → TRYING DEFAULT")
        print(f"Failed command: {cmd_str}", flush=True)
        print(out2, flush=True)

        ok2, cmd_str2, out3 = verify_can_record_quick(None)
        if ok2:
            banner("DEFAULT DEVICE RECORD TEST PASSED")
            print("Proceeding with DEFAULT capture device (no -D).", flush=True)
            ALSA_DEVICE = ""  # clear so record uses default
            return

        banner("MIC TEST FAILED (FORCED + DEFAULT)")
        print("Proceeding anyway (NOT exiting), but Whisper may see BLANK_AUDIO.", flush=True)
        print("\n--- forced output ---\n", out2, flush=True)
        print("\n--- default output ---\n", out3, flush=True)
        return

    banner("MIC TEST FAILED (DEFAULT)")
    print("Proceeding anyway (NOT exiting), but audio may be blank.", flush=True)
    print(out2, flush=True)


# ----------------------------
# Countdown + WAV validation
# ----------------------------
def countdown(n=COUNTDOWN_SECONDS):
    if n <= 0:
        return
    banner("GET READY TO SPEAK")
    for i in range(n, 0, -1):
        print(f"Starting in {i}...", flush=True)
        time.sleep(1)


def wav_has_voice(wav_path: Path, rms_threshold=RMS_THRESHOLD):
    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            fr = wf.getframerate()
            n_frames = wf.getnframes()

            if fr != SAMPLE_RATE or n_channels != CHANNELS or sampwidth != 2:
                return True

            frames = wf.readframes(min(n_frames, SAMPLE_RATE))
            if not frames:
                return False

            samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
            if not samples:
                return False

            s2 = 0
            for s in samples:
                s2 += s * s
            rms = math.sqrt(s2 / len(samples))
            return rms >= rms_threshold
    except Exception:
        return True


# ----------------------------
# Record Audio
# ----------------------------
def record_chunk(wav_path: Path):
    countdown(COUNTDOWN_SECONDS)

    banner("START SPEAK NOW (RECORDING...)")
    print(f"Speak clearly for {CHUNK_SECONDS} second(s):  OPEN  or  CLOSE", flush=True)

    t0 = time.perf_counter()

    cmd = ["arecord"]
    if ALSA_DEVICE:
        cmd += ["-D", ALSA_DEVICE]
    cmd += ["-f", FORMAT, "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-d", str(CHUNK_SECONDS), str(wav_path)]

    rc, out = run_cmd(cmd)
    dt = time.perf_counter() - t0

    banner("STOP RECORDING (RECORDING FINISHED)")
    print(f"Record time: {dt:.3f}s", flush=True)

    if rc != 0:
        print("[RECORD] arecord failed", flush=True)
        print(out, flush=True)
        return False

    size = wav_path.stat().st_size if wav_path.exists() else 0
    print(f"WAV size: {size} bytes", flush=True)

    if size < MIN_WAV_BYTES:
        print("[RECORD] File too small → likely no audio", flush=True)
        return False

    if not wav_has_voice(wav_path):
        print("[RECORD] Silence detected → speak louder / check mute", flush=True)
        return False

    print("[RECORD] Valid audio captured", flush=True)
    return True


# ----------------------------
# Whisper Transcribe (transcript only)
# ----------------------------
_TS_LINE_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]\s*(.*)$")

def extract_transcript(out: str):
    if not out:
        return ""
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    pieces = []
    for ln in lines:
        m = _TS_LINE_RE.match(ln)
        if m:
            txt = (m.group(1) or "").strip()
            if txt and txt != "[BLANK_AUDIO]":
                pieces.append(txt)
    return " ".join(pieces).strip()


def transcribe_wav(wav_path: Path):
    banner("TRANSCRIBING (NOT RECORDING NOW)")
    t0 = time.perf_counter()

    cmd = [str(WHISPER_BIN), "-m", str(MODEL_FILE), "-f", str(wav_path)]
    rc, out = run_cmd(cmd, cwd=str(MODEL_DIR))

    dt = time.perf_counter() - t0
    transcript = extract_transcript(out)

    banner("TRANSCRIPTION COMPLETED" if rc == 0 else "TRANSCRIPTION FAILED")
    print(f"Whisper time: {dt:.3f}s", flush=True)
    print("TRANSCRIBED TEXT:", flush=True)
    print(transcript if transcript else "(empty)", flush=True)

    return (rc == 0), transcript


def detect_command(text: str):
    t = (text or "").lower()
    for pat in OPEN_PATTERNS:
        if re.search(pat, t):
            return "OPEN"
    for pat in CLOSE_PATTERNS:
        if re.search(pat, t):
            return "CLOSE"
    return None


# ----------------------------
# LED Action (UPDATED)
# ----------------------------
def led_action(cmd: str):
    """
    IMPORTANT:
    MCU draws LED matrix by calling detect_gate_command() itself.
    So here we only PRINT for debug and update last_detected_cmd.
    """
    print(f"LED MATRIX ACTION (MCU will draw): {cmd}", flush=True)


def voice_loop():
    global last_detected_cmd, _last_cmd_time, _last_cmd_value

    banner("WHISPER VOICE LOOP STARTED")

    while True:
        tmp_wav = None
        try:
            fd, name = tempfile.mkstemp(prefix="gate_", suffix=".wav", dir="/tmp")
            os.close(fd)
            tmp_wav = Path(name)

            print("STAGE: Recording chunk...", flush=True)
            if not record_chunk(tmp_wav):
                print("Invalid/silent audio. Retrying...", flush=True)
                continue

            print("STAGE: Transcribing...", flush=True)
            ok, transcript = transcribe_wav(tmp_wav)
            if not ok:
                print("Transcription failed. Retrying...", flush=True)
                continue

            print("STAGE: Detecting command...", flush=True)
            cmd = detect_command(transcript)

            if cmd:
                now = time.time()
                if _last_cmd_value == cmd and (now - _last_cmd_time) < IGNORE_REPEAT_SECONDS:
                    print(f"Too soon repeat: {cmd} (ignored)", flush=True)
                    continue

                _last_cmd_value = cmd
                _last_cmd_time = now

                banner(f"DETECTED COMMAND: {cmd}")
                last_detected_cmd = cmd

                # Debug print only; MCU reads last_detected_cmd and draws matrix
                led_action(cmd)
            else:
                banner("NO COMMAND DETECTED")
                print("Say only: open / close", flush=True)

        finally:
            if tmp_wav and tmp_wav.exists():
                tmp_wav.unlink()
                print("Cleanup: temp wav deleted", flush=True)


# PROVIDED TO MCU
def detect_gate_command():
    global last_detected_cmd
    return last_detected_cmd


# Startup
ensure_mic_connected_or_continue()

threading.Thread(target=voice_loop, daemon=True).start()
Bridge.provide("detect_gate_command", detect_gate_command)
App.run()

