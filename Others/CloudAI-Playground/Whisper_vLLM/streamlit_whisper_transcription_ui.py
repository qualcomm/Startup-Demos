#===--streamlit_whisper_transcription_ui.py-------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import os
import io
import json
import time
import queue
import re
import tempfile
from datetime import datetime
from pathlib import Path

import av
import httpx
import numpy as np
import pydub
import streamlit as st
from openai import OpenAI
from streamlit_webrtc import WebRtcMode, webrtc_streamer


# -----------------------------
# Basic settings
# -----------------------------
DEFAULT_API_BASE = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
DEFAULT_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
DEFAULT_MODEL = os.getenv("VLLM_MODEL", "openai/whisper-tiny.en")

SUPPORTED_AUDIO_TYPES = [
    "wav", "mp3", "m4a", "ogg", "flac", "webm", "mp4", "mpeg", "mpga"
]


# -----------------------------
# Session state init
# -----------------------------
if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = DEFAULT_API_BASE

if "api_key" not in st.session_state:
    st.session_state.api_key = DEFAULT_API_KEY

if "model" not in st.session_state:
    st.session_state.model = DEFAULT_MODEL

if "history" not in st.session_state:
    st.session_state.history = []

if "last_result" not in st.session_state:
    st.session_state.last_result = ""

if "last_filename" not in st.session_state:
    st.session_state.last_filename = None

# Realtime transcription
if "live_text" not in st.session_state:
    st.session_state.live_text = ""

if "live_chunk_ms" not in st.session_state:
    st.session_state.live_chunk_ms = 2000

if "live_overlap_ms" not in st.session_state:
    st.session_state.live_overlap_ms = 400

if "live_decode_window_ms" not in st.session_state:
    st.session_state.live_decode_window_ms = 8000

if "live_decode_interval_ms" not in st.session_state:
    st.session_state.live_decode_interval_ms = 2000


# -----------------------------
# Helpers
# -----------------------------
def save_uploaded_file_to_temp(uploaded_file) -> str:
    """Save Streamlit uploaded file to a temp path and return the path."""
    suffix = Path(uploaded_file.name).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def build_openai_client() -> OpenAI:
    return OpenAI(
        api_key=st.session_state.api_key,
        base_url=st.session_state.api_base_url,
    )


def list_models_safe():
    """Try listing models from the server."""
    try:
        client = build_openai_client()
        models = client.models.list()
        return [m.id for m in models.data]
    except Exception:
        return []


def transcribe_sync(
    audio_path: str,
    model: str,
    language: str | None,
    temperature: float,
    response_format: str,
) -> str:
    """Synchronous transcription via OpenAI client."""
    client = build_openai_client()
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=f,
            model=model,
            language=language if language else None,
            temperature=temperature,
            response_format=response_format,
        )

    if isinstance(resp, str):
        return resp

    if hasattr(resp, "text"):
        return resp.text

    return str(resp)


async def transcribe_stream_async(
    audio_path: str,
    api_base: str,
    model: str,
    language: str | None,
    temperature: float,
    result_placeholder,
):
    """
    Streaming transcription using raw HTTP because OpenAI client does not
    expose streaming transcription the same way as chat streaming.
    """
    url = api_base.rstrip("/") + "/audio/transcriptions"
    data = {
        "model": model,
        "stream": "true",
        "temperature": str(temperature),
    }
    if language:
        data["language"] = language

    full_text = ""

    async with httpx.AsyncClient(timeout=None) as client:
        with open(audio_path, "rb") as f:
            files = {
                "file": (os.path.basename(audio_path), f, "application/octet-stream")
            }
            async with client.stream("POST", url, files=files, data=data) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data: "):
                        line = line[len("data: "):]

                    if line.strip() == "[DONE]":
                        break

                    chunk = json.loads(line)

                    content = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    )
                    if content:
                        full_text += content
                        result_placeholder.markdown(full_text + "▌")

    result_placeholder.markdown(full_text)
    return full_text


