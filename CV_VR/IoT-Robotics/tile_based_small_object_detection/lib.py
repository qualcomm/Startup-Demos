#===-------------------------lib.py---------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# GStreamer (GI)
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib


@dataclass(frozen=True)
class TileSpec:
    x0: int
    y0: int
    w: int
    h: int

@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    cls: int
    label: str
    tile_id: int

    def as_dict(self) -> Dict:
        return {
            'x1': float(self.x1),
            'y1': float(self.y1),
            'x2': float(self.x2),
            'y2': float(self.y2),
            'score': float(self.score),
            'cls': int(self.cls),
            'label': self.label,
            'tile_id': int(self.tile_id),
        }


# ----------------------------- utils -----------------------------

def clip_xyxy(x1, y1, x2, y2, w, h):
    x1 = float(np.clip(x1, 0, w - 1))
    y1 = float(np.clip(y1, 0, h - 1))
    x2 = float(np.clip(x2, 0, w - 1))
    y2 = float(np.clip(y2, 0, h - 1))
    return x1, y1, x2, y2


def _starts_1d(length: int, tile: int, overlap: float) -> List[int]:
    stride = int(round(tile * (1.0 - overlap)))
    if length <= tile:
        return [0]
    starts = list(range(0, length - tile + 1, stride))
    last = length - tile
    if starts[-1] != last:
        starts.append(last)
    return starts


def plan_tiles(W: int, H: int, tile: int, overlap: float) -> List[TileSpec]:
    xs = _starts_1d(W, tile, overlap)
    ys = _starts_1d(H, tile, overlap)
    return [TileSpec(x0=x, y0=y, w=tile, h=tile) for y in ys for x in xs]


# ----------------------------- NMS -----------------------------

def iou_xyxy(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(a[2]) - float(a[0])) * max(0.0, float(a[3]) - float(a[1]))
    area_b = max(0.0, float(b[2]) - float(b[0])) * max(0.0, float(b[3]) - float(b[1]))
    union = area_a + area_b - inter
    return 0.0 if union <= 0 else inter / union


def nms(dets: List[Detection], iou_thr: float = 0.5, class_aware: bool = True) -> List[Detection]:
    if not dets:
        return []
    dets_sorted = sorted(dets, key=lambda d: d.score, reverse=True)
    keep: List[Detection] = []
    while dets_sorted:
        best = dets_sorted.pop(0)
        keep.append(best)
        best_box = np.array([best.x1, best.y1, best.x2, best.y2], dtype=np.float32)
        remain: List[Detection] = []
        for d in dets_sorted:
            if class_aware and d.label != best.label:
                remain.append(d)
                continue
            box = np.array([d.x1, d.y1, d.x2, d.y2], dtype=np.float32)
            if iou_xyxy(best_box, box) < iou_thr:
                remain.append(d)
        dets_sorted = remain
    return keep


# ----------------------------- draw -----------------------------

def draw_detections(img: Image.Image, dets: List[Detection]) -> Image.Image:
    out = img.copy()
    dr = ImageDraw.Draw(out)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for d in dets:
        dr.rectangle([d.x1, d.y1, d.x2, d.y2], outline=(255, 0, 0), width=2)
        dr.text((d.x1, max(0, d.y1 - 12)), f"{d.label}:{d.score:.2f}", fill=(255, 0, 0), font=font)
    return out


# ----------------------------- qtimlvdetection text parser (carry over from v9) -----------------------------

def _gst_unescape_all(s: str) -> str:
    if not s:
        return ''
    s = s.replace('\x00', '')

    # Turn escaped quotes into quotes (multi-pass)
    s = s.replace('\\\\\\\\"', '"').replace('\\\\\\"', '"').replace('\\\\"', '"').replace('\\"', '"')

    # Collapse backslashes
    for _ in range(3):
        s = s.replace('\\\\', '\\')

    # Unescape GstStructure punctuation: \\, \\= \\< \\> \\; \\(
    s = re.sub(r'\\([,=<>;()\[\]])', r'\1', s)
    s = s.replace('\\ ', ' ')
    return s

