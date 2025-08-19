#===--logger.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import os
import inspect
import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
logs_folder_path = os.path.join(os.path.dirname(current_dir), "logs")
os.makedirs(logs_folder_path, exist_ok=True)
DEBUG_LOG_FILE = os.path.join(logs_folder_path, "debug.log")

def write_log(message, log_file=DEBUG_LOG_FILE):
    caller_frame = inspect.stack()[1]
    caller_filename = os.path.basename(caller_frame.filename)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{caller_filename}] {message}\n"
    with open(log_file, "a") as file:
        file.write(log_entry)

def reset_log(log_file=DEBUG_LOG_FILE):
    with open(log_file, "w") as file:
        pass  

def main():
    write_log("Accessed Directly from logger.py main function.")

if __name__ == "__main__":
    main()
