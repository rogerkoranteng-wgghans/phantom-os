"""
Webcam capture for emotional context detection.
Optional — gracefully disabled when no camera present.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("opencv-python not installed — camera capture disabled")


class CameraCapture:
    def __init__(self, fps: int = 2, quality: int = 60):
        self.fps = fps
        self.quality = quality
        self._running = False
        self._cap = None
        self._available = False

        if CV2_AVAILABLE:
            self._available = self._probe_camera()

    def _probe_camera(self) -> bool:
        """Try to open the camera and read one frame. Returns True only if both succeed."""
        import threading
        result = [False]

        def _try():
            try:
                # Suppress noisy V4L2 stderr messages during probe
                import os, sys
                devnull = open(os.devnull, "w")
                old_stderr_fd = os.dup(2)
                os.dup2(devnull.fileno(), 2)
                try:
                    cap = cv2.VideoCapture(0)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if cap.isOpened():
                        ret, _ = cap.read()
                        result[0] = ret
                    cap.release()
                finally:
                    os.dup2(old_stderr_fd, 2)
                    os.close(old_stderr_fd)
                    devnull.close()
            except Exception:
                pass

        t = threading.Thread(target=_try, daemon=True)
        t.start()
        t.join(timeout=3.0)  # give it 3 s max — V4L2 hangs longer than this

        if result[0]:
            logger.info("CameraCapture: camera detected")
        else:
            logger.info("CameraCapture: no usable camera — emotion detection disabled")
        return result[0]

    @property
    def available(self) -> bool:
        return self._available

    def capture_face_frame(self) -> str | None:
        """Capture frame, detect face region, return base64 JPEG or None."""
        if not CV2_AVAILABLE or not self._available or self._cap is None:
            return None
        try:
            ret, frame = self._cap.read()
            if not ret:
                return None

            # Detect face
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(80, 80))

            if len(faces) > 0:
                # Crop largest face with padding
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                pad = int(w * 0.3)
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(frame.shape[1], x + w + pad)
                y2 = min(frame.shape[0], y + h + pad)
                face_img = frame[y1:y2, x1:x2]
            else:
                # Send full frame if no face detected
                face_img = frame

            # Encode to JPEG
            _, buf = cv2.imencode(
                ".jpg", face_img, [cv2.IMWRITE_JPEG_QUALITY, self.quality]
            )
            return base64.b64encode(buf.tobytes()).decode("utf-8")

        except Exception as e:
            logger.debug(f"capture_face_frame error: {e}")
            return None

    def estimate_emotion(self, face_frame) -> dict:
        """
        Basic emotion estimation from face landmarks.
        Returns: frustration, confidence, urgency, engagement scores.
        """
        if not CV2_AVAILABLE:
            return {"has_face": False, "frustration": 0.0, "confidence": 0.5, "urgency": 0.0, "engagement": 0.5}

        try:
            gray = cv2.cvtColor(face_frame, cv2.COLOR_BGR2GRAY)

            # Use simple heuristics based on face detection features
            # In production you'd use a proper emotion model
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
            has_face = len(faces) > 0

            if not has_face:
                return {"has_face": False, "frustration": 0.0, "confidence": 0.5, "urgency": 0.0, "engagement": 0.5}

            # Simple brightness/contrast-based proxy metrics
            mean_brightness = float(np.mean(gray)) / 255.0
            std_brightness = float(np.std(gray)) / 128.0

            engagement = min(1.0, mean_brightness * 1.2)
            frustration = max(0.0, min(1.0, std_brightness - 0.3))
            confidence = max(0.0, min(1.0, mean_brightness))
            urgency = 0.0

            return {
                "has_face": True,
                "frustration": round(frustration, 3),
                "confidence": round(confidence, 3),
                "urgency": round(urgency, 3),
                "engagement": round(engagement, 3),
            }
        except Exception as e:
            logger.debug(f"estimate_emotion error: {e}")
            return {"has_face": False, "frustration": 0.0, "confidence": 0.5, "urgency": 0.0, "engagement": 0.5}

    async def start(self, on_emotion: Callable[[dict], Awaitable[None]]) -> None:
        """Start capture loop. Calls on_emotion with emotion dict."""
        if not self._available:
            logger.info("CameraCapture: skipping (no camera)")
            return

        self._running = True
        loop = asyncio.get_event_loop()

        try:
            self._cap = cv2.VideoCapture(0)

            while self._running:
                start = time.monotonic()

                def capture_and_analyze():
                    frame_b64 = self.capture_face_frame()
                    if frame_b64:
                        import numpy as np_local
                        import base64 as b64
                        raw = b64.b64decode(frame_b64)
                        arr = np_local.frombuffer(raw, np_local.uint8)
                        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        return self.estimate_emotion(img)
                    return None

                emotion = await loop.run_in_executor(None, capture_and_analyze)
                if emotion and emotion.get("has_face"):
                    try:
                        await on_emotion(emotion)
                    except Exception as e:
                        logger.debug(f"on_emotion callback error: {e}")

                elapsed = time.monotonic() - start
                await asyncio.sleep(max(0.0, (1.0 / self.fps) - elapsed))

        except Exception as e:
            logger.error(f"CameraCapture error: {e}")
        finally:
            if self._cap:
                self._cap.release()

    async def stop(self) -> None:
        self._running = False