def _parse_one_bbox_record(rec: str) -> Optional[Tuple[str, float, float, float, float, float]]:
    if not rec:
        return None
    rec = _gst_unescape_all(rec)

    parts = rec.split(',', 1)
    if not parts:
        return None
    label = parts[0].strip().strip('"')

    m_conf = re.search(r'confidence=\((?:double|float)\)\s*([0-9.]+)', rec)
    if not m_conf:
        return None
    conf = float(m_conf.group(1))
    score = conf / 100.0 if conf > 1.0 else conf

    m_rect = re.search(r'rectangle=\((?:float|double)\)\s*<\s*([^>]+?)\s*>', rec)
    if not m_rect:
        return None

    nums = [x.strip() for x in m_rect.group(1).split(',')]
    if len(nums) < 4:
        return None

    def to_f(snum: str) -> float:
        snum = re.sub(r'\s+', '', snum)
        return float(snum)

    try:
        x = to_f(nums[0])
        y = to_f(nums[1])
        w = to_f(nums[2])
        h = to_f(nums[3])
    except Exception:
        return None

    return label, score, x, y, w, h

class LabelMapper:
    def __init__(self):
        self.label_to_idx = {}
        self.idx_to_label = []

    def get_cls(self, label: str) -> int:
        if label not in self.label_to_idx:
            idx = len(self.idx_to_label)
            self.label_to_idx[label] = idx
            self.idx_to_label.append(label)
        return self.label_to_idx[label]

def parse_qtimlvdetection_text(
    text: str,
    tile: TileSpec,
    tile_id: int,
    #label_to_idx: Dict[str, int],
    score_thr: float,
    assume_normalized: bool = True,
) -> List[Detection]:
    t = _gst_unescape_all(text)
    records = re.findall(r'"([^\"]*?rectangle=.*?;)"', t, flags=re.DOTALL)
    label_mapper = LabelMapper()

    dets: List[Detection] = []
    for rec in records:
        parsed = _parse_one_bbox_record(rec)
        if not parsed:
            continue
        label, score, x, y, w, h = parsed
        if score < score_thr:
            continue

        norm = assume_normalized
        if assume_normalized and max(x, y, w, h) > 2.0:
            norm = False

        if norm:
            x1 = x * tile.w
            y1 = y * tile.h
            x2 = (x + w) * tile.w
            y2 = (y + h) * tile.h
        else:
            x1, y1, x2, y2 = x, y, x + w, y + h

        x1, y1, x2, y2 = clip_xyxy(x1, y1, x2, y2, tile.w, tile.h)
        gx1, gy1 = x1 + tile.x0, y1 + tile.y0
        gx2, gy2 = x2 + tile.x0, y2 + tile.y0

        cls = label_mapper.get_cls(label)
        dets.append(Detection(gx1, gy1, gx2, gy2, score, cls, label, tile_id))

    return dets


# ----------------------------- Gst helpers -----------------------------

def _make_element(factory: str, name: str) -> Gst.Element:
    el = Gst.ElementFactory.make(factory, name)
    if el is None:
        raise RuntimeError(f"Failed to create element: {factory} (name={name})")
    return el


def _link_chain(elems: List[Gst.Element]) -> None:
    """Link a list of elements sequentially using element.link(next).

    This avoids GI differences around link_many availability.
    """
    for a, b in zip(elems, elems[1:]):
        if not a.link(b):
            raise RuntimeError(f"Failed to link: {a.get_name()}({a.get_factory().get_name()}) -> {b.get_name()}({b.get_factory().get_name()})")


