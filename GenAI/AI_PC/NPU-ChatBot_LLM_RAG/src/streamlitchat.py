#===--streamlitchat.py----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import os
import yaml
import time
import socket
import subprocess
import streamlit as st
import logging
import shutil
from pathlib import Path
from handlers.rag_pipeline import rag_pipeline as rag
from handlers import prompt_handler as prompthandler
from handlers.logger import reset_log

script_path = Path(__file__).resolve()
script_directory = script_path.parent

# Configure basic logging for the application
logs_path = script_directory / 'logs' / 'debug.log'
if not os.path.exists(logs_path):
    os.makedirs(logs_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app_logger = logging.getLogger(__name__)

# Constants for configurable items
RAG_DB_UPDATE_KEYWORD = "updateDB"
END_OF_MESSAGE_SENTINEL = "#END#"
ASSISTANT_HEADER_TOKEN = "assistant<|end_header_id|>"
GENIE_LOADER_SUCCESS = "200"

def update_rag_db(documents_path, config):
    st.session_state.rag_db_status = "Updating RAG database..."
    app_logger.info(f"Triggering RAG database update from {documents_path}...")

    with st.spinner("Processing documents and updating RAG knowledge base... This may take a moment."):
        try:
            rag(config['keywords'][RAG_DB_UPDATE_KEYWORD])
            st.session_state.rag_db_status = "Database updated successfully!"
            st.success("RAG database updated successfully!")
            app_logger.info("RAG database updated successfully.")
        except Exception as e:
            st.session_state.rag_db_status = f"Update failed: {e}"
            st.error(f"Failed to update RAG database: {e}")
            app_logger.error(f"Failed to update RAG database: {e}")
        finally:
            pass

# Load configuration from YAML file
if "config" not in st.session_state:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, 'config.yaml')
    try:
        app_logger.info("Loading configuration...")
        with open(config_file, 'r') as file:
            st.session_state.config = yaml.safe_load(file)
            app_logger.info("Configuration loaded successfully.")
    except FileNotFoundError:
        error_msg = f"Error: Configuration file '{config_file}' not found."
        app_logger.critical(error_msg)
        st.error(error_msg + " Please ensure 'config.yaml' exists in the script directory.")
        st.stop()
    except yaml.YAMLError as e:
        error_msg = f"Error: Failed to parse configuration file - {e}"
        app_logger.critical(error_msg)
        st.error(error_msg + " Please check your 'config.yaml' syntax.")
        st.stop()

# Initialize RAG status in session state
if "rag_enabled" not in st.session_state:
    st.session_state.rag_enabled = False
if "rag_db_status" not in st.session_state:
    st.session_state.rag_db_status = ""

# Define the documents directory relative to the script
script_dir = os.path.dirname(os.path.abspath(__file__))
documents_dir = script_directory.parent / 'documents'
documents_path = Path(documents_dir).resolve()

# Create the documents directory if it doesn't exist
os.makedirs(documents_path, exist_ok=True)
app_logger.info(f"Documents directory: {documents_path}")


# Initialize the chat application
if "_init" not in st.session_state:
    reset_log()
    app_logger.info("Application initialization started.")

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Define genie_loader path
        genie_loader = os.path.join(script_dir, "handlers", "genie_loader.py")
        genie_dll_path = st.session_state.config['dir']['QNN_SDK'] + st.session_state.config['dir']['dll_path']
        genie_bundle_path = os.path.join(script_dir, "..", "genie_bundle")

        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        stdout_path = os.path.join(log_dir, 'genieloader_output.log')

        # pyarm_path handling
        pyarm_path = os.path.join(script_dir, "..", ".venv_arm64", "Scripts", "python.exe")
        if not os.path.exists(pyarm_path):
            app_logger.warning(f"Default pyarm_path '{pyarm_path}' not found. Checking config.yaml for alternative.")
            try:
                pyarm_path = st.session_state.config['dir']['pyarm']
                if not os.path.exists(pyarm_path):
                    error_msg = (
                        "Error: Python ARM environment not found. "
                        f"Please check the path: '{pyarm_path}' specified in config.yaml, "
                        "or ensure '.venv_arm64' is correctly set up. Refer to setup instructions."
                    )
                    app_logger.critical(error_msg)
                    st.error(error_msg)
                    st.stop()
            except KeyError:
                error_msg = (
                    "Error: 'pyarm' path not found in config.yaml under 'dir'. "
                    "Please configure the path to your Python ARM environment. Refer to setup instructions."
                )
                app_logger.critical(error_msg)
                st.error(error_msg)
                st.stop()

        # genie_bundle path handling
        genie_bundle_path = os.path.join(script_dir, "..", "genie_bundle", "genie_config.json")
        if not os.path.exists(genie_bundle_path):
            app_logger.warning(f"Default genie_bundle path '{genie_bundle_path}' not found. Checking config.yaml for alternative.")
            try:
                genie_bundle_path = st.session_state.config['dir']['genie_bundle']
                app_logger.info(f"Trying to use '{genie_bundle_path}' from config.yaml.")
                if not os.path.exists(genie_bundle_path):
                    error_msg = (
                        "Error: genie_bundle not found. "
                        f"Please check the path: '{genie_bundle_path}' specified in config.yaml, "
                        "or ensure 'genie_bundle' is correctly set up. Refer to Readme.md for instructions on preparing Genie_bundle."
                    )
                    app_logger.critical(error_msg)
                    st.error(error_msg)
                    st.stop()
            except KeyError:
                error_msg = (
                    "Error: 'genie_bundle' path not found in config.yaml under 'dir'. "
                    "Please configure the path to your genie_bundle. Refer to Readme.md for instructions on preparing Genie_bundle."
                )
                app_logger.critical(error_msg)
                st.error(error_msg)
                st.stop()

        # Run the genie_loader.py script in the different Python environment (Python for ARM)
        app_logger.info(f"Starting genie_loader.py using {pyarm_path}...")
        with open(stdout_path, 'w') as stdout_f:
            process = subprocess.Popen(
                [pyarm_path, genie_loader, genie_dll_path, genie_bundle_path,
                 st.session_state.config['socket']['addr'],
                 str(st.session_state.config['socket']['port'])],
                stdout=stdout_f,
                stderr=subprocess.STDOUT
            )

        time.sleep(1)
        app_logger.info(f"Attempting to connect to socket at {st.session_state.config['socket']['addr']}:{st.session_state.config['socket']['port']}")
        client_socket.connect((st.session_state.config['socket']['addr'], st.session_state.config['socket']['port']))
        st.session_state.client_socket = client_socket
        app_logger.info(f"Socket connected: {st.session_state.client_socket.getsockname()}")

        st.info("Waiting for model to initialize... This may take a moment.")
        genie_status = st.session_state.client_socket.recv(4096).decode('utf-8')
        if genie_status == GENIE_LOADER_SUCCESS:
            genie_status = ""
            st.session_state._init = 1
            st.success("Application Initialized and Genie Loader started!")
            app_logger.info("Application initialization completed successfully.")

    except socket.error as e:
        error_msg = f"Error: Failed to connect to model server socket - {e}. Is the genie_loader running and listening?"
        app_logger.critical(error_msg)
        st.error(error_msg)
        st.stop()
    except Exception as e:
        error_msg = f"An unexpected error occurred during initialization: {e}"
        app_logger.critical(error_msg, exc_info=True)
        st.error(error_msg)
        st.stop()

if "client_socket" not in st.session_state or \
   st.session_state.client_socket.fileno() == -1:
    app_logger.warning("Client socket not found or closed. Attempting to reconnect...")
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((st.session_state.config['socket']['addr'], st.session_state.config['socket']['port']))
        st.session_state.client_socket = client_socket
        st.info("Reconnected to model server.")
        app_logger.info("Reconnection successful.")
    except Exception as e:
        error_msg = f"Failed to reconnect to model server: {e}. Please restart the application if issues persist."
        app_logger.error(error_msg)
        st.error(error_msg)
        st.stop()

# --- Streamlit UI Begins Here ---
st.title("NPU-Chatbot with Local RAG")

# --- RAG Section in Sidebar ---
with st.sidebar:
    st.header("Retrieval Augmented Generation (RAG) Settings")
    st.markdown(f"Document storage directory: \n`{documents_path}`")

    # Toggle switch for RAG
    st.session_state.rag_enabled = st.checkbox(
        "Enable RAG (Retrieval Augmented Generation)",
        value=st.session_state.rag_enabled,
        help="When enabled, the model will try to retrieve information from uploaded documents."
    )
    if st.session_state.rag_enabled:
        st.info("RAG is **ENABLED**.")
    else:
        st.warning("RAG is **DISABLED**.")

    with st.form("Upload Documents (PDF only)", clear_on_submit=True):
        st.header("Upload your documents")
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type="pdf",
            accept_multiple_files=True,
            help="Upload PDF documents to be included in the RAG knowledge base."
        )
        submit_button = st.form_submit_button(label="Upload")
        if submit_button:
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    file_path = documents_path / uploaded_file.name
                    try:
                        if not file_path.resolve().is_relative_to(documents_path.resolve()):
                            st.error(f"Attempted path traversal detected: {uploaded_file.name}")
                            app_logger.warning(f"Path traversal attempt blocked: {uploaded_file.name}")
                            continue

                        with open(file_path, "wb") as f:
                            shutil.copyfileobj(uploaded_file, f)
                        st.success(f"Uploaded `{uploaded_file.name}` to `{documents_path.name}`")
                        app_logger.info(f"Uploaded {uploaded_file.name} to {documents_path}")
                    except Exception as e:
                        st.error(f"Error uploading `{uploaded_file.name}`: {e}")
                        app_logger.error(f"Error uploading {uploaded_file.name}: {e}")

    st.subheader("Update RAG Knowledge Base")
    st.write("Click the button below to process newly uploaded documents and update the RAG database.")

    if st.session_state.rag_db_status:
        st.info(st.session_state.rag_db_status)

    if st.button("Update RAG Database"):
        update_rag_db(documents_path, st.session_state.config)

# --- Chat Interface Begins Here ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Let's start Conversation! 👇"}]

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up? please type 'exit' to quit the application"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
        if prompt.lower() == st.session_state.config['keywords']['exit_prompt']:
            try:
                st.session_state.client_socket.send("exit".encode())
                st.session_state.client_socket.close()
                app_logger.info("User initiated exit. Socket closed.")
                st.success("Chat session ended. Goodbye!")
                st.stop()
            except Exception as e:
                st.warning(f"Could not send exit command or close socket cleanly: {e}")
                app_logger.warning(f"Error during graceful exit: {e}")
                st.stop()

        # Pass the RAG status to the prompt handler
        _gen_prompt = prompthandler.prompt_handler(
            prompt,
            st.session_state.config['keywords']['bot_name'],
            st.session_state.rag_enabled
        )
        gen_prompt = _gen_prompt.encode('utf-8')
        app_logger.info(f"Sending prompt: {gen_prompt[:100]}...")

        try:
            st.session_state.client_socket.sendall(gen_prompt)
            app_logger.info("Message sent to model server.")
        except socket.error as e:
            error_msg = f"Network error: Could not send message to model server. Is the server running? ({e})"
            st.error(error_msg)
            app_logger.error(error_msg, exc_info=True)
            st.session_state.client_socket = None
            st.stop()

    with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            try:
                received_data = ""
                while True:
                    chunk = st.session_state.client_socket.recv(4096).decode('utf-8')
                    if not chunk:
                        app_logger.warning("Socket connection closed by peer during receive.")
                        break
                    received_data += chunk

                    if END_OF_MESSAGE_SENTINEL in received_data:
                        break

                    full_response = received_data.replace(END_OF_MESSAGE_SENTINEL, '') \
                             .replace(ASSISTANT_HEADER_TOKEN, '') \
                             .strip()
                    message_placeholder.markdown(full_response + "▌")
                
                # Final cleanup for chat history
                full_response = received_data.replace(END_OF_MESSAGE_SENTINEL, '') \
                             .replace(ASSISTANT_HEADER_TOKEN, '') \
                             .strip()
                message_placeholder.markdown(full_response)
                app_logger.info("Received response from model server.")

            except socket.error as e:
                error_msg = f"Network error: Could not receive message from model server. ({e})"
                st.error(error_msg)
                app_logger.error(error_msg, exc_info=True)
                st.session_state.client_socket = None
                full_response = "Error: Could not get a response from the model."
            except Exception as e:
                error_msg = f"An unexpected error occurred while receiving response: {e}"
                st.error(error_msg)
                app_logger.error(error_msg, exc_info=True)
                full_response = "Error: An internal error occurred."

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
