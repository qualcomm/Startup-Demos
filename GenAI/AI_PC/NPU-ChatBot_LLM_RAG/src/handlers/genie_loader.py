#===--genie_loader.py-----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import os
import json
import sys
import ctypes
import socket
from logger import write_log

# Define constants for success and failure
SUCCESS = 0
FAILURE = -1
SERVER_SUCCESS = "200"
response_completed = '#END#'

def load_genie_dll(genie_dll_path: str) -> ctypes.CDLL:
    """
    Load the Genie DLL from the specified path.

    Args:
    genie_dll_path (str): The path to the Genie DLL.

    Returns:
    ctypes.CDLL: The loaded Genie DLL.
    """
    try:
        os.chdir(genie_dll_path)
        write_log("Genie.dll Loaded Sucessfully")
        return ctypes.CDLL(os.path.join(genie_dll_path, "Genie.dll"))
    except OSError as e:
        write_log(f"Failed to load Genie DLL: {e}")
        sys.exit(FAILURE)

def load_genie_config(genie_config_path: str) -> dict:
    """
    Load the Genie configuration from the specified JSON file.

    Args:
    genie_config_path (str): The path to the Genie configuration JSON file.

    Returns:
    dict: The loaded Genie configuration.
    """
    try:
        with open(genie_config_path, 'r') as file:
            config = json.load(file)
            write_log("Genie config Loaded Successfully")
            return config
    except json.JSONDecodeError as e:
        write_log(f"Failed to load Genie configuration: {e}")
        sys.exit(FAILURE)
    except FileNotFoundError as e:
        write_log(f"Failed to find Genie configuration file: {e}")
        sys.exit(FAILURE)

def create_genie_dialog_config(genie_dll: ctypes.CDLL, config: dict) -> ctypes.POINTER:
    """
    Create a Genie Dialog configuration from the specified configuration.

    Args:
    genie_dll (ctypes.CDLL): The loaded Genie DLL.
    config (dict): The Genie configuration.

    Returns:
    ctypes.POINTER: The created Genie Dialog configuration handle.
    """
    config_str = json.dumps(config).encode('utf-8')
    m_config_handle = ctypes.POINTER(ctypes.c_void_p)()
    result_cfg = genie_dll.GenieDialogConfig_createFromJson(config_str, ctypes.byref(m_config_handle))
    if result_cfg != SUCCESS:
        write_log(f"Failed to create Genie Dialog configuration: {result_cfg}")
        sys.exit(FAILURE)
    write_log("Genie Dialog Created Successfully")
    return m_config_handle

def create_genie_dialog(genie_dll: ctypes.CDLL, config_handle: ctypes.POINTER) -> ctypes.POINTER:
    """
    Create a Genie Dialog from the specified configuration handle.

    Args:
    genie_dll (ctypes.CDLL): The loaded Genie DLL.
    config_handle (ctypes.POINTER): The Genie Dialog configuration handle.

    Returns:
    ctypes.POINTER: The created Genie Dialog handle.
    """
    m_dialog_handle = ctypes.POINTER(ctypes.c_void_p)()
    result_diag = genie_dll.GenieDialog_create(config_handle, ctypes.byref(m_dialog_handle))
    if result_diag != SUCCESS:
        write_log(f"Failed to create Genie Dialog: {result_diag}")
        sys.exit(FAILURE)
    else:
        write_log("Genie Dialog created successfully.")
    return m_dialog_handle

def query_genie_dialog(genie_dll: ctypes.CDLL, dialog_handle: ctypes.POINTER, tagged_prompt: bytes, callback_func) -> int:
    """
    Query the Genie Dialog with the specified prompt.

    Args:
    genie_dll (ctypes.CDLL): The loaded Genie DLL.
    dialog_handle (ctypes.POINTER): The Genie Dialog handle.
    tagged_prompt (bytes): The prompt to query the Genie Dialog with.
    callback_func: The callback function to handle responses from the Genie Dialog.

    Returns:
    int: The result of the query.
    """
    GENIE_DIALOG_SENTENCE_COMPLETE = 0
    model_response = ctypes.c_char_p()
    result = genie_dll.GenieDialog_query(dialog_handle,
                                         tagged_prompt,
                                         GENIE_DIALOG_SENTENCE_COMPLETE,
                                         callback_func,
                                         model_response)
    if not model_response:
        genie_dll.GenieDialog_reset(dialog_handle)
    return result

def genie_callback(response_back: ctypes.c_char_p, sentence_code: ctypes.c_int, user_data: ctypes.c_char_p) -> None:
    """
    Callback function to handle responses from the Genie Dialog.

    Args:
    response_back (str): The response from the Genie Dialog.
    sentence_code (int): The sentence code indicating the type of response.
    user_data (str): The user data associated with the response.
    """
    global user_data_str
    response_back = response_back.decode('utf-8')
    user_data_str += response_back
    if sentence_code == 2:
        client.send(response_back.encode())
    if sentence_code == 3:
        user_data_str = ""
        client.send(response_completed.encode())

def main():
    if len(sys.argv) != 5:
        write_log("Usage: python genie_loader.py <genie_dll_path> <genie_config_path>")
        sys.exit(FAILURE)

    global client
    global user_data_str
    user_data_str = ""
    server = None

    try:
        genie_dll_path = sys.argv[1]
        genie_config_path = sys.argv[2] + "genie_config.json"
        addr = sys.argv[3]
        port = int(sys.argv[4])

        # Create a socket object
        server = socket.socket()
        server.bind((addr, port))
        server.listen()
        client, addr = server.accept()

        genie_dll = load_genie_dll(genie_dll_path)
        config = load_genie_config(genie_config_path)
        config_handle = create_genie_dialog_config(genie_dll, config)
        dialog_handle = create_genie_dialog(genie_dll, config_handle)

        if dialog_handle:
            client.send(SERVER_SUCCESS.encode('utf-8'))

        # Define the callback function type
        CALLBACK_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
        genie_callback_func = CALLBACK_TYPE(genie_callback)

        while True:
            tagged_prompt = client.recv(10000).decode()
            tagged_prompt = tagged_prompt.encode('utf-8')        
            if tagged_prompt == b"exit":
                client.send("GoodBye!".encode('utf-8'))
                break
            write_log(tagged_prompt)
            result = query_genie_dialog(genie_dll, dialog_handle, tagged_prompt, genie_callback_func)
            print(result)
    except Exception as e:
        write_log(f"Error in main function: {e}")
        if 'client' in globals() and client:
            try:
                client.close()
            except:
                pass
        sys.exit(FAILURE)
    finally:
        if server:
            server.close()

if __name__ == "__main__":
    main()
