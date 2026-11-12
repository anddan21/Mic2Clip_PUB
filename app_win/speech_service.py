"""Google Cloud Speech to Text streaming session."""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Callable, Optional

import config

logger = logging.getLogger(__name__)

# Google limits; restart streams before the hard cap.
_STREAM_MAX_SECONDS = 240.0

_speech_mod: object | bool | None = None


def _speech():
    global _speech_mod
    if _speech_mod is False:
        return None
    if _speech_mod is None:
        try:
            from google.cloud import speech_v1 as speech_v1

            _speech_mod = speech_v1
        except ImportError:
            _speech_mod = False
    return _speech_mod if _speech_mod else None


def speech_credentials_configured() -> bool:
    return bool(config.GOOGLE_APPLICATION_CREDENTIALS) and os.path.isfile(
        config.GOOGLE_APPLICATION_CREDENTIALS
    )


class StreamingDictationSession:
    """Mic capture + Google streaming loop; stream restarts after each utterance."""

    def __init__(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[str], None],
        on_closed: Callable[[], None] = lambda: None,
        language_code: str = "ru-RU",
    ) -> None:
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error
        self._on_closed = on_closed
        self._language_code = language_code
        self._automatic_punctuation = True
        self._stream_generation = 0
        self._lang_lock = threading.Lock()
        self._client_lock = threading.Lock()
        self._current_client: object | None = None
        self._audio_q: queue.Queue[Optional[bytes]] = queue.Queue(maxsize=64)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._mic = None
        self._last_stream_start = 0.0

    def set_language_code(self, language_code: str) -> None:
        with self._lang_lock:
            if language_code == self._language_code:
                return
            self._language_code = language_code
            self._stream_generation += 1
        self._close_current_client()

    def set_automatic_punctuation(self, enabled: bool) -> None:
        with self._lang_lock:
            if enabled == self._automatic_punctuation:
                return
            self._automatic_punctuation = enabled
            self._stream_generation += 1
        self._close_current_client()

    def is_running(self) -> bool:
        return (
            not self._stop.is_set()
            and self._thread is not None
            and self._thread.is_alive()
            and self._mic is not None
        )

    def _close_current_client(self) -> None:
        with self._client_lock:
            client = self._current_client
            self._current_client = None
        if client is None:
            return
        try:
            if hasattr(client, "transport") and hasattr(client.transport, "close"):
                client.transport.close()
        except Exception:
            pass

    def _set_current_client(self, client: object) -> None:
        with self._client_lock:
            self._current_client = client

    def _drain_audio_queue(self) -> None:
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def _mic_chunk(self, pcm: bytes) -> None:
        if self._stop.is_set():
            return
        try:
            self._audio_q.put_nowait(pcm)
        except queue.Full:
            try:
                _ = self._audio_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._audio_q.put_nowait(pcm)
            except queue.Full:
                pass

    def _run_one_stream(self, speech: object) -> None:
        with self._lang_lock:
            lang = self._language_code
            auto_punct = self._automatic_punctuation
            stream_gen = self._stream_generation

        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=config.SAMPLE_RATE,
            language_code=lang,
            enable_automatic_punctuation=auto_punct,
            model="latest_long",
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=True,
            single_utterance=True,
        )

        client = speech.SpeechClient()
        self._set_current_client(client)
        self._last_stream_start = time.monotonic()

        stream_active = [True]

        def _stream_stale() -> bool:
            with self._lang_lock:
                return self._stream_generation != stream_gen

        def _end_stream() -> None:
            stream_active[0] = False
            self._close_current_client()

        def audio_requests():
            while not self._stop.is_set() and stream_active[0]:
                if _stream_stale():
                    return
                try:
                    chunk = self._audio_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                if chunk is None:
                    return
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        stream_started = time.monotonic()
        try:
            responses = client.streaming_recognize(streaming_config, audio_requests())
            for response in responses:
                if self._stop.is_set() or _stream_stale():
                    break
                if time.monotonic() - stream_started >= _STREAM_MAX_SECONDS:
                    logger.debug("Speech stream time limit, restarting")
                    break

                for result in response.results:
                    if not result.alternatives:
                        continue
                    text = result.alternatives[0].transcript.strip()
                    if not text:
                        continue

                    if result.is_final:
                        self._on_final(text)
                        _end_stream()
                        return
                    else:
                        self._on_partial(text)

                if not stream_active[0]:
                    break
        except Exception as e:
            logger.debug("Stream ended: %s", e)
        finally:
            _end_stream()
            self._on_closed()

    def start(self) -> None:
        # Always clean up existing mic/queue state before starting a new one
        self.stop()

        speech = _speech()
        if not speech:
            self._on_error("Google Cloud Speech is not installed.")
            return
        if not speech_credentials_configured():
            self._on_error(
                "Speech to Text error. Check credentials in env file."
            )
            return
        self._stop.clear()
        self._drain_audio_queue()
        from audio_stream import MicCapture

        self._mic = MicCapture(on_pcm_chunk=self._mic_chunk)
        self._thread = threading.Thread(
            target=self._run_one_stream, args=(speech,), daemon=True
        )
        self._thread.start()
        try:
            self._mic.start()
        except Exception as e:
            logger.exception("Mic start failed")
            self._on_error(str(e))
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        self._close_current_client()
        if self._mic:
            try:
                self._mic.stop()
            except Exception:
                logger.exception("Mic stop failed")
            self._mic = None
        try:
            self._audio_q.put_nowait(None)
        except queue.Full:
            pass
        if self._thread:
            if threading.current_thread() != self._thread:
                self._thread.join(timeout=5.0)
            self._thread = None
        self._drain_audio_queue()
