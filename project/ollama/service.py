"""
project/ollama/service.py

Generic Ollama service for background processing tasks
"""

import httpx
import logging
from typing import Dict, Optional, AsyncGenerator
from project.config import settings

logger = logging.getLogger(__name__)


class OllamaService:
    """Generic Ollama LLM service for any task"""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = 300.0

    async def health_check(self) -> bool:
        """Check Ollama availability"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Generate text from prompt (non-streaming)

        Args:
            prompt: Input prompt
            model: Model name (defaults to configured model)
            temperature: Generation temperature (0.0-1.0)
            max_tokens: Max tokens to generate

        Returns:
            Dict with 'response' key containing generated text
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ollama generate failed: {e}")
            raise

    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate text with streaming (for SSE)

        Args:
            prompt: Input prompt
            model: Model name
            temperature: Generation temperature
            max_tokens: Max tokens to generate

        Yields:
            Dict chunks with 'response' and 'done' keys
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", url, json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.strip():
                            import json

                            yield json.loads(line)
        except Exception as e:
            logger.error(f"Ollama stream failed: {e}")
            raise


ollama_service = OllamaService()
