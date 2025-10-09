# Convert your Pre-trained YoloV4 model with .cfg and .weights to Pytorch and Onnx format for Object detection inference on AIPC CPU or GPU

## Table of Contents
- [Overview](#1-overview)
- [Features](#2-features)
- [Clone the YoloV4 example repo](#3-clone-the-yolov4-example-repo)
- [Go to the pytorch-YOLOv4 folder and put the python codes there](#4-go-to-the-pytorch-yolov4-folder-and-put-the-python-codes-there)
- [Convert your pre-trained YoloV4 cfg and weights](#5-convert-your-pre-trained-yolov4-cfg-and-weights)
- [Covert pt to onnx](#6-covert-pt-to-onnx)
- [Run YoloV4 inference](#7-run-yolov4-inference)

---

# 1. Overview

Due to YoloV4 model is not supported on Qualcomm AI Hub, this guide provides an example to run Pre-trained Yolov4 onnx model on CPU or GPU for Qualcomm AIPC.

---

# 2. Features

- YoloV4 darknet backbone for Object Detection.
- Pre-trained yolov4.cfg and yolov4.weights files convert to yolov4.pt format.
- yolov4.pt file convert to yolov4.onnx format.
- Python code for .onnx inference.

---


# 3. Clone the YoloV4 example repo

```bash
git clone https://github.com/Tianxiaomo/pytorch-YOLOv4.git
```

# 4. Go to the pytorch-YOLOv4 folder and put the python codes there

```bash
cd pytorch-YOLOv4/
mv /path to .pt/convert2pytorch.py ./
mv /path to .pt/export_trace_and_onnx.py ./
```

# 5. Convert your pre-trained YoloV4 cfg and weights 

```bash
python convert2pytorch.py
```

# 6. Covert pt to onnx

```bash
python export_trace_and_onnx.py
```

# 7. Run YoloV4 inference

```bash
python inference_yolov4_onnx.py
```




