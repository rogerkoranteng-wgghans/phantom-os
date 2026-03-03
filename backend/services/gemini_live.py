"""
Gemini Live API session manager.
Handles real-time bidirectional streaming of screen frames + audio.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Callable, Awaitable

from google import genai
from google.genai import types

from services.action_schema import action_to_prompt_hint, parse_gemini_response
from models.schemas import Action

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash-native-audio-latest"

SYSTEM_PROMPT = """You are Phantom OS — an advanced autonomous AI operating system layer with full visibility of the user's screen and the ability to hear their voice in real time.

Your purpose: understand the user's intent from voice commands and screen context, then autonomously complete tasks on their computer across any application.

## Your Capabilities
- You see the user's screen as a continuous video stream
- You hear the user's voice in real time
- You can take any action on their computer: click buttons, type text, navigate browsers, open apps, etc.

## How to Take Actions
{action_format}

## Behavior Guidelines
- ALWAYS narrate what you're doing: "I'm opening your email client now", "Searching for flights to London..."
- For complex tasks, break them down and narrate each step
- If you're unsure what the user wants, ask ONE clarifying question
- For high-risk actions (sending emails, deleting files, purchases), ALWAYS set requires_confirmation: true
- If a task requires research, say so: "Let me look that up for you"
- Be concise but warm in your narration — you're a trusted assistant, not a robot
- If you detect the user seems frustrated (they've repeated themselves, their voice sounds tense), acknowledge it: "I understand this is frustrating. Let me handle this."

## Context Awareness
- You remember what you've done in this session
- You can see what's currently on screen — use this to make smart decisions
- If an action fails (button not found, page not loaded), adapt and try a different approach

Remember: You are not a chatbot. You are an operating system. Act, don't just talk.
"""


class GeminiLiveSession:
    def __init__(
        self,
        session_id: str,
        on_action: Callable[[Action], Awaitable[None]],
        on_audio: Callable[[bytes], Awaitable[None]],
        on_text: Callable[[str], Awaitable[None]],
    ):
        self.session_id = session_id
        self._on_action = on_action
        self._on_audio = on_audio
        self._on_text = on_text

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        self._client = genai.Client(api_key=api_key)
        self._session = None
        self._receive_task: asyncio.Task | None = None
        self._running = False

        # Buffer for accumulating text response before parsing actions
        self._text_buffer = ""

    async def start(self) -> None:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=SYSTEM_PROMPT.format(
                action_format=action_to_prompt_hint()
            ),
        )

        self._session_ctx = self._client.aio.live.connect(
            model=MODEL, config=config
        )
        self._session = await self._session_ctx.__aenter__()
        self._running = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info(f"GeminiLiveSession started for session {self.session_id}")

    async def send_frame(self, frame_b64: str) -> None:
        """Send a JPEG screen frame (base64 encoded)."""
        if not self._session or not self._running:
            return
        try:
            await self._session.send_realtime_input(
                video=types.Blob(
                    mime_type="image/jpeg",
                    data=base64.b64decode(frame_b64),
                )
            )
        except Exception as e:
            logger.error(f"send_frame error: {e}")

    async def send_audio(self, audio_b64: str) -> None:
        """Send a PCM audio chunk (base64 encoded, 16kHz mono)."""
        if not self._session or not self._running:
            return
        try:
            await self._session.send_realtime_input(
                audio=types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=base64.b64decode(audio_b64),
                )
            )
        except Exception as e:
            logger.error(f"send_audio error: {e}")

    async def send_end_of_turn(self) -> None:
        """No-op: native audio model uses built-in VAD for turn detection.
        Sending send_client_content(turns=[], turn_complete=True) causes a 1007
        invalid argument error on gemini-2.5-flash-native-audio-latest.
        The model auto-detects end of speech and responds via its built-in VAD.
        """
        pass

    async def send_text(self, text: str) -> None:
        """Send a text message (for system notifications to Gemini)."""
        if not self._session or not self._running:
            return
        try:
            await self._session.send_client_content(
                turns=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=text)],
                    )
                ],
                turn_complete=True,
            )
        except Exception as e:
            logger.error(f"send_text error: {e}")

    async def _receive_loop(self) -> None:
        """Background task that reads Gemini responses and dispatches them."""
        audio_chunks_received = 0
        response_count = 0
        try:
            async for response in self._session.receive():
                if not self._running:
                    break

                response_count += 1
                # Log every response at INFO level so we can see what Gemini sends
                logger.info(f"[GEMINI] Response #{response_count}: type={type(response).__name__} attrs={[a for a in dir(response) if not a.startswith('_')]}")

                server_content = getattr(response, "server_content", None)
                if not server_content:
                    # Check for other top-level fields (tool_call, go_away, etc.)
                    for attr in ("tool_call", "go_away", "setup_complete", "usage_metadata"):
                        val = getattr(response, attr, None)
                        if val:
                            logger.info(f"[GEMINI] Non-content field '{attr}': {val}")
                    continue

                logger.info(f"[GEMINI] server_content attrs: {[a for a in dir(server_content) if not a.startswith('_')]}")

                model_turn = getattr(server_content, "model_turn", None)
                if model_turn:
                    parts = getattr(model_turn, "parts", []) or []
                    logger.info(f"[GEMINI] model_turn has {len(parts)} parts")
                    for i, part in enumerate(parts):
                        part_attrs = [a for a in dir(part) if not a.startswith('_')]
                        logger.info(f"[GEMINI] part[{i}] attrs={part_attrs}")

                        # Audio response (Gemini's voice)
                        inline_data = getattr(part, "inline_data", None)
                        if inline_data and getattr(inline_data, "data", None):
                            audio_chunks_received += 1
                            logger.info(
                                f"[GEMINI] Audio chunk #{audio_chunks_received} received "
                                f"({len(inline_data.data)} bytes) → forwarding to client"
                            )
                            await self._on_audio(inline_data.data)

                        # Text response (present even in AUDIO-only mode)
                        text = getattr(part, "text", None)
                        if text:
                            logger.info(f"[GEMINI] Text part: {text[:120]!r}")
                            self._text_buffer += text
                            await self._on_text(text)
                else:
                    logger.info(f"[GEMINI] No model_turn. turn_complete={getattr(server_content, 'turn_complete', None)}")

                # Parse actions and clear buffer at turn boundary
                if getattr(server_content, "turn_complete", False):
                    logger.info(f"[GEMINI] Turn complete. Buffer length: {len(self._text_buffer)} chars")
                    if self._text_buffer:
                        actions = parse_gemini_response(self._text_buffer)
                        for action in actions:
                            logger.info(
                                f"Action extracted: {action.action_type} | "
                                f"risk={action.risk_level} | confidence={action.confidence}"
                            )
                            await self._on_action(action)
                        self._text_buffer = ""

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self._running:
                logger.error(f"GeminiLive receive_loop error: {e}", exc_info=True)

    async def stop(self) -> None:
        self._running = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._session_ctx:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing Gemini session: {e}")
        logger.info(f"GeminiLiveSession stopped for session {self.session_id}")
