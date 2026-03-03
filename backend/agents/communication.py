"""
CommunicationAgent: Draft emails, messages, and documents in the user's voice/style.
"""
from __future__ import annotations

import logging
import os

from google import genai

from agents.memory import MemoryAgent

logger = logging.getLogger(__name__)


class CommunicationAgent:
    def __init__(self, memory_agent: MemoryAgent):
        self._memory = memory_agent
        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key) if api_key else None

    async def _get_style_context(self) -> str:
        """Get user's communication style from semantic memory."""
        prefs = await self._memory.recall(
            query="communication style email writing", memory_type="semantic", limit=5
        )
        if prefs:
            return "User preferences:\n" + "\n".join(f"- {p.content}" for p in prefs)
        return "Use a professional but friendly tone."

    async def draft_email(
        self,
        to: list[str],
        subject: str,
        intent: str,
        user_style_context: str = "",
    ) -> str:
        if not self._client:
            return f"[Email draft for: {intent}]"

        style = user_style_context or await self._get_style_context()
        try:
            prompt = f"""
Draft an email with the following details:
To: {', '.join(to)}
Subject: {subject}
Intent: {intent}

{style}

Write ONLY the email body (no subject line, no "To:" header).
Keep it concise and natural. Match the user's preferred style.
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"draft_email error: {e}")
            return f"[Draft: {intent}]"

    async def draft_message(
        self,
        platform: str,
        intent: str,
        user_style_context: str = "",
        channel: str = "",
    ) -> str:
        if not self._client:
            return f"[{platform} message: {intent}]"

        style = user_style_context or await self._get_style_context()
        try:
            prompt = f"""
Draft a {platform} message{f' for #{channel}' if channel else ''}.
Intent: {intent}
{style}

Write ONLY the message body. Keep it appropriate for {platform} (concise for Slack/Teams, can be longer for formal platforms).
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"draft_message error: {e}")
            return f"[Message: {intent}]"

    async def draft_document(
        self,
        title: str,
        intent: str,
        context: str = "",
    ) -> str:
        if not self._client:
            return f"# {title}\n\n[Document: {intent}]"

        style = await self._get_style_context()
        try:
            prompt = f"""
Draft a document titled "{title}".
Purpose: {intent}
{f'Context: {context}' if context else ''}
{style}

Write the full document content in Markdown format.
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"draft_document error: {e}")
            return f"# {title}\n\n{intent}"

    async def learn_style(
        self, session_id: str, past_communications: list[str]
    ) -> None:
        """Extract writing style from past communications and save to memory."""
        if not self._client or not past_communications:
            return

        sample = "\n\n---\n\n".join(past_communications[:5])
        try:
            prompt = f"""
Analyze this person's writing style from their communications and describe it in 3-5 bullet points.
Focus on: tone (formal/casual), sentence length, vocabulary, punctuation habits, greeting/closing style.

Communications:
{sample[:3000]}

Output ONLY the bullet points, each starting with "User".
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            lines = [l.strip() for l in response.text.strip().split("\n") if l.strip()]
            for line in lines[:5]:
                await self._memory.store(
                    content=line,
                    memory_type="semantic",
                    tags=["communication_style", "auto_learned"],
                    session_id=session_id,
                )
            logger.info(f"Communication style learned: {len(lines)} preferences")
        except Exception as e:
            logger.error(f"learn_style error: {e}")
