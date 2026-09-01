#===-------------------------main.py--------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import time

import numpy as np

from arduino.app_bricks.asr import WAVAutomaticSpeechRecognition
from arduino.app_bricks.llm import LargeLanguageModel
from arduino.app_bricks.tts import TextToSpeech
from arduino.app_peripherals.speaker import BaseSpeaker
from arduino.app_utils import App

INPUT_WAV = "assets/input.wav"
TRANSCRIPT_PATH = "output/transcript.txt"
LLM_RESPONSE_PATH = "output/llm_response.txt"
OUTPUT_WAV_PATH = "output/response.wav"


class NullSpeaker(BaseSpeaker):
    """No-op BaseSpeaker for file-only TTS synthesis on devices with no physical speaker plugged in.

    synthesize_wav() only reads self.sample_rate and never calls start()/play()/_write_audio(),
    so these overrides are never actually invoked in this pipeline; they exist only to satisfy
    BaseSpeaker's abstract-method contract.
    """

    def _open_speaker(self):
        pass

    def _close_speaker(self):
        pass

    def _write_audio(self, audio_chunk):
        pass


print("PIPELINE_STAGE: ASR_START")
with open(INPUT_WAV, "rb") as f:
    audio_bytes = f.read()

t0 = time.time()
asr = WAVAutomaticSpeechRecognition(audio_bytes)
App.start_brick(asr)
transcript = asr.transcribe()
t1 = time.time()
print(f"PIPELINE_STAGE: ASR_DONE transcript={transcript!r} elapsed={t1 - t0:.2f}s")

with open(TRANSCRIPT_PATH, "w") as f:
    f.write(transcript)

print("PIPELINE_STAGE: LLM_START")
llm = LargeLanguageModel(model="genie:qwen3_4b_instruct_2507")
prompt = f"Reply in one short sentence to this transcribed voice message: {transcript}"
t2 = time.time()
llm_response = llm.chat(prompt)
t3 = time.time()
print(f"PIPELINE_STAGE: LLM_DONE response={llm_response!r} elapsed={t3 - t2:.2f}s")

with open(LLM_RESPONSE_PATH, "w") as f:
    f.write(llm_response)

print("PIPELINE_STAGE: TTS_START")
no_speaker = NullSpeaker(sample_rate=44100, channels=1, format=np.int16, buffer_size=1024, auto_reconnect=False)
tts = TextToSpeech(speaker=no_speaker)
t4 = time.time()
wav_bytes = tts.synthesize_wav(llm_response)
t5 = time.time()
print(f"PIPELINE_STAGE: TTS_DONE output_bytes={len(wav_bytes)} elapsed={t5 - t4:.2f}s")

with open(OUTPUT_WAV_PATH, "wb") as f:
    f.write(wav_bytes)

print("PIPELINE_COMPLETE")
