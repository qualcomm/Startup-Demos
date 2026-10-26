#===-- IncidentLens.py -------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import requests
import base64
import tempfile
import hashlib
from PIL import Image
import autogen

# ==========================================================
# Model Server Configuration
# ==========================================================

# InternVL container
# Host port 8001 maps to container port 8000
IMAGE_API_URL = "http://localhost:8001/v1/chat/completions"
IMAGE_HEALTH_URL = "http://localhost:8001/health"
IMAGE_MODEL = "OpenGVLab/InternVL2_5-1B"

# LLaVA container
# Host port 8000 maps to container port 8000
INCIDENT_API_URL = "http://localhost:8000/v1/chat/completions"
INCIDENT_HEALTH_URL = "http://localhost:8000/health"
INCIDENT_MODEL = "llava-hf/llava-1.5-7b-hf"

CURRENT_IMAGE_PATH = None

agent_outputs = {
    "ImageAnalyzer": None,
    "IncidentAgent": None
}

# ==========================================================
# Utility Functions
# ==========================================================

def check_health(url):
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def compress_image(input_path):
    image = Image.open(input_path).convert("RGB")
    image.thumbnail((768, 768))

    compressed_path = input_path.replace(".png", "_compressed.jpg")
    image.save(compressed_path, "JPEG", quality=75, optimize=True)

    return compressed_path


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def image_model_call(prompt):
    global CURRENT_IMAGE_PATH

    if not CURRENT_IMAGE_PATH:
        return "Error: No image uploaded."

    try:
        base64_image = encode_image(CURRENT_IMAGE_PATH)

        payload = {
            "model": IMAGE_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 350,
            "temperature": 0.1
        }

        response = requests.post(
            IMAGE_API_URL,
            json=payload,
            timeout=300
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]

        return f"Error: InternVL image model returned status code {response.status_code}"

    except Exception as e:
        return f"Error: {str(e)}"


def incident_model_call(prompt):
    try:
        payload = {
            "model": INCIDENT_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 500,
            "temperature": 0.1
        }

        response = requests.post(
            INCIDENT_API_URL,
            json=payload,
            timeout=180
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]

        return f"Error: LLaVA incident model returned status code {response.status_code}"

    except Exception as e:
        return f"Error: {str(e)}"


# ==========================================================
# AutoGen Agent Workflow
# ==========================================================

def run_autogen_agents():
    global agent_outputs

    agent_outputs = {
        "ImageAnalyzer": None,
        "IncidentAgent": None
    }

    # ------------------------------------------------------
    # Agent 1: ImageAnalyzer
    # Calls InternVL on localhost:8001
    # ------------------------------------------------------

    image_analyzer = autogen.AssistantAgent(
        name="ImageAnalyzer",
        llm_config=False,
        system_message=(
            "You are ImageAnalyzer. "
            "You analyze uploaded incident/error images and extract simple technical evidence."
        )
    )

    def image_analyzer_reply(recipient, messages, sender, config):
        prompt = """
Analyze this uploaded incident or error image.

Give simple bullet points only.

Include:
- Visible issue or error
- Affected application, device, service, or system
- Visible error code or message
- Whether it looks like failure, warning, timeout, crash, unavailable, or unknown
- Severity level: Low, Medium, High, or Critical
- Short technical evidence

Keep it short and easy to understand.
Do not create a long report.
"""

        result = image_model_call(prompt)

        agent_outputs["ImageAnalyzer"] = result

        return True, f"""
ImageAnalyzer completed image analysis.

{result}
"""

    image_analyzer.register_reply(
        trigger=autogen.Agent,
        reply_func=image_analyzer_reply,
        position=0
    )

    # ------------------------------------------------------
    # Agent 2: IncidentAgent
    # Calls LLaVA on localhost:8000
    # ------------------------------------------------------

    incident_agent = autogen.AssistantAgent(
        name="IncidentAgent",
        llm_config=False,
        system_message=(
            "You are IncidentAgent. "
            "You read ImageAnalyzer findings and generate root cause and incident report."
        )
    )

    def incident_agent_reply(recipient, messages, sender, config):
        image_findings = agent_outputs["ImageAnalyzer"]

        prompt = f"""
You are IncidentAgent.

ImageAnalyzer has provided these findings:

{image_findings}

Create a simple incident output.

Use only these sections:

1. Root Cause
- Explain the likely root cause in simple words.

2. Issue Type
- Hardware Issue, Software Issue, Network Issue, Configuration Issue, Resource Issue, or Unknown.

3. Severity
- Low, Medium, High, or Critical.

4. Impact
- Explain what may be affected.

5. Immediate Action
- Give 3 simple action items.

6. Final Incident Summary
- Give a short final summary.

Keep it simple and professional.
"""

        result = incident_model_call(prompt)

        agent_outputs["IncidentAgent"] = result

        return True, f"""
IncidentAgent completed root cause and incident report.

{result}
"""

    incident_agent.register_reply(
        trigger=autogen.Agent,
        reply_func=incident_agent_reply,
        position=0
    )

    # ------------------------------------------------------
    # User Proxy Agent
    # ------------------------------------------------------

    user_proxy = autogen.UserProxyAgent(
        name="IncidentManager",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=5,
        code_execution_config=False
    )

    # ------------------------------------------------------
    # AutoGen GroupChat
    # ------------------------------------------------------

    groupchat = autogen.GroupChat(
        agents=[
            user_proxy,
            image_analyzer,
            incident_agent
        ],
        messages=[],
        max_round=3,
        speaker_selection_method="round_robin"
    )

    manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config=False
    )

    initial_message = """
Incident image uploaded.

Start AutoGen workflow:
1. ImageAnalyzer should analyze the uploaded image.
2. IncidentAgent should use ImageAnalyzer output to generate root cause and incident report.
"""

    user_proxy.initiate_chat(
        manager,
        message=initial_message
    )

    final_report = f"""
AUTOGEN INCIDENT TRIAGE REPORT

STAGE 1: IMAGE ANALYSIS

{agent_outputs["ImageAnalyzer"]}

STAGE 2: ROOT CAUSE AND INCIDENT REPORT

{agent_outputs["IncidentAgent"]}
"""

    return final_report.strip()


# ==========================================================
# Streamlit Dashboard
# ==========================================================

st.set_page_config(
    page_title="Incident Analyzer",
    layout="wide"
)

st.title("Incident Analyzer")
st.write("Upload an incident image. AutoGen agents will automatically analyze it and generate the report.")

st.sidebar.header("Agent Flow")
st.sidebar.write("1. ImageAnalyzer")
st.sidebar.write("2. IncidentAgent")

st.sidebar.header("Model Routing")
st.sidebar.write("ImageAnalyzer uses InternVL on port 8001")
st.sidebar.write("IncidentAgent uses LLaVA on port 8000")

uploaded_file = st.file_uploader(
    "Upload incident image",
    type=["png", "jpg", "jpeg"]
)

if "last_file_hash" not in st.session_state:
    st.session_state.last_file_hash = None

if "final_report" not in st.session_state:
    st.session_state.final_report = None

if "image_analysis" not in st.session_state:
    st.session_state.image_analysis = None

if "incident_report" not in st.session_state:
    st.session_state.incident_report = None


if uploaded_file is not None:

    file_bytes = uploaded_file.getvalue()
    file_hash = hashlib.md5(file_bytes).hexdigest()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Uploaded Image")
        st.image(uploaded_file, use_container_width=True)

    if file_hash != st.session_state.last_file_hash:

        st.session_state.last_file_hash = file_hash
        st.session_state.final_report = None
        st.session_state.image_analysis = None
        st.session_state.incident_report = None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(file_bytes)
            temp_image_path = temp_file.name

        compressed_image_path = compress_image(temp_image_path)

        CURRENT_IMAGE_PATH = compressed_image_path

        with col2:
            st.subheader("Server Status")

            if check_health(IMAGE_HEALTH_URL):
                st.success("InternVL ImageAnalyzer server is running on localhost:8001")
            else:
                st.error("InternVL ImageAnalyzer server is not running on localhost:8001")
                st.stop()

            if check_health(INCIDENT_HEALTH_URL):
                st.success("LLaVA IncidentAgent server is running on localhost:8000")
            else:
                st.error("LLaVA IncidentAgent server is not running on localhost:8000")
                st.stop()

        progress = st.progress(0)
        status = st.empty()

        status.info("Starting AutoGen agents...")
        progress.progress(20)

        with st.spinner("AutoGen agents are communicating and analyzing..."):
            final_report = run_autogen_agents()

        progress.progress(100)
        status.success("AutoGen incident analysis completed.")

        st.session_state.final_report = final_report
        st.session_state.image_analysis = agent_outputs["ImageAnalyzer"]
        st.session_state.incident_report = agent_outputs["IncidentAgent"]

    if st.session_state.final_report:

        st.divider()

        st.subheader("Stage 1: Image Analysis")
        st.write(st.session_state.image_analysis)

        st.subheader("Stage 2: Root Cause and Incident Report")
        st.write(st.session_state.incident_report)

        st.subheader("Final Report")
        st.text_area(
            "Generated Report",
            st.session_state.final_report,
            height=450
        )

        st.download_button(
            label="Download Report",
            data=st.session_state.final_report,
            file_name="incident_triage_report.txt",
            mime="text/plain"
        )

else:
    st.info("Upload an image to start automatic AutoGen incident analysis.")

