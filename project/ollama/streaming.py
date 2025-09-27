"""
companion/project/ollama/streaming.py

SSE streaming for Ollama responses
"""

import httpx
import json
import logging
from typing import AsyncGenerator
from project.config import settings

logger = logging.getLogger(__name__)


class OllamaStreamingService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = 300.0

    async def stream_generate(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream text generation chunk by chunk"""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,  # Enable streaming
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", url, json=payload
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                yield chunk["response"]
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"[Error: {str(e)}]"

    async def stream_enhance_note(
        self, title: str, content: str, enhancement_type: str = "summary"
    ) -> AsyncGenerator[str, None]:
        """Stream note enhancement"""
        prompts = {
            "summary": f"""Summarize in 2-3 sentences:\n\nTitle:
            {title}\n\nContent:\n{content}\n\nSummary:""",
            "improve": f"""Improve and expand:\n\nTitle:
            {title}\n\nContent:\n{content}\n\nEnhanced:""",
        }

        prompt = prompts.get(enhancement_type, prompts["summary"])

        async for chunk in self.stream_generate(prompt):
            yield chunk


streaming_service = OllamaStreamingService()