def run_tile_pipeline_appsink(
    image_path: str,
    model_path: str,
    labels_path: str,
    W: int,
    H: int,
    tile: Optional[TileSpec],
    delegate: str,
    module: str,
    constants: str,
    threshold_percent: float,
    results: int,
    pre_engine: str,
    timeout_sec: float,
    gst_debug: Optional[str],
) -> str:
    if gst_debug:
        os.environ['GST_DEBUG'] = str(gst_debug)

    pipeline = Gst.Pipeline.new('tile-pipeline')

    src = _make_element('filesrc', 'src')
    src.set_property('location', image_path)

    dec = _make_element('decodebin', 'dec')

    conv1 = _make_element('videoconvert', 'conv1')
    caps1 = _make_element('capsfilter', 'caps1')
    caps1.set_property('caps', Gst.Caps.from_string(f'video/x-raw,format=RGB,width={W},height={H}'))

    chain: List[Gst.Element] = [conv1, caps1]

    if tile is not None:
        crop = _make_element('videocrop', 'crop')
        right = max(0, W - (tile.x0 + tile.w))
        bottom = max(0, H - (tile.y0 + tile.h))
        crop.set_property('left', int(tile.x0))
        crop.set_property('top', int(tile.y0))
        crop.set_property('right', int(right))
        crop.set_property('bottom', int(bottom))

        scale = _make_element('videoscale', 'scale')
        conv2 = _make_element('videoconvert', 'conv2')
        caps2 = _make_element('capsfilter', 'caps2')
        caps2.set_property('caps', Gst.Caps.from_string('video/x-raw,format=RGB'))
        chain += [crop, scale, conv2, caps2]

    pre = _make_element('qtimlvconverter', 'pre')
    pre.set_property('engine', pre_engine)

    tfl = _make_element('qtimltflite', 'tfl')
    tfl.set_property('delegate', delegate)
    tfl.set_property('model', model_path)

    det = _make_element('qtimlvdetection', 'det')
    det.set_property('threshold', float(threshold_percent))
    det.set_property('results', int(results))
    det.set_property('module', module)
    det.set_property('labels', labels_path)
    det.set_property('constants', constants)

    textcaps = _make_element('capsfilter', 'textcaps')
    textcaps.set_property('caps', Gst.Caps.from_string('text/x-raw,format=utf8'))

    sink = _make_element('appsink', 'appsink')
    sink.set_property('emit-signals', True)
    sink.set_property('sync', False)
    sink.set_property('max-buffers', 16)
    sink.set_property('drop', False)

    chain += [pre, tfl, det, textcaps, sink]

    # Add all elements to pipeline
    for el in [src, dec] + chain:
        pipeline.add(el)

    # Link filesrc -> decodebin
    if not src.link(dec):
        raise RuntimeError('Failed to link filesrc -> decodebin')

    # Link decodebin dynamic pad to conv1 sink
    def _on_pad_added(db: Gst.Element, pad: Gst.Pad):
        caps = pad.get_current_caps() or pad.query_caps()
        caps_s = caps.to_string() if caps else ''
        # Only link video pads
        if not caps_s.startswith('video/'):
            return
        sinkpad = conv1.get_static_pad('sink')
        if sinkpad is None or sinkpad.is_linked():
            return
        pad.link(sinkpad)

    dec.connect('pad-added', _on_pad_added)

    # Link the rest of the chain sequentially
    _link_chain(chain)

    chunks: List[bytes] = []
    error_info = {'err': None, 'dbg': None}
    got_eos = {'flag': False}
    timed_out = {'flag': False}

    def on_new_sample(appsink: Gst.Element):
        sample = appsink.emit('pull-sample')
        if sample is None:
            return Gst.FlowReturn.OK
        buf = sample.get_buffer()
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if ok:
            try:
                chunks.append(bytes(mapinfo.data))
            finally:
                buf.unmap(mapinfo)
        return Gst.FlowReturn.OK

    sink.connect('new-sample', on_new_sample)

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    loop = GLib.MainLoop()

    def on_message(bus: Gst.Bus, msg: Gst.Message):
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            error_info['err'] = err
            error_info['dbg'] = dbg
            loop.quit()
        elif t == Gst.MessageType.EOS:
            got_eos['flag'] = True
            loop.quit()
        return True

    bus.connect('message', on_message)

    def on_timeout():
        timed_out['flag'] = True
        loop.quit()
        return False

    GLib.timeout_add(int(timeout_sec * 1000), on_timeout)

    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        pipeline.set_state(Gst.State.NULL)
        raise RuntimeError('Failed to set pipeline to PLAYING')

    loop.run()

    pipeline.set_state(Gst.State.NULL)
    bus.remove_signal_watch()

    if error_info['err'] is not None:
        raise RuntimeError(f'GStreamer ERROR: {error_info["err"]}\nDEBUG: {error_info["dbg"]}')

    if timed_out['flag']:
        raise RuntimeError(f'GStreamer timed out after {timeout_sec:.1f}s (EOS={got_eos["flag"]})')

    raw = b''.join(chunks).replace(b'\x00', b'')
    return raw.decode('utf-8', errors='replace')