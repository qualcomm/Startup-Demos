#===--app.py--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

import csv
import io
import tempfile
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS

from backend.analyzer import analyze_video, get_video_metadata, sse_message


app = Flask(__name__)
CORS(app)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "video_analysis_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_REGISTRY: dict[str, dict] = {}


@app.post("/api/upload")
def upload_video():
    file = request.files.get("video")
    if file is None or not file.filename:
        return jsonify({"error": "Missing video file."}), 400

    video_id = uuid.uuid4().hex
    suffix = Path(file.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"{video_id}{suffix}"
    file.save(video_path)

    metadata = get_video_metadata(video_path)
    VIDEO_REGISTRY[video_id] = {
        "path": video_path,
        "metadata": metadata,
        "filename": file.filename,
    }

    return jsonify({
        "video_id": video_id,
        "video_url": f"/api/video/{video_id}",
        **metadata,
    })


@app.get("/api/video/<video_id>")
def stream_video(video_id: str):
    record = VIDEO_REGISTRY.get(video_id)
    if record is None:
        return jsonify({"error": "Video not found."}), 404
    return send_file(record["path"], mimetype="video/mp4", conditional=True)


@app.get("/api/analyze/<video_id>")
def analyze(video_id: str):
    record = VIDEO_REGISTRY.get(video_id)
    if record is None:
        return jsonify({"error": "Video not found."}), 404

    prompt = request.args.get("prompt", "Is there a tiger in this frame ?")
    try:
        frame_gap = max(int(request.args.get("frame_gap", "30")), 1)
    except ValueError:
        return jsonify({"error": "frame_gap must be an integer."}), 400

    def event_stream():
        try:
            yield sse_message({"type": "start", "metadata": record["metadata"]})
            for message in analyze_video(record["path"], prompt, frame_gap):
                yield sse_message(message)
            yield sse_message({"type": "done"})
        except Exception as error:  # pragma: no cover - surfaced to client
            yield sse_message({"type": "error", "message": str(error)})

    return Response(event_stream(), mimetype="text/event-stream")


@app.post("/api/export")
def export():
    payload = request.get_json(silent=True) or {}
    results = payload.get("results") or []
    tolerance = int(payload.get("tolerance", 3))
    events = _group_events(results, tolerance)
    csv_content = _export_csv(events)
    return send_file(
        io.BytesIO(csv_content.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="video-event-detector-events.csv",
    )


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


def _group_events(results: list[dict], tolerance: int) -> list[dict]:
    events = []
    current_event = None
    consecutive_no = 0

    for item in sorted(results, key=lambda v: v["frame_num"]):
        if item["answer"]:
            if current_event is None:
                current_event = {
                    "start_frame": item["frame_num"],
                    "start_time": item["timestamp"],
                    "end_frame": item["frame_num"],
                    "end_time": item["timestamp"],
                    "positive_frames": 1,
                }
            else:
                current_event["end_frame"] = item["frame_num"]
                current_event["end_time"] = item["timestamp"]
                current_event["positive_frames"] += 1
            consecutive_no = 0
            continue

        if current_event is None:
            continue

        consecutive_no += 1
        if consecutive_no > tolerance:
            events.append(current_event)
            current_event = None
            consecutive_no = 0

    if current_event is not None:
        events.append(current_event)

    for index, event in enumerate(events, start=1):
        event["event_id"] = index

    return events


def _export_csv(events: list[dict]) -> str:
    fieldnames = ["event_id", "start_frame", "end_frame", "start_time", "end_time", "positive_frames"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for event in events:
        writer.writerow({key: event.get(key) for key in fieldnames})
    return buffer.getvalue()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