def add_history(filename: str, model: str, language: str, text: str):
    st.session_state.history.insert(
        0,
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": filename,
            "model": model,
            "language": language or "",
            "text": text,
        },
    )


# -----------------------------
# Live transcription helpers
# -----------------------------
def normalize_transcript_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def merge_incremental_text(existing: str, new_text: str) -> str:
    """
    Apply a more conservative merge to real-time transcription results to reduce duplication and fragmented sentences.
    """
    existing = normalize_transcript_text(existing)
    new_text = normalize_transcript_text(new_text)

    if not new_text:
        return existing
    if not existing:
        return new_text

    existing_cmp = existing.lower()
    new_cmp = new_text.lower()

    max_overlap = min(len(existing_cmp), len(new_cmp), 120)
    overlap = 0

    # At least 8 characters are required to be considered a valid overlap.
    for k in range(max_overlap, 7, -1):
        if existing_cmp[-k:] == new_cmp[:k]:
            overlap = k
            break

    merged_tail = new_text[overlap:].lstrip()
    if not merged_tail:
        return existing

    merged = (existing + " " + merged_tail).strip()
    merged = normalize_transcript_text(merged)
    return merged


def export_audiosegment_to_wav_bytes(segment: pydub.AudioSegment) -> bytes:
    buffer = io.BytesIO()
    segment.export(buffer, format="wav")
    return buffer.getvalue()


def transcribe_audio_bytes_sync(
    audio_bytes: bytes,
    api_base: str,
    model: str,
    language: str | None,
    temperature: float,
) -> str:
    """
    Send the in-memory WAV bytes directly to /audio/transcriptions.
    """
    url = api_base.rstrip("/") + "/audio/transcriptions"
    data = {
        "model": model,
        "temperature": str(temperature),
    }
    if language:
        data["language"] = language

    files = {
        "file": ("live_chunk.wav", audio_bytes, "audio/wav")
    }

    resp = httpx.post(url, data=data, files=files, timeout=120.0)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = resp.json()
        if isinstance(payload, dict) and "text" in payload:
            return str(payload["text"]).strip()
        return json.dumps(payload, ensure_ascii=False)

    return resp.text.strip()


def run_live_transcription(
    model: str,
    language: str | None,
    temperature: float,
):

    webrtc_ctx = webrtc_streamer(
        key="speech-to-text",
        mode=WebRtcMode.SENDONLY,
        audio_receiver_size=2048,
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        media_stream_constraints={
            "video": False,
            "audio": {
                "echoCancellation": False,
                "noiseSuppression": False,
                "autoGainControl": False,
            },
        },
    )

    status_indicator = st.empty()
    text_output = st.empty()

    live_col1, live_col2 = st.columns([1, 1])
    with live_col1:
        clear_live_btn = st.button("Clear Real-Time Result", use_container_width=True)
    with live_col2:
        st.write("")

    if clear_live_btn:
        st.session_state.live_text = ""

    if st.session_state.live_text:
        text_output.markdown(f"**Text:** {st.session_state.live_text}")

    if not webrtc_ctx.state.playing:
        status_indicator.info("Press Start。")
        return

    status_indicator.write("Running. Say something!")

    rolling_audio = pydub.AudioSegment.empty()
    pending_audio = pydub.AudioSegment.empty()

    decode_window_ms = int(st.session_state.live_decode_window_ms)
    decode_interval_ms = int(st.session_state.live_decode_interval_ms)
    chunk_ms = int(st.session_state.live_chunk_ms)
    overlap_ms = int(st.session_state.live_overlap_ms)

    last_decode_time = time.time()

    while True:
        if not webrtc_ctx.state.playing:
            status_indicator.write("Stopped.")
            break

        if webrtc_ctx.audio_receiver:
            sound_chunk = pydub.AudioSegment.empty()

            try:
                audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
            except queue.Empty:
                time.sleep(0.05)
                status_indicator.write("No frame arrived.")
                continue

            status_indicator.write("Running. Say something!")

            for audio_frame in audio_frames:
                sound = pydub.AudioSegment(
                    data=audio_frame.to_ndarray().tobytes(),
                    sample_width=audio_frame.format.bytes,
                    frame_rate=audio_frame.sample_rate,
                    channels=len(audio_frame.layout.channels),
                )
                sound_chunk += sound

            if len(sound_chunk) == 0:
                continue

            # Whisper Input Condition：mono + 16kHz
            sound_chunk = sound_chunk.set_channels(1).set_frame_rate(16000)

            pending_audio += sound_chunk
            rolling_audio += sound_chunk

            # Use a rolling window and retain at most the most recent decode_window_ms.
            if len(rolling_audio) > decode_window_ms:
                rolling_audio = rolling_audio[-decode_window_ms:]

            # Do not proceed until the minimum chunk length is reached.
            if len(pending_audio) < chunk_ms:
                continue

            now = time.time()
            if now - last_decode_time < decode_interval_ms / 1000.0:
                continue

            last_decode_time = now

            # Decode the most recent few seconds of audio, rather than decoding only the new chunk.
            current_decode_audio = rolling_audio
            wav_bytes = export_audiosegment_to_wav_bytes(current_decode_audio)

            try:
                text = transcribe_audio_bytes_sync(
                    audio_bytes=wav_bytes,
                    api_base=st.session_state.api_base_url,
                    model=model,
                    language=language,
                    temperature=temperature,
                )
            except Exception as e:
                status_indicator.error(f"Transcription Failed：{e}")
                continue

            clean_text = text.strip().rstrip(" .,!?:;")
            if len(clean_text) >= 6:
                st.session_state.live_text = merge_incremental_text(
                    st.session_state.live_text,
                    clean_text
                )
                text_output.markdown(f"**Text:** {st.session_state.live_text}")

            # Keep only the overlap in pending_audio to prevent it from growing indefinitely.
            if overlap_ms > 0 and len(pending_audio) > overlap_ms:
                pending_audio = pending_audio[-overlap_ms:]
            else:
                pending_audio = pydub.AudioSegment.empty()

        else:
            status_indicator.write("AudioReceiver is not set. Abort.")
            break


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("Settings")

new_api_base = st.sidebar.text_input("API Base URL", st.session_state.api_base_url)
new_api_key = st.sidebar.text_input("API Key", st.session_state.api_key, type="password")

if new_api_base != st.session_state.api_base_url:
    st.session_state.api_base_url = new_api_base

if new_api_key != st.session_state.api_key:
    st.session_state.api_key = new_api_key

st.sidebar.divider()

server_models = list_models_safe()
if server_models:
    try:
        default_idx = server_models.index(st.session_state.model)
    except ValueError:
        default_idx = 0
    selected_model = st.sidebar.selectbox("Model", server_models, index=default_idx)
else:
    selected_model = st.sidebar.text_input("Model", st.session_state.model)

st.session_state.model = selected_model

language = st.sidebar.text_input("Language (optional)", value="en")
temperature = st.sidebar.slider("Temperature", 0.0, 1.0, 0.0, 0.1)
stream_mode = st.sidebar.checkbox("Streaming", value=True)
response_format = st.sidebar.selectbox(
    "Response Format (sync only)",
    ["json", "text", "verbose_json"],
    index=0,
)

st.sidebar.divider()
st.sidebar.subheader("Real-Time Record Settings")

st.session_state.live_chunk_ms = st.sidebar.slider(
    "Real-time segment length (ms)",
    min_value=500,
    max_value=4000,
    value=int(st.session_state.live_chunk_ms),
    step=100,
)

st.session_state.live_overlap_ms = st.sidebar.slider(
    "Segment overlap (ms)",
    min_value=0,
    max_value=1500,
    value=int(st.session_state.live_overlap_ms),
    step=50,
)

st.session_state.live_decode_window_ms = st.sidebar.slider(
    "Rolling decode window (ms)",
    min_value=3000,
    max_value=12000,
    value=int(st.session_state.live_decode_window_ms),
    step=500,
)

st.session_state.live_decode_interval_ms = st.sidebar.slider(
    "Decode interval (ms)",
    min_value=500,
    max_value=4000,
    value=int(st.session_state.live_decode_interval_ms),
    step=100,
)

st.sidebar.divider()
st.sidebar.caption("If the audio file is too large, you can adjust Streamlit's server.maxUploadSize.")

# -----------------------------
# Main UI
# -----------------------------
st.title("Whisper Transcription UI (vLLM + Qualcomm AIC100)")
st.caption("Press Start to begin audio capture. The program will segment the audio every n seconds and send each segment for transcription.")

uploaded_file = st.file_uploader(
    "Upload audio file",
    type=SUPPORTED_AUDIO_TYPES,
    accept_multiple_files=False,
)

if uploaded_file is not None:
    st.audio(uploaded_file)
    st.write(f"File Name:`{uploaded_file.name}`")
    st.write(f"Size:`{uploaded_file.size / 1024 / 1024:.2f} MB`")

    col1, col2 = st.columns([1, 1])

    with col1:
        run_btn = st.button("Start Transcribe", type="primary", use_container_width=True)
    with col2:
        clear_btn = st.button("Clear Result", use_container_width=True)

    if clear_btn:
        st.session_state.last_result = ""
        st.session_state.last_filename = None
        st.rerun()

    if run_btn:
        tmp_path = None
        try:
            tmp_path = save_uploaded_file_to_temp(uploaded_file)
            st.session_state.last_filename = uploaded_file.name

            with st.status("Transcribing...", expanded=True) as status:
                st.write(f"Model: {st.session_state.model}")
                st.write(f"Streaming: {stream_mode}")
                st.write(f"Language: {language or '(auto)'}")

                result_placeholder = st.empty()

                if stream_mode:
                    import asyncio
                    result_text = asyncio.run(
                        transcribe_stream_async(
                            audio_path=tmp_path,
                            api_base=st.session_state.api_base_url,
                            model=st.session_state.model,
                            language=language.strip() or None,
                            temperature=temperature,
                            result_placeholder=result_placeholder,
                        )
                    )
                else:
                    result_text = transcribe_sync(
                        audio_path=tmp_path,
                        model=st.session_state.model,
                        language=language.strip() or None,
                        temperature=temperature,
                        response_format=response_format,
                    )
                    result_placeholder.markdown(result_text)

                st.session_state.last_result = result_text
                add_history(
                    filename=uploaded_file.name,
                    model=st.session_state.model,
                    language=language.strip(),
                    text=result_text,
                )
                status.update(label="Done", state="complete")

        except Exception as e:
            st.error(f"Transcription Failed:{e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

# -----------------------------
# Live transcription UI
# -----------------------------
st.divider()
st.subheader("Real Time Record and Transcribe")


run_live_transcription(
    model=st.session_state.model,
    language=language.strip() or None,
    temperature=temperature,
)

# -----------------------------
# Result display
# -----------------------------
if st.session_state.last_result:
    st.subheader("Latest Result")
    st.text_area(
        "Transcription",
        value=st.session_state.last_result,
        height=220,
    )

    download_name = (
        Path(st.session_state.last_filename).stem + "_transcription.txt"
        if st.session_state.last_filename
        else "transcription.txt"
    )

    st.download_button(
        "Download TXT",
        data=st.session_state.last_result,
        file_name=download_name,
        mime="text/plain",
    )

# -----------------------------
# History
# -----------------------------
if st.session_state.history:
    st.subheader("History")
    for idx, item in enumerate(st.session_state.history):
        with st.expander(
            f"{item['time']} | {item['filename']} | {item['model']}",
            expanded=(idx == 0),
        ):
            st.write(f"Language: {item['language'] or '(auto)'}")
            st.text_area(
                f"Result #{idx}",
                value=item["text"],
                height=180,
                key=f"history_{idx}",
            )
