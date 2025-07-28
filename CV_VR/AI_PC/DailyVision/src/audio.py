# //===---------------------audio.py-----------------------------------------===//
# // Part of the Startup-Demos Project, under the MIT License
# // See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# // for license information.
# // Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# // SPDX-License-Identifier: MIT License
# //===----------------------------------------------------------------------===//

import pyttsx3  # Import the text-to-speech conversion library

def speak_text(text):
    speaker = pyttsx3.init()
    speaker.say(text)
    speaker.runAndWait()

