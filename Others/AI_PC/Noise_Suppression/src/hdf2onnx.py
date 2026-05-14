#===--hdf2onnx.py---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import argparse
import tf2onnx
import sys
import tensorflow as tf

from model import rnnoise_model_tflite
from data import get_tf_dataset_from_h5
from convert import tflite_convert


# ----------------------------------------------------------------------
# Argument parser (added only)
# ----------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Convert RNNoise Keras (HDF5) model to ONNX format"
)

parser.add_argument(
    "--ckpt_path",
    type=str,
    required=True,
    help="Path to the trained RNNoise checkpoint (.weights.h5)"
)

parser.add_argument(
    "--output_path",
    type=str,
    default="rnnoise_1.onnx",
    help="Output ONNX model path"
)

parser.add_argument(
    "--timesteps",
    type=int,
    default=1,
    help="Number of timesteps used when constructing RNNoise model"
)

FLAGS = parser.parse_args()


# ----------------------------------------------------------------------
# Original code (unchanged)
# ----------------------------------------------------------------------
model = rnnoise_model_tflite(timesteps=FLAGS.timesteps)

status = model.load_weights(FLAGS.ckpt_path)
if hasattr(status, "expect_partial"):
    status.expect_partial()

converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_fp32_model = converter.convert()

# Refer to tensorflow-onnx keras-resnet50.ipynb
Inputs = [
    "main_input",
    "vad_gru_prev_state",
    "noise_gru_prev_state",
    "denoise_gru_prev_state",
]

spec = []
for i, inp in enumerate(model.inputs):
    spec.append(tf.TensorSpec(inp.shape, tf.float32, name=Inputs[i]))

model_proto, _ = tf2onnx.convert.from_keras(
    model,
    input_signature=spec,
    opset=13,
    output_path=FLAGS.output_path
)
