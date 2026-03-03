"""
Phantom OS Desktop Agent — Main Entry Point

Orchestrates: screen capture, audio capture, camera/emotion,
WebSocket backend connection, action execution, HUD overlay.

Usage:
  python main.py
  python main.py --backend-url ws://localhost:8000
  python main.py --no-hud --no-camera
  python main.py --session-id my-session
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from capture.screen import ScreenCapture
from capture.audio import AudioCapture
from capture.camera import CameraCapture
from executor.mouse import MouseExecutor
from executor.keyboard import KeyboardExecutor
from executor.system import SystemExecutor
from overlay.hud import PhantomHUD
from client import PhantomClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class ActionDispatcher:
    """Routes action commands from backend to the correct executor."""

    def __init__(
        self,
        mouse: MouseExecutor,
        keyboard: KeyboardExecutor,
        system: SystemExecutor,
        hud: PhantomHUD,
        client: PhantomClient,
    ):
        self._mouse = mouse
        self._keyboard = keyboard
        self._system = system
        self._hud = hud
        self._client = client

    async def dispatch(self, action_dict: dict) -> None:
        action_type = action_dict.get("action_type", "")
        params = action_dict.get("parameters", {})
        target = action_dict.get("target") or {}
        narration = action_dict.get("narration", "")
        action_id = action_dict.get("action_id", "")
        confidence = float(action_dict.get("confidence", 1.0))

        # Show HUD
        if narration:
            self._hud.show_narration(narration)

        # Show target if we have coordinates
        if target.get("x") and target.get("y"):
            self._hud.show_target(
                x=int(target["x"]),
                y=int(target["y"]),
                width=target.get("width", 60),
                height=target.get("height", 30),
                label=target.get("label", action_type),
                confidence=confidence,
            )

        success = True
        error = ""
        screenshot_after = ""

        try:
            if action_type == "click":
                x = target.get("x", params.get("x", 0))
                y = target.get("y", params.get("y", 0))
                double = params.get("double", False)
                button = params.get("button", "left")
                await self._mouse.click(x, y, button=button, double=double)

            elif action_type == "type":
                text = params.get("text", "")
                wpm = params.get("wpm", 80)
                await self._keyboard.type_text(text, wpm=wpm)

            elif action_type == "scroll":
                x = target.get("x", params.get("x", 960))
                y = target.get("y", params.get("y", 540))
                amount = params.get("amount", 3)
                direction = params.get("direction", "down")
                await self._mouse.scroll(x, y, amount=amount, direction=direction)

            elif action_type == "key_combo":
                keys = params.get("keys", [])
                if keys:
                    await self._keyboard.hotkey(*keys)

            elif action_type == "navigate":
                url = params.get("url", "")
                if url:
                    await self._system.open_url(url)

            elif action_type == "open_app":
                app_name = params.get("app_name", "")
                if app_name:
                    success = await self._system.open_app(app_name)
                    if not success:
                        error = f"Could not open app: {app_name}"

            elif action_type == "drag":
                await self._mouse.drag(
                    params.get("from_x", 0), params.get("from_y", 0),
                    params.get("to_x", 0), params.get("to_y", 0),
                )

            elif action_type == "read_clipboard":
                content = await self._system.get_clipboard()
                logger.info(f"Clipboard: {content[:100]}")

            elif action_type == "write_clipboard":
                text = params.get("text", "")
                await self._system.set_clipboard(text)

            elif action_type == "screenshot":
                screenshot_after = await self._system.take_screenshot()

            elif action_type == "wait":
                duration_ms = params.get("duration_ms", 1000)
                await asyncio.sleep(duration_ms / 1000)

            else:
                logger.warning(f"Unknown action type: {action_type}")
                error = f"Unknown action: {action_type}"
                success = False

        except Exception as e:
            success = False
            error = str(e)
            logger.error(f"Action execution error ({action_type}): {e}")

        # Report result back to backend
        await self._client.send_action_result(
            action_id=action_id,
            success=success,
            error=error,
            screenshot_after=screenshot_after,
        )

        if success:
            logger.info(f"✓ {action_type} executed successfully")
        else:
            logger.error(f"✗ {action_type} failed: {error}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Phantom OS Desktop Agent")
    parser.add_argument(
        "--backend-url",
        default=os.getenv("BACKEND_URL", "ws://localhost:8000"),
        help="Backend WebSocket URL",
    )
    parser.add_argument(
        "--session-id",
        default=os.getenv("SESSION_ID", str(uuid4())),
        help="Session ID (auto-generated if not provided)",
    )
    parser.add_argument("--no-hud", action="store_true", help="Disable HUD overlay")
    parser.add_argument("--no-camera", action="store_true", help="Disable webcam")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════╗
║           PHANTOM OS — DESKTOP AGENT     ║
╠══════════════════════════════════════════╣
║  Session ID : {args.session_id[:36]}
║  Backend    : {args.backend_url}
║  HUD        : {'OFF' if args.no_hud else 'ON'}
║  Camera     : {'OFF' if args.no_camera else 'AUTO'}
╚══════════════════════════════════════════╝
""")

    # Init components
    screen_capture = ScreenCapture()
    audio_capture = AudioCapture()
    camera_capture = CameraCapture() if not args.no_camera else None
    mouse_executor = MouseExecutor(screen_capture.screen_width, screen_capture.screen_height)
    keyboard_executor = KeyboardExecutor()
    system_executor = SystemExecutor()
    hud = PhantomHUD(screen_capture.screen_width, screen_capture.screen_height) if not args.no_hud else PhantomHUD(0, 0)
    client = PhantomClient(args.backend_url, args.session_id)
    dispatcher = ActionDispatcher(mouse_executor, keyboard_executor, system_executor, hud, client)

    # Voice activity: track silence to auto-send end_of_turn
    last_audio_time = [0.0]
    SILENCE_THRESHOLD_MS = 800  # 800ms silence → end of turn

    # ── Register callbacks ────────────────────────────────────────────────────

    @client.on_action
    async def handle_action(action_dict: dict) -> None:
        hud.show_status("EXECUTING")
        screen_before = await system_executor.take_screenshot()
        await dispatcher.dispatch(action_dict)
        hud.show_status("LISTENING")

    # Continuous output stream so chunks queue up instead of interrupting each other
    _audio_stream = None
    try:
        import sounddevice as sd
        import numpy as np
        _audio_stream = sd.OutputStream(samplerate=24000, channels=1, dtype="float32")
        _audio_stream.start()
        logger.info("[PLAYBACK] Audio output stream opened (24kHz mono float32)")
    except Exception as e:
        logger.error(f"[PLAYBACK] Could not open audio output stream: {e}")

    @client.on_audio
    async def handle_audio_playback(audio_bytes: bytes) -> None:
        """Write Phantom's voice into the continuous output stream."""
        logger.info(f"[PLAYBACK] Received {len(audio_bytes)} bytes of audio from backend")
        if _audio_stream is None:
            logger.error("[PLAYBACK] No audio stream — skipping")
            return
        try:
            import numpy as np
            pcm = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            _audio_stream.write(pcm)
            logger.info(f"[PLAYBACK] Wrote {len(pcm)} samples to output stream")
        except Exception as e:
            logger.error(f"[PLAYBACK] Audio write error: {e}")

    @client.on_text
    async def handle_text(text: str) -> None:
        if text.strip():
            print(f"\n🤖 Phantom: {text.strip()}")

    @client.on_confirmation
    async def handle_confirmation(payload: dict) -> None:
        action = payload.get("action", {})
        narration = action.get("narration", "Action requires confirmation")
        risk = action.get("risk_level", "high").upper()
        action_id = action.get("action_id", "")

        print(f"\n⚠️  CONFIRMATION REQUIRED [{risk}]")
        print(f"   {narration}")
        print("   [Y]es / [N]o: ", end="", flush=True)

        hud.show_narration(f"⚠️ Confirm: {narration[:60]}...", duration_ms=30000)

        # Non-blocking input using asyncio
        loop = asyncio.get_event_loop()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, input),
                timeout=30.0,
            )
            if response.strip().lower() in ("y", "yes", ""):
                await client.confirm_action(action_id)
                print("✓ Action confirmed")
            else:
                await client.reject_action(action_id)
                print("✗ Action rejected")
        except asyncio.TimeoutError:
            await client.reject_action(action_id)
            print("\n⏱ Timeout — action rejected")

    @client.on_session_state
    async def handle_session_state(state: dict) -> None:
        status = state.get("status", "idle").upper()
        hud.show_status(status)

    # ── Capture callbacks ─────────────────────────────────────────────────────

    async def on_frame(frame_b64: str) -> None:
        await client.send_frame(frame_b64)

    async def on_audio(audio_b64: str) -> None:
        last_audio_time[0] = time.monotonic()
        screen_capture.set_active_mode(True)
        logger.debug(f"[MIC] Sending audio chunk to backend ({len(audio_b64)} b64 chars)")
        await client.send_audio(audio_b64)
        hud.show_status("LISTENING")

    async def on_emotion(emotion: dict) -> None:
        await client.send_emotion(emotion)

    # ── Silence detection → end_of_turn ──────────────────────────────────────
    async def silence_detector() -> None:
        was_speaking = False
        while True:
            await asyncio.sleep(0.1)
            if last_audio_time[0] > 0:
                silence_ms = (time.monotonic() - last_audio_time[0]) * 1000
                if silence_ms > SILENCE_THRESHOLD_MS and was_speaking:
                    await client.send_end_of_turn()
                    hud.show_status("THINKING")
                    screen_capture.set_active_mode(True)
                    was_speaking = False
                elif silence_ms < SILENCE_THRESHOLD_MS:
                    was_speaking = True

    # ── Heartbeat ─────────────────────────────────────────────────────────────
    async def heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(15)
            await client.heartbeat()

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    stop_event = asyncio.Event()

    def handle_sigint():
        print("\n\nPhantom OS shutting down...")
        stop_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, handle_sigint)

    # ── Run all tasks ─────────────────────────────────────────────────────────
    tasks = [
        asyncio.create_task(client.connect(), name="ws_client"),
        asyncio.create_task(screen_capture.start(on_frame), name="screen_capture"),
        asyncio.create_task(audio_capture.start(on_audio), name="audio_capture"),
        asyncio.create_task(silence_detector(), name="silence_detector"),
        asyncio.create_task(heartbeat_loop(), name="heartbeat"),
    ]

    if camera_capture and camera_capture.available:
        tasks.append(asyncio.create_task(camera_capture.start(on_emotion), name="camera"))

    print("🚀 Phantom OS is running. Speak to give commands.\n")
    hud.show_status("LISTENING")

    # Wait for shutdown signal
    await stop_event.wait()

    # Cancel all tasks
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await client.disconnect()
    await screen_capture.stop()
    await audio_capture.stop()
    if _audio_stream:
        _audio_stream.stop()
        _audio_stream.close()
    hud.stop()

    print("Phantom OS stopped.")


if __name__ == "__main__":
    asyncio.run(main())
