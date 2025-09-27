"""
companion/project/ollama/service.py

Ollama service with improved prompts
"""

import httpx
import logging
from typing import Dict
from project.config import settings

logger = logging.getLogger(__name__)


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = 300.0

    async def health_check(self) -> bool:
        """Check if Ollama is available"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def generate(self, prompt: str) -> Dict:
        """Generate text from prompt"""
        url = f"{self.base_url}/api/generate"

        payload = {"model": self.model, "prompt": prompt, "stream": False}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def enhance_note(
        self, title: str, content: str, enhancement_type: str = "summary"
    ) -> Dict:
        """Enhance note content"""
        prompts = {
            "summary": f"""Create a concise 2-3 sentence summary of this note:

Title: {title}

Content:
{content}

Summary:""",
            "improve": f"""Improve and expand this note
              with better writing quality, more details, and clarity:

Title: {title}

Original Content:
{content}

Enhanced Version:""",
        }

        prompt = prompts.get(enhancement_type, prompts["summary"])

        try:
            result = await self.generate(prompt)
            return {
                "enhanced_content": result.get("response", "").strip(),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Enhancement failed: {e}")
            return {"enhanced_content": "", "success": False, "error": str(e)}


ollama_service = OllamaService()
