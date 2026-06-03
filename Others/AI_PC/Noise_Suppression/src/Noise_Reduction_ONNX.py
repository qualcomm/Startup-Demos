#===--Noise_Reduction_ONNX.py---------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import argparse
import onnxruntime
import numpy as np
from pathlib import Path
import logging
import sys
import numpy as np
import soundfile as sf
import time
from data import RNNoisePreProcess, load_wav


# ----------------------------------------------------------------------
# Argument parser (added only)
# ----------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="RNNoise noise suppression demo using ONNX Runtime + QNN Execution Provider"
)

parser.add_argument(
    "--onnx_model_path",
    type=str,
    default="./model/rnnoise_qaihub.onnx/model.onnx/model.onnx",
    help="Path to the AI Hub compiled ONNX model"
)

parser.add_argument(
    "--backend_path",
    type=str,
    default="QnnHtp.dll",
    help="Path to QNN backend library (e.g., QnnHtp.dll)"
)

parser.add_argument(
    "--enable_htp_fp16_precision",
    type=str,
    default="1",
    help="QNN EP option: enable_htp_fp16_precision (string '0' or '1')"
)

parser.add_argument(
    "--htp_performance_mode",
    type=str,
    default="burst",
    help="QNN EP option: htp_performance_mode"
)

parser.add_argument(
    "--htp_graph_finalization_optimization_mode",
    type=str,
    default="3",
    help="QNN EP option: htp_graph_finalization_optimization_mode"
)

parser.add_argument(
    "--fallback",
    type=str,
    default="true",
    help="QNN EP option: fallback (string 'true'/'false')"
)

parser.add_argument(
    "--disable_cpu_ep_fallback",
    type=str,
    default="1",
    help="Session option: session.disable_cpu_ep_fallback (string '0' or '1')"
)

parser.add_argument(
    "--noisy_wav",
    type=str,
    default="./data/noisy_testset_wav/p232_003.wav",
    help="Input noisy WAV file path"
)

parser.add_argument(
    "--sample_rate",
    type=int,
    default=48000,
    help="Output WAV sample rate"
)

parser.add_argument(
    "--output_wav",
    type=str,
    default="",
    help="Optional output WAV path. If empty, saves next to input with *_denoised suffix."
)

args = parser.parse_args()


options = onnxruntime.SessionOptions()
options.add_session_config_entry("session.disable_cpu_ep_fallback", args.disable_cpu_ep_fallback)

onnx_model_path = args.onnx_model_path

ep_options = {
    "backend_path": args.backend_path,
    "enable_htp_fp16_precision": args.enable_htp_fp16_precision,
    "htp_performance_mode": args.htp_performance_mode,
    "htp_graph_finalization_optimization_mode": args.htp_graph_finalization_optimization_mode,
    "fallback": args.fallback,
}

# Create an ONNX Runtime session.​
session = onnxruntime.InferenceSession(
    onnx_model_path,
    sess_options=options,
    providers=["QNNExecutionProvider"],
    provider_options=[ep_options]
)

outputs = session.get_outputs()  # [0].name
inputs = session.get_inputs()

# Create test data
for input_meta in inputs:
    print(f"Name: {input_meta.name}, Type: {input_meta.type}, Shape: {input_meta.shape}")

vad_gru_state = np.zeros((1, 24), dtype=np.float32)
noise_gru_state = np.zeros((1, 48), dtype=np.float32)
denoise_gru_state = np.zeros((1, 96), dtype=np.float32)

preprocess = RNNoisePreProcess(training=False)

noisy_wav = args.noisy_wav
# noisy_wav = "path/to/your/audio"
loaded_audio = load_wav(noisy_wav)

start = time.time()
print(start)

final_denoised_audio = []
num_samples = len(loaded_audio) // preprocess.FRAME_SIZE

for i in range(num_samples):
    audio_window = loaded_audio[i * RNNoisePreProcess.FRAME_SIZE:
                                i * RNNoisePreProcess.FRAME_SIZE + RNNoisePreProcess.FRAME_SIZE]

    silence, features, X, P, Ex, Ep, Exp = preprocess.process_frame(audio_window)
    features = np.expand_dims(features, (0, 1)).astype(np.float32)

    if not silence:
        input_data = [features, vad_gru_state, noise_gru_state, denoise_gru_state]
        # print(features)
        result = session.run(
            None,
            {
                "main_input": input_data[0],
                "vad_gru_prev_state": input_data[1],
                "noise_gru_prev_state": input_data[2],
                "denoise_gru_prev_state": input_data[3],
            }
        )
        denoise_output, vad_out, vad_gru_state, noise_gru_state, denoise_gru_state = result
        vad_gru_state = np.squeeze(vad_gru_state, axis=1)
        noise_gru_state = np.squeeze(noise_gru_state, axis=1)
        denoise_gru_state = np.squeeze(denoise_gru_state, axis=1)
        denoise_output = np.squeeze(np.array(denoise_output))
        denoised_audio_tmp = preprocess.post_process(silence, denoise_output, X, P, Ex, Ep, Exp)
        denoised_audio_tmp = np.rint(denoised_audio_tmp).astype(np.int16)
        final_denoised_audio.append(denoised_audio_tmp)
    else:
        final_denoised_audio.append(np.zeros([preprocess.FRAME_SIZE], dtype=np.int16))

print(time.time() - start)
denoised_audio = np.concatenate(final_denoised_audio, axis=0)

noisy_wav = Path(noisy_wav)

if args.output_wav and len(args.output_wav) > 0:
    out_path = Path(args.output_wav)
else:
    out_path = Path(noisy_wav.parent, f"{noisy_wav.stem}_denoised{noisy_wav.suffix}")

sf.write(out_path, denoised_audio, args.sample_rate, 'PCM_16')
logging.info(f"Denoising {noisy_wav} complete. Output saved to {out_path}")