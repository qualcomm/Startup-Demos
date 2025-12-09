# Object Detection Python CLI Application

## Table of contents
- [Overview](#1-overview)
- [Requirements](#2-requirements)
- [Preparing model assets](#3-preparing-model-assets)
- [Running Python app](#4-running-python-app)

## 1. Overview

Object detection application for Windows on Snapdragon® with [YOLOv8-Detection](https://aihub.qualcomm.com/compute/models/yolov8_det) using ONNX runtime.

Ultralytics YOLOv8 is a machine learning model that predicts object bounding boxes and classes in images. Optimized for Qualcomm Compute platform, this application enables real-time object detection.

This Python application demonstrates how to use [QNN Execution Provider](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html) to accelerate the model using the Snapdragon® Neural Processing Unit (NPU).

## 2. Requirements

### Platform

- Windows on Snapdragon® (Qualcomm Compute platform, e.g. X Elite and X Plus)
- Windows 11
- This application is tested on ASUS Vivobook S15 (S5507).

### Tools and SDK

- Python
   - This application is tested with Python 3.10.9.
   - Download and install [Python 3.10.9 64-bit](https://www.python.org/downloads/release/python-3109/) on your Windows on Snapdragon.
   - Required packages.
      - numpy
      - onnxruntime-qnn
      - opencv-python

- Qualcomm AI Runtime SDK : [QNN SDK](https://softwarecenter.qualcomm.com/)
  - The required QNN dependency libraries are included in onnxruntime-qnn package.
  - If you plan to use a specific version of QNN libraries, download and install Qualcomm AI Runtime SDK from Qualcomm Software Center.
  ![sample_input](./images/airt.png)
  - This Python application is tested with default QNN libraries from onnxruntime-qnn and QNN v2.39.0.250926.
  - Find your `QNN_SDK_ROOT`. For example, `QNN_SDK_ROOT = C:\Qualcomm\AIStack\QAIRT\2.39.0.250926`.
  - Remember this directory if you plan to use a specific version of QNN libraries.
      - `<QNN_SDK_ROOT>\lib\arm64x-windows-msvc`

## 3. Preparing model assets

### Compiling and downloading the model from Qualcomm AI Hub

Set up Python environment as described in [Qualcomm AI Hub](https://aihub.qualcomm.com/get-started).

Follow the [instruction](https://github.com/quic/ai-hub-models/tree/main/qai_hub_models/models/yolov8_det) and run the export script to produce a model optimized for on-device deployment.
```bash
python -m qai_hub_models.models.yolov8_det.export --device "Snapdragon X Elite CRD" --target-runtime onnx
```

After the compilation is finished, go to [Qualcomm AI Hub Jobs page](https://app.aihub.qualcomm.com/jobs/) to check compiled result and download the ONNX model and model.data file to `./assets/` directory.

![sample_input](./images/aihub.png)

### Video assets
Prepare your video assets and place into `./assets/` directory.

Model input resolution is 640 x 640.

If input video is in different resolution, it will be resized to 640 x 640.

## 4. Running Python app

### Checking the assets directory

Please ensure that you have followed the section above and placed the following assets into the specific directory. You may change the directory if needed.

   - Video assets : `./assets/`
   - ONNX model from Qualcomm AI Hub : `./assets/`
   
### Installing required Python packages

Open your terminal and navigate to the project directory.

```bash
pip install numpy onnxruntime-qnn opencv-python
```

### Running object detection app via CLI

The default confidence threshold and IoU threshold for NMS are 0.5 and 0.4, respectively.

Run the application with default QNN libraries from onnxruntime-qnn package.

```bash
python .\Object_Detection_ONNX.py --onnx_path .\assets\model.onnx --video_path .\assets\people_run.mp4
```

You can also run the application with a specific version of QNN libraries.

```bash
python .\Object_Detection_ONNX.py --onnx_path .\assets\model.onnx --video_path .\assets\people_run.mp4 --qnn_path C:\Qualcomm\AIStack\QAIRT\2.39.0.250926\lib\arm64x-windows-msvc\QnnHtp.dll
```
Running with the specified confidence and IoU thresholds for NMS.

```bash
python .\Object_Detection_ONNX.py --onnx_path .\assets\model.onnx --video_path .\assets\people_run.mp4 --conf_thres 0.6 --iou_thres 0.5
```

### Example Output

Inference is accelerated by Snapdragon® Neural Processing Unit (NPU).
![sample_output](images/output.png)
