#===--face_recognizer.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import os

import numpy as np
from PIL import Image

from ai_edge_litert.interpreter import Interpreter
from arduino.app_bricks.dbstorage_sqlstore import SQLStore

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "models", "MobileFaceNet_full_integer_quant.tflite")
INPUT_SIZE = (112, 112)
MATCH_THRESHOLD = 0.55
NUM_THREADS = min(4, os.cpu_count() or 1)

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

TABLE = "enrolled_faces"


class FaceRecognizer:
  """Generates face embeddings with MobileFaceNet and matches them against enrolled faces."""

  def __init__(self, db: SQLStore):
    self._db = db
    self._db.create_table(TABLE, {"name": "TEXT", "embedding": "BLOB"})

    self._interpreter = Interpreter(model_path=MODEL_PATH, num_threads=NUM_THREADS)
    self._interpreter.allocate_tensors()
    self._input_detail = self._interpreter.get_input_details()[0]
    self._output_detail = self._interpreter.get_output_details()[0]

  def embed(self, face_crop: np.ndarray) -> np.ndarray:
    """Compute an L2-normalized embedding for a cropped face image (RGB numpy array).

    Preprocessing follows the model's training pipeline: scale to [0, 1] then
    apply ImageNet mean/std normalization per RGB channel (confirmed against
    the exported graph and the source training/eval scripts).

    Handles both float32 and int8-quantized models transparently, using each
    tensor's own quantization params (scale, zero_point) rather than assuming
    a dtype — so the same code runs a float model or a quantized one
    interchangeably.
    """
    image = Image.fromarray(face_crop).convert("RGB").resize(INPUT_SIZE)
    tensor = np.asarray(image, dtype=np.float32) / 255.0
    tensor = (tensor - IMAGENET_MEAN) / IMAGENET_STD
    tensor = np.expand_dims(tensor, axis=0)

    in_dtype = self._input_detail["dtype"]
    if in_dtype != np.float32:
      in_scale, in_zero = self._input_detail["quantization"]
      tensor = np.round(tensor / in_scale + in_zero).astype(in_dtype)

    self._interpreter.set_tensor(self._input_detail["index"], tensor)
    self._interpreter.invoke()
    embedding = self._interpreter.get_tensor(self._output_detail["index"])[0]

    out_dtype = self._output_detail["dtype"]
    if out_dtype != np.float32:
      out_scale, out_zero = self._output_detail["quantization"]
      embedding = (embedding.astype(np.float32) - out_zero) * out_scale

    norm = np.linalg.norm(embedding)
    if norm == 0:
      raise ValueError("Model produced a zero-norm embedding; cannot compute a valid match score for this frame.")
    return embedding / norm

  def add_sample(self, name: str, embedding: np.ndarray):
    """Add a new face sample for the given name, keeping any previously enrolled samples."""
    self._db.store(TABLE, {"name": name, "embedding": embedding.astype(np.float32).tobytes()}, create_table=False)

  def match(self, embedding: np.ndarray) -> tuple[str | None, float]:
    """Find the best matching enrolled name for the given embedding, across all samples of all names.

    Returns:
        tuple[str | None, float]: (name, score) of the best match, or (None, score) if
        no enrollment scores above MATCH_THRESHOLD.
    """
    best_name = None
    best_score = 0.0
    for row in self._db.read(TABLE):
      candidate = np.frombuffer(row["embedding"], dtype=np.float32)
      score = float(np.dot(embedding, candidate))
      if score > best_score:
        best_score = score
        best_name = row["name"]

    if best_name is not None and best_score >= MATCH_THRESHOLD:
      return best_name, best_score
    return None, best_score

  def list_enrolled(self) -> list[str]:
    rows = self._db.execute_sql(f"SELECT DISTINCT name FROM {TABLE} ORDER BY name ASC")
    return [row["name"] for row in rows] if rows else []

  def delete(self, name: str):
    self._db.execute_sql(f"DELETE FROM {TABLE} WHERE name = ?", (name,))
