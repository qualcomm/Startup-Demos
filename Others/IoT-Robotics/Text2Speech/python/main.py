#===--main.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
from arduino.app_utils import App
from arduino.app_bricks.web_ui import WebUI
import os
import time
import io
import base64
import json
import wave
import threading
from piper import PiperVoice

MODEL = "assets/en_US-amy-low.onnx"
CONFIG = "assets/en_US-amy-low.onnx.json"

def synthesize_wav_base64(text: str) -> str:
   """
   Produce WAV(PCM16 mono) and return as base64 string.
   """
   buf = io.BytesIO()
   with wave.open(buf, "wb") as wav_file:
       wav_file.setnchannels(1)       # mono
       wav_file.setsampwidth(2)       # 16-bit PCM
       wav_file.setframerate(SAMPLE_RATE)

       # Piper writes raw PCM frames into wav container
       with _voice_lock:
           voice.synthesize_wav(text, wav_file)

   return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_sample_rate(v):
   for attr in ("sample_rate", "config"):
       try:
           sr = getattr(v, attr)
           if isinstance(sr, int):           # voice.sample_rate
               return sr
           if hasattr(sr, "sample_rate"):    # voice.config.sample_rate
               return sr.sample_rate
       except Exception:
           pass
   return 22050


def parse_data(data):
   if isinstance(data, str):
       return json.loads(data)
   return data if isinstance(data, dict) else {}


def on_run_tts(sid, data):
   try:
       parsed = parse_data(data)
       text = (parsed.get("text") or "").strip()

       if not text:
           ui.send_message("tts_error", {"message": "No text provided."}, sid)
           return

       t0 = time.time() * 1000.0
       wav_b64 = synthesize_wav_base64(text)
       dt = time.time() * 1000.0 - t0

       ui.send_message(
           "tts_complete",
           {
               "audio_wav_base64": wav_b64,
               "sample_rate": SAMPLE_RATE,
               "processing_time_ms": dt,
           },
           sid,
       )

   except Exception as e:
       ui.send_message("tts_error", {"message": str(e)}, sid)

# Load model once (important!)
voice = PiperVoice.load(model_path=MODEL, config_path=CONFIG, use_cuda=False)
SAMPLE_RATE = get_sample_rate(voice)
_voice_lock = threading.Lock()


ui = WebUI()
# Register message handler (same as your classification example)
ui.on_message("run_tts", on_run_tts)

# Start the application (same as your example)
App.run()