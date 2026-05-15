#===------------------------main.py---------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
"""
Purpose
-------
This script performs **tile-based object detection** for large images using
GStreamer + Qualcomm IM SDK (qtimltflite + qtimlvdetection), with all
post-processing handled in Python for **maximum controllability and stability**.

High-level flow
---------------
1. Load a large input image (e.g. 4K)
2. Split the image into overlapping tiles (Python-controlled tiling)
3. For each tile, run a GStreamer pipeline:

   filesrc → decodebin → videoconvert → videocrop (tile)
   → qtimlvconverter → qtimltflite → qtimlvdetection
   → text/x-raw (utf8) → appsink

4. Parse qtimlvdetection's text output in Python
5. Convert per-tile detections back to global image coordinates
6. Apply **global class-aware NMS** across all tiles
7. Save results to JSON and an annotated output image

"""
import argparse
import json
import os
import time
from typing import List
from PIL import Image

# GStreamer (GI)
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib
from lib import plan_tiles, run_tile_pipeline_appsink, parse_qtimlvdetection_text, nms, draw_detections

def parse_args():
    p = argparse.ArgumentParser(
        description=(
            'Tile-based object detection for large images using a Python-constructed '
            'GStreamer pipeline with Qualcomm IM SDK (qtimltflite + qtimlvdetection). '
            'The input image is split into overlapping tiles, processed per-tile, and '
            'merged using global class-aware NMS.'
        )
    )

    # ---- Input / Model ----
    p.add_argument(
        '--image', required=True,
        help='Path to the input image file (e.g. high-resolution or 4K image).'
    )
    p.add_argument(
        '--model', required=True,
        help='Path to the TFLite object detection model.'
    )
    p.add_argument(
        '--labels', required=True,
        help='Path to the label file corresponding to the model.'
    )

    # ---- GStreamer / IM SDK ----
    p.add_argument(
        '--delegate', default='external', choices=['none', 'gpu', 'external'],
        help='TFLite delegate used by qtimltflite (default: external).'
    )
    p.add_argument(
        '--module', default='yolov8',
        help='Detection module name passed to qtimlvdetection (e.g. yolov8).'
    )
    p.add_argument(
        '--constants', required=True,
        help=('Model-specific constants for qtimlvdetection. '
            'Required for quantized models. '
            'Typically obtained by inspecting the model using Netron.')
    )
    p.add_argument(
        '--results', type=int, default=20,
        help='Maximum number of detection results per tile (default: 50).'
    )

    # ---- Tiling ----
    p.add_argument(
        '--tile', type=int, default=641,
        help='Tile size (width and height) in pixels (default: 641).'
    )
    p.add_argument(
        '--overlap', type=float, default=0.2,
        help='Overlap ratio between adjacent tiles (default: 0.2).'
    )

    # ---- Thresholds / NMS ----
    p.add_argument(
        '--score-thr', type=float, default=0.5,
        help='Score threshold for filtering detections (default: 0.25).'
    )
    p.add_argument(
        '--nms-iou', type=float, default=0.3,
        help='IoU threshold used for global NMS (default: 0.5).'
    )
    p.add_argument(
        '--no-global-nms', action='store_true',
        help='Disable global NMS and keep per-tile detection results.'
    )

    # ---- Detection Output Interpretation ----
    p.add_argument(
        '--assume-normalized', action='store_true',
        help=('Assume bounding boxes from qtimlvdetection are normalized '
            '(0~1 range). Enabled by default.')
    )
    p.set_defaults(assume_normalized=True)

    # ---- Pipeline / Debug ----
    p.add_argument(
        '--pre-engine', type=str, default='ocv',
        help='Pre-processing engine used by qtimlvconverter (default: ocv).'
    )
    p.add_argument(
        '--timeout', type=float, default=30.0,
        help='Timeout (in seconds) for each tile GStreamer pipeline execution.'
    )
    p.add_argument(
        '--gst-debug', type=str, default=None,
        help='GST_DEBUG level string for GStreamer debugging (optional).'
    )

    # ---- Outputs ----
    p.add_argument(
        '--raw-out-dir', type=str, default='./raw_text_tiles',
        help='Directory to save per-tile raw text output from appsink (optional).'
    )
    p.add_argument(
        '--no-save-raw', action='store_true',
        help='Do not save per-tile raw text outputs.'
    )
    p.set_defaults(no_save_raw=True)

    p.add_argument(
        '--out-json', type=str, default='./out.json',
        help='Path to save merged detection results in JSON format.'
    )
    p.add_argument(
        '--out-image', type=str, default='./out.jpg',
        help='Path to save the annotated output image.'
    )

    return p.parse_args()


