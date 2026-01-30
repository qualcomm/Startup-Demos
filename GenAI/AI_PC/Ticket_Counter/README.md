## [Startup_Demo](../../../)/[GenAI](../../)/[AI PC](../)/[Ticket Counter](./)

---

# Ticket Counter

## Table of Contents
- [1. Overview](#1-overview)
- [2. Features](#2-features)
- [3. Setup Instructions](#3-setup-instructions)
  - [3.1 Miniconda Installation](#31-miniconda-installation)
  - [3.2 Git Configuration](#32-git-configuration)
  - [3.3 AnythingLLM Configuration](#33-anythingllm-configuration)
- [4. Environment Setup](#4-environment-setup)
- [5. File Structure](#5-file-structure)
- [6. Usage](#6-usage)
- [7. Run the Application](#7-run-the-application)
  - [7.1 Initialize the database](#71-initialize-the-database)
  - [7.2 Launch the Streamlit Application](#72-launch-the-streamlit-application)
  - [7.3. Navigating the Ticketing Assistant Interface](#73-navigating-the-ticketing-assistant-interface)
---

# 1. Overview

A voice-driven ticket counter assistant built with Streamlit, Whisper ONNX, and LLaMA integration. It helps users inquire about ticketing details through speech, providing transcription, route insights, fare estimation, and QR-based ticket metadata for reference. The assistant also offers contextual destination insights, supports admin visibility through an editable dashboard, and generates ticket summaries for operational tracking and user assistance

---

## 2. Features

- 🎙️ Voice Recording: Capture speech using selected microphone devices.
- 🧠 Whisper Transcription: Convert speech to text using ONNX Whisper models.
- 🧾 LLaMA Extraction: Extract source, destination, and ticket count from transcribed text.
- 🏙️ City List: Displays supported cities from a SQLite database.
- 💰 Fare Estimation: Calculates fare and platform based on route and ticket count.
- 📦 QR Code Generation: Generates QR code with ticket metadata for reference.
- 🧭 Travel Insights: Provides contextual information about destinations using LLaMA.
- 🗃️ Ticket Logging: Stores ticket metadata and transcription in SQLite.
- 🔐 Configurable Settings: Sidebar UI for API keys, model paths, and recording options.

---

# 3. Setup Instructions

Before proceeding further, please ensure that **all the setup steps outlined below are completed in the specified order**. These instructions are essential for configuring the various tools required to successfully run the application.

Each section provides a reference to internal documentation for detailed guidance. Please follow them carefully to avoid any setup issues later in the process.

---

## 3.1 Miniconda Installation

Miniconda is required to manage the application's Python environment and dependencies. Please follow the setup instructions carefully to ensure a consistent and reproducible environment.

For detailed steps, refer to the internal documentation:  
[Set up Miniconda]( ../../../Hardware/Tools.md#miniconda-setup)

## 3.2 Git Configuration

Git is required for version control and collaboration. Proper configuration ensures seamless integration with repositories and development workflows.

For detailed steps, refer to the internal documentation:  
[Setup Git]( ../../../Hardware/Tools.md#git-setup)

## 3.3 AnythingLLM Configuration

AnythingLLM is required as the backend server for this application. You need access to a running AnythingLLM instance to provide the LLM and RAG capabilities.

You can use either a local or remote AnythingLLM server:

- **Local:** Follow the [AnythingLLM installation guide](https://github.com/Mintplex-Labs/anything-llm#installation) to set up and run the server on your machine.
- **Remote:** Obtain the API URL and API key from your administrator.

For detailed setup instructions, refer to the below steps

### ✅ Step-by-Step: Create Workspace in AnythingLLM

**🖥️ 1. Launch AnythingLLM**
   - Open the AnythingLLM Desktop App or access your self-hosted instance in a browser.

**🆕 2. Create a New Workspace**
   - Click on “New Workspace”.
   - Enter a Workspace Name (e.g., test).
   - Click Create.

**⚙️ 3. Configure the Workspace**
   - Go to the Workspace Settings.
   - Navigate to Agent Configuration.
   - Under LLM Provider, select AnythingLLM NPU (or your preferred provider).
   - Choose your model (e.g., LLaMA 3.1).
   - Click Update Workspace Agent.

**🔑 Step-by-Step: Get API Key and Base URL**
   - 🔐 4. Generate API Key
   - Go to Settings → API Keys.
   - Click “Generate New API Key”.
   - Copy the key and store it securely.

### 🧪 Testing in AnythingLLM Chat

Once your workspace is created and configured:

- Go to the Chat tab in AnythingLLM.
- Select your workspace from the dropdown.
- Type a message (e.g., “What is the capital of Karnataka?”).
- The response should come from the configured LLaMA model.
---

# 4. Environment Setup

To set up the Python environment required for running the application, follow the steps below. This ensures all dependencies are installed in an isolated and reproducible environment.

## Steps

1. **Create your working directory**:
   ```bash
   mkdir my_working_directory
   cd my_working_directory
   ```

2. **Download and Prepare Whisper ONNX Models from Qualcomm AI-HUB**:

- This guide walks you through installing dependencies, exporting the Whisper ONNX model, and validating speech-to-text functionality on the Snapdragon X Elite platform.
 It includes setting up the Conda environment, installing FFmpeg, Python dependencies, QNN runtime, and downloading the Whisper-base model.

- Follow the [Run Whisper on Snapdragon X Elite guide](https://github.com/quic/ai-hub-apps/tree/main/apps/windows/python/Whisper#run-whisper-on-snapdragon-x-elite) to set up and export the whisper model from the qualcomm ai-hub-apps repository.

**Setup Steps**

- **Step 1**: Clone the repository - git clone https://github.com/quic/ai-hub-apps.git
- **Step 2**: Navigate to the Whisper app directory -cd ai-hub-apps/apps/windows/python/Whisper
- **Step 3**: Run the setup script to install all necessary dependencies.
- **Step 4**: Export the Whisper ONNX model using the provided script
- **Step 5**: Validate speech-to-text functionality using demo.py

**Move Build Directory to C Drive**

- After exporting the Whisper ONNX models, you will have a folder named build in your current working directory. To make it accessible for your application, `move it to the C drive`.

- Create the following repository structure to run the application.This will move the entire build directory — including the whisper_base model ONNX files, corresponding encoder/decoder folders, and model.bin — to `C:\build`.

  🔍 Resulting Structure

  ```
  C:\
  └── build\
      └── whisper_base\
          ├── HfWhisperEncoder\
          │   ├── model.onnx
          │   └── model.bin
          │
          ├── HfWhisperDecoder\
          │   ├── model.onnx
          │   └── model.bin
  ```

3. **Download Your Application**:
   ```bash
   git clone -n --depth=1 --filter=tree:0 https://github.com/qualcomm/Startup-Demos.git
   cd Startup-Demos
   git sparse-checkout set --no-cone /GenAI/AI_PC/Ticket_Counter
   git checkout
   ```

4. **Navigate to Application Directory**:
   ```bash
   cd ./GenAI/AI_PC/Ticket_Counter
   ```

5. **Install the required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

> 💡 Make sure you have Miniconda or Anaconda installed before running these commands.

---

# 5. File Structure

```
requirements.txt                 # Lists all Python dependencies needed to run the app

src/
│
├── init_db.py                   # Initializes the database schema and connections
├── app.py                       # Main entry point for the Streamlit app
│
└── modules/
    │
    ├── config/
    │   └── fares.json            # Contains fare configuration data and constants
    │
    ├── pages/
    │   ├── home.py              # Home page UI and logic
    │   ├── workspace.py         # Workspace for audio recording and transcription confirmation
    │   └── dashboard.py         # Dashboard for ticket insights, editing, cancellation, and CSV export
    │
    └── utils/
        ├── fare_utils.py        # Functions for fare calculation and validation
        ├── llm_utils.py         # Utilities for LLM-based natural language processing
        └── transcription_utils.py # Functions for handling audio transcription and error correction

```

# 6. Usage

The application provides two main interfaces:

### 🧭 Navigation Overview:

The assistant includes three main pages accessible via sidebar navigation:

**🎫 Workspace Page**:

- Select Recording duration and input device selection
- Enter the created workspace name
- Enter the API key generated from AnythingLLM
- Transcribe audio using Whisper ONNX.
- Confirm transcription accuracy.
- Extract source, destination, and ticket count using LLaMA.
- View fare, platform, and QR code metadata
- Download ticket metadata
- Access destination travel insights via LLaMA

**📊 Dashboard Page**:

- View all generated tickets with metadata
- Edit or cancel tickets
- Summarize ticketing activity
- Visualize insights using graphs (e.g., ticket trends, popular routes)
- Download ticket logs and summaries as CSV files
---

# 7. Run the Application

To launch the voice-based ticketing assistant, follow these steps from the root application directory:

## 7.1 Initialize the database

This step sets up the necessary tables and schema for ticket storage and fare calculations.

```bash
python run src/init_db.py
```

## 7.2 Launch the Streamlit Application

Start the interactive UI for ticket assistance, voice transcription, and dashboard insights.

```bash
streamlit run src/app.py
```
This will start the interactive web interface where you can configure and use the application.

## 7.3. Navigating the Ticketing Assistant Interface

- The application uses the Whisper model to transcribe user voice inputs into text.
- This transcribed text is then processed by AnythingLLM models, which generate intelligent responses — including automatic detection and correction of source and destination locations, and provide destination-specific insights.
- To enable this functionality, you must provide a valid API key for the AnythingLLM integration

![N|Solid](./Images/ticket_counter_output.gif)

---
