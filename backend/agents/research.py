"""
ResearchAgent: Web research and information extraction using Gemini + Google Search.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class ResearchAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key) if api_key else None
        self._http = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "PhantomOS/1.0 ResearchAgent"},
        )

    async def search(self, query: str, context: str = "") -> dict[str, Any]:
        """Search the web and return structured results."""
        if not self._client:
            return {"error": "Gemini client not available", "query": query}

        try:
            google_search_tool = types.Tool(google_search=types.GoogleSearch())
            prompt = f"""
Research the following query and provide a comprehensive response.
{f'Context: {context}' if context else ''}

Query: {query}

Provide:
1. A concise summary (2-3 sentences)
2. Key facts (bullet points)
3. Source URLs if available
4. Structured data if applicable (as JSON in a ```json block)
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(tools=[google_search_tool]),
            )

            text = response.text or ""
            # Extract structured data if present
            structured_data = None
            import re
            json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if json_match:
                import json
                try:
                    structured_data = json.loads(json_match.group(1))
                except Exception:
                    pass

            # Extract URLs from grounding metadata
            sources = []
            if hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
                        gm = candidate.grounding_metadata
                        if hasattr(gm, "grounding_chunks"):
                            for chunk in gm.grounding_chunks:
                                if hasattr(chunk, "web") and chunk.web:
                                    sources.append({
                                        "title": chunk.web.title,
                                        "url": chunk.web.uri,
                                    })

            return {
                "query": query,
                "summary": text,
                "sources": sources,
                "structured_data": structured_data,
            }

        except Exception as e:
            logger.error(f"ResearchAgent.search error: {e}")
            return {"error": str(e), "query": query}

    async def extract_from_page(self, url: str, what_to_extract: str) -> dict[str, Any]:
        """Fetch a URL and extract specific information."""
        try:
            resp = await self._http.get(url, follow_redirects=True)
            resp.raise_for_status()
            # Take first 8000 chars of text content
            content = resp.text[:8000]
        except Exception as e:
            return {"error": f"Failed to fetch {url}: {e}"}

        if not self._client:
            return {"error": "Gemini client not available"}

        try:
            prompt = f"""
Extract the following from this web page content:
{what_to_extract}

Page content:
{content}

Output the extracted information as JSON.
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            import json, re
            json_match = re.search(r"```json\s*(.*?)\s*```", response.text or "", re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return {"extracted": response.text, "url": url}
        except Exception as e:
            return {"error": str(e), "url": url}

    async def parallel_research(self, queries: list[str]) -> list[dict[str, Any]]:
        """Run multiple searches concurrently."""
        return await asyncio.gather(*[self.search(q) for q in queries])

    async def close(self) -> None:
        await self._http.aclose()
