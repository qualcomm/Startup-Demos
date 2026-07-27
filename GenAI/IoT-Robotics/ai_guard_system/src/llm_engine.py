#===-----------------ai_guard_system llm_engine-----------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import os
import re
import sqlite3
import threading
import json
import subprocess
import time
from collections import deque
from datetime import datetime

# =====================================================================
#  Suppress C++ / TensorFlow stderr noise (before importing litert_lm)
# =====================================================================
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["ABSL_MIN_LOG_LEVEL"] = "3"

_real_stderr_fd = os.dup(2)
_devnull_fd = os.open(os.devnull, os.O_WRONLY)
os.dup2(_devnull_fd, 2)
os.close(_devnull_fd)

import litert_lm

os.dup2(_real_stderr_fd, 2)

# =====================================================================
#  Paths
# =====================================================================
MODEL_PATH  = os.path.expanduser("./gemma-4-E2B-it.litertlm")
DB_PATH     = os.path.expanduser("./events.db")
RULES_PATH  = os.path.expanduser("./rules_en.json")
ALERTS_PATH = os.path.expanduser("./alerts.db")


# =====================================================================
#  Database initialisation (create views and alert table)
# =====================================================================

def init_db(db_path, alerts_path):
    """Create the events_view in the main DB and the alerts table in the alerts DB."""

    # -- events_view: unpivot the 4 count columns into (object_type, count) rows --
    conn = sqlite3.connect(db_path)
    conn.execute("DROP VIEW IF EXISTS events_view;")
    conn.execute("""
        CREATE VIEW events_view AS
        SELECT timestamp, camera_id, 'person'  AS object_type, person_count  AS count
          FROM events WHERE person_count  > 0
        UNION ALL
        SELECT timestamp, camera_id, 'vehicle' AS object_type, vehicle_count AS count
          FROM events WHERE vehicle_count > 0
        UNION ALL
        SELECT timestamp, camera_id, 'animal'  AS object_type, animal_count  AS count
          FROM events WHERE animal_count  > 0
        UNION ALL
        SELECT timestamp, camera_id, 'item'  AS object_type, item_count  AS count
          FROM events WHERE item_count  > 0;
    """)
    conn.close()
    print("[SYS] events_view created ✅")

    # -- alerts table (separate DB) --
    conn = sqlite3.connect(alerts_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,       -- alert trigger time 'YYYY-MM-DD HH:MM:SS'
            rule_name TEXT,       -- rule name
            detail TEXT            -- trigger data (JSON)
        );
    """)
    conn.close()
    print("[SYS] alerts table ready ✅")


# =====================================================================
#  Prompt templates
# =====================================================================

# Schema description given to the LLM so it can generate correct SQL.
SCHEMA = """
CREATE TABLE events_view (
    timestamp TEXT,       -- format: 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD HH:MM:SS', one row per minute
    camera_id INTEGER,    -- 0 or 1 (two cameras)
    object_type TEXT,     -- 'person', 'vehicle', 'animal', 'object'
    count INTEGER         -- detected count for this minute
);
-- One row per minute per camera per object type.
-- Use replace(timestamp,'T',' ') before strftime/DATE functions.

-- alerts lives in a separate DB, attached as alert_db
CREATE TABLE alert_db.alerts (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,       -- alert trigger time 'YYYY-MM-DD HH:MM:SS'
    rule_name TEXT,       -- rule name
    detail TEXT            -- raw trigger data (JSON string)
);
-- Query alerts via alert_db.alerts
""".strip()

# NL2SQL prompt: asks the LLM to convert a natural-language question into SQL.
NL2SQL_PROMPT = """You are a SQLite assistant. Return only one SQL statement. Do not explain.

Schema:
{schema}

Rules:
1. "person" = 'person', "vehicle" / "car" = 'vehicle', "animal" = 'animal', "item" = 'item'
2. Always apply replace(timestamp,'T',' ') before any strftime / DATE function.
3. "evening" / "night" = 18:00–23:59, "morning" = 06:00–11:59, "afternoon" = 12:00–17:59.
4. Only refer to recent conversation history when the question contains follow-up cues such as "same", "previous", "that one", "again", "same condition", "continue", "last question".
5. When using GROUP BY on a time expression, the SELECT clause must include the full strftime(...) AS alias — do not omit it.
6. When the question asks about a specific object type, always add a WHERE object_type = '...' condition.
7. Do NOT use SQLite's datetime('now') or time('now'). The current time is {now} — use this value directly.
8. "just now" / "now" = the last 1 minutes, "recently" = the last 5 minutes.
9. SQLite does NOT support INTERVAL syntax. For time arithmetic,either use datetime('...', '-N minutes') or calculate the timestamp directly.
10. When the question refers to a specific date (e.g. "on 6/1", "today","yesterday"), always use a range:replace(timestamp,'T',' ') >= 'YYYY-MM-DD 00:00:00'AND replace(timestamp,'T',' ') < 'YYYY-MM-DD+1 00:00:00'
    Never use = with a single timestamp for date queries.

Recent conversation:
{history}

Examples:
Q: Which time period has the most people on cam0?
A: SELECT strftime('%H', replace(timestamp,'T',' ')) AS hour, SUM(count) AS total FROM events_view WHERE camera_id = 0 AND object_type = 'person' GROUP BY hour ORDER BY total DESC LIMIT 1;

Q: Which camera had the most people on the evening of 5/19?
A: SELECT camera_id, SUM(count) AS total FROM events_view WHERE object_type = 'person' AND replace(timestamp,'T',' ') >= '2026-05-19 18:00:00' AND replace(timestamp,'T',' ') < '2026-05-20 00:00:00' GROUP BY camera_id ORDER BY total DESC LIMIT 1;

Q: What type of object was detected the most?
A: SELECT object_type, SUM(count) AS total FROM events_view GROUP BY object_type ORDER BY total DESC LIMIT 1;

Q: What is the average number of people detected per hour on cam1?
A: SELECT strftime('%H', replace(timestamp,'T',' ')) AS hour, AVG(count) AS avg_person FROM events_view WHERE camera_id = 1 AND object_type = 'person' GROUP BY hour ORDER BY hour;

Q: {question}
A: """

# Answer prompt: asks the LLM to produce a human-friendly answer from SQL results.
ANSWER_PROMPT = """You are the assistant for an Edge AI surveillance system. Answer concisely in English.

User question: {question}
SQL query: {sql}
Query result:
{result_table}

Notes:
- camera_id 0 → say "cam0", camera_id 1 → say "cam1"
- object_type translation: person = 人, vehicle = 車/交通工具, animal = 動物, object = 物品
- If the result is None or empty, treat it as 0 or "none detected"
Based on the results above, answer the question directly. Do not repeat the SQL."""

# Rule-to-SQL prompt: converts a natural-language alert rule into an SQL query.
RULE_TO_SQL_PROMPT = """You are a SQLite assistant. Return only one SQL statement. Do not explain.

Schema:
{schema}

Requirements: Generate one SQL query based on the following alert rule.
- When the condition is met, the SQL must return at least one row.
- When the condition is NOT met, the SQL must return zero rows.
- For "last N minutes", use: replace(timestamp,'T',' ') >= datetime('now','localtime','-N minutes')
- Always apply replace(timestamp,'T',' ') before any time function.
- "person" = 'person', "vehicle" / "car" = 'vehicle', "animal" = 'animal', "item" = 'item'
- cam0 = camera_id 0, cam1 = camera_id 1
- "early morning" / "dawn" = 00:00–06:00
- "detected X for N consecutive minutes" = in the last N minutes, X was detected in N distinct minutes.
  Use COUNT(DISTINCT strftime('%Y-%m-%d %H:%M', replace(timestamp,'T',' '))) to count,
  combined with HAVING >= N.

Examples:
Rule: Vehicle detected for 3 consecutive minutes
SQL: SELECT camera_id, COUNT(DISTINCT strftime('%Y-%m-%d %H:%M', replace(timestamp,'T',' '))) AS mins FROM events_view WHERE object_type = 'vehicle' AND replace(timestamp,'T',' ') >= datetime('now','localtime','-3 minutes') GROUP BY camera_id HAVING mins >= 3;

Rule: Person detected on cam0
SQL: SELECT timestamp, camera_id, count FROM events_view WHERE camera_id = 0 AND object_type = 'person' AND replace(timestamp,'T',' ') >= datetime('now','localtime','-1 minutes') LIMIT 10;

Alert rule: {rule_nl}

SQL: """


# =====================================================================
#  LLM generation
# =====================================================================

def llm_generate(engine, prompt, stream=False) -> str:
    """
    Generate text from the LLM engine.

    Temporarily redirects stderr to /dev/null to suppress C++ runtime noise,
    then restores it after the first chunk (streaming) or after completion.
    """
    full_text = []

    _devnull = os.open(os.devnull, os.O_WRONLY)
    _backup = os.dup(2)
    os.dup2(_devnull, 2)
    os.close(_devnull)

    with engine.create_conversation() as conv:
        if stream:
            first_chunk = True
            for chunk in conv.send_message_async(prompt):
                if first_chunk:
                    os.dup2(_backup, 2)
                    os.close(_backup)
                    first_chunk = False
                for item in chunk.get("content", []):
                    if item.get("type") == "text":
                        print(item["text"], end="", flush=True)
                        full_text.append(item["text"])
            if first_chunk:
                os.dup2(_backup, 2)
                os.close(_backup)
            print()
        else:
            resp = conv.send_message(prompt)
            os.dup2(_backup, 2)
            os.close(_backup)
            full_text.append(resp["content"][0]["text"])

    return "".join(full_text)


# =====================================================================
#  SQL extraction and execution
# =====================================================================

def extract_sql(text: str) -> str:
    """Extract the first SQL SELECT statement from LLM output text."""
    clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text).replace("\r", "\n")

    # Try ```sql ... ``` fenced block first
    m = re.search(r"```sql\s*(.*?)\s*```", clean, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Try generic ``` ... ``` block
    m = re.search(r"```\s*(.*?)\s*```", clean, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Try bare SELECT statement
    m = re.search(r"(SELECT\s+.+?)(;|$)", clean, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip() + ";"

    return ""


def run_query(db_path: str, sql: str, alerts_path: str = ""):
    """Execute SQL against the events DB (optionally attaching the alerts DB)."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        # Attach alerts DB so SQL can reference alert_db.alerts
        if alerts_path:
            conn.execute(f"ATTACH DATABASE '{alerts_path}' AS alert_db;")
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
        return cols, rows, None
    except Exception as e:
        return [], [], str(e)


def format_result_table(columns, rows, limit=20) -> str:
    """Format query results as a plain-text table for the LLM answer prompt."""
    if not rows:
        return "(no data)"
    header = " | ".join(columns) if columns else "result"
    lines = [header, "-" * len(header)]
    for r in rows[:limit]:
        lines.append(" | ".join("NULL" if v is None else str(v) for v in r))
    return "\n".join(lines)


# =====================================================================
#  Conversation context (keep last 2 turns)
# =====================================================================

FOLLOWUP_HINTS = ("same", "previous", "last question", "that one", "again", "same condition", "continue", "earlier")


def is_followup(question: str) -> bool:
    """Detect whether a question is a follow-up that requires conversation context."""
    q_lower = question.lower()
    return any(k in q_lower for k in FOLLOWUP_HINTS)


def build_history_text(hist, question: str) -> str:
    """Build a history snippet for the NL2SQL prompt (only for follow-up questions)."""
    if not hist or not is_followup(question):
        return "(none)"
    lines = []
    for i, h in enumerate(hist, 1):
        lines.append(f"[prev {i}] Q: {h['question']}")
        lines.append(f"[prev {i}] SQL: {h['sql']}")
    return "\n".join(lines)


# =====================================================================
#  RuleChecker: background rule evaluation + alert notification
# =====================================================================

class RuleChecker:
    """
    Background daemon thread that periodically evaluates user-defined rules
    against the SQLite database and sends desktop notifications (+ writes
    to alerts.db) when a rule triggers.
    """

    def __init__(self, db_path, alerts_path, rules_path, engine, llm_lock):
        self.db_path = db_path
        self.alerts_path = alerts_path       # separate alerts DB
        self.rules_path = rules_path
        self.engine = engine
        self.llm_lock = llm_lock             # shared with main thread
        self._stop = threading.Event()
        self._compiled = []                  # compiled rule list

        # Load and compile rules
        raw_rules = self._load_rules(rules_path)
        if raw_rules:
            self._compile_rules(raw_rules)

    # ----- Load rules from JSON -----
    @staticmethod
    def _load_rules(path):
        if not os.path.isfile(path):
            print(f"[RULE] ⚠ Rules file not found: {path} — using empty list")
            return []
        with open(path, "r", encoding="utf-8") as f:
            rules = json.load(f)
        print(f"[RULE] Loaded {len(rules)} rules")
        return rules

    # ----- Compile rules (NL → SQL via LLM) -----
    def _compile_rules(self, raw_rules):
        print("[RULE] 🔄 Compiling rules to SQL (running LLM)...", flush=True)
        for r in raw_rules:
            if not r.get("enabled", True):
                self._compiled.append({
                    **r, "sql": None,
                    "last_triggered": 0,
                    "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                print(f"  ⏸ {r['name']} (disabled)")
                continue

            prompt = RULE_TO_SQL_PROMPT.format(schema=SCHEMA, rule_nl=r["rule_nl"])
            with self.llm_lock:
                resp = llm_generate(self.engine, prompt, stream=False)
            sql = extract_sql(resp)
            self._compiled.append({
                **r, "sql": sql,
                "last_triggered": 0,
                "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            status = "✅" if sql else "⚠ Failed to generate SQL"
            print(f"  {status} {r['name']}")
            if sql:
                print(f"      SQL: {sql}")
        print(f"[RULE] Rule compilation finished ({len(self._compiled)} rules)\n")

    # ----- Background check (runs every 10 s) -----
    def _check_once(self):
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        for rule in self._compiled:
            if not rule.get("enabled", True) or not rule.get("sql"):
                continue

            # Skip if still in cooldown period (check_interval=0 means no cooldown)
            cooldown = rule.get("check_interval", 0)
            if cooldown > 0 and (now - rule["last_triggered"]) < cooldown:
                continue

            try:
                # Only check data newer than the rule's activation watermark
                activated = rule["activated_at"]
                safe_sql = rule["sql"].replace(
                    "events_view",
                    f"(SELECT * FROM events_view "
                    f"WHERE replace(timestamp,'T',' ') >= '{activated}') "
                    f"AS events_view"
                )
                cur = conn.cursor()
                cur.execute(safe_sql)
                rows = cur.fetchall()
                if rows:
                    self._send_alert(rule["name"], rows)
                    rule["last_triggered"] = now
                    # Advance watermark so the same data doesn't re-trigger
                    rule["activated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f'[RULE] ❌ Rule "{rule["name"]}" SQL error: {e}')
        conn.close()

    def _send_alert(self, rule_name, data):
        """Write alert to alerts.db + send desktop notification + console log."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        detail = json.dumps(data[:10], ensure_ascii=False, default=str)

        # Write to alerts DB
        try:
            conn = sqlite3.connect(self.alerts_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                "INSERT INTO alerts (timestamp, rule_name, detail) VALUES (?, ?, ?)",
                (now_str, rule_name, detail)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[RULE] ❌ Failed to write alerts.db: {e}")

        # Desktop notification (notify-send)
        notify_body = f"Time: {now_str}\n{detail[:100]}"
        try:
            subprocess.run(
                ["notify-send", "-u", "critical", "-i", "dialog-warning",
                 f"⚠ {rule_name}", notify_body],
                timeout=5, check=False,
            )
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Console output
        print(f"\n{'='*50}")
        print(f"[ALERT] ⚠ {rule_name}")
        print(f"[ALERT] 🕐 {now_str}")
        print(f"[ALERT] 📊 {detail[:200]}")
        print(f"{'='*50}\n")

    # ----- Thread control -----
    def start(self):
        """Start the background rule checker (runs immediately, then every 10 s)."""
        # Run an immediate check on startup
        try:
            self._check_once()
        except Exception as e:
            print(f"[RULE] ❌ Initial check error: {e}")

        def _loop():
            while not self._stop.is_set():
                self._stop.wait(10)  # check every 10 seconds
                try:
                    self._check_once()
                except Exception as e:
                    print(f"[RULE] ❌ Background check error: {e}")

        t = threading.Thread(target=_loop, daemon=True, name="RuleChecker")
        t.start()
        print("[RULE] ✅ Background rule checker started\n")

    def stop(self):
        self._stop.set()
        print("[RULE] Background rule checker stopped")

    # ----- Dynamic rule management -----
    def add_rule(self, name, rule_nl, check_interval=60):
        """Add a new rule: compile via LLM and add to the background check list."""
        new_rule = {
            "name": name, "rule_nl": rule_nl,
            "check_interval": check_interval, "enabled": True,
        }
        prompt = RULE_TO_SQL_PROMPT.format(schema=SCHEMA, rule_nl=rule_nl)
        print(f"[RULE] 🔄 Compiling rule \"{name}\"...", flush=True)
        with self.llm_lock:
            resp = llm_generate(self.engine, prompt, stream=False)
        sql = extract_sql(resp)
        if not sql:
            print(f"[RULE] ⚠ Failed to generate SQL — rule not added")
            return False
        self._compiled.append({
            **new_rule, "sql": sql,
            "last_triggered": 0,
            "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._save_rules()
        print(f"[RULE] ✅ Rule \"{name}\" added")
        print(f"       SQL: {sql}")
        return True

    def delete_rule(self, index):
        """Delete the rule at the given index."""
        if 0 <= index < len(self._compiled):
            removed = self._compiled.pop(index)
            self._save_rules()
            print(f"[RULE] 🗑 Deleted rule \"{removed['name']}\"")
            return True
        else:
            print(f"[RULE] ⚠ Invalid index: {index} (total {len(self._compiled)} rules)")
            return False

    def list_rules(self):
        """Print all rules in a formatted table."""
        if not self._compiled:
            print("[RULE] No rules defined")
            return
        print(f"\n{'─'*70}")
        print(f"  {'#':<4} {'Name':<16} {'Cooldown':>8}  {'Status':<6}  {'Activated':<20} SQL")
        print(f"{'─'*70}")
        for i, r in enumerate(self._compiled):
            status = "✅ ON" if r.get("enabled", True) and r.get("sql") else "⏸ OFF"
            sql_short = (r.get("sql") or "N/A")[:40]
            activated = r.get("activated_at", "N/A")
            cd = r.get("check_interval", 0)
            cd_str = f"{cd}s" if cd > 0 else "none"
            print(f"  {i:<4} {r['name']:<16} {cd_str:>8}  {status:<6}  {activated:<20} {sql_short}")
        print(f"{'─'*70}\n")

    def _save_rules(self):
        """Persist current rules back to the JSON file (original fields only)."""
        output = []
        for r in self._compiled:
            output.append({
                "name": r["name"],
                "rule_nl": r["rule_nl"],
                "check_interval": r.get("check_interval", 60),
                "enabled": r.get("enabled", True),
            })
        with open(self.rules_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)


# =====================================================================
#  CLI main (interactive terminal mode)
# =====================================================================

def main():
    print("=" * 60)
    print("  Edge AI Guard — NL2SQL (View + Rule Alert v6-en)")
    print("  Type 'q' to quit | 'raw' to toggle SQL/result display")
    print("  Type 'rule' for rule command help")
    print("=" * 60)

    # Create views and tables
    init_db(DB_PATH, ALERTS_PATH)

    print("[SYS] Loading model...", flush=True)

    _devnull = os.open(os.devnull, os.O_WRONLY)
    _backup = os.dup(2)
    os.dup2(_devnull, 2)
    os.close(_devnull)

    engine = litert_lm.Engine(MODEL_PATH, backend=litert_lm.Backend.GPU)

    os.dup2(_backup, 2)
    os.close(_backup)

    print("[SYS] Model ready! ✅\n", flush=True)

    # Shared LLM lock (prevents concurrent access)
    llm_lock = threading.Lock()

    # Start background rule checker
    checker = RuleChecker(DB_PATH, ALERTS_PATH, RULES_PATH, engine, llm_lock)
    checker.start()

    show_raw = False
    history = deque(maxlen=2)

    try:
        while True:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                question = input("[You] ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not question:
                continue
            if question.lower() == "q":
                break
            if question.lower() == "raw":
                show_raw = not show_raw
                print(f"[SYS] raw={'ON' if show_raw else 'OFF'}")
                continue

            # ----- Rule management commands -----
            if question.lower() == "rule":
                print("\n📋 Rule commands:")
                print("  rule list       — list all rules")
                print("  rule add        — add a new rule (interactive)")
                print("  rule del <N>    — delete rule #N")
                print()
                continue

            if question.lower() == "rule list":
                checker.list_rules()
                continue

            if question.lower().startswith("rule del"):
                parts = question.split()
                if len(parts) == 3 and parts[2].isdigit():
                    checker.delete_rule(int(parts[2]))
                else:
                    print("[SYS] Usage: rule del <index>")
                continue

            if question.lower() == "rule add":
                try:
                    name = input("  Rule name: ").strip()
                    rule_nl = input("  Rule description (natural language): ").strip()
                    interval_str = input("  Cooldown (seconds, 0=notify every time, default 0): ").strip()
                    interval = int(interval_str) if interval_str else 0
                    if name and rule_nl:
                        checker.add_rule(name, rule_nl, interval)
                    else:
                        print("[SYS] Name and description cannot be empty")
                except (KeyboardInterrupt, EOFError):
                    print("\n[SYS] Cancelled")
                continue

            # ----- Step 1: NL → SQL -----
            print("[SYS] 🔄 LLM generating SQL...", flush=True)
            history_text = build_history_text(history, question)
            prompt1 = NL2SQL_PROMPT.format(
                schema=SCHEMA, history=history_text, question=question, now=current_time
            )
            with llm_lock:
                sql_text = llm_generate(engine, prompt1, stream=False)
            sql = extract_sql(sql_text)

            if not sql:
                print("[SYS] ⚠ Could not extract SQL")
                print(f"[LLM raw] {sql_text}")
                continue

            if show_raw:
                print(f"[SQL] {sql}")

            # ----- Step 2: Execute SQL -----
            print("[SYS] 🔄 Querying SQLite...", flush=True)
            cols, rows, err = run_query(DB_PATH, sql, ALERTS_PATH)
            if err:
                print(f"[SYS] ❌ SQL error: {err}")
                print(f"[SQL] {sql}")
                continue

            result_table = format_result_table(cols, rows)
            if show_raw:
                print(f"[Result]\n{result_table}")

            # ----- Step 3: Generate answer -----
            print("[SYS] 🔄 LLM generating answer...\n", flush=True)
            prompt2 = ANSWER_PROMPT.format(
                question=question, sql=sql, result_table=result_table
            )
            print("[Answer] ", end="", flush=True)
            with llm_lock:
                answer = llm_generate(engine, prompt2, stream=True)

            # Update conversation history
            history.appendleft({"question": question, "sql": sql})
            print()

    finally:
        checker.stop()
        engine.close()
        print("Bye!")


if __name__ == "__main__":
    main()
