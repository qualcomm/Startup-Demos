#===--Object_Detection_ONNX.py--------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import onnxruntime
import numpy as np
import cv2
from class_ca import category
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('--onnx_path', type=str, required=True, help='Path to ONNX model')
parser.add_argument('--qnn_path', type=str, required=True, help='Path to QnnHtp.dll')
parser.add_argument('--video_path', type=str, required=True, help='Path to input video')
parser.add_argument('--conf_thres', type=float, default=0.5, help='Confidence threshold for NMS')
parser.add_argument('--iou_thres', type=float, default=0.4, help='IoU threshold for NMS')

args = parser.parse_args()

def main():
    options = onnxruntime.SessionOptions()

    # (Optional) Enable configuration that raises an exception if the model can't be run entirely on the QNN HTP backend.
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

    ep_options = {
                  "backend_path": args.qnn_path,
                  "enable_htp_fp16_precision": "1",
                  "htp_performance_mode": "burst",
                  "htp_graph_finalization_optimization_mode": "3"
                 }
                 
    # Create an ONNX Runtime session.
    try:
        session = onnxruntime.InferenceSession(args.onnx_path,
                                               sess_options=options,
                                               providers=["QNNExecutionProvider"],
                                               provider_options=[ep_options])

        outputs = session.get_outputs()[0].name
        inputs = session.get_inputs()[0].name
        
    except Exception as e:
        print(f"Error creating ONNX session: {e}")
        print("Please check that onnxruntime-qnn and QNN libraries are correctly installed and configured.")
        exit()
        
    cap = cv2.VideoCapture(args.video_path)

    if not cap.isOpened():
        print('No frame')
        exit()

    while True:
        ret, frame = cap.read()
        if not ret:
            print('Video ends')
            break
            
        resized_frame = cv2.resize(frame, (640, 640))
        input_frame = np.array(resized_frame, dtype=np.float32)

        # Ensure correct layout (NCHW) and re-scale
        input_array = np.expand_dims(np.transpose(input_frame / 255.0, (2, 0, 1)), axis=0)
        
        # Run the model with your input
        result = session.run(None, {inputs: input_array})
        boxes, confidences, ids = result

        class_wise_boxes = {}
        class_wise_confidences = {}
        class_wise_indices = {}

        unique_class_ids = np.unique(ids)

        for class_id in unique_class_ids:
            class_mask = ids == class_id
            class_boxes = boxes[class_mask]
            class_confidences = confidences[class_mask]
        
            indices = cv2.dnn.NMSBoxes(class_boxes.tolist(), class_confidences.tolist(), args.conf_thres, args.iou_thres)
            
            class_wise_boxes[class_id] = class_boxes
            class_wise_confidences[class_id] = class_confidences
            class_wise_indices[class_id] = indices

        for class_id in class_wise_indices:
            if len(class_wise_indices[class_id]) > 0:
                for i in class_wise_indices[class_id].flatten():
                    x1, y1, x2, y2 = (int(coord) for coord in class_wise_boxes[class_id][i])
                    confidence = class_wise_confidences[class_id][i]
                    cv2.rectangle(resized_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    text = f'{category[class_id]} {confidence:.2f}'
                    cv2.putText(resized_frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.imshow('YOLOv8 Video', resized_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
