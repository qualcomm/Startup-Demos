# NPU Chatbot + Local RAG

## Table of Contents
- [1. Overview](#1-overview)
- [2. Features](#2-features)
- [3. Requirements](#3-requirements)
- [4. Setup Instructions](#4-setup-instructions)
  - [4.1 Python Installation](#41-python-installation)
  - [4.2 Git Configuration](#42-git-configuration)
- [5. Environment Setup](#5-environment-setup)
- [6. File Structure](#6-file-structure)
- [7. Run the Application](#7-run-the-application)


# 1. Overview

Chat application for Windows on Snapdragon® demonstrating a large language model (LLM, e.g., [Llama 3.1 8B](https://aihub.qualcomm.com/compute/models/llama_v3_1_8b_instruct)) using Genie SDK.

The app demonstrates how to use the Genie APIs from [QAIRT SDK](https://qpm.qualcomm.com/#/main/tools/details/Qualcomm_AI_Runtime_SDK) to run and accelerate LLMs using the Snapdragon® Neural Processing Unit (NPU).

# 2. Features
- **Chat with Local LLM**: Conversational interface powered by LLMs running locally via the Genie framework.
- **Genie Bundle Integration**: Seamlessly loads and utilizes `genie_bundle` definitions from `genie_config.json` for model inference.
- **Local RAG (Retrieval-Augmented Generation)**: Facilitates RAG implementation with local PDFs.

# 3. Requirements

### Platform

- Snapdragon® Platform (e.g. X-Elite)
- Windows 11+

### Genie Bundle

#### Compile to Context Binary via AI Hub and Generate Genie Bundle

1. Please follow [this tutorial](https://github.com/quic/ai-hub-apps/tree/main/tutorials/llm_on_genie)
to generate `genie_bundle` required by ChatApp. If you use any of the Llama 3 models, the app will work without modifications. If you use another model, you
will need to update the prompt format in `src\handlers\prompt_handler.py` first.

2. Copy bundle assets from step 1 to `NPU-Chatbot_LLM_RAG\genie_bundle`. You should see `NPU-Chatbot_LLM_RAG\genie_bundle\*.bin` context binary files.

**Note:** if `genie_bundle` saved in some other location, please update the `genie_bundle` path in `src\config.yaml`.

### Tools and SDK

- QAIRT SDK: [Qualcomm AI Runtime SDK](https://qpm.qualcomm.com/#/main/tools/details/Qualcomm_AI_Runtime_SDK) (see [QNN SDK](https://qpm.qualcomm.com/#/main/tools/details/qualcomm_ai_engine_direct) for older versions)
  - Refer to [Setup QAIRT SDK](#setup-qairt-sdk) to install compatible QAIRT SDK for models downloaded from AI Hub.

**Note:** please update the path QAIRT SDK root path in `src\config.yaml`.

# 4. Setup Instructions

Before proceeding, ensure that **all setup steps outlined below are completed in the specified order**. These instructions are critical for configuring the necessary tools and dependencies to successfully run the application.

Each section provides references to internal documentation or external guides for detailed guidance. Please follow them carefully to avoid any setup issues.

## 4.1 Python Installation

This application requires two different python environments to successfully run the application.
- python (64-bit) [Windows installer (64-bit)](https://www.python.org/downloads/windows/) for stramlit,chromaDB and RAG implementation
- python (ARM64) [Windows installer (ARM64)](https://www.python.org/ftp/python/3.13.5/python-3.13.5-arm64.exe) for loading generated context binaries on NPU using [Gen AI Inference Extensions (GENIE)](https://www.qualcomm.com/developer/software/gen-ai-inference-extensions) libraries.

## 4.2 Git Configuration

Git is required for version control and collaboration. Proper configuration ensures seamless integration with repositories and development workflows.

For detailed steps, refer to the internal documentation (or adjust to a public link if applicable):
[Setup Git]( ../../../Hardware/Tools.md#git-setup) <!-- Adjust path if needed -->

---

# 5. Environment Setup

To set up the environments required for running the application, follow the steps below.

## Steps

1.  **Create working directory (if not already done)**:
    ```bash
    mkdir <your_working_dir>
    cd <your_working_dir>
    ```

2. **Download Application**:
   ```bash
   git clone -n --depth=1 --filter=tree:0 https://github.com/qualcomm/Startup-Demos.git
   cd Startup-Demos
   git sparse-checkout set --no-cone /GenAI/AI_PC/NPU-Chatbot_LLM_RAG
   git checkout
   ```

3. **Navigate to Application Directory**:
   ```bash
   cd ./GenAI/AI_PC/NPU-Chatbot_LLM_RAG
   ```

4.  **Create the `venv` environments** 
- *with Python (64-bit):* 

   To create a virtual environment using a specific Python version (e.g., Python 3.10), run:

    ```bash
    "C:\path\to\AppData\Local\Programs\Python\Python310\python.exe" -m venv .venv
    ```

- *with Python (ARM64):*

   To create a virtual environment using a specific Python version (e.g., Python 3.13 arm64), run:

    ```bash
    "C:\path\to\AppData\Local\Programs\Python\Python313-arm64\python.exe" -m venv .venv_arm64
    ```
    
    The environment will be created in a directory named `.venv_arm64` and `.venv` at `NPU-Chatbot_LLM_RAG\`.

    **Note:** Recommend to create both the virtual environments at `NPU-Chatbot_LLM_RAG\`, if you are changing the path or the name of the `.venv_arm64`, please update the `pyarm` path in  path in `src\config.yaml` accordingly.

5.  **Activate the environment**:
    ```bash
    .venv\Scripts\activate
    ```

6.  **Install the required dependencies for the app**:
    ```bash
    pip install -r requirements.txt
    ```

7.  **To download embedding model locally**:
    ```bash
    py \src\handlers\initial_setup.py
    ```

# 6. File Structure

```
requirements.txt
src/
    config.yaml                 # Application configuration file
    streamlitchat.py            # Main entry point for the Streamlit app
    handlers/
        __init__.py
        genie_loader.py         # loads model from genie_bundle to the NPU
        initial_setup.py        # To download embedding model locally, one-time setup.
        logger.py               # Custom logging utility, Handles logging in different handlers files and generate logs at `src\logs\debug.log`
        prompt_handler.py       # Manages prompt
        rag_pipeline.py         # Manages RAG pipeline
```

# 7. Run the Application

To run the Streamlit application:

1.  **Activate the virtual environment**:

    **Note:** Please ensure that `.venv` environment is acticated.

    ```bash
    .venv\Scripts\activate
    ```

2.  **Run the Streamlit application**:
    ```bash
    cd src\
    streamlit run streamlitchat.py
    ```

This will launch the application in your default web browser. You can then navigate to the provided URL (usually `http://localhost:8501`) to interact with the LLM Chat and the upload the PDFs to interact.

### Application Demo

> ✅ Once all configurations are complete, you can begin interacting with the application through the chat interface.

![N|Solid](./images/Demo.gif)

---
