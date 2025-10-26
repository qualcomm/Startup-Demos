#===--transcription_utils.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import sounddevice as sd
import wave
import os
from datetime import datetime
from qai_hub_models.models._shared.hf_whisper.app import HfWhisperApp
from qai_hub_models.utils.onnx_torch_wrapper import OnnxModelTorchWrapper, OnnxSessionOptions

SAMPLERATE = 48000

def list_input_devices():
    devices = sd.query_devices()
    input_devices = [device for device in devices if device['max_input_channels'] > 0]
    device_names = [f"{i}: {device['name']}" for i, device in enumerate(input_devices)]
    return input_devices, device_names

def record_audio(device_index, duration):
    filename = f"temp_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    recording = sd.rec(int(SAMPLERATE * duration), samplerate=SAMPLERATE, channels=1, dtype='int16', device=device_index)
    sd.wait()
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLERATE)
        wf.writeframes(recording.tobytes())
    return filename

def transcribe_audio(audio_file_path: str, model_size="base",
                     encoder_path="C:/build/whisper_base/HfWhisperEncoder/model.onnx",
                     decoder_path="C:/build/whisper_base/HfWhisperDecoder/model.onnx") -> str:
    options = OnnxSessionOptions.aihub_defaults()
    options.context_enable = False

    try:
        app = HfWhisperApp(
            OnnxModelTorchWrapper.OnNPU(encoder_path),
            OnnxModelTorchWrapper.OnNPU(decoder_path),
            f"openai/whisper-{model_size}"
        )
        transcription = app.transcribe(audio_file_path)
        return transcription
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {str(e)}")

