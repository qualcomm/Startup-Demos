# [Startup_Demo](../../../)/[GenAI](../../)/[CloudAI-Playground](../)/[online_server_endpoint_stream](./)

# Online OpenAI-Compatible Streaming Server on AIC100 Ultra

## Table of Contents
- [1. Overview](#1-overview)
- [2. Requirements](#2-requirements)
  - [2.1 Hardware](#21-hardware)
  - [2.2 Software](#22-software)
- [3. Model Optimization & Inference Stack](#3-model-optimization--inference-stack)
- [4. System Workflow](#4-system-workflow)
- [5. Setup Instructions](#5-setup-instructions)
  - [5.1 Clone the Project](#51-clone-the-project)
  - [5.2 Download Pre-compiled Model (QPC)](#52-download-pre-compiled-model-qpc)
  - [5.3 Prepare Target Folder](#53-prepare-target-folder)
  - [5.4 Pull Docker Image](#54-pull-docker-image)
  - [5.5 Run Server Container](#55-run-server-container)
- [6. Run the Demo](#6-run-the-demo)
  - [6.1 Launch Server Endpoint](#61-launch-server-endpoint)
  - [6.2 Run Streaming Client](#62-run-streaming-client)
- [7. Demo Output](#7-demo-output)

---
## 1. Overview
This sample demonstrates an **on‑prem OpenAI‑compatible online inference endpoint with streaming support (`stream=true`)** running on **Qualcomm Cloud AI 100 Ultra (AIC100 Ultra)**.

It uses **vLLM with QAIC backend** to serve **Llama 3.3 70B (32K context length)** and supports token‑by‑token streaming responses suitable for chat, agent, and interactive applications.

---
## 2. Requirements
### 2.1 Hardware
This sample targets **on‑prem deployment** using dedicated AI accelerators.

- Qualcomm **Cloud AI 100 Ultra (AIC100 Ultra)** PCIe cards
- Devices exposed as `/dev/accel/accel*`
- Optimized for **LLM inference** workloads

Reference:
https://www.qualcomm.com/artificial-intelligence/data-center/cloud-ai-100-ultra#Overview

### 2.2 Software
- Ubuntu Linux host
- Docker
- Qualcomm Cloud AI SDK (Platform & Apps) **v1.20.2**
- vLLM (QAIC backend)


### Hardware Status Check (QAIC)

Before proceeding with Docker containers or launching the vLLM server,  
**verify that the Cloud AI 100 Ultra card and Cloud AI SDK are functioning correctly**.

Run the following command on the host system:

```bash
sudo /opt/qti-aic/tools/qaic-util -t 1
```
Expected behavior:

QAIC devices are detected successfully
No error messages are reported
Driver, firmware, and SDK are operating normally


![N|Solid](./card_status.jpg)

---

## 3. Model Optimization & Inference Stack
This sample uses the standard Qualcomm Cloud AI software stack:

- **Cloud AI SDK (Platform & Apps)**: device drivers, runtime, and tooling

Reference (Software section):
https://www.qualcomm.com/artificial-intelligence/data-center/cloud-ai-100-ultra#Software
- **Efficient Transformer Library**: Transformer optimizations for QAIC

Documentation: https://quic.github.io/efficient-transformers/source/release_docs.html

Validated models: https://quic.github.io/efficient-transformers/source/validate.html
- **vLLM**: OpenAI‑compatible serving with streaming support

Reference:
https://quic.github.io/cloud-ai-sdk-pages/latest/Getting-Started/Installation/vLLM/vLLM/
- **Pre‑compiled QPC artifacts** for fast bring‑up

Model catalog:
http://qualcom-qpc-models.s3-website-us-east-1.amazonaws.com/QPC/catalog-index/

---
## 4. System Workflow
```mermaid
flowchart LR
    Client -->|"OpenAI API (stream=true)"| vLLM_Server
    vLLM_Server --> QAIC[AIC100 Ultra]
    QAIC -->|"Token generation"| vLLM_Server
    vLLM_Server -->|"Streaming tokens"| Client
```

---
## 5. Setup Instructions
### 5.1 Clone the Project
Clone the sample project and prepare a working directory:
```bash
mkdir /home/qitc/yourfolder/
cd /home/qitc/yourfolder/
git clone -n --depth=1 --filter=tree:0 https://github.com/qualcomm/Startup-Demos.git
cd Startup-Demos
git sparse-checkout set --no-cone /GenAI/CloudAI-Playground/online_server_endpoint_stream/
git checkout
cd GenAI/CloudAI-Playground/online_server_endpoint_stream
```

---
### 5.2 Download Pre-compiled Model (QPC)
Download the pre‑compiled Llama 3.3 70B QPC artifact:
```
https://qualcom-qpc-models.s3-accelerate.amazonaws.com/SDK1.20.2/meta-llama/Llama-3.3-70B-Instruct/qpc_16cores_128pl_32768cl_1fbs_4devices_mxfp6_mxint8.tar.gz
```

Extract it:
```bash
tar -xzvf qpc_*.tar.gz -C /home/qitc/yourfolder/
```

---
### 5.3 Prepare Target Folder
Copy the streaming client example into the same target folder as the QPC:
```bash
cp openai_client_stream.py /home/qitc/yourfolder/
```

---
### 5.4 Pull Docker Image
```bash
docker pull ghcr.io/quic/cloud_ai_inference_ubuntu22:1.20.2.0
```

---
### 5.5 Run Server Container
```bash
docker run -dit --name qaic-server   --device=/dev/accel/accel0   --device=/dev/accel/accel1   --device=/dev/accel/accel2   --device=/dev/accel/accel3   -v /home/qitc/yourfolder/:/home/qitc/yourfolder/   -p 8000:8000   ghcr.io/quic/cloud_ai_inference_ubuntu22:1.20.2.0
```

---
## 6. Run the Demo
### 6.1 Launch Server Endpoint
Inside the container:
```bash
docker exec -it qaic-server /bin/bash
source /opt/vllm-env/bin/activate
python -m vllm.entrypoints.openai.api_server   --host 0.0.0.0   --port 8000   --model meta-llama/Llama-3.3-70B-Instruct   --device qaic   --quantization mxfp6   --kv-cache-dtype mxint8   --override-qaic-config "qpc_path=/path-to-target-folder/qpc"
```
![N|Solid](./server_start.jpg)


---
### 6.2 Run Streaming Client
In another terminal (or same container):
```bash
docker exec -it qaic-server /bin/bash
source /opt/vllm-env/bin/activate
python /home/qitc/yourfolder/openai_client_stream.py
```

---
## 7. Demo Output
- Server starts successfully and listens on port `8000`
- Client receives **token‑by‑token streaming output**

![N|Solid](./client_inference.gif)
