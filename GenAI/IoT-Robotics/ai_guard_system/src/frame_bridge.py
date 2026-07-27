#===----------------ai_guard_system frame_bridge----------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import time
import numpy as np
from multiprocessing import shared_memory
from multiprocessing import resource_tracker


# =====================================================================
#  Constants
# =====================================================================

# Header: write_counter (uint64, 8 bytes) + timestamp (float64, 8 bytes)
HEADER_SIZE = 16

# Default frame dimensions
DEFAULT_HEIGHT = 480
DEFAULT_WIDTH = 640
DEFAULT_CHANNELS = 3


# =====================================================================
#  resource_tracker workaround
# =====================================================================

def _unregister_from_resource_tracker(name: str):
    """
    Remove this shared memory segment from Python's resource_tracker.

    Prevents the Reader from auto-unlinking on exit — unlinking is the
    Writer's responsibility.

    Note: Python 3.13+ added a ``track=False`` parameter, but 3.12 and
    earlier require this manual workaround.
    """
    try:
        resource_tracker.unregister(f"/{name}", "shared_memory")
    except Exception:
        pass


# =====================================================================
#  SharedFrameWriter (used by cv_pipeline)
# =====================================================================

class SharedFrameWriter:
    """
    Writes frames into shared memory using double buffering.

    Usage::

        writer = SharedFrameWriter("cam0")
        writer.write(frame)   # numpy array, shape=(H, W, 3), dtype=uint8
        writer.close()        # call on exit
    """

    def __init__(self, name: str, height: int = DEFAULT_HEIGHT,
                 width: int = DEFAULT_WIDTH, channels: int = DEFAULT_CHANNELS):
        self.name = f"aiguard_{name}"
        self.height = height
        self.width = width
        self.channels = channels
        self._frame_size = height * width * channels
        # Total size: header + 2 frame buffers (double buffering)
        self._total_size = HEADER_SIZE + self._frame_size * 2
        self._counter = 0

        # Create shared memory (remove stale segment if it exists)
        try:
            old_shm = shared_memory.SharedMemory(name=self.name)
            old_shm.close()
            old_shm.unlink()
        except FileNotFoundError:
            pass

        self._shm = shared_memory.SharedMemory(
            name=self.name,
            create=True,
            size=self._total_size,
        )

        # Header view: [counter(float64), timestamp(float64)]
        self._header = np.ndarray((2,), dtype=np.float64,
                                  buffer=self._shm.buf[:HEADER_SIZE])
        self._header[:] = 0

        # Two frame buffer views
        offset0 = HEADER_SIZE
        offset1 = HEADER_SIZE + self._frame_size
        self._buffers = [
            np.ndarray((height, width, channels), dtype=np.uint8,
                       buffer=self._shm.buf[offset0:offset0 + self._frame_size]),
            np.ndarray((height, width, channels), dtype=np.uint8,
                       buffer=self._shm.buf[offset1:offset1 + self._frame_size]),
        ]

        print(f"[SharedFrame] Writer created: {self.name} "
              f"({width}x{height}x{channels}, double-buffered, "
              f"{self._total_size} bytes)")

    def write(self, frame: np.ndarray):
        """
        Write a frame into shared memory (double-buffered).

        Steps:
        1. Copy into buffer[(counter+1) % 2]  (the one Reader is NOT reading)
        2. Increment counter (atomically switches Reader's target buffer)
        """
        # Ensure correct dimensions
        if frame.shape != (self.height, self.width, self.channels):
            import cv2
            frame = cv2.resize(frame, (self.width, self.height))

        # Write into the "next" buffer (Reader currently reads counter % 2)
        next_idx = (self._counter + 1) % 2
        np.copyto(self._buffers[next_idx], frame)

        # Update header: timestamp first, then counter as the commit signal
        self._counter += 1
        self._header[1] = time.time()              # timestamp
        self._header[0] = float(self._counter)      # counter (Reader sees this)

    def close(self):
        """Close and release shared memory (Writer is responsible for unlink)."""
        try:
            self._shm.close()
            self._shm.unlink()
            print(f"[SharedFrame] Writer closed: {self.name}")
        except Exception as e:
            print(f"[SharedFrame] Writer close error: {e}")


