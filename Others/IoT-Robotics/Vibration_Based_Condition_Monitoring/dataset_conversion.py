#===--dataset_conversion.py----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from pathlib import Path
import pandas as pd
from scipy.io import loadmat
from itertools import islice
import argparse


# -------------------------------------------------
# Parse ONLY the required command-line arguments
# -------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="MAT to EI CSV converter")

    parser.add_argument("--base-dir", required=True,
                        help="Path to the input dataset folder (must contain Healthy/ and Faulty/ folders)")
    
    parser.add_argument("--out-dir", required=True,
                        help="Path to the output folder for CSV files")

    return parser.parse_args()


# -------------------------------------------------
# Your original function (unchanged)
# -------------------------------------------------
def mat_to_ei_csv(mat_file, label, out_dir):
    m = loadmat(mat_file)
    
    if MAT_KEY not in m:
        print(f"[WARN] No key '{MAT_KEY}' in {mat_file.name}, skipping.")
        return False
    
    data = m[MAT_KEY]

    # Fix shape
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    if data.shape[1] < 3:
        print(f"[WARN] {mat_file.name} has only {data.shape[1]} columns, expected 3.")
        return False
    
    # Build timestamp column
    N = data.shape[0]
    timestamps = [int(i * SAMPLING_MS) for i in range(N)]

    df = pd.DataFrame({
        "timestamp": timestamps,
        "accX": data[:, 0],
        "accY": data[:, 1],
        "accZ": data[:, 2]
    })
    
    # Filename with EI label prefix
    out_name = f"{label}.{mat_file.stem}.csv"
    df.to_csv(out_dir / out_name, index=False)
    return True


# -------------------------------------------------
# Helper (unchanged)
# -------------------------------------------------
def take_n(files, n):
    if n is None:
        return files
    return list(islice(files, n))


# -------------------------------------------------
# Main program (same logic, only paths replaced)
# -------------------------------------------------
if __name__ == "__main__":

    args = parse_args()

    BASE_DIR = Path(args.base_dir)
    OUT_DIR = Path(args.out_dir)

    # your same default values
    N_FILES_PER_CLASS = None
    SAMPLING_MS = 1.0
    MAT_KEY = "H"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Folders Ready.")

    total = 0

    # Healthy class
    healthy_files = sorted((BASE_DIR / "Healthy").glob("*.mat"))
    for f in take_n(healthy_files, N_FILES_PER_CLASS):
        if mat_to_ei_csv(f, "healthy", OUT_DIR):
            total += 1

    # Faulty class
    faulty_files = sorted((BASE_DIR / "Faulty").glob("*.mat"))
    for f in take_n(faulty_files, N_FILES_PER_CLASS):
        if mat_to_ei_csv(f, "faulty", OUT_DIR):
            total += 1

    print(f"[DONE] Converted {total} files into {OUT_DIR}")

