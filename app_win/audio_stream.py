"""Capture microphone via sounddevice; emit PCM LINEAR16 mono chunks."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

import config

logger = logging.getLogger(__name__)

class MicCapture:
    def __init__(
        self,
        on_pcm_chunk: Callable[[bytes], None],
        sample_rate: int = config.SAMPLE_RATE,
        channels: int = config.CHANNELS,
        block_ms: float = 80.0,
    ) -> None:
        self._on_pcm_chunk = on_pcm_chunk
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_samples = max(1, int(sample_rate * (block_ms / 1000.0)))
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            logger.debug("sounddevice status: %s", status)
        # indata: float32 shape (frames, channels)
        mono = indata[:, 0] if indata.shape[1] > 1 else indata.ravel()
        clipped = np.clip(mono, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16).tobytes()
        try:
            self._on_pcm_chunk(pcm)
        except Exception:
            logger.exception("PCM chunk handler failed")

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            raise RuntimeError("sounddevice is not installed.")
        with self._lock:
            if self._stream is not None:
                return
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                blocksize=self.block_samples,
                callback=self._callback,
            )
            self._stream.start()

    def stop(self) -> None:
        with self._lock:
            if self._stream is None:
                return
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
