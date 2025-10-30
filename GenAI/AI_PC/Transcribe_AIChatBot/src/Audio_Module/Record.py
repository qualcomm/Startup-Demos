#===--Record.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import pyaudio
import wave
import logging
import streamlit as st

#Initialize logging
logging.basicConfig(level=logging.INFO)

class Audio_Module:
    def __init__(self):
        self.p = pyaudio.PyAudio()

    def list_input_devices(self):
        device_count = self.p.get_device_count()
        devices = []
        for i in range(device_count):
            device_info = self.p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                devices.append((i, device_info['name']))
        return devices

    def record_audio(self, filename, duration, device_index=0):
        try:
            # Set up the audio recording parameters
            chunk = 1024  # Record in chunks of 1024 samples
            sample_format = pyaudio.paInt16  # 16 bits per sample
            channels = 1
            fs = 44100  # Record at 44100 samples per second

            # Check if there's at least one input device
            if self.p.get_device_count() == 0:
                raise RuntimeError("No audio input devices found")

            logging.info('Recording audio...')

            stream = self.p.open(format=sample_format,
                                 channels=channels,
                                 rate=fs,
                                 frames_per_buffer=chunk,
                                 input=True,
                                 input_device_index=device_index)

            frames = []  # Initialize array to store frames

            # Store data in chunks for the specified duration
            for _ in range(0, int(fs / chunk * duration)):
                try:
                    data = stream.read(chunk, exception_on_overflow=False)
                    frames.append(data)
                except Exception as e:
                    logging.error(f"Unexpected error during recording: {e}")
            # Stop and close the stream
            stream.stop_stream()
            stream.close()
            self.p.terminate()

            logging.info('Finished recording')
            st.success("Recording finished")

            # Save the recorded data as a WAV file
            wf = wave.open(filename, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(self.p.get_sample_size(sample_format))
            wf.setframerate(fs)
            wf.writeframes(b''.join(frames))
            wf.close()
            return filename
        except Exception as e:
            raise RuntimeError(f"Error recording audio: {e}")

