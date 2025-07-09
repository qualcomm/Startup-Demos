# Playground Chat + RAG + ChromaDB Demo Application

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Setup Instructions](#%EF%B8%8F-setup-instructions)
  - [Miniconda Installation](#-miniconda-installation)
  - [Git Configuration](#-git-configuration)
- [Environment Setup](#-environment-setup)
- [Getting API Access](#-getting-api-access)
  - [Cloud AI Playground](#%EF%B8%8F-cloud-ai-playground)
  - [Allam Playground](#-allam-playground)
- [Set the API Key in Environment (Optional)](#%EF%B8%8F-set-the-api-key-in-environment-optional)
- [Run the Application](#-run-the-application)
  - [Application Demo](#-8-application-demo)



---

## Overview

This demo application demonstrates how to integrate a Large Language Model (LLM) with Retrieval-Augmented Generation (RAG) using ChromaDB as the vector store. It enables users to query documents using natural language and receive contextually enriched responses.

---

## Features

- Modular RAG pipeline with pluggable components.
- ChromaDB integration for fast and scalable vector search.
- Support for multiple LLM backends (e.g., Cloud AI Playground, Allam Playground, Custom).
- Choose between various models.

---

# 🛠️ Setup Instructions

Before proceeding further, please ensure that **all the setup steps outlined below are completed in the specified order**. These instructions are essential for configuring the various tools required to successfully run the application.

Each section provides a reference to internal documentation for detailed guidance. Please follow them carefully to avoid any setup issues later in the process.

---

## 📦 Miniconda Installation

Miniconda is required to manage the application's Python environment and dependencies. Please follow the setup instructions carefully to ensure a consistent and reproducible environment.

For detailed steps, refer to the internal documentation:  
[Set up Miniconda]( ../../../Hardware/Tools.md#miniconda-setup)

## 🔧 Git Configuration

Git is required for version control and collaboration. Proper configuration ensures seamless integration with repositories and development workflows.

For detailed steps, refer to the internal documentation:  
[Setup Git]( ../../../Hardware/Tools.md#git-setup)

---
## 🧪 Environment Setup

To set up the Python environment required for running the application, follow the steps below. This ensures all dependencies are installed in an isolated and reproducible environment.

### 🔧 Steps

1. **Create your working directory** :
   ```bash
   mkdir my_working_directory
   cd my_working_directory
   ```

1. **Download Your Application** :
   ```bash
   git clone -n --depth=1 --filter=tree:0 https://github.com/qualcomm/Startup-Demos.git
   cd Startup-Demos
   git sparse-checkout set --no-cone /GenAI/CloudAI-Playground/ChatBot_LLM_RAG
   git checkout
   ```
   
1. **Navigate to Application Directory** :
   ```bash
   cd ./GenAI/CloudAI-Playground/ChatBot_LLM_RAG
   ```

1. **Create a new Conda environment** with Python 3.12:
   ```bash
   conda create -n myenv python=3.12
   ```

1. **Activate the environment**:
   ```bash
   conda activate myenv
   ```

1. **Install the required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

> 💡 Make sure you have Miniconda or Anaconda installed before running these commands.

## 🔑 Getting API Access

To use the application features that rely on external AI services, you need to obtain API keys from the respective playgrounds. Follow the instructions below for each platform.

### ☁️ Cloud AI Playground

To retrieve your API key for the Cloud AI Playground, refer to the documentation: 
[API Key for Cloud AI Playground](../../../Hardware/Cloud%20AI%20Playground.md#APIKey-for-CloudAI-Playground)

### 🧠 Allam Playground

To retrieve your API key for the Cloud AI Playground, refer to the documentation: 
[API Key for Allam Playground](../../../Hardware/Cloud%20AI%20Playground.md#APIKey-for-Allam-Playground)

> Once you have obtained the keys, make sure to securely store them in your environment configuration or secrets manager as per your project’s security guidelines.

## 🛡️ Set the API Key in Environment (Optional)

To securely manage your API keys, it is recommended to store them as environment variables. This approach helps avoid hardcoding sensitive information in your codebase.

### 🔧 How to Set Environment Variables
For instructions on setting environment variables on your system, refer to the documentation:  
[Setup Environment Variables](../../../Hardware/Tools.md#setup-environment-variables)

> 💡 Once set, your application can access the API key using standard environment variable access methods in your programming language (e.g., `os.environ` in Python).

## 🚀 Run the Application

To launch the application, execute the following command from the application directory:

```bash
streamlit run .\src\ChatApp.py
```

This will start the interactive web interface where you can configure and use the application.

---

### 🧠 1. Select LLM Instance

Choose the Large Language Model (LLM) provider you want to use (e.g., CloudAI Playground, Allam Playground, etc.). This determines the backend service that will process your queries.

![N|Solid](./images/SelectLLMInstance.png)

---

### 🔐 2. Configure API Key

Enter the API key associated with the selected LLM instance. This is required to authenticate and access the model's capabilities.

![N|Solid](./images/ConfigureLLMAPIKey.png)

---

### 🧬 3. Select LLM Model

After selecting the provider, choose the specific model (e.g., `Llama-3.3-70B`, `Llama-3.1-8B`, etc.) that best suits your use case.

![N|Solid](./images/SelectLLMModel.png)

---

### 🧠 4. Select Embedding Instance and Configure API Key *(Optional)*

If your workflow involves document embeddings (e.g., for semantic search), select the embedding service provider and configure its API key.

![N|Solid](./images/SelectEmbInstance.png)

---

### 🧬 5. Select Embedding Model

Choose the embedding model (e.g., `BAAI/bge-base-en-v1.5`) to convert your documents into vector representations.

![N|Solid](./images/SelectEMBModel.png)

---

### 📄 6. Upload Your PDF File

Upload one or more PDF documents that you want the application to process. These documents will be parsed and embedded for querying.

![N|Solid](./images/UploadPDF.png)

---

### 🗃️ 7. Choose Options for Use and Configure Database

Decide how you want to manage the document data in the vector database. The following options are available:

1. **Use Existing** – Query the existing database without modifying it.
2. **Add to Existing Database** – Append new documents to the current database.
3. **Generate New Database** – Clear existing data and create a new database from uploaded files.
4. **Clear Database** – Remove all data from the current database.
5. **No Database** – Skip database usage and query the LLM directly.
6. **Clear Chat History** – Reset the current chat session.

![N|Solid](./images/GenerateDataBase.png)

---
### ✅ 8. Application Demo
> ✅ Once all configurations are complete, you can begin interacting with the application through the chat interface.

![N|Solid](./images/PlaygroundDemo.gif)

