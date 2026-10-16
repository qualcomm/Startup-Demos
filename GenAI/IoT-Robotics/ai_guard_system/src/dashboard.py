#===----------------ai_guard_system dashboard----------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
"""
Edge AI Guard System — NiceGUI Dashboard

Usage:
1. Alert Banner / Alert Log: Real-time alert popup and chronological alert history with details.
2. Live Camera Preview: Side-by-side dual-camera feeds with bounding box overlay and streaming status.
3. AI Guard Chat: Natural-language queries translated to SQL by on-device LLM.
4. Rule: View/delete active rules in Rule List; add new rules in natural language via Add Rule form.
"""

import os
import sys
import json
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime
from collections import deque

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["ABSL_MIN_LOG_LEVEL"] = "3"

# =====================================================================
#  Import dependencies
# =====================================================================

import cv2
import numpy as np
from nicegui import ui, app, run
from starlette.responses import StreamingResponse
from frame_bridge import SharedFrameReader

from llm_engine import (
    MODEL_PATH,
    DB_PATH,
    RULES_PATH,
    ALERTS_PATH,
    SCHEMA,
    NL2SQL_PROMPT,
    ANSWER_PROMPT,
    RULE_TO_SQL_PROMPT,
    llm_generate,
    extract_sql,
    run_query,
    format_result_table,
    is_followup,
    build_history_text,
    init_db,
    RuleChecker,
)


# =====================================================================
#  Global settings
# =====================================================================

CAM_WIDTH = 640
CAM_HEIGHT = 480
STREAM_FPS = 10
JPEG_QUALITY = 70


# =====================================================================
#  LLM Engine (global)
# =====================================================================

llm_engine = None
llm_ready = False
llm_lock = threading.Lock()
rule_checker = None


def init_llm():
    """Background thread: initialise the LLM engine."""
    global llm_engine, llm_ready
    try:
        import litert_lm
        llm_engine = litert_lm.Engine(
            MODEL_PATH,
            backend=litert_lm.Backend.GPU,
        )
        llm_ready = True
        print(f"[LLM] Engine loaded: {MODEL_PATH}")
    except Exception as e:
        print(f"[LLM] Engine load failed: {e}")
        llm_ready = False


# =====================================================================
#  Chat conversation history
# =====================================================================

chat_history = deque(maxlen=2)


# =====================================================================
#  SQL Guard
# =====================================================================

