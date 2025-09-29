"""
companion/project/ollama/service.py

Ollama service with improved prompts and error handling
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
        self.max_content_length = 50000  # 50k char limit
        self.max_title_length = 500

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
        """Enhance note content with validation"""

        # Input validation
        if not title or not content:
            return {
                "enhanced_content": "",
                "success": False,
                "error": "Title and content are required",
            }

        if len(title) > self.max_title_length:
            return {
                "enhanced_content": "",
                "success": False,
                "error": f"Title exceeds {self.max_title_length} characters",
            }

        if len(content) > self.max_content_length:
            return {
                "enhanced_content": "",
                "success": False,
                "error": f"Content exceeds \
                    {self.max_content_length} characters",
            }

        # Sanitize inputs
        title = title.strip()
        content = content.strip()

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
            "outline": f"""Create a structured outline from this note:

Title: {title}

Content:
{content}

Outline:""",
            "key_points": f"""Extract the key points from this note:

Title: {title}

Content:
{content}

Key Points:""",
        }

        prompt = prompts.get(enhancement_type, prompts["summary"])

        try:
            # Check Ollama availability first
            if not await self.health_check():
                return {
                    "enhanced_content": "",
                    "success": False,
                    "error": "Ollama service is currently unavailable",
                }

            result = await self.generate(prompt)

            # Validate response
            enhanced_content = result.get("response", "").strip()

            if not enhanced_content:
                return {
                    "enhanced_content": "",
                    "success": False,
                    "error": "No content generated",
                }

            # Log success metrics
            logger.info(
                f"Successfully enhanced note: type={enhancement_type}, "
                f"original_length={len(content)}, "
                f"enhanced_length={len(enhanced_content)}"
            )

            return {
                "enhanced_content": enhanced_content,
                "success": True,
                "metadata": {
                    "type": enhancement_type,
                    "original_length": len(content),
                    "enhanced_length": len(enhanced_content),
                    "compression_ratio": round(
                        len(enhanced_content) / len(content), 2
                    ),
                },
            }

        except httpx.TimeoutException:
            logger.error(
                f"Ollama \
                      request timeout for enhancement type: {enhancement_type}"
            )
            return {
                "enhanced_content": "",
                "success": False,
                "error": "Request timeout - content may be too long",
            }
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Ollama HTTP \
                    error: {e.response.status_code} - {e.response.text}"
            )
            return {
                "enhanced_content": "",
                "success": False,
                "error": f"Service error: {e.response.status_code}",
            }
        except Exception as e:
            logger.error(f"Enhancement failed: {e}")
            return {
                "enhanced_content": "",
                "success": False,
                "error": f"Enhancement failed: {str(e)}",
            }


ollama_service = OllamaService()
