#===--rb3_intersection_traffic_measure.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, sys, time, signal, argparse, csv, json, math
from dataclasses import dataclass, field
from collections import Counter, OrderedDict, deque

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gst, GLib

try:
    import cairo
except Exception:
    cairo = None

# -----------------------------
# Utils
# -----------------------------
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def bbox_area(b):
    return max(0.0, b[2]-b[0]) * max(0.0, b[3]-b[1])

def bbox_iou(a, b):
    xx1 = max(a[0], b[0]); yy1 = max(a[1], b[1])
    xx2 = min(a[2], b[2]); yy2 = min(a[3], b[3])
    w = max(0.0, xx2 - xx1); h = max(0.0, yy2 - yy1)
    inter = w * h
    area1 = max(0.0, (a[2]-a[0])*(a[3]-a[1]))
    area2 = max(0.0, (b[2]-b[0])*(b[3]-b[1]))
    return inter / (area1 + area2 - inter + 1e-6)

def ema_bbox(old, new, alpha=0.6):
    return (
        alpha*new[0] + (1-alpha)*old[0],
        alpha*new[1] + (1-alpha)*old[1],
        alpha*new[2] + (1-alpha)*old[2],
        alpha*new[3] + (1-alpha)*old[3],
    )

def normalize_text(raw: str) -> str:
    if not raw:
        return ""
    s = raw
    while "\\\\" in s:
        s = s.replace("\\\\", "\\")
    s = s.replace("\\&", "&")
    s = (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&#34;", "\""))
    s = s.replace("\\ ", " ").replace("\\,", ",").replace("\\=", "=")
    s = s.replace("\\(", "(").replace("\\)", ")").replace("\\<", "<").replace("\\>", ">")
    s = s.replace('\\"', '"')
    return s

def get_caps_wh(elem, fallback=(1920,1080)):
    try:
        pad = elem.get_static_pad("sink")
        caps = pad.get_current_caps() if pad else None
        if not caps or caps.get_size() == 0:
            return fallback
        st = caps.get_structure(0)
        ok_w, w = st.get_int("width")
        ok_h, h = st.get_int("height")
        if ok_w and ok_h:
            return int(w), int(h)
    except Exception:
        pass
    return fallback

def simple_nms(dets, iou_thr=0.6):
    # per-label NMS
    by_label = {}
    for d in dets:
        by_label.setdefault(d["label"], []).append(d)
    kept = []
    for lb, arr in by_label.items():
        arr = sorted(arr, key=lambda x: x["conf"], reverse=True)
        out = []
        for d in arr:
            ok = True
            for k in out:
                if bbox_iou(d["bbox"], k["bbox"]) >= iou_thr:
                    ok = False
                    break
            if ok:
                out.append(d)
        kept.extend(out)
    return kept

# -----------------------------
# Parse detections from qtimlpostprocess text/x-raw
# -----------------------------
RE_DET = re.compile(
    r'"(?P<label>[^",]+)\s*,\s*id=\(uint\)\s*(?P<oid>\d+)\s*,\s*confidence=\(double\)\s*(?P<conf>[-0-9.eE]+).*?'
    r'rectangle=\(float\)\s*<\s*(?P<x>[-0-9.eE]+)\s*,\s*(?P<y>[-0-9.eE]+)\s*,\s*(?P<w>[-0-9.eE]+)\s*,\s*(?P<h>[-0-9.eE]+)',
    re.IGNORECASE | re.DOTALL
)

def parse_dets(raw: str):
    s = normalize_text(raw)
    dets = []
    for m in RE_DET.finditer(s):
        label = m.group("label").strip()
        conf = float(m.group("conf")) / 100.0  # qtimlpostprocess 常用 0~100；這裡轉成 0~1
        x = float(m.group("x")); y = float(m.group("y"))
        w = float(m.group("w")); h = float(m.group("h"))
        x1 = clamp(x, 0.0, 1.0); y1 = clamp(y, 0.0, 1.0)
        x2 = clamp(x+w, 0.0, 1.0); y2 = clamp(y+h, 0.0, 1.0)
        dets.append({"bbox": (x1,y1,x2,y2), "label": label, "conf": conf})
    return dets, s

# -----------------------------
# Tracking (v8.6.4 core: reattach + draw hysteresis + split min-area)
# -----------------------------
@dataclass
class Track:
    tid: int
    bbox: tuple
    conf: float
    label: str
    miss: int = 0
    hits: int = 0
    last_frame: int = 0
    draw_until: int = 0
    ever_drawn: bool = False
    label_hist: Counter = field(default_factory=Counter)

    def update_label(self, new_label: str):
        self.label_hist[new_label] += 1
        self.label = self.label_hist.most_common(1)[0][0]

@dataclass
class LostTrack:
    tid: int
    bbox: tuple
    conf: float
    label: str
    last_frame: int
    hits: int
    label_hist: Counter = field(default_factory=Counter)

class TrackerReattach:
    def __init__(self,
                 iou_high=0.20, iou_low=0.15,
                 max_miss=20, ema_alpha=0.60,
                 label_gate=True,
                 reattach_window=75, reattach_iou=0.28, reattach_center=0.14, reattach_size_ratio=3.0,
                 min_hits_to_lost=3, spawn_iou_block=0.35, lost_max=300,
                 draw_grace=60, conf_draw_on=0.50, conf_draw_off=0.30, min_hits_to_draw=3):
        self.iou_high = iou_high
        self.iou_low = iou_low
        self.max_miss = max_miss
        self.ema_alpha = ema_alpha
        self.label_gate = label_gate

        self.reattach_window = reattach_window
        self.reattach_iou = reattach_iou
        self.reattach_center = reattach_center
        self.reattach_size_ratio = reattach_size_ratio
        self.min_hits_to_lost = min_hits_to_lost
        self.spawn_iou_block = spawn_iou_block
        self.lost_max = lost_max

        self.draw_grace = draw_grace
        self.conf_draw_on = conf_draw_on
        self.conf_draw_off = conf_draw_off
        self.min_hits_to_draw = min_hits_to_draw

        self.tracks = []
        self.next_id = 0
        self.lost_pool = OrderedDict()

    @staticmethod
    def _center(b):
        return ((b[0]+b[2])*0.5, (b[1]+b[3])*0.5)

    def _greedy_match(self, tracks_idx, dets_idx, dets, iou_th):
        pairs = []
        for ti in tracks_idx:
            tr = self.tracks[ti]
            for di in dets_idx:
                d = dets[di]
                if self.label_gate and tr.label and d["label"] and tr.label != d["label"]:
                    continue
                s = bbox_iou(tr.bbox, d["bbox"])
                if s >= iou_th:
                    pairs.append((s, ti, di))
        pairs.sort(reverse=True, key=lambda x: x[0])

        matched_t, matched_d, assigns = set(), set(), []
        for s, ti, di in pairs:
            if ti in matched_t or di in matched_d:
                continue
            matched_t.add(ti); matched_d.add(di)
            assigns.append((ti, di, s))
        return assigns, matched_t, matched_d

    def _lost_prune(self, cur_frame):
        expired = []
        for tid, lt in self.lost_pool.items():
            if cur_frame - lt.last_frame > self.reattach_window:
                expired.append(tid)
        for tid in expired:
            self.lost_pool.pop(tid, None)
        while len(self.lost_pool) > self.lost_max:
            self.lost_pool.popitem(last=False)

    def _try_reattach(self, det, cur_frame, active_ids):
        best_tid, best_iou, best_lt = None, 0.0, None
        dc = self._center(det["bbox"])
        da = bbox_area(det["bbox"]) + 1e-9

        for tid, lt in self.lost_pool.items():
            if tid in active_ids:
                continue
            if cur_frame - lt.last_frame > self.reattach_window:
                continue
            if self.label_gate and lt.label and det["label"] and lt.label != det["label"]:
                continue

            s = bbox_iou(lt.bbox, det["bbox"])
            if s < self.reattach_iou:
                continue

            lc = self._center(lt.bbox)
            dist = ((dc[0]-lc[0])**2 + (dc[1]-lc[1])**2) ** 0.5
            if dist > self.reattach_center:
                continue

            la = bbox_area(lt.bbox) + 1e-9
            ratio = max(da/la, la/da)
            if ratio > self.reattach_size_ratio:
                continue

            if s > best_iou:
                best_iou, best_tid, best_lt = s, tid, lt

        if best_tid is None:
            return None, None
        self.lost_pool.pop(best_tid, None)
        return best_tid, best_lt

    def update(self, dets, cur_frame, conf_high=0.45, conf_low=0.12):
        self._lost_prune(cur_frame)

        hi = [i for i,d in enumerate(dets) if d["conf"] >= conf_high]
        lo = [i for i,d in enumerate(dets) if conf_low <= d["conf"] < conf_high]

        all_tracks_idx = list(range(len(self.tracks)))

        assigns1, mT1, mD1 = self._greedy_match(all_tracks_idx, hi, dets, self.iou_high)
        for ti, di, _ in assigns1:
            tr = self.tracks[ti]; d = dets[di]
            tr.bbox = ema_bbox(tr.bbox, d["bbox"], self.ema_alpha)
            tr.conf = d["conf"]; tr.miss = 0; tr.hits += 1; tr.last_frame = cur_frame
            tr.update_label(d["label"])
            if tr.hits >= self.min_hits_to_draw and tr.conf >= self.conf_draw_on:
                tr.ever_drawn = True
                tr.draw_until = cur_frame + self.draw_grace
            elif tr.ever_drawn:
                tr.draw_until = max(tr.draw_until, cur_frame + self.draw_grace)

        rem_tracks = [ti for ti in all_tracks_idx if ti not in mT1]
        rem_lo = [di for di in lo if di not in mD1]
        assigns2, mT2, mD2 = self._greedy_match(rem_tracks, rem_lo, dets, self.iou_low)
        for ti, di, _ in assigns2:
            tr = self.tracks[ti]; d = dets[di]
            tr.bbox = ema_bbox(tr.bbox, d["bbox"], self.ema_alpha)
            tr.conf = d["conf"]; tr.miss = 0; tr.hits += 1; tr.last_frame = cur_frame
            tr.update_label(d["label"])
            if tr.hits >= self.min_hits_to_draw and tr.conf >= self.conf_draw_on:
                tr.ever_drawn = True
                tr.draw_until = cur_frame + self.draw_grace
            elif tr.ever_drawn:
                tr.draw_until = max(tr.draw_until, cur_frame + self.draw_grace)

        matched_tracks = mT1.union(mT2)
        matched_dets = mD1.union(mD2)

        for i, tr in enumerate(self.tracks):
            if i not in matched_tracks:
                tr.miss += 1

        alive = []
        active_ids = set()
        for tr in self.tracks:
            if tr.miss > self.max_miss:
                if tr.hits >= self.min_hits_to_lost:
                    self.lost_pool[tr.tid] = LostTrack(
                        tid=tr.tid, bbox=tr.bbox, conf=tr.conf, label=tr.label,
                        last_frame=cur_frame, hits=tr.hits, label_hist=tr.label_hist
                    )
            else:
                alive.append(tr); active_ids.add(tr.tid)
        self.tracks = alive

        # spawn new tracks from unmatched HIGH dets; before that try reattach
        for di in hi:
            if di in matched_dets:
                continue
            d = dets[di]

            # block spawn on duplicates
            blocked = False
            for tr in self.tracks:
                if self.label_gate and tr.label and d["label"] and tr.label != d["label"]:
                    continue
                if bbox_iou(tr.bbox, d["bbox"]) >= self.spawn_iou_block:
                    blocked = True; break
            if blocked:
                continue

            reuse_tid, reuse_lt = self._try_reattach(d, cur_frame, active_ids)
            if reuse_tid is not None:
                tr = Track(
                    tid=reuse_tid, bbox=d["bbox"], conf=d["conf"], label=d["label"],
                    miss=0, hits=max(1, reuse_lt.hits), last_frame=cur_frame, label_hist=reuse_lt.label_hist
                )
                tr.update_label(d["label"])
                tr.ever_drawn = True
                tr.draw_until = cur_frame + self.draw_grace
                self.tracks.append(tr); active_ids.add(reuse_tid)
                continue

            tr = Track(tid=self.next_id, bbox=d["bbox"], conf=d["conf"], label=d["label"], miss=0, hits=1, last_frame=cur_frame)
            tr.update_label(d["label"])
            self.next_id += 1
            self.tracks.append(tr); active_ids.add(tr.tid)

        return self.tracks, len(self.lost_pool)

# -----------------------------
# Direction Counting (EW/NS) by line crossing
# -----------------------------
class DirectionCounter:
    """
    Two lines:
      - vertical x = x_v  => East/West
      - horizontal y = y_h => North/South
    With cooldown to avoid jitter double counting.
    """
    def __init__(self, *,
                 x_v=0.50, v_ymin=0.35, v_ymax=0.85,
                 y_h=0.55, h_xmin=0.20, h_xmax=0.80,
                 cooldown_frames=30,
                 window_sec=60,
                 csv_path=""):
        self.x_v = x_v
        self.v_ymin, self.v_ymax = v_ymin, v_ymax
        self.y_h = y_h
        self.h_xmin, self.h_xmax = h_xmin, h_xmax

        self.cooldown = cooldown_frames
        self.prev_center = {}   # tid -> (cx, cy)
        self.last_v = {}        # tid -> last frame counted on vertical
        self.last_h = {}        # tid -> last frame counted on horizontal

        self.east = 0
        self.west = 0
        self.north = 0
        self.south = 0

        self.window_sec = window_sec
        self.events = deque()  # (ts, dir) for last window

        self.csv_path = csv_path.strip()
        self._csv_f = None
        self._csv_w = None
        if self.csv_path:
            self._csv_f = open(self.csv_path, "a", newline="")
            self._csv_w = csv.writer(self._csv_f)
            if self._csv_f.tell() == 0:
                self._csv_w.writerow(["ts", "frame", "tid", "dir"])

    @staticmethod
    def _center(bbox):
        x1,y1,x2,y2 = bbox
        return ((x1+x2)*0.5, (y1+y2)*0.5)

    def _push_event(self, ts, frame_idx, tid, dname):
        self.events.append((ts, dname))
        # prune time window
        cutoff = ts - self.window_sec
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        if self._csv_w:
            self._csv_w.writerow([f"{ts:.3f}", frame_idx, tid, dname])
            self._csv_f.flush()

    def window_counts(self):
        c = Counter([d for _, d in self.events])
        return dict(c)

    def update(self, tracks, frame_idx, ts_now=None):
        if ts_now is None:
            ts_now = time.time()

        alive = set()

        for tr in tracks:
            tid = tr.tid
            alive.add(tid)
            cx, cy = self._center(tr.bbox)

            if tid in self.prev_center:
                px, py = self.prev_center[tid]

                # Vertical line => East/West (only if cy within range)
                if self.v_ymin <= cy <= self.v_ymax:
                    lastf = self.last_v.get(tid, -10**9)
                    if frame_idx - lastf >= self.cooldown:
                        if px < self.x_v and cx >= self.x_v:
                            self.east += 1
                            self.last_v[tid] = frame_idx
                            self._push_event(ts_now, frame_idx, tid, "E")
                        elif px > self.x_v and cx <= self.x_v:
                            self.west += 1
                            self.last_v[tid] = frame_idx
                            self._push_event(ts_now, frame_idx, tid, "W")

                # Horizontal line => North/South (only if cx within range)
                if self.h_xmin <= cx <= self.h_xmax:
                    lastf = self.last_h.get(tid, -10**9)
                    if frame_idx - lastf >= self.cooldown:
                        if py < self.y_h and cy >= self.y_h:
                            self.south += 1
                            self.last_h[tid] = frame_idx
                            self._push_event(ts_now, frame_idx, tid, "S")
                        elif py > self.y_h and cy <= self.y_h:
                            self.north += 1
                            self.last_h[tid] = frame_idx
                            self._push_event(ts_now, frame_idx, tid, "N")

            self.prev_center[tid] = (cx, cy)

        # cleanup prev_center for dead ids
        for tid in list(self.prev_center.keys()):
            if tid not in alive:
                self.prev_center.pop(tid, None)

    def close(self):
        if self._csv_f:
            try:
                self._csv_f.close()
            except Exception:
                pass


# -----------------------------
# Queue/Flow Estimation + Fake HUD Tracks (for on-screen display)
# -----------------------------
# NOTE (Ray):
#   RB3 端只做「量測」(measurement)；塞不塞車/紅綠燈策略交給 traffic agent。
#
# WHY we use "Fake Track HUD" instead of adding more cairo text?
#   在某些 RB3/IMSDK 影像 (GBM/Wayland + zero-copy) 上，CPU-side cairo 額外畫的文字
#   不一定會進到最後合成的顯示層；但既有的「track box + label」通常是可見的。
#   因此我們合成兩個假的 Track (hud tracks)，把 EW/NS 的 queue/flow 放進 label，
#   並把它們 append 到 state["tracks"]，讓它們走同一條既有 draw loop。
#
class QueueFlowEstimator:
    """Estimate EW/NS queue + flow as stable 0~1 metrics (measurement only)."""

    def __init__(self, counter, fps=30.0,
                 depth=0.10,
                 stop_thr=0.015,
                 stop_hold=6,
                 q_scale=6.0,
                 f_scale=0.25,
                 beta_q=0.85,
                 beta_f=0.75):
        self.counter = counter
        self.fps = max(1e-6, float(fps))
        self.depth = float(depth)
        self.stop_thr = float(stop_thr)
        self.stop_hold = int(stop_hold)
        self.q_scale = float(q_scale)
        self.f_scale = float(f_scale)
        self.beta_q = float(beta_q)
        self.beta_f = float(beta_f)

        self.prev_center = {}
        self.low_streak = {}

        self.ew_queue = 0.0
        self.ns_queue = 0.0
        self.ew_flow  = 0.0
        self.ns_flow  = 0.0
        self.ew_stop_raw = 0
        self.ns_stop_raw = 0

    @staticmethod
    def clamp01(x: float) -> float:
        return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

    @staticmethod
    def _center(bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)

    def _in_ew_zone(self, cx: float, cy: float) -> bool:
        xmin = max(0.0, self.counter.x_v - self.depth)
        xmax = self.counter.x_v
        return (xmin <= cx <= xmax) and (self.counter.v_ymin <= cy <= self.counter.v_ymax)

    def _in_ns_zone(self, cx: float, cy: float) -> bool:
        ymin = max(0.0, self.counter.y_h - self.depth)
        ymax = self.counter.y_h
        return (self.counter.h_xmin <= cx <= self.counter.h_xmax) and (ymin <= cy <= ymax)

    def _sat(self, n: float, scale: float) -> float:
        if scale <= 0:
            return 0.0
        return 1.0 - math.exp(-float(n) / scale)

    def update(self, tracks, frame_idx: int, ts_now: float = None):
        if ts_now is None:
            ts_now = time.time()

        alive = set()
        n_ew_stop = 0
        n_ns_stop = 0

        for tr in tracks:
            tid = tr.tid
            alive.add(tid)
            cx, cy = self._center(tr.bbox)

            if tid in self.prev_center:
                px, py = self.prev_center[tid]
                dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                speed = dist * self.fps
            else:
                speed = 1e9

            in_ew = self._in_ew_zone(cx, cy)
            in_ns = self._in_ns_zone(cx, cy)
            low = (speed < self.stop_thr)

            if (in_ew or in_ns) and low:
                self.low_streak[tid] = self.low_streak.get(tid, 0) + 1
            else:
                self.low_streak[tid] = 0

            if self.low_streak[tid] >= self.stop_hold:
                if in_ew:
                    n_ew_stop += 1
                if in_ns:
                    n_ns_stop += 1

            self.prev_center[tid] = (cx, cy)

        for tid in list(self.prev_center.keys()):
            if tid not in alive:
                self.prev_center.pop(tid, None)
                self.low_streak.pop(tid, None)

        self.ew_stop_raw = n_ew_stop
        self.ns_stop_raw = n_ns_stop

        q_ew_raw = self._sat(n_ew_stop, self.q_scale)
        q_ns_raw = self._sat(n_ns_stop, self.q_scale)
        self.ew_queue = self.clamp01(self.beta_q * self.ew_queue + (1.0 - self.beta_q) * q_ew_raw)
        self.ns_queue = self.clamp01(self.beta_q * self.ns_queue + (1.0 - self.beta_q) * q_ns_raw)

        wc = self.counter.window_counts()
        win = max(1, int(self.counter.window_sec))
        ew_rate = (wc.get('E', 0) + wc.get('W', 0)) / float(win)
        ns_rate = (wc.get('N', 0) + wc.get('S', 0)) / float(win)
        f_ew_raw = self._sat(ew_rate, self.f_scale)
        f_ns_raw = self._sat(ns_rate, self.f_scale)
        self.ew_flow = self.clamp01(self.beta_f * self.ew_flow + (1.0 - self.beta_f) * f_ew_raw)
        self.ns_flow = self.clamp01(self.beta_f * self.ns_flow + (1.0 - self.beta_f) * f_ns_raw)

        return {
            'EW_queue': self.ew_queue,
            'NS_queue': self.ns_queue,
            'EW_flow': self.ew_flow,
            'NS_flow': self.ns_flow,
            'EW_stop_raw': self.ew_stop_raw,
            'NS_stop_raw': self.ns_stop_raw,
        }

# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()

    # input/model
    ap.add_argument("--input", default="/home/ubuntu/rene_video.mp4")
    ap.add_argument("--model", default="/etc/models/yolov8_det_quantized.tflite")
    ap.add_argument("--labels", default="/etc/labels/coco_labels.txt")
    ap.add_argument("--module", default="yolov8")
    ap.add_argument("--fps", default="30/1")

    # qtimlpostprocess settings (confidence in 0~100) [1](https://qualcomm-confluence.atlassian.net/wiki/spaces/VAISDK/pages/1669367917/qtimlpostprocess)[2](https://qualcomm-confluence.atlassian.net/wiki/spaces/VAISDK/pages/1669367572/How+to+build+AI+use+cases+using+IM+SDK)
    ap.add_argument("--conf-post", type=float, default=20.0)
    ap.add_argument("--results", type=int, default=10)

    # tracking knobs (fixed demo defaults)
    ap.add_argument("--conf-high", type=float, default=0.45)
    ap.add_argument("--conf-low", type=float, default=0.12)
    ap.add_argument("--det-nms-iou", type=float, default=0.60)
    ap.add_argument("--min-area-track", type=float, default=0.0006)
    ap.add_argument("--min-area-draw", type=float, default=0.0015)

    ap.add_argument("--conf-draw-on", type=float, default=0.50)
    ap.add_argument("--conf-draw-off", type=float, default=0.30)
    ap.add_argument("--draw-grace", type=int, default=60)

    ap.add_argument("--max-miss", type=int, default=20)
    ap.add_argument("--reattach-window", type=int, default=75)
    ap.add_argument("--reattach-iou", type=float, default=0.28)
    ap.add_argument("--reattach-center", type=float, default=0.14)
    ap.add_argument("--debug-raw", action="store_true")

    # class filter (demo: vehicles only)
    ap.add_argument("--classes", default="car,truck,bus,motorbike,bicycle")

    # counting lines (normalized coords)
    ap.add_argument("--x-v", type=float, default=0.50)
    ap.add_argument("--v-ymin", type=float, default=0.35)
    ap.add_argument("--v-ymax", type=float, default=0.85)

    ap.add_argument("--y-h", type=float, default=0.55)
    ap.add_argument("--h-xmin", type=float, default=0.20)
    ap.add_argument("--h-xmax", type=float, default=0.80)

    ap.add_argument("--cooldown", type=int, default=30)
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--count-csv", default="", help="optional csv path to log count events")
    ap.add_argument("--output", default="", help="optional mp4 output path (record Wayland output incl. overlay)")
    ap.add_argument("--intersection-id", default="A", help="intersection id for agent payload")

    args = ap.parse_args()

    # --- optional MP4 output (records exactly what you see on Wayland, including overlay) ---
    record_branch = ""
    if args.output:
        record_branch = f"""
        post. ! queue !
            videoconvert ! video/x-raw,format=NV12 !
            v4l2h264enc capture-io-mode=4 output-io-mode=4 !
            h264parse ! mp4mux !
            filesink location=\"{args.output}\"
        """

    if cairo is None:
        print("❌ python-cairo not found. Install: sudo apt-get install -y python3-cairo")
        sys.exit(1)

    keep_classes = set([c.strip() for c in args.classes.split(",") if c.strip()])

    os.environ["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    os.environ["WAYLAND_DISPLAY"] = os.environ.get("WAYLAND_DISPLAY", "wayland-1")

    Gst.init(None)

    settings_json = "{\\\"confidence\\\": %.1f}" % args.conf_post

    pipeline_str = f"""
        qtimlvconverter name=preproc
        qtimltflite name=inference delegate=external
            external-delegate-path=libQnnTFLiteDelegate.so
            external-delegate-options="QNNExternalDelegate,backend_type=htp;"
            model="{args.model}"
        qtimlpostprocess name=postproc results={args.results} module={args.module} labels="{args.labels}" settings="{settings_json}"

        filesrc location="{args.input}" ! qtdemux ! queue ! h264parse !
            v4l2h264dec capture-io-mode=4 output-io-mode=4 !
            video/x-raw,format=NV12 ! queue ! tee name=split

        split. ! queue !
            videoconvert ! cairooverlay name=co ! videoconvert !
            videorate ! video/x-raw,framerate={args.fps} !
            tee name=post

        post. ! queue !
            waylandsink sync=true fullscreen=true

        {record_branch}

        split. ! queue ! preproc.
        preproc. ! queue ! inference.
        inference. ! queue ! postproc.
        postproc. ! capsfilter caps="text/x-raw,format=utf8" !
            appsink name=meta_sink emit-signals=true sync=false max-buffers=1 drop=true
    """

    pipeline = Gst.parse_launch(pipeline_str)
    cairo_ov = pipeline.get_by_name("co")
    appsink = pipeline.get_by_name("meta_sink")
    if cairo_ov is None or appsink is None:
        print("❌ Missing cairooverlay/meta_sink")
        sys.exit(1)

    tracker = TrackerReattach(
        max_miss=args.max_miss,
        reattach_window=args.reattach_window,
        reattach_iou=args.reattach_iou,
        reattach_center=args.reattach_center,
        draw_grace=args.draw_grace,
        conf_draw_on=args.conf_draw_on,
        conf_draw_off=args.conf_draw_off,
    )

    counter = DirectionCounter(
        x_v=args.x_v, v_ymin=args.v_ymin, v_ymax=args.v_ymax,
        y_h=args.y_h, h_xmin=args.h_xmin, h_xmax=args.h_xmax,
        cooldown_frames=args.cooldown,
        window_sec=args.window_sec,
        csv_path=args.count_csv
    )



    # --- queue/flow estimator (0~1 for traffic agent) ---

    def _parse_fps(s):

        try:

            ss = str(s).strip()

            if "/" in ss:

                a, b = ss.split("/", 1)

                return float(a) / max(1e-6, float(b))

            return float(ss)

        except Exception:

            return 30.0


    est = QueueFlowEstimator(counter, fps=_parse_fps(args.fps))

    stopping = {"v": False}
    eos_sent = {"v": False}
    frame_no = {"n": 0}
    state = {"tracks": [], "lost": 0, "t": time.time(), "n": 0, "head": "", "dets_keep": 0, "cur": 0,
             "ew_queue": 0.0, "ns_queue": 0.0, "ew_flow": 0.0, "ns_flow": 0.0,
             "ew_stop_raw": 0, "ns_stop_raw": 0}

    def on_sample(sink):
        if stopping["v"]:
            return Gst.FlowReturn.EOS
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK

        buf = sample.get_buffer()
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        raw = mapinfo.data.decode("utf-8", errors="ignore").strip()
        buf.unmap(mapinfo)

        dets, norm = parse_dets(raw)

        # filter vehicles and small noise
        dets = [d for d in dets if d["label"] in keep_classes]
        dets = [d for d in dets if bbox_area(d["bbox"]) >= args.min_area_track]
        dets = simple_nms(dets, iou_thr=args.det_nms_iou)
        state["dets_keep"] = len(dets)

        frame_no["n"] += 1
        cur = frame_no["n"]
        state["cur"] = cur

        tracks, lost_cnt = tracker.update(dets, cur_frame=cur, conf_high=args.conf_high, conf_low=args.conf_low)
        state["tracks"] = tracks
        state["lost"] = lost_cnt
        state["head"] = (norm or "")[:220].replace("\n", " ")

        # update counters
        counter.update(tracks, cur, ts_now=time.time())


        # update queue/flow estimator
        qf = est.update(tracks, cur, ts_now=time.time())
        state["ew_queue"] = qf["EW_queue"]; state["ns_queue"] = qf["NS_queue"]
        state["ew_flow"]  = qf["EW_flow"];  state["ns_flow"]  = qf["NS_flow"]
        state["ew_stop_raw"] = qf["EW_stop_raw"]; state["ns_stop_raw"] = qf["NS_stop_raw"]

        # FAKE_HUD_TRACKS (方案A):
        #   Synthesize two pseudo tracks and append into state["tracks"].
        #   They will be drawn by the SAME track draw-loop that already works.
        hud = []
        try:
            # Large enough to pass min-area-draw; placed top-left.
            b0 = (0.02, 0.02, 0.60, 0.08)
            b1 = (0.02, 0.09, 0.60, 0.15)
            t0 = Track(tid=900001, bbox=b0, conf=1.0,
                       label=f"AGENT EW q={state['ew_queue']:.2f} f={state['ew_flow']:.2f} s={state['ew_stop_raw']}")
            t1 = Track(tid=900002, bbox=b1, conf=1.0,
                       label=f"AGENT NS q={state['ns_queue']:.2f} f={state['ns_flow']:.2f} s={state['ns_stop_raw']}")
            for tt in (t0, t1):
                tt.hits = 999
                tt.ever_drawn = True
                tt.draw_until = cur + 999999
            hud = [t0, t1]
        except Exception:
            hud = []

        # append HUD tracks to draw-list ONLY (NOT to tracker/counter logic)
        state["tracks"] = list(tracks) + hud

        # periodic log
        state["n"] += 1
        now = time.time()
        if now - state["t"] >= 1.0:
            drawables = 0
            for tr in tracks:
                if bbox_area(tr.bbox) < args.min_area_draw:
                    continue
                if tr.conf >= args.conf_draw_on:
                    drawables += 1
                elif tr.ever_drawn and cur <= tr.draw_until and tr.conf >= args.conf_draw_off:
                    drawables += 1
            ew = counter.east + counter.west
            ns = counter.north + counter.south
            print(f"[fixed-v8.6.4+count] dets_keep={state['dets_keep']} tracks={len(tracks)} lost={lost_cnt} draw={drawables} "
                  f"EW={ew}(E{counter.east}/W{counter.west}) NS={ns}(N{counter.north}/S{counter.south}) fps~{state['n']}")

            payload = {
                "intersection_id": args.intersection_id,
                "timestamp": int(now),
                "lanes": {
                    "EW": {"queue": float(state["ew_queue"]), "flow": float(state["ew_flow"])},
                    "NS": {"queue": float(state["ns_queue"]), "flow": float(state["ns_flow"])},
                }
            }
            print("[agent] " + json.dumps(payload, separators=(",", ":")))
            state["t"] = now
            state["n"] = 0
            if args.debug_raw:
                print("[Debug] head:", state["head"])
        return Gst.FlowReturn.OK

    appsink.connect("new-sample", on_sample)

    def on_draw(overlay, cr, timestamp, duration):
        cur = state["cur"]
        W, H = get_caps_wh(overlay, fallback=(1920,1080))

        hud_lines = []  # (key,text) for AGENT HUD
        # --- draw counting lines (yellow) ---
        cr.set_source_rgba(1.0, 1.0, 0.0, 0.9)
        cr.set_line_width(4.0)

        xv = int(counter.x_v * W)
        y1 = int(counter.v_ymin * H)
        y2 = int(counter.v_ymax * H)
        cr.move_to(xv, y1); cr.line_to(xv, y2); cr.stroke()

        yh = int(counter.y_h * H)
        x1 = int(counter.h_xmin * W)
        x2 = int(counter.h_xmax * H)
        cr.move_to(x1, yh); cr.line_to(x2, yh); cr.stroke()

        # --- draw tracks (green boxes + white text) ---
        cr.set_line_width(3.0)
        for tr in state["tracks"]:
            # HUD pseudo tracks: do NOT draw green boxes; collect text and draw under LASTxxs
            if tr.tid >= 900000:
                key = 0 if tr.label.startswith('AGENT EW') else 1
                hud_lines.append((key, tr.label))
                continue

            if bbox_area(tr.bbox) < args.min_area_draw:
                continue

            draw_it = False
            if tr.conf >= args.conf_draw_on:
                draw_it = True
            elif tr.ever_drawn and cur <= tr.draw_until and tr.conf >= args.conf_draw_off:
                draw_it = True
            if not draw_it:
                continue

            x1n, y1n, x2n, y2n = tr.bbox
            px = max(0, int(x1n*W)); py = max(0, int(y1n*H))
            pw = max(2, int((x2n-x1n)*W)); ph = max(2, int((y2n-y1n)*H))

            cr.set_source_rgba(0.0, 1.0, 0.0, 1.0)
            cr.rectangle(px, py, pw, ph)
            cr.stroke()

            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(26)
            cr.move_to(px, max(0, py-8))
            cr.show_text(f"{tr.label} #{tr.tid} ({tr.conf:.2f})")
        # --- draw stats text ---
        wc = counter.window_counts()
        ew = counter.east + counter.west
        ns = counter.north + counter.south

        cr.set_source_rgba(1.0, 1.0, 0.0, 1.0)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(28)
        cr.move_to(30, 40)
        cr.show_text(f"TOTAL  EW={ew} (E{counter.east}/W{counter.west})   NS={ns} (N{counter.north}/S{counter.south})")
        cr.set_font_size(22)
        cr.move_to(30, 70)
        cr.show_text(f"LAST{counter.window_sec}s  E{wc.get('E',0)} W{wc.get('W',0)}  N{wc.get('N',0)} S{wc.get('S',0)}")


        # --- AGENT HUD: pinned right under LASTxxs (no ugly boxes) ---
        if hud_lines:
            hud_lines.sort(key=lambda x: x[0])
            # background for readability
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.55)
            cr.rectangle(20, 78, max(300, W-40), 70)
            cr.fill()

            cr.set_source_rgba(1.0, 1.0, 0.0, 1.0)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(22)

            y = 105
            for _, txt in hud_lines[:2]:
                cr.move_to(30, y)
                cr.show_text(txt)
                y += 28


        return True

    cairo_ov.connect("draw", on_draw)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def on_bus(bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            print("❌ GStreamer ERROR:", err.message)
            if dbg:
                print(dbg)
            stopping["v"] = True
            try:
                pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
            counter.close()
            loop.quit()
        elif msg.type == Gst.MessageType.EOS:
            stopping["v"] = True
            try:
                pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
            counter.close()
            loop.quit()

    bus.connect("message", on_bus)

    def handle_sigint(sig, frame):
        print("\n⛔ Ctrl+C: stop")
        stopping["v"] = True
        if args.output and not eos_sent["v"]:
            eos_sent["v"] = True
            try:
                pipeline.send_event(Gst.Event.new_eos())
                return
            except Exception:
                pass
        try:
            pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        counter.close()
        loop.quit()

    signal.signal(signal.SIGINT, handle_sigint)

    print("▶ Running fixed v8.6.4 + intersection counting (EW/NS)")
    pipeline.set_state(Gst.State.PLAYING)
    loop.run()
    pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    main()