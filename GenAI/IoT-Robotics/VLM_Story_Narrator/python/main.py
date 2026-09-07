#===-------------------------main.py--------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import time

import numpy as np

from arduino.app_bricks.vlm import VisionLanguageModel
from arduino.app_bricks.tts import TextToSpeech
from arduino.app_peripherals.speaker import BaseSpeaker
from arduino.app_utils import App

INPUT_IMAGE = "assets/demo_image.png"
STORY_TEXT_PATH = "output/story.txt"
OUTPUT_WAV_PATH = "output/narration.wav"

STORY_PROMPT = (
    "Look at this image and write a short, imaginative story about it in one "
    "paragraph (about 60-80 words), suitable to be read aloud."
)


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


print("PIPELINE_STAGE: VLM_START")
vlm = VisionLanguageModel(max_tokens=200)
t0 = time.time()
story_text = vlm.chat(STORY_PROMPT, images=[INPUT_IMAGE])
t1 = time.time()
print(f"PIPELINE_STAGE: VLM_DONE story={story_text!r} elapsed={t1 - t0:.2f}s")

with open(STORY_TEXT_PATH, "w") as f:
    f.write(story_text)

print("PIPELINE_STAGE: TTS_START")
no_speaker = NullSpeaker(sample_rate=44100, channels=1, format=np.int16, buffer_size=1024, auto_reconnect=False)
tts = TextToSpeech(speaker=no_speaker)
t2 = time.time()
wav_bytes = tts.synthesize_wav(story_text)
t3 = time.time()
print(f"PIPELINE_STAGE: TTS_DONE output_bytes={len(wav_bytes)} elapsed={t3 - t2:.2f}s")

with open(OUTPUT_WAV_PATH, "wb") as f:
    f.write(wav_bytes)

print("PIPELINE_COMPLETE")
