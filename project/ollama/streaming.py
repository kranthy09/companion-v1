"""
project/ollama/streaming.py

Updated OllamaStreamingService with blog streaming method
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
            "stream": True,
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

    async def stream_content(
        self, title: str, content: str, enhancement_type: str = "summary"
    ) -> AsyncGenerator[str, None]:
        """Stream note enhancement"""
        prompts = {
            "summary": f"""Create insightful summary with key takeaways.
                Title: {title}
                Context: {content}

                Provide:
                1. Executive summary (3-5 sentences)
                2. Top 3 key insights
                3. Main conclusion
            Summary:""",
            "improve": f"""Improve and expand:
Title: {title}
Content:
{content}

Enhanced:""",
        }

        prompt = prompts.get(enhancement_type, prompts["summary"])

        async for chunk in self.stream_generate(prompt):
            yield chunk

    async def stream_blog_content(
        self, title: str, content: str, enhancement_type: str = "improve"
    ) -> AsyncGenerator[str, None]:
        """
        Stream blog content enhancement

        Args:
            title: Blog post title
            content: Blog post content
            enhancement_type: improve, expand, or summarize
        """
        prompts = {
            "improve": f"""Improve this blog post for better quality,
            clarity, and engagement.
Maintain the core message but enhance writing style,
 fix grammar, and make it compelling.

Title: {title}

Current Content:
{content}

Divide the content into 7 Sections
1. Title, description
2. Introduction
3. Heading, Content Section
4. Heading, Content Section
5. Heading, Content Section
6. Heading, Conclusion
7. Next Steps:
Be professional.
Improved Version:
""",

            "expand": f"""Expand this blog post with more depth,
              examples, and insights.
Add relevant details, statistics, and real-world
 applications while maintaining flow.

Title: {title}

Current Content:
{content}

Expanded Version:""",

            "summarize": f"""Create a concise summary of this blog
              post highlighting key points.

Title: {title}

Content:
{content}

Summary:
- Key Points (bullet format)
- Main Takeaway
- Action Items""",
        }

        prompt = prompts.get(enhancement_type, prompts["improve"])

        async for chunk in self.stream_generate(prompt):
            yield chunk


streaming_service = OllamaStreamingService()
