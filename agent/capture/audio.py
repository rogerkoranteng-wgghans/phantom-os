"""
Low-latency microphone capture with voice activity detection.
- PCM 16kHz mono (Gemini Live requirement)
- 100ms chunks
- Energy-based VAD to skip silence
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Callable, Awaitable

import numpy as np

try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except OSError:
    sd = None  # type: ignore[assignment]
    _SD_AVAILABLE = False

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_MS = 100
CHUNK_FRAMES = int(SAMPLE_RATE * CHUNK_MS / 1000)  # 1600 frames per chunk


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_ms: int = CHUNK_MS,
        vad_threshold: float = 0.05,  # RMS energy threshold (raised from 0.01 to filter noise)
    ):
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.chunk_frames = int(sample_rate * chunk_ms / 1000)
        self.vad_threshold = vad_threshold

        self._running = False
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=50)
        self._loop: asyncio.AbstractEventLoop | None = None

    def is_speech(self, audio_data: np.ndarray) -> bool:
        """Simple energy-based voice activity detection."""
        rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
        return rms > self.vad_threshold

    def to_base64(self, audio_data: np.ndarray) -> str:
        """Convert numpy int16 PCM to base64 string."""
        pcm_bytes = audio_data.astype(np.int16).tobytes()
        return base64.b64encode(pcm_bytes).decode("utf-8")

    def _safe_enqueue(self, chunk: np.ndarray) -> None:
        """Put a chunk on the queue, silently dropping it when full."""
        try:
            self._queue.put_nowait(chunk)
        except asyncio.QueueFull:
            pass  # Consumer is behind — drop oldest audio chunk

    def _sounddevice_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        """Called by sounddevice in a separate thread."""
        if status:
            logger.debug(f"AudioCapture sounddevice status: {status}")
        if self._loop and self._loop.is_running():
            mono = indata[:, 0] if indata.ndim > 1 else indata.flatten()
            # Use a bound method so QueueFull is caught inside the event-loop
            # callback, not propagated through asyncio's exception handler.
            self._loop.call_soon_threadsafe(self._safe_enqueue, mono.copy())

    async def start(self, on_audio: Callable[[str], Awaitable[None]]) -> None:
        """Start audio capture. Calls on_audio with base64 PCM chunks."""
        if not _SD_AVAILABLE:
            logger.warning(
                "AudioCapture disabled: PortAudio library not found. "
                "Install with: sudo apt-get install libportaudio2"
            )
            # Keep the coroutine alive so the task doesn't exit
            while self._running:
                await asyncio.sleep(1)
            return

        self._running = True
        self._loop = asyncio.get_event_loop()

        logger.info(f"AudioCapture started (16kHz mono, {self.chunk_ms}ms chunks)")

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.int16,
            blocksize=self.chunk_frames,
            callback=self._sounddevice_callback,
        )

        chunks_sent = 0
        with stream:
            while self._running:
                try:
                    chunk = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                    if self.is_speech(chunk):
                        audio_b64 = self.to_base64(chunk)
                        chunks_sent += 1
                        if chunks_sent == 1 or chunks_sent % 20 == 0:
                            logger.info(f"[AUDIO] Speech detected — chunk #{chunks_sent} sent to backend")
                        try:
                            await on_audio(audio_b64)
                        except Exception as e:
                            logger.error(f"on_audio callback error: {e}")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"AudioCapture error: {e}")

    async def stop(self) -> None:
        self._running = False
        logger.info("AudioCapture stopped")
