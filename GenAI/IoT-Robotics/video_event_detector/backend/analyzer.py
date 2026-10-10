#===--analyzer.py---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

import base64
import json
import re
from pathlib import Path

import cv2

from backend.internvl import run_internvl_frame


YES_PATTERN = re.compile(r"\byes\b", re.IGNORECASE)
NO_PATTERN = re.compile(r"\bno\b", re.IGNORECASE)


def get_video_metadata(video_path: Path) -> dict:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = (total_frames / fps) if fps else 0.0
    capture.release()

    return {
        "fps": fps,
        "total_frames": total_frames,
        "duration": duration,
    }


def build_prompt(prompt: str) -> str:
    prompt = prompt.strip()
    return f"{prompt}\nAnswer with only yes or no."


def parse_yes_no(response: str) -> bool:
    has_yes = bool(YES_PATTERN.search(response))
    has_no = bool(NO_PATTERN.search(response))
    if has_yes and not has_no:
        return True
    if has_no and not has_yes:
        return False
    normalized = response.strip().lower().rstrip(".")
    if normalized == "yes":
        return True
    return False


def analyze_video(video_path: Path, prompt: str, frame_gap: int):
    metadata = get_video_metadata(video_path)
    total_frames = metadata["total_frames"]
    fps = metadata["fps"]
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    sampled_frames = list(range(0, total_frames, max(frame_gap, 1)))
    total_samples = len(sampled_frames)
    prepared_prompt = build_prompt(prompt)

    try:
        for index, frame_num in enumerate(sampled_frames, start=1):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ok, frame = capture.read()
            print(
                f"analyzing frame {frame_num} ({index}/{total_samples})",
                flush=True,
            )
            if not ok:
                continue

            timestamp = (frame_num / fps) if fps else 0.0
            try:
                response = run_internvl_frame(frame, prepared_prompt)
            except Exception as error:
                print(f"frame {frame_num}: inference failed: {error}", flush=True)
                continue

            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 72],
            )
            frame_preview = None
            if ok:
                frame_preview = f"data:image/jpeg;base64,{base64.b64encode(encoded.tobytes()).decode('ascii')}"

            result = {
                "frame_num": frame_num,
                "timestamp": round(timestamp, 3),
                "answer": parse_yes_no(response),
                "frame_preview": frame_preview,
            }
            progress = {
                "current": index,
                "total": total_samples,
                "percent": round((index / total_samples) * 100, 1) if total_samples else 100.0,
            }
            yield {
                "type": "result",
                "result": result,
                "progress": progress,
            }
    finally:
        capture.release()


def sse_message(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"
