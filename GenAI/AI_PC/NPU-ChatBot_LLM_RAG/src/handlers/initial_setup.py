#===--initial_setup.py----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import os
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Initialize embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Get the directory of the current script (src/handlers/)
current_script_dir = Path(__file__).parent

# Construct the path to the "models" directory
save_path = current_script_dir.parent.parent / "models"

# Create the directory if it doesn't exist
os.makedirs(save_path, exist_ok=True)

# Save the model to the constructed path
model.save(str(save_path))

print(f"Model saved to: {save_path}")
