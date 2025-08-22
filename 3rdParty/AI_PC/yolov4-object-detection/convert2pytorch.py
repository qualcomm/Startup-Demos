#===--convert2pytorch.py--------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import torch
from tool.darknet2pytorch import Darknet

cfg_file = '/path-to-folder/yolov4.cfg'
weight_file = '/path-to-folder/yolov4.weights'
output_file = '/path-to-folder/yolov4.pt'

# Build the model architecture and load the weights
model = Darknet(cfg_file)
model.load_weights(weight_file)
model.eval()

# Save the complete model, including architecture and weights
torch.save(model, output_file)