# =====================================================================
#  SharedFrameReader (used by main_UI)
# =====================================================================

class SharedFrameReader:
    """
    Reads frames from shared memory using double buffering.

    Does NOT unlink shared memory on close — that is the Writer's job.

    Usage::

        reader = SharedFrameReader("cam0")
        frame, meta = reader.read()
        # frame: numpy array or None
        # meta:  {"counter": int, "timestamp": float, "age_ms": float}
        reader.close()
    """

    def __init__(self, name: str, height: int = DEFAULT_HEIGHT,
                 width: int = DEFAULT_WIDTH, channels: int = DEFAULT_CHANNELS):
        self.name = f"aiguard_{name}"
        self.height = height
        self.width = width
        self.channels = channels
        self._frame_size = height * width * channels
        self._total_size = HEADER_SIZE + self._frame_size * 2
        self._last_counter = 0

        self._shm = None
        self._header = None
        self._buffers = None
        self._connected = False

    def _try_connect(self) -> bool:
        """Attempt to connect to shared memory (Writer may not be running yet)."""
        if self._connected:
            return True
        try:
            self._shm = shared_memory.SharedMemory(name=self.name)

            # Remove from resource_tracker to prevent Reader from unlinking
            _unregister_from_resource_tracker(self.name)

            self._header = np.ndarray(
                (2,), dtype=np.float64, buffer=self._shm.buf[:HEADER_SIZE]
            )

            offset0 = HEADER_SIZE
            offset1 = HEADER_SIZE + self._frame_size
            self._buffers = [
                np.ndarray((self.height, self.width, self.channels),
                           dtype=np.uint8,
                           buffer=self._shm.buf[offset0:offset0 + self._frame_size]),
                np.ndarray((self.height, self.width, self.channels),
                           dtype=np.uint8,
                           buffer=self._shm.buf[offset1:offset1 + self._frame_size]),
            ]

            self._connected = True
            print(f"[SharedFrame] Reader connected: {self.name}")
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"[SharedFrame] Reader connect error: {e}")
            return False

    def read(self):
        """
        Read the latest frame (double-buffered safe read).

        Reads buffer[counter % 2] — the one Writer has already finished.
        Writer is currently writing to (counter+1) % 2, so no conflict.

        Returns:
            (frame, meta) — frame is a numpy array or None;
            meta is a dict with keys: counter, timestamp, age_ms.
        """
        if not self._try_connect():
            return None, {"counter": 0, "timestamp": 0, "age_ms": -1}

        counter = int(self._header[0])
        timestamp = float(self._header[1])
        age_ms = (time.time() - timestamp) * 1000 if timestamp > 0 else -1

        meta = {
            "counter": counter,
            "timestamp": timestamp,
            "age_ms": age_ms,
        }

        if counter == 0:
            return None, meta

        # Read the most recently completed buffer
        read_idx = counter % 2
        frame = self._buffers[read_idx].copy()  # copy to avoid later mutations
        self._last_counter = counter

        return frame, meta

    @property
    def has_new_frame(self) -> bool:
        """Check whether a new frame is available (counter has advanced)."""
        if not self._connected:
            return False
        return int(self._header[0]) != self._last_counter

    @property
    def is_connected(self) -> bool:
        """Whether the reader is connected to shared memory."""
        return self._connected

    def close(self):
        """
        Close the connection (does NOT unlink — that's the Writer's job).

        Since we unregistered from resource_tracker, no auto-unlink occurs.
        """
        try:
            if self._shm:
                self._shm.close()
            print(f"[SharedFrame] Reader closed: {self.name}")
        except Exception as e:
            print(f"[SharedFrame] Reader close error: {e}")
        self._connected = False
        self._shm = None
        self._header = None
        self._buffers = None
