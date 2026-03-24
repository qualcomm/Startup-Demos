#===--dashboard_dual.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------===//

import json
import time
import requests
import streamlit as st

# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------
st.set_page_config(
    page_title="Traffic AI Agent - Dual (Analysis)",
    layout="wide",
)

st.title("🚦 Traffic AI Agent — Dual Intersection (Analysis)")
st.caption("On‑prem decision + routing + LLM explanation demo")

# ------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------
API_BASE = st.sidebar.text_input("Demo API Base URL", "http://localhost:9000")
auto_refresh = st.sidebar.checkbox("Auto refresh", True)
refresh_sec = st.sidebar.slider("Refresh interval (sec)", 1, 10, 2)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Analysis mode:\n"
    "- Auto-decision runs in the backend\n"
    "- This UI keeps the last N explanations to avoid memory growth"
)

# ------------------------------------------------------------
# Session state init
# ------------------------------------------------------------
if "typing" not in st.session_state:
    st.session_state.typing = False

MAX_HISTORY = 3

for k in [
    "history_A", "history_B",
    "live_text_A", "live_text_B",
    "live_route_A", "live_route_B",
    "decide_count_A", "decide_count_B",
]:
    if k not in st.session_state:
        if k.startswith("history_"):
            st.session_state[k] = []
        elif k.startswith("decide_count_"):
            st.session_state[k] = 0
        else:
            st.session_state[k] = None

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def fetch_state(iid: str):
    r = requests.get(
        f"{API_BASE}/state",
        params={"intersection_id": iid},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()

def explain_stream(iid: str, query: str):
    payload = {
        "intersection_id": iid,
        "origin": "A",
        "destination": "C",
        "user_query": query,
    }
    r = requests.post(
        f"{API_BASE}/explain_stream",
        json=payload,
        stream=True,
        timeout=300,
    )
    r.raise_for_status()
    return r

def decide_once(iid: str):
    payload = {
        "intersection_id": iid,
        "constraints": {
            "green_min": 20,
            "green_max": 60,
            "delta_max": 10,
            "max_step_change": 5,
        },
        "current_plan": {
            "NS_green": 30,
            "EW_green": 30,
            "yellow_sec": 3,
            "all_red_sec": 1,
        },
    }
    r = requests.post(f"{API_BASE}/decide", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def render_metrics(latest: dict):
    lanes = latest["lanes"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("NS Queue", f'{lanes["NS"]["queue"]:.2f}')
    c2.metric("NS Flow",  f'{lanes["NS"]["flow"]:.2f}')
    c3.metric("EW Queue", f'{lanes["EW"]["queue"]:.2f}')
    c4.metric("EW Flow",  f'{lanes["EW"]["flow"]:.2f}')
    st.caption(f'Current signal phase: {latest["current_phase"]}')

def render_chart(points: list):
    if not points:
        return
    st.line_chart({
        "NS_queue": [p["lanes"]["NS"]["queue"] for p in points],
        "EW_queue": [p["lanes"]["EW"]["queue"] for p in points],
        "NS_flow":  [p["lanes"]["NS"]["flow"] for p in points],
        "EW_flow":  [p["lanes"]["EW"]["flow"] for p in points],
    })

def render_decision_panel(iid: str, state: dict):
    decisions = state.get("last_decisions", []) if state else []
    st.session_state[f"decide_count_{iid}"] = len(decisions)

    left, right = st.columns([1, 1])

    with left:
        st.markdown("### 🚦 Signal Decision")
        if st.button(f"Force decision (debug) — {iid}", key=f"btn_decide_{iid}"):
            try:
                d = decide_once(iid)
                st.success("Decision sent to backend ✅")
                st.json(d)
            except Exception as e:
                st.error(f"Decision failed: {e}")

        if decisions:
            st.markdown("**Latest decision**")
            st.json(decisions[-1])
        else:
            st.info(
                "No decision yet.\n\n"
                "Auto‑decision runs in the backend. "
                "You can wait a few seconds or use the debug button above."
            )

    with right:
        st.markdown("### 📌 Decision Summary")
        if decisions:
            last = decisions[-1]
            phase = last.get("next_phase", "N/A")
            green = last.get("green_sec", "N/A")
            delta = last.get("delta", {}).get("green_sec")
            reasons = last.get("reason_codes", [])

            st.write(f"- Next phase: **{phase}**")
            st.write(f"- Green seconds: **{green}**")
            if delta is not None:
                st.write(f"- Δ green seconds: **{delta}**")
            if reasons:
                st.write(f"- Reason codes: `{', '.join(reasons)}`")
            st.write(f"- Decision count (window): **{len(decisions)}**")
        else:
            st.write("- Next phase: N/A")
            st.write("- Green seconds: N/A")
            st.write("- Δ green seconds: N/A")
            st.write("- Reason codes: N/A")
            st.write("- Decision count (window): 0")

def render_panel(iid: str):
    st.subheader(f"Intersection {iid}")

    try:
        state = fetch_state(iid)
    except Exception:
        st.warning("No data available yet.")
        state = None

    if state and state.get("latest"):
        render_metrics(state["latest"])
    if state and state.get("points"):
        render_chart(state["points"])

    if state:
        render_decision_panel(iid, state)

    st.divider()

    hist_key = f"history_{iid}"
    with st.expander("🧠 Explanation History", expanded=True):
        for i, h in enumerate(st.session_state[hist_key]):
            st.markdown(f"### #{len(st.session_state[hist_key]) - i}")
            st.write("🚗 Route decision:", h.get("route"))
            st.markdown(h.get("text", ""))
            st.divider()

    live_route_key = f"live_route_{iid}"
    live_text_key = f"live_text_{iid}"

    if st.session_state[live_route_key] is not None:
        st.markdown(
            f"🚗 **(Live) Route decision**: `{st.session_state[live_route_key]}`"
        )
    if st.session_state[live_text_key]:
        st.markdown(st.session_state[live_text_key])

    query = st.text_area(
        f"Explain query ({iid})",
        "Explain the current traffic trends, signal decision rationale, "
        "and compare the direct route with via_B.",
        height=100,
        key=f"inp_q_{iid}",
    )

    if st.button(f"Explain {iid}", key=f"btn_explain_{iid}"):
        st.session_state.typing = True
        st.session_state[live_text_key] = ""
        st.session_state[live_route_key] = None

        route_ph = st.empty()
        text_ph = st.empty()

        try:
            resp = explain_stream(iid, query)
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                line = line.strip()
                if not line.startswith("data:"):
                    continue

                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break

                msg = json.loads(data)

                if msg.get("type") == "meta":
                    current_route = msg.get("routing")
                    st.session_state[live_route_key] = current_route
                    route_ph.markdown(
                        f"🚗 **Route decision**: `{current_route}`"
                    )
                elif msg.get("type") == "token":
                    st.session_state[live_text_key] += msg.get("content", "")
                    text_ph.markdown(st.session_state[live_text_key])

        except Exception as e:
            st.error(f"Explain failed: {e}")

        record = {
            "route": st.session_state[live_route_key],
            "text": st.session_state[live_text_key],
        }
        st.session_state[hist_key].insert(0, record)
        st.session_state[hist_key] = st.session_state[hist_key][:MAX_HISTORY]

        st.session_state.typing = False

# ------------------------------------------------------------
# Layout
# ------------------------------------------------------------
colA, colB = st.columns(2)
with colA:
    render_panel("A")
with colB:
    render_panel("B")

# ------------------------------------------------------------
# Auto refresh
# ------------------------------------------------------------
if auto_refresh and not st.session_state.typing:
    time.sleep(refresh_sec)
    st.rerun()