def main():
    args = parse_args()

    Gst.init(None)

    if not args.no_save_raw:
        os.makedirs(args.raw_out_dir, exist_ok=True)

    img = Image.open(args.image).convert('RGB')
    W, H = img.size

    tiles = plan_tiles(W, H, tile=args.tile, overlap=args.overlap)
    do_crop = True

    all_dets: List[Detection] = []

    t0 = time.perf_counter()

    for tid, ts in enumerate(tiles):
        txt = run_tile_pipeline_appsink(
            image_path=args.image,
            model_path=args.model,
            labels_path=args.labels,
            W=W,
            H=H,
            tile=ts,
            delegate=args.delegate,
            module=args.module,
            constants=args.constants,
            threshold_percent=float(args.score_thr) * 100.0,
            results=args.results,
            pre_engine=args.pre_engine,
            timeout_sec=args.timeout,
            gst_debug=args.gst_debug,
        )

        if not args.no_save_raw:
            out_txt = os.path.join(args.raw_out_dir, f'tile_{tid:04d}.txt')
            with open(out_txt, 'w', encoding='utf-8', errors='replace') as f:
                f.write(txt)

        dets = parse_qtimlvdetection_text(
            text=txt,
            tile=ts if do_crop else TileSpec(0, 0, W, H),
            tile_id=tid,
            score_thr=args.score_thr,
            assume_normalized=args.assume_normalized,
        )
        all_dets.extend(dets)

    t1 = time.perf_counter()

    merged = all_dets if args.no_global_nms else nms(all_dets, iou_thr=args.nms_iou, class_aware=True)

    t2 = time.perf_counter()

    meta = {
        'image': {'path': args.image, 'width': W, 'height': H},
        'tile': {'size': args.tile, 'overlap': args.overlap, 'count': len(tiles), 'cropping_in_pipeline': bool(do_crop)},
        'gst': {
            'delegate': args.delegate,
            'model': args.model,
            'module': args.module,
            'results': int(args.results),
            'threshold_sent_to_qtimlvdetection': float(args.score_thr) * 100.0,
            'text_caps': 'text/x-raw,format=utf8',
            'sink': 'appsink',
        },
        'thresholds': {'score': args.score_thr, 'nms_iou': args.nms_iou},
        'timing': {'gst_total_sec': t1 - t0, 'postprocess_sec': t2 - t1, 'end_to_end_sec': t2 - t0},
        'counts': {'raw_dets': len(all_dets), 'merged_dets': len(merged)},
        'raw_out_dir': None if args.no_save_raw else args.raw_out_dir,
    }

    print('[Summary]')
    print(json.dumps(meta, indent=2, ensure_ascii=False))

    with open(args.out_json, 'w', encoding='utf-8') as f:
        json.dump({'meta': meta, 'detections': [d.as_dict() for d in merged]}, f, indent=2, ensure_ascii=False)
    print(f'[OK] Saved JSON: {args.out_json}')

    out_img = draw_detections(img, merged)
    out_img.save(args.out_image)
    print(f'[OK] Saved annotated image: {args.out_image}')


if __name__ == '__main__':
    main()