#===-- app_multi_vllm.py -------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import requests, base64, json, time

st.title("🖼️ Image Inference Assistant")

# Fixed model list
model_options = [
    "llava-hf/llava-1.5-7b-hf",
    "OpenGVLab/InternVL2_5-1B"
]

# Model selection dropdown
selected_model = st.selectbox("Select a model", model_options, key="selected_model")

# Determine whether the selected model supports images
supports_image = ("llava" in selected_model.lower()) or ("internvl" in selected_model.lower())

# Image upload and prompt input
uploaded_file = st.file_uploader("Upload image" if supports_image else "(This model does not support image upload)",
                                 type=["jpg","jpeg","png"],
                                 accept_multiple_files=False,
                                 disabled=not supports_image,
                                 key="uploaded_file")
prompt = st.text_input("Enter prompt", "", key="input_prompt")

# Show image (if uploaded)
if supports_image and uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded image", width=600)

if st.button("Send request"):
    if not prompt and uploaded_file is None:
        st.warning("Please enter a prompt or upload an image.")
        st.stop()

    # Build OpenAI-compatible API request payload and enable streaming
    messages = []
    user_content = []
    if supports_image and uploaded_file:
        # Convert the image into a base64 data URI
        img_bytes = uploaded_file.read()
        mime_type = uploaded_file.type or "image/png"
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "image_url",
            "image_url": { "url": f"data:{mime_type};base64,{img_b64}" }
        })
    if prompt:
        user_content.append({ "type": "text", "text": prompt })
    messages.append({ "role": "user", "content": user_content })
    payload = {
        "model": selected_model,
        "messages": messages,
        "stream": True  # <- enable streaming mode
    }

    # Choose API endpoint (based on model)
    if selected_model == "llava-hf/llava-1.5-7b-hf":
        api_url = "http://localhost:8000/v1/chat/completions"
    elif selected_model == "OpenGVLab/InternVL2_5-1B":
        api_url = "http://localhost:8001/v1/chat/completions"
    else:
        st.error("Unknown model. Cannot send request.")
        st.stop()

    try:
        # Send request and stream the response
        response = requests.post(api_url, json=payload, stream=True)
    except Exception as e:
        st.error(f"API request failed: {e}")
        st.stop()

    if response.status_code != 200:
        # Handle error response
        try:
            err = response.json()
        except:
            err = {"error": {"message": response.text}}
        st.error(f"Model error: {err.get('error', {}).get('message', 'Unknown error')}")
        st.stop()

    # Prepare a placeholder to progressively display the output
    output_placeholder = st.empty()
    displayed_text = ""

    # Read the streaming response line by line
    for chunk in response.iter_lines(decode_unicode=True):
        if chunk is None or chunk.strip() == "":
            # Skip heartbeats or empty lines
            continue
        if chunk.strip().startswith("data:"):
            data = chunk.strip()[len("data:"):].strip()
            if data == "[DONE]":
                # Streaming end signal
                break
            # Try to parse JSON
            try:
                chunk_data = json.loads(data)
            except json.JSONDecodeError:
                continue
            # If partial text content is included
            if "choices" in chunk_data:
                delta = chunk_data["choices"][0].get("delta", {})
                # Extract text fragment
                content_chunk = delta.get("content", "")
                if content_chunk:
                    # Show the fragment character by character
                    for char in content_chunk:
                        displayed_text += char
                        output_placeholder.markdown(displayed_text)
                        # A slight delay to render a typewriter-like effect
                        time.sleep(0.02)
            # (Optional) Handle images: if the model returns an image URL
            if chunk_data.get("choices") and isinstance(chunk_data["choices"][0].get("delta", {}), dict):
                delta = chunk_data["choices"][0]["delta"]
                if "image_url" in delta:
                    img_url_info = delta["image_url"]  # e.g., {"url": "data:image/png;base64,..."}
                    img_url = img_url_info.get("url", "")
                    if img_url:
                        # Decode and display Base64 image data
                        if img_url.startswith("data:image"):
                            header, b64data = img_url.split(",", 1)
                            st.image(base64.b64decode(b64data))
                        else:
                            st.image(img_url)
    # (If needed, add any post-stream handling here, e.g., an extra newline or a final hint)