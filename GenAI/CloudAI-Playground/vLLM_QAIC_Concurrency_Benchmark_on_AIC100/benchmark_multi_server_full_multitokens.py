#===-- benchmark_multi_server_full_multitokens.py ------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import asyncio
import aiohttp
import time
import csv
import os
from datetime import datetime
import matplotlib.pyplot as plt

# =========================
# Config
# =========================
ENDPOINTS = [
    "http://localhost:8000/v1/chat/completions",
    "http://localhost:8001/v1/chat/completions",
    "http://localhost:8002/v1/chat/completions",
    "http://localhost:8003/v1/chat/completions",
]

MODEL_NAME = "meta-llama/Llama-3.2-3B-Instruct"
PROMPT = "Explain what AI is in simple terms."
TEMPERATURE = 0.7

# Sweep decode workload
MAX_TOKENS_LIST = [32, 128, 512]

# Sweep concurrency
CONCURRENCY_LEVELS = [1, 4, 8, 12, 16, 24, 32, 40, 48, 56, 64]

# Measurement windows
DURATION_S = 20
WARMUP_S = 3
REPEATS_PER_LEVEL = 3
REQUEST_TIMEOUT_S = 60

# Metrics
ENABLE_TOKEN_METRICS = True

# Output
RUN_TAG = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = "results"


# =========================
# Payload builder
# =========================
def build_payload(max_tokens: int):
    return {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens,
        "temperature": TEMPERATURE,
    }


# =========================
# One request (E2E latency)
# =========================
async def send_one(session, url, payload):
    start = time.perf_counter()
    try:
        async with session.post(url, json=payload, timeout=REQUEST_TIMEOUT_S) as resp:
            data = await resp.json()
            elapsed = time.perf_counter() - start

            if resp.status < 200 or resp.status >= 300:
                return False, elapsed, None

            completion_tokens = None
            if ENABLE_TOKEN_METRICS:
                usage = data.get("usage", {})
                if isinstance(usage, dict):
                    completion_tokens = usage.get("completion_tokens", None)

            return True, elapsed, completion_tokens

    except Exception:
        return False, None, None


# =========================
# Worker: fixed endpoint pinning (worker_id % N)
# =========================
async def worker(worker_id, session, end_t, warmup_end_t, per_worker_stats, payload):
    n = len(ENDPOINTS)
    url = ENDPOINTS[worker_id % n]
    ep_idx = worker_id % n

    local_success = 0
    local_fail = 0
    local_lat = []
    local_tokens = 0

    while True:
        now = time.perf_counter()
        if now >= end_t:
            break

        ok, latency, comp_tokens = await send_one(session, url, payload)
        done_t = time.perf_counter()

        # Use completion time for warmup filtering
        if done_t < warmup_end_t:
            continue

        if ok:
            local_success += 1
            if latency is not None:
                local_lat.append(latency)
            if comp_tokens is not None:
                local_tokens += comp_tokens
        else:
            local_fail += 1

    per_worker_stats.append((ep_idx, local_success, local_fail, local_lat, local_tokens))


# =========================
# Run one level (one concurrency, one max_tokens) for fixed duration
# =========================
async def run_level(concurrency, max_tokens):
    payload = build_payload(max_tokens)

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_S + 5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        t0 = time.perf_counter()
        warmup_end = t0 + WARMUP_S
        end_t = t0 + WARMUP_S + DURATION_S

        per_worker_stats = []
        tasks = [
            worker(i, session, end_t, warmup_end, per_worker_stats, payload)
            for i in range(concurrency)
        ]
        await asyncio.gather(*tasks)

    # Aggregate per-endpoint
    n = len(ENDPOINTS)
    ep_success = [0] * n
    ep_fail = [0] * n
    ep_latencies = [[] for _ in range(n)]
    ep_tokens = [0] * n

    for ep_idx, s, f, lats, toks in per_worker_stats:
        ep_success[ep_idx] += s
        ep_fail[ep_idx] += f
        ep_latencies[ep_idx].extend(lats)
        ep_tokens[ep_idx] += toks

    total_success = sum(ep_success)
    total_fail = sum(ep_fail)
    all_lat = [x for sub in ep_latencies for x in sub]

    # Throughput over measured window (exclude warmup)
    tps = total_success / DURATION_S if DURATION_S > 0 else 0.0
    tok_per_s = (sum(ep_tokens) / DURATION_S) if (ENABLE_TOKEN_METRICS and DURATION_S > 0) else None

    avg_lat = (sum(all_lat) / len(all_lat)) if all_lat else None
    max_lat = max(all_lat) if all_lat else None

    ep_tps = [s / DURATION_S for s in ep_success]
    ep_tokps = [(t / DURATION_S) for t in ep_tokens] if ENABLE_TOKEN_METRICS else [None] * n
    ep_avg_lat = [(sum(l)/len(l) if l else None) for l in ep_latencies]

    return {
        "concurrency": concurrency,
        "max_tokens": max_tokens,

        "total_success": total_success,
        "total_fail": total_fail,

        "tps_req_per_s": tps,
        "tok_per_s": tok_per_s,

        "avg_latency_s": avg_lat,
        "max_latency_s": max_lat,

        "ep_success": ep_success,
        "ep_fail": ep_fail,
        "ep_tps": ep_tps,
        "ep_tokps": ep_tokps,
        "ep_avg_lat": ep_avg_lat,
    }


# =========================
# Repeat & aggregate
# =========================
def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


async def run_repeats(concurrency, repeats, max_tokens):
    runs = []
    for _ in range(repeats):
        runs.append(await run_level(concurrency, max_tokens))
    return runs


def aggregate_runs(runs):
    n = len(ENDPOINTS)
    return {
        "concurrency": runs[0]["concurrency"],
        "max_tokens": runs[0]["max_tokens"],

        "tps_req_per_s_mean": mean([r["tps_req_per_s"] for r in runs]),
        "tok_per_s_mean": mean([r["tok_per_s"] for r in runs]),
        "avg_latency_s_mean": mean([r["avg_latency_s"] for r in runs]),
        "max_latency_s_mean": mean([r["max_latency_s"] for r in runs]),

        **{f"ep{i}_tps_mean": mean([r["ep_tps"][i] for r in runs]) for i in range(n)},
        **{f"ep{i}_tokps_mean": mean([r["ep_tokps"][i] for r in runs]) for i in range(n)},
        **{f"ep{i}_avg_lat_mean": mean([r["ep_avg_lat"][i] for r in runs]) for i in range(n)},
        **{f"ep{i}_fail_mean": mean([r["ep_fail"][i] for r in runs]) for i in range(n)},

        "total_fail_mean": mean([r["total_fail"] for r in runs]),
        "total_success_mean": mean([r["total_success"] for r in runs]),
    }


# =========================
# IO & plotting
# =========================
def safe_format(x, digits=2):
    return f"{x:.{digits}f}" if x is not None else "N/A"


def save_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def plot_overall_tps(rows, out_png, title_suffix=""):
    conc = [r["concurrency"] for r in rows]
    tps = [r["tps_req_per_s_mean"] for r in rows]
    plt.figure()
    plt.plot(conc, tps, marker="o")
    plt.xlabel("Concurrency (total across 4 servers)")
    plt.ylabel("TPS (requests/sec)")
    plt.title(f"Aggregate TPS vs Concurrency (4 servers) - {MODEL_NAME}{title_suffix}")
    plt.grid(True, linestyle="--", alpha=0.6)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_png, dpi=150, bbox_inches="tight", pad_inches=0.2)
    plt.close()


def plot_latency(rows, out_png, title_suffix=""):
    conc = [r["concurrency"] for r in rows]
    avg_lat = [r["avg_latency_s_mean"] for r in rows]
    max_lat = [r["max_latency_s_mean"] for r in rows]
    plt.figure()
    plt.plot(conc, avg_lat, marker="o", label="Avg latency")
    plt.plot(conc, max_lat, marker="x", label="Max latency")
    plt.xlabel("Concurrency (total across 4 servers)")
    plt.ylabel("Latency (sec)")
    plt.title(f"Latency vs Concurrency (4 servers) - {MODEL_NAME}{title_suffix}")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_png, dpi=150, bbox_inches="tight", pad_inches=0.2)
    plt.close()


def plot_per_endpoint_tps(rows, out_png, title_suffix="", jitter_x=True):
    """
    jitter_x=True will shift x slightly per endpoint so overlapping lines are visible.
    """
    conc = [r["concurrency"] for r in rows]
    plt.figure()

    offsets = [-0.30, -0.10, 0.10, 0.30]
    styles = ["-", "--", "-.", ":"]

    for i in range(len(ENDPOINTS)):
        tps_i = [r[f"ep{i}_tps_mean"] for r in rows]
        x_i = [(c + offsets[i]) for c in conc] if jitter_x else conc
        plt.plot(x_i, tps_i, marker="o", linestyle=styles[i], linewidth=2, label=f"endpoint {i}")

    plt.xlabel("Concurrency (total across 4 servers)")
    plt.ylabel("TPS per endpoint (req/s)")
    plt.title(f"Per-endpoint TPS vs Concurrency - {MODEL_NAME}{title_suffix}")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_png, dpi=150, bbox_inches="tight", pad_inches=0.2)
    plt.close()


def plot_multi_tokens_curves(all_rows_by_tokens, out_png, y_key, y_label, title):
    """
    Draw multiple lines (one per max_tokens) on the same chart.
    y_key: e.g. "tps_req_per_s_mean" or "tok_per_s_mean"
    """
    plt.figure()
    for max_tokens, rows in all_rows_by_tokens.items():
        conc = [r["concurrency"] for r in rows]
        y = [r[y_key] for r in rows]
        plt.plot(conc, y, marker="o", label=f"max_tokens={max_tokens}")

    plt.xlabel("Concurrency (total across 4 servers)")
    plt.ylabel(y_label)
    plt.title(title)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_png, dpi=150, bbox_inches="tight", pad_inches=0.2)
    plt.close()


# =========================
# Main
# =========================
async def main():
    print("Endpoints:")
    for e in ENDPOINTS:
        print("  ", e)
    print(f"\nModel={MODEL_NAME}, duration={DURATION_S}s, warmup={WARMUP_S}s, repeats={REPEATS_PER_LEVEL}")
    print(f"MAX_TOKENS_LIST={MAX_TOKENS_LIST}\n")

    os.makedirs(OUT_DIR, exist_ok=True)

    # Collect results for final multi-curve plots
    all_rows_by_tokens = {}

    for max_tokens in MAX_TOKENS_LIST:
        print("\n==============================")
        print(f" MAX_TOKENS = {max_tokens}")
        print("==============================\n")

        agg_rows = []

        for c in CONCURRENCY_LEVELS:
            runs = await run_repeats(c, REPEATS_PER_LEVEL, max_tokens)
            agg = aggregate_runs(runs)
            agg_rows.append(agg)

            print(f"=== Concurrency {c} ===")
            print(f"Aggregate TPS(mean): {safe_format(agg['tps_req_per_s_mean'])} req/s")
            print(f"Tokens/s(mean):      {safe_format(agg['tok_per_s_mean'])}")
            print(f"Avg latency(mean):   {safe_format(agg['avg_latency_s_mean'])} s")
            print(f"Max latency(mean):   {safe_format(agg['max_latency_s_mean'])} s")
            print(f"Total fail(mean):    {safe_format(agg['total_fail_mean'])}")
            print("")

        all_rows_by_tokens[max_tokens] = agg_rows

        # Per max_tokens outputs
        csv_path = f"{OUT_DIR}/multi_results_tok{max_tokens}_{RUN_TAG}.csv"
        tps_png = f"{OUT_DIR}/multi_tps_tok{max_tokens}_{RUN_TAG}.png"
        lat_png = f"{OUT_DIR}/multi_latency_tok{max_tokens}_{RUN_TAG}.png"
        per_png = f"{OUT_DIR}/per_endpoint_tps_tok{max_tokens}_{RUN_TAG}.png"

        save_csv(agg_rows, csv_path)
        plot_overall_tps(agg_rows, tps_png, title_suffix=f" (max_tokens={max_tokens})")
        plot_latency(agg_rows, lat_png, title_suffix=f" (max_tokens={max_tokens})")
        plot_per_endpoint_tps(agg_rows, per_png, title_suffix=f" (max_tokens={max_tokens})", jitter_x=True)

        print("Saved:")
        print("  CSV :", csv_path)
        print("  TPS :", tps_png)
        print("  LAT :", lat_png)
        print("  PER :", per_png)

    # Final multi-curve summary plots (compare max_tokens)
    multi_tps_png = f"{OUT_DIR}/compare_tps_multi_tokens_{RUN_TAG}.png"
    multi_tokps_png = f"{OUT_DIR}/compare_tokps_multi_tokens_{RUN_TAG}.png"

    plot_multi_tokens_curves(
        all_rows_by_tokens,
        multi_tps_png,
        y_key="tps_req_per_s_mean",
        y_label="TPS (requests/sec)",
        title=f"Aggregate TPS vs Concurrency (compare max_tokens) - {MODEL_NAME}"
    )

    plot_multi_tokens_curves(
        all_rows_by_tokens,
        multi_tokps_png,
        y_key="tok_per_s_mean",
        y_label="Tokens/sec",
        title=f"Tokens/sec vs Concurrency (compare max_tokens) - {MODEL_NAME}"
    )

    print("\nSaved multi-curve comparison plots:")
    print("  TPS compare :", multi_tps_png)
    print("  Tok/s compare:", multi_tokps_png)


if __name__ == "__main__":
    asyncio.run(main())