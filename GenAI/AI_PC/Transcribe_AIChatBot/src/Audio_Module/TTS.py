#===--TTS.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import pyttsx3
import os

class TTS_Module:
    def __init__(self, voice=None):
        self.engine = pyttsx3.init()

        # Get available voices
        voices = self.engine.getProperty('voices')

        # Set default voice based on platform or availability
        if voice:
            self.voice = voice
        elif voices:
            self.voice = voices[0].id  # Use first available voice
        else:
            self.voice = 'com.apple.speech.synthesis.voice.Alex'  # Fallback

        self.engine.setProperty('voice', self.voice)

    def text_to_speech(self, text, output_file, lang='en'):
        try:
            if not text or text.strip() == "":
                raise ValueError("Empty text provided for speech synthesis")

            self.engine.save_to_file(text, output_file)
            self.engine.runAndWait()
            return output_file
        except Exception as e:
            raise RuntimeError(f"Error in text-to-speech conversion: {e}")