def sql_guard(sql: str) -> bool:
    """Only allow SELECT statements (read-only)."""
    cleaned = sql.strip().lower()
    stripped_lines = [
        line.strip() for line in cleaned.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    if not stripped_lines:
        return False
    first_kw = stripped_lines[0].split()[0] if stripped_lines[0].split() else ""
    return first_kw == "select"


# =====================================================================
#  NL2SQL Pipeline (synchronous, invoked via run.io_bound)
# =====================================================================

def nl2sql_pipeline(question: str) -> dict:
    """Run the full NL → SQL → query → answer pipeline (blocking)."""
    response = {
        "question": question,
        "sql": "",
        "result": None,
        "answer": "",
        "error": None,
    }

    if not llm_ready or llm_engine is None:
        response["answer"] = "[LLM not ready yet, please wait...]"
        return response

    history_text = build_history_text(list(chat_history), question)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = NL2SQL_PROMPT.format(
        schema=SCHEMA,
        history=history_text,
        question=question,
        now=now_str,
    )

    with llm_lock:
        raw = llm_generate(llm_engine, prompt)
    sql = extract_sql(raw)
    response["sql"] = sql

    if not sql:
        response["answer"] = "Sorry, I couldn't understand this question. Please try rephrasing."
        return response

    if not sql_guard(sql):
        response["answer"] = "\u26a0\ufe0f Security restriction: only SELECT queries are allowed."
        response["error"] = f"SQL Guard blocked: {sql}"
        return response

    cols, rows, err = run_query(DB_PATH, sql, ALERTS_PATH)
    if err:
        response["error"] = err
        response["answer"] = f"Query failed: {err}"
        return response

    result_text = format_result_table(cols, rows)
    response["result"] = [dict(zip(cols, r)) for r in rows]

    answer_prompt = ANSWER_PROMPT.format(
        question=question,
        sql=sql,
        result_table=result_text,
    )

    with llm_lock:
        answer = llm_generate(llm_engine, answer_prompt)
    response["answer"] = answer

    chat_history.append({
        "question": question,
        "sql": sql,
        "result_text": result_text,
    })

    return response


# =====================================================================
#  RuleChecker Hot-Reload (add/delete rules sync immediately)
# =====================================================================

def hot_add_rule(compiled_rule: dict):
    """Immediately add a new rule to RuleChecker's compiled list."""
    global rule_checker
    if rule_checker is None:
        return
    try:
        rule_checker._compiled.append(compiled_rule)
        print(f"[RuleChecker] Hot-add: {compiled_rule.get('name', '?')}")
    except Exception as e:
        print(f"[RuleChecker] Hot-add error: {e}")


def hot_remove_rule(name: str):
    """Immediately remove a rule from RuleChecker's compiled list by name."""
    global rule_checker
    if rule_checker is None:
        return
    try:
        before = len(rule_checker._compiled)
        rule_checker._compiled = [
            r for r in rule_checker._compiled if r.get("name") != name
        ]
        after = len(rule_checker._compiled)
        if after < before:
            print(f"[RuleChecker] Hot-remove: {name}")
    except Exception as e:
        print(f"[RuleChecker] Hot-remove error: {e}")


# =====================================================================
#  Rule Manager (JSON persistence + LLM compilation)
# =====================================================================

def load_rules() -> list:
    """Load rules from the JSON file."""
    if not Path(RULES_PATH).exists():
        return []
    try:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_rules(rules: list):
    """Save rules to the JSON file."""
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def add_rule_with_llm(name: str, description: str, interval_sec: int) -> dict:
    """
    Add a new rule: LLM auto-generates the SQL, then sync to RuleChecker.

    - activated_at format: 'YYYY-MM-DD HH:MM:SS' (space, not T)
    - check_interval maps to interval_sec (used by RuleChecker)
    """
    sql = ""
    if llm_ready and llm_engine is not None:
        prompt = RULE_TO_SQL_PROMPT.format(
            schema=SCHEMA,
            rule_nl=description,
        )
        with llm_lock:
            raw = llm_generate(llm_engine, prompt)
            sql = extract_sql(raw)

    # Use space-separated format (consistent with RuleChecker)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build the rule dict for rules.json
    new_rule = {
        "name": name,
        "description": description,
        "rule_nl": description,
        "sql": sql,
        "interval_sec": interval_sec,
        "check_interval": interval_sec,
        "activated_at": now_str,
        "enabled": True,
    }
    rules = load_rules()
    rules.append(new_rule)
    save_rules(rules)

    # Hot-reload: sync to RuleChecker._compiled
    if sql:
        compiled = {
            "name": name,
            "description": description,
            "sql": sql,
            "check_interval": interval_sec,
            "interval_sec": interval_sec,
            "activated_at": now_str,
            "enabled": True,
            "last_triggered": 0,
        }
        hot_add_rule(compiled)

    return new_rule


def delete_rule(name: str) -> bool:
    """Delete a rule by name from JSON and hot-remove from RuleChecker."""
    rules = load_rules()
    filtered = [r for r in rules if r.get("name") != name]
    if len(filtered) == len(rules):
        return False
    save_rules(filtered)

    # Hot-reload: remove from RuleChecker
    hot_remove_rule(name)

    return True


# =====================================================================
#  Alert Helpers (read from alerts.db)
# =====================================================================

_last_alert_id = 0   # Track last alert ID for toast notifications


def fetch_recent_alerts(limit: int = 50) -> list:
    """Read the latest alerts from alerts.db."""
    try:
        conn = sqlite3.connect(ALERTS_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute(
            "SELECT id, timestamp, rule_name, detail "
            "FROM alerts ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "rule_name": r[2],
                "detail": r[3][:120] if r[3] else "",
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[Alert] DB read error: {e}")
        return []


def get_max_alert_id() -> int:
    """Return the current maximum alert ID in alerts.db."""
    try:
        conn = sqlite3.connect(ALERTS_PATH)
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM alerts")
        row = cur.fetchone()
        conn.close()
        return row[0] or 0
    except Exception:
        return 0


def fetch_new_alerts(since_id: int) -> list:
    """Fetch alerts with ID greater than since_id (for toast popup)."""
    try:
        conn = sqlite3.connect(ALERTS_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute(
            "SELECT id, timestamp, rule_name, detail "
            "FROM alerts WHERE id > ? ORDER BY id ASC",
            (since_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "rule_name": r[2],
                "detail": r[3][:120] if r[3] else "",
            }
            for r in rows
        ]
    except Exception:
        return []


def clear_all_alerts():
    """Delete all rows from alerts.db."""
    try:
        conn = sqlite3.connect(ALERTS_PATH)
        conn.execute("DELETE FROM alerts")
        conn.commit()
        conn.close()
        print("[Alert] All alerts cleared")
    except Exception as e:
        print(f"[Alert] Clear error: {e}")


# =====================================================================
#  Camera Manager (shared-memory reader → JPEG)
# =====================================================================

class CameraManager:
    """Manages reading frames from shared memory and encoding them as JPEG."""

    def __init__(self, cam_name: str, width=CAM_WIDTH, height=CAM_HEIGHT):
        self.cam_name = cam_name
        self.width = width
        self.height = height
        self._reader = None
        self._last_reconnect = 0
        self._reconnect_interval = 2.0
        self._no_signal_jpeg = None

    def start(self):
        """Create the shared-memory reader and prepare the no-signal image."""
        self._reader = SharedFrameReader(
            self.cam_name, height=self.height, width=self.width
        )
        self._no_signal_jpeg = self._make_no_signal_jpeg()
        print(f"[Camera] Reader started for: {self.cam_name}")

    def stop(self):
        """Close the shared-memory reader."""
        if self._reader:
            self._reader.close()

    def _make_no_signal_jpeg(self) -> bytes:
        """Generate a static 'No Signal' JPEG placeholder."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.putText(frame, "No Signal", (self.width // 4, self.height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (128, 128, 128), 3)
        cv2.putText(frame, f"waiting for cv_pipeline ({self.cam_name})...",
                    (30, self.height // 2 + 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1)
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        return buf.tobytes()

    def _try_reconnect(self):
        """Attempt to reconnect the shared-memory reader (rate-limited)."""
        now = time.time()
        if now - self._last_reconnect < self._reconnect_interval:
            return
        self._last_reconnect = now
        try:
            if self._reader:
                self._reader.close()
            self._reader = SharedFrameReader(
                self.cam_name, height=self.height, width=self.width
            )
        except Exception:
            pass

    @property
    def is_streaming(self) -> bool:
        """Whether the shared-memory reader is connected."""
        if self._reader is None:
            return False
        return self._reader.is_connected

    def get_jpeg_bytes(self) -> bytes:
        """Read the latest frame and return JPEG bytes (or no-signal placeholder)."""
        frame = None
        age_ms = -1

        if self._reader:
            try:
                frame, meta = self._reader.read()
                age_ms = meta.get("age_ms", -1)
            except Exception:
                frame = None

        # If no frame or too stale, try reconnecting
        if frame is None or age_ms > 5000:
            self._try_reconnect()

        if frame is None or age_ms > 5000:
            return self._no_signal_jpeg or b""

        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        return buf.tobytes()


cam0_mgr = CameraManager("cam0")
cam1_mgr = CameraManager("cam1")


# =====================================================================
#  MJPEG Streaming Endpoints
# =====================================================================

def mjpeg_generator(cam_mgr: CameraManager):
    """Yield MJPEG frames as a multipart stream."""
    interval = 1.0 / STREAM_FPS
    while True:
        jpeg = cam_mgr.get_jpeg_bytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )
        time.sleep(interval)


@app.get("/stream/cam0")
def stream_cam0():
    return StreamingResponse(
        mjpeg_generator(cam0_mgr),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/stream/cam1")
def stream_cam1():
    return StreamingResponse(
        mjpeg_generator(cam1_mgr),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# =====================================================================
#  NiceGUI — UI
# =====================================================================

DARK_STYLE = """
<style>
body {
    background-color: #1a1a2e !important;
}
.nicegui-content {
    max-width: 100% !important;
    padding: 16px !important;
}
.section-card {
    background-color: #16213e !important;
    border-radius: 12px;
    padding: 16px;
}
.chat-bubble-user {
    background-color: #0f3460;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 4px 0;
    color: #e0e0e0;
}
.chat-bubble-ai {
    background-color: #1a1a40;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 4px 0;
    color: #a0d2db;
    border-left: 3px solid #0f3460;
}
.cam-stream {
    width: 100%;
    border-radius: 8px;
    background-color: #000;
}
.alert-row-new {
    animation: alert-flash 1s ease-in-out 2;
}
@keyframes alert-flash {
    0%, 100% { background-color: transparent; }
    50% { background-color: rgba(255, 80, 80, 0.15); }
}
</style>
"""


@ui.page("/")
def main_page():
    """Main dashboard page."""

    ui.html(DARK_STYLE)

    with ui.row().classes("w-full items-center justify-between mb-4"):
        ui.label("\U0001f6e1\ufe0f Edge AI Guard System").classes("text-3xl font-bold text-white")
        ui.label("Dashboard").classes("text-lg text-gray-400")

    # =================================================================
    #  Camera section (MJPEG streaming)
    # =================================================================
    with ui.row().classes("w-full gap-4 mb-4"):

        with ui.card().classes("section-card flex-1"):
            ui.label("\U0001f4f7 Camera 0").classes("text-lg font-bold text-white mb-2")
            ui.html('<img src="/stream/cam0" class="cam-stream" />')
            cam0_status = ui.label("connecting...").classes("text-xs text-gray-400 mt-1")

        with ui.card().classes("section-card flex-1"):
            ui.label("\U0001f4f7 Camera 1").classes("text-lg font-bold text-white mb-2")
            ui.html('<img src="/stream/cam1" class="cam-stream" />')
            cam1_status = ui.label("connecting...").classes("text-xs text-gray-400 mt-1")

    def update_cam_status():
        cam0_status.set_text("\U0001f7e2 streaming" if cam0_mgr.is_streaming else "\U0001f534 waiting")
        cam1_status.set_text("\U0001f7e2 streaming" if cam1_mgr.is_streaming else "\U0001f534 waiting")

    ui.timer(2.0, update_cam_status)

    # =================================================================
    #  LLM Chat + Rule List
    # =================================================================
    with ui.row().classes("w-full gap-4"):

        # ----- LLM Chat -----
        with ui.card().classes("section-card flex-1"):
            ui.label("\U0001f4ac AI Guard Chat").classes("text-lg font-bold text-white mb-2")

            chat_container = ui.column().classes("w-full overflow-y-auto").style("max-height: 400px;")

            with ui.row().classes("w-full mt-2 gap-2"):
                chat_input = ui.input(
                    placeholder="Ask a question (e.g. how many people in the last hour?)"
                ).classes("flex-grow").props("dark outlined color=white")
                send_btn = ui.button("Send", color="blue").classes("self-end")

            llm_status = ui.label(
                "\U0001f7e2 LLM Ready" if llm_ready else "\U0001f7e1 LLM loading..."
            ).classes("text-xs text-gray-400 mt-1")

            def update_llm_status():
                if llm_ready:
                    llm_status.set_text("\U0001f7e2 LLM Ready")

            ui.timer(2.0, update_llm_status)

            async def handle_send():
                question = chat_input.value.strip()
                if not question:
                    return

                with chat_container:
                    ui.html(f'<div class="chat-bubble-user">\U0001f9d1 {question}</div>')

                chat_input.set_value("")
                send_btn.disable()
                ui.notify("\u23f3 Querying...", type="ongoing", timeout=2000)

                result = await run.io_bound(nl2sql_pipeline, question)

                with chat_container:
                    ui.html(f'<div class="chat-bubble-ai">\U0001f916 {result["answer"]}</div>')

                    if result["sql"]:
                        with ui.expansion("\U0001f4c4 View SQL", icon="code").classes("text-gray-500 text-xs"):
                            ui.code(result["sql"], language="sql")

                    if result["error"]:
                        ui.label(f'\u26a0\ufe0f {result["error"]}').classes("text-red-400 text-xs")

                send_btn.enable()

                await ui.run_javascript(
                    'const el = document.querySelector(".overflow-y-auto");'
                    'if (el) el.scrollTop = el.scrollHeight;'
                )

            send_btn.on_click(handle_send)
            chat_input.on("keydown.enter", handle_send)

        # ----- Rule List -----
        with ui.card().classes("section-card flex-1"):
            ui.label("\U0001f4dc Rule List").classes("text-lg font-bold text-white mb-2")

            rule_columns = [
                {"name": "name",        "label": "Name",         "field": "name",        "align": "left"},
                {"name": "description", "label": "Description",  "field": "description", "align": "left"},
                {"name": "interval_sec","label": "Cooldown (s)", "field": "interval_sec","align": "center"},
                {"name": "activated_at","label": "Activated",    "field": "activated_at","align": "center"},
            ]

            rules_table = ui.table(
                columns=rule_columns,
                rows=load_rules(),
                row_key="name",
                selection="single",
            ).classes("w-full").props("dark flat bordered")

            def handle_delete():
                selected = rules_table.selected
                if not selected:
                    ui.notify("\u26a0\ufe0f Please select a rule to delete", type="warning")
                    return
                name = selected[0].get("name", "")
                if delete_rule(name):
                    rules_table.rows = load_rules()
                    rules_table.selected = []
                    ui.notify(f"\u2705 Deleted rule: {name}", type="positive")
                else:
                    ui.notify(f"\u274c Rule not found: {name}", type="negative")

            ui.button("\U0001f5d1\ufe0f Delete selected", color="red", on_click=handle_delete).classes("mt-2")

            ui.separator().classes("my-3")
            ui.label("\u2795 Add Rule").classes("text-md font-bold text-white mb-1")
            ui.label("Describe the rule in natural language; LLM will auto-generate SQL").classes("text-xs text-gray-500 mb-2")

            with ui.column().classes("w-full gap-2"):
                rule_name = ui.input("Rule name").props(
                    "dark outlined dense color=white"
                ).classes("w-full")
                rule_desc = ui.input(
                    "Rule description (e.g. person detected for 5 consecutive minutes)"
                ).props("dark outlined dense color=white").classes("w-full")

                with ui.row().classes("gap-2"):
                    rule_interval = ui.number(
                        "Cooldown (s)", value=60, min=5, max=3600
                    ).props("dark outlined dense color=white").classes("w-32")
                    add_btn = ui.button("Add", color="green", icon="add")

            async def handle_add():
                name = rule_name.value.strip()
                desc = rule_desc.value.strip()
                interval = int(rule_interval.value or 60)

                if not name or not desc:
                    ui.notify("\u26a0\ufe0f Name and description are required", type="warning")
                    return

                if not llm_ready:
                    ui.notify("\u26a0\ufe0f LLM not loaded yet, cannot generate SQL", type="warning")
                    return

                add_btn.disable()
                ui.notify("\u23f3 LLM generating SQL...", type="ongoing", timeout=5000)

                new_rule = await run.io_bound(add_rule_with_llm, name, desc, interval)
                rules_table.rows = load_rules()

                if new_rule.get("sql"):
                    ui.notify(f"\u2705 Rule added: {name} (active immediately)", type="positive")
                else:
                    ui.notify(
                        f"\u26a0\ufe0f Rule added but SQL generation failed — check description",
                        type="warning",
                    )

                add_btn.enable()
                rule_name.set_value("")
                rule_desc.set_value("")
                rule_interval.set_value(60)

            add_btn.on_click(handle_add)

    # =================================================================
    #  Alert Log Panel (reads from alerts.db, auto-refresh)
    # =================================================================
    with ui.card().classes("section-card w-full mt-4"):

        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label("\u26a0\ufe0f Alert Log").classes("text-lg font-bold text-white")
                alert_badge = ui.badge("0", color="red").props("floating")

            def handle_clear():
                clear_all_alerts()
                alert_table.rows = []
                alert_badge.set_text("0")
                ui.notify("\U0001f5d1\ufe0f All alerts cleared", type="info")

            ui.button("Clear All", color="grey-8", icon="delete_sweep",
                      on_click=handle_clear).props("flat dense")

        alert_columns = [
            {"name": "id",        "label": "#",         "field": "id",        "align": "center", "sortable": True},
            {"name": "timestamp", "label": "Time",      "field": "timestamp", "align": "left",   "sortable": True},
            {"name": "rule_name", "label": "Rule",      "field": "rule_name", "align": "left"},
            {"name": "detail",    "label": "Detail",    "field": "detail",    "align": "left"},
        ]

        alert_table = ui.table(
            columns=alert_columns,
            rows=fetch_recent_alerts(),
            row_key="id",
        ).classes("w-full").props("dark flat bordered dense")

        # -- Track last seen alert ID for toast popup --
        nonlocal_state = {"last_alert_id": get_max_alert_id()}

        def poll_alerts():
            """Periodically refresh the alert table and show toast for new alerts."""
            # Refresh table
            alerts = fetch_recent_alerts()
            alert_table.rows = alerts
            alert_badge.set_text(str(len(alerts)))

            # Check for new alerts since last poll
            new_alerts = fetch_new_alerts(nonlocal_state["last_alert_id"])
            for a in new_alerts:
                ui.notify(
                    f"\u26a0\ufe0f {a['rule_name']}\n{a['timestamp']}",
                    type="negative",
                    position="top-right",
                    close_button=True,
                    timeout=8000,
                )
            if new_alerts:
                nonlocal_state["last_alert_id"] = new_alerts[-1]["id"]

        ui.timer(5.0, poll_alerts)

    # =================================================================
    #  Footer
    # =================================================================
    ui.separator().classes("my-4")
    with ui.row().classes("w-full justify-between"):
        ui.label("Edge AI Guard System v0.5 — Internal Demo").classes(
            "text-xs text-gray-500"
        )
        ui.label(f"Device: IQ9 (QCS9075) | Model: {Path(MODEL_PATH).stem}").classes(
            "text-xs text-gray-500"
        )


# =====================================================================
#  Application startup / shutdown events
# =====================================================================

@app.on_startup
async def on_startup():
    global rule_checker

    print("[System] Initializing database...")
    init_db(DB_PATH, ALERTS_PATH)

    print("[System] Starting shared frame readers...")
    cam0_mgr.start()
    cam1_mgr.start()

    print("[System] Loading LLM engine (background)...")
    threading.Thread(target=init_llm, daemon=True).start()

    def start_rule_checker():
        global rule_checker
        # Wait for LLM to be ready before compiling rules
        while not llm_ready:
            time.sleep(1)
        rule_checker = RuleChecker(DB_PATH, ALERTS_PATH, RULES_PATH, llm_engine, llm_lock)
        rule_checker.start()
        print("[System] RuleChecker started.")

    threading.Thread(target=start_rule_checker, daemon=True).start()


@app.on_shutdown
async def on_shutdown():
    print("[System] Shutting down...")
    cam0_mgr.stop()
    cam1_mgr.stop()
    if rule_checker:
        rule_checker.stop()
    print("[System] Goodbye.")


# =====================================================================
#  Launch NiceGUI
# =====================================================================

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8080,
        title="Edge AI Guard System",
        dark=True,
        reload=False,
        show=False,
    )
