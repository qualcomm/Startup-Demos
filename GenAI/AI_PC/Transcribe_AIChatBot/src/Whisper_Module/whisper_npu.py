#===---------whisper_npu.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from qai_hub_models.models._shared.hf_whisper.app import HfWhisperApp
from qai_hub_models.utils.onnx_torch_wrapper import OnnxModelTorchWrapper, OnnxSessionOptions

class WhisperWrapper_Module:
    def __init__(self, encoder_path, decoder_path, model_size="base"):
        self.encoder_path = encoder_path
        self.decoder_path = decoder_path
        self.model_size = model_size

        options = OnnxSessionOptions.aihub_defaults()
        options.context_enable = False

        self.app = HfWhisperApp(
            OnnxModelTorchWrapper.OnNPU(self.encoder_path),
            OnnxModelTorchWrapper.OnNPU(self.decoder_path),
            f"openai/whisper-{self.model_size}"
        )

    def transcribe_audio(self, audio_file_path):
        return self.app.transcribe(audio_file_path)

