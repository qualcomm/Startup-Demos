#===--aihub_conversion.py-------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import argparse
import qai_hub as hub


def build_parser():
    parser = argparse.ArgumentParser(
        description="Compile an ONNX model on Qualcomm AI Hub and download the AI Hub-optimized ONNX."
    )

    parser.add_argument(
        "--onnx_model",
        type=str,
        default="rnnoise_1.onnx",
        help="Path to the input ONNX model to compile on AI Hub."
    )

    parser.add_argument(
        "--model_name",
        type=str,
        default="rnnoise",
        help="Model name used for the AI Hub compile job."
    )

    parser.add_argument(
        "--device",
        type=str,
        default="Snapdragon X Elite CRD",
        help="Target AI Hub device name (e.g., 'Snapdragon X Elite CRD')."
    )

    parser.add_argument(
        "--out",
        type=str,
        default="./model/rnnoise_qaihub.onnx",
        help="Output path to save the compiled (AI Hub) ONNX model."
    )

    parser.add_argument(
        "--output_names",
        type=str,
        default="denoise_output,vad_out,vad_gru_state,noise_gru_state,denoise_gru_state",
        help="Comma-separated output node names passed to AI Hub compile options."
    )

    # Keep your original RNNoise input specs as defaults
    parser.add_argument(
        "--main_input_shape",
        type=str,
        default="1,1,42",
        help="Comma-separated shape for main_input. Default: 1,1,42"
    )
    parser.add_argument(
        "--vad_state_shape",
        type=str,
        default="1,24",
        help="Comma-separated shape for vad_gru_prev_state. Default: 1,24"
    )
    parser.add_argument(
        "--noise_state_shape",
        type=str,
        default="1,48",
        help="Comma-separated shape for noise_gru_prev_state. Default: 1,48"
    )
    parser.add_argument(
        "--denoise_state_shape",
        type=str,
        default="1,96",
        help="Comma-separated shape for denoise_gru_prev_state. Default: 1,96"
    )

    parser.add_argument(
        "--skip_profile",
        action="store_true",
        help="If set, skip submit_profile_job (compile + download only)."
    )

    return parser


def parse_shape(shape_str: str):
    return tuple(int(x.strip()) for x in shape_str.split(",") if x.strip())


def main():
    args = build_parser().parse_args()

    output_names = [s.strip() for s in args.output_names.split(",") if s.strip()]

    input_specs = {
        "main_input": (parse_shape(args.main_input_shape), "float32"),
        "vad_gru_prev_state": (parse_shape(args.vad_state_shape), "float32"),
        "noise_gru_prev_state": (parse_shape(args.noise_state_shape), "float32"),
        "denoise_gru_prev_state": (parse_shape(args.denoise_state_shape), "float32"),
    }

    onnx_compile_job = hub.submit_compile_job(
        model=args.onnx_model,
        input_specs=input_specs,
        name=args.model_name,
        device=hub.Device(args.device),
        options=f"--target_runtime onnx --output_names {','.join(output_names)}",
    )

    target_model = onnx_compile_job.get_target_model()

    if not args.skip_profile:
        hub.submit_profile_job(
            model=target_model,
            device=hub.Device(args.device),
        )

    onnx_compile_job.download_target_model(args.out)


if __name__ == "__main__":
    main()