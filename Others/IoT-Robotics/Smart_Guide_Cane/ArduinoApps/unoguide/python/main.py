#===--main.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import time
import os
import threading
import subprocess
from arduino.app_utils import *

# -----------------------------------------------------------------------------
# One-click deployment mode (Linux MPU side)
# -----------------------------------------------------------------------------
def env_flag(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if v == "":
        return default
    return v in ("1", "true", "yes", "y", "on")


def env_int(name: str, default: int) -> int:
    v = os.environ.get(name, "").strip()
    if v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


DEPLOYMENT_MODE = (
    env_flag("APP_DEPLOYMENT", False)
    or env_flag("DEPLOYMENT_MODE", False)
    or env_flag("DEPLOYMENT", False)
)

# Feature toggles
ENABLE_VOICE = env_flag("APP_VOICE", True)
DEBUG_LOG = (False if DEPLOYMENT_MODE else env_flag("APP_DEBUG", False))

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
LABEL_FILE = os.environ.get("APP_LABEL_FILE", "/app/python/label.txt")
AUDIO_DIR = os.environ.get("APP_AUDIO_DIR", "/app/python/audio")

# -----------------------------------------------------------------------------
# Mapping (AI label -> WAV)
# -----------------------------------------------------------------------------
MAP = {
    "red_light": "red_light_stereo.wav",
    "yellow_light": "yellow_light_stereo.wav",
    "green_light": "green_light_stereo.wav",
    "off": "idle_stereo.wav",
}

# -----------------------------------------------------------------------------
# aplay settings
# -----------------------------------------------------------------------------
APLAY = os.environ.get("APLAY_BIN", "/usr/bin/aplay")
DEVICE = os.environ.get("APLAY_DEVICE", "").strip()

# -----------------------------------------------------------------------------
# Debounce / cooldown
# -----------------------------------------------------------------------------
current_label = "off"
_prev_label = "off"
_last_play_ms = 0

COOLDOWN_MS = env_int("APP_VOICE_COOLDOWN_MS", 2500)
REPEAT_COUNT = env_int("APP_VOICE_REPEAT_COUNT", 3)
REPEAT_GAP_MS = env_int("APP_VOICE_REPEAT_GAP_MS", 150)

# =============================================================================
# NEW: Audio device self-check + auto fallback to plughw
# =============================================================================
# Behavior:
# - If APLAY_DEVICE is not set: try to auto pick plughw:<card>,<dev> from `aplay -l`
# - If APLAY_DEVICE is set to hw:X,Y and playback fails (mono not supported):
#     automatically retry using plughw:X,Y
# - Optional one-time startup self-test with a short WAV (default idle.wav)
#
# Env controls:
#   APP_AUDIO_AUTOFIX=1 (default)  -> enable auto-fallback logic
#   APP_AUDIO_SELFTEST=1 (default) -> do a one-time test playback on startup
#   APP_AUDIO_TEST_WAV=<file>      -> default: idle.wav
#
AUDIO_AUTOFIX = env_flag("APP_AUDIO_AUTOFIX", True)
AUDIO_SELFTEST = env_flag("APP_AUDIO_SELFTEST", True)
AUDIO_TEST_WAV = os.environ.get("APP_AUDIO_TEST_WAV", "idle_stereo.wav").strip() or "idle_stereo.wav"
_audio_checked = False


def _dbg(msg: str) -> None:
    if DEBUG_LOG:
        print(msg, flush=True)


def _run_aplay(device: str, wav_path: str) -> subprocess.CompletedProcess:
    cmd = [APLAY, "-q"]
    if device:
        cmd += ["-D", device]
    cmd += [wav_path]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _parse_first_playback_device_from_aplay_l() -> str:
    """
    Parse first 'card X' and 'device Y' from `aplay -l` output.
    Return a plughw string like: plughw:X,Y
    """
    try:
        p = subprocess.run([APLAY, "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        # Example:
        # card 1: II [Jabra ...], device 0: USB Audio [USB Audio]
        card_id = None
        dev_id = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("card ") and "device" in line:
                # naive parse: card <num> ... device <num>:
                try:
                    # split by spaces
                    parts = line.replace(":", " ").replace(",", " ").split()
                    # parts: ['card','1','II','[Jabra',...,'device','0','USB','Audio',...]
                    card_id = int(parts[1])
                    di = parts.index("device")
                    dev_id = int(parts[di + 1])
                    break
                except Exception:
                    continue
        if card_id is not None and dev_id is not None:
            return f"plughw:{card_id},{dev_id}"
    except Exception:
        pass
    return ""


def _ensure_playable_device(wav_path: str) -> None:
    """
    Ensure DEVICE is set to a playable ALSA device.
    This function may mutate global DEVICE.
    """
    global DEVICE, _audio_checked
    if _audio_checked or not AUDIO_AUTOFIX:
        return
    _audio_checked = True

    if not ENABLE_VOICE:
        _dbg("[APP][AUDIO] voice disabled, skip audio check")
        return

    if not os.path.exists(wav_path):
        print(f"[APP][AUDIO] self-test WAV not found: {wav_path}", flush=True)
        return

    # 1) If user didn't set APLAY_DEVICE, try to auto pick first card/device as plughw
    if not DEVICE:
        guess = _parse_first_playback_device_from_aplay_l()
        if guess:
            DEVICE = guess
            print(f"[APP][AUDIO] APLAY_DEVICE not set, auto-select: {DEVICE}", flush=True)

    # 2) Try playing once using DEVICE (or default if still empty)
    res = _run_aplay(DEVICE, wav_path)
    if res.returncode == 0:
        _dbg(f"[APP][AUDIO] audio check OK using device='{DEVICE or 'default'}'")
        return

    err = (res.stderr or "").strip()
    print(f"[APP][AUDIO] audio check failed using device='{DEVICE or 'default'}' rc={res.returncode}", flush=True)
    if err:
        print(f"[APP][AUDIO] STDERR: {err}", flush=True)

    # 3) If DEVICE is hw:X,Y, retry as plughw:X,Y (fix mono/stereo mismatch)
    if DEVICE.startswith("hw:"):
        plug = "plughw:" + DEVICE[len("hw:"):]
        res2 = _run_aplay(plug, wav_path)
        if res2.returncode == 0:
            DEVICE = plug
            print(f"[APP][AUDIO] fallback OK -> use '{DEVICE}' (auto-fix)", flush=True)
            return
        err2 = (res2.stderr or "").strip()
        print(f"[APP][AUDIO] fallback '{plug}' failed rc={res2.returncode}", flush=True)
        if err2:
            print(f"[APP][AUDIO] STDERR: {err2}", flush=True)

    # 4) As a last attempt, if DEVICE empty or weird, try plughw auto-guess
    guess = _parse_first_playback_device_from_aplay_l()
    if guess and guess != DEVICE:
        res3 = _run_aplay(guess, wav_path)
        if res3.returncode == 0:
            DEVICE = guess
            print(f"[APP][AUDIO] auto-guess OK -> use '{DEVICE}' (auto-fix)", flush=True)
            return

    print("[APP][AUDIO] audio not playable. Suggest setting APLAY_DEVICE=plughw:<card>,<dev>", flush=True)


# -----------------------------------------------------------------------------
# Playback
# -----------------------------------------------------------------------------
def _play_wav_async(path: str) -> None:
    """Play a WAV file asynchronously via ALSA aplay."""
    if not ENABLE_VOICE:
        return

    # NEW: ensure device works before first playback
    if AUDIO_SELFTEST:
        _ensure_playable_device(path)

    def _run():
        try:
            for i in range(max(1, REPEAT_COUNT)):
                cmd = [APLAY, "-q"]
                if DEVICE:
                    cmd += ["-D", DEVICE]
                cmd += [path]

                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    print(f"[APP][AUDIO] aplay failed rc={res.returncode} dev='{DEVICE or 'default'}' path={path}", flush=True)
                    if res.stderr:
                        print("[APP][AUDIO] STDERR:", res.stderr.strip(), flush=True)

                    # NEW: runtime auto-fallback if hw: fails (e.g., mono not supported)
                    if AUDIO_AUTOFIX and DEVICE.startswith("hw:"):
                        plug = "plughw:" + DEVICE[len("hw:"):]
                        res2 = _run_aplay(plug, path)
                        if res2.returncode == 0:
                            DEVICE_LOCAL = plug
                            print(f"[APP][AUDIO] runtime fallback OK -> use '{DEVICE_LOCAL}'", flush=True)
                            # Update global DEVICE so future plays use plughw
                            globals()["DEVICE"] = DEVICE_LOCAL
                        else:
                            if res2.stderr:
                                print("[APP][AUDIO] fallback STDERR:", res2.stderr.strip(), flush=True)

                if i < max(1, REPEAT_COUNT) - 1:
                    time.sleep(max(0, REPEAT_GAP_MS) / 1000.0)
        except Exception as e:
            print("[APP] aplay error:", e, flush=True)

    threading.Thread(target=_run, daemon=True).start()


def label_reader() -> None:
    """Poll label file at 10Hz; update current_label; play audio on label change."""
    global current_label, _prev_label, _last_play_ms

    # NEW: optional one-time startup self-test (use idle.wav by default)
    if ENABLE_VOICE and AUDIO_SELFTEST:
        test_wav = os.path.join(AUDIO_DIR, AUDIO_TEST_WAV)
        _ensure_playable_device(test_wav)

    while True:
        try:
            if os.path.exists(LABEL_FILE):
                with open(LABEL_FILE, "r") as f:
                    s = f.read().strip()

                if s:
                    current_label = s

                    if current_label != _prev_label:
                        if DEBUG_LOG:
                            print(f"[APP] label change: {_prev_label} -> {current_label}", flush=True)

                        now = int(time.time() * 1000)
                        fname = MAP.get(current_label)

                        if fname and (now - _last_play_ms) >= COOLDOWN_MS:
                            wav = os.path.join(AUDIO_DIR, fname)
                            if os.path.exists(wav):
                                if DEBUG_LOG:
                                    print(f"[APP][AUDIO] play {wav} (repeat={REPEAT_COUNT}, cooldown={COOLDOWN_MS}ms)", flush=True)
                                _play_wav_async(wav)
                                _last_play_ms = now
                            else:
                                print(f"[APP] WAV not found: {wav}", flush=True)

                        _prev_label = current_label

        except Exception as e:
            print("[APP] read label.txt error:", e, flush=True)

        time.sleep(0.1)


def get_ai_label() -> str:
    return current_label


Bridge.provide("get_ai_label", get_ai_label)
threading.Thread(target=label_reader, daemon=True).start()
App.run()
