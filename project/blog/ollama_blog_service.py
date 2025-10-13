# project/blog/ollama_blog_service.py
import logging
from typing import AsyncGenerator
from project.ollama.service import ollama_service

logger = logging.getLogger(__name__)


class OllamaBlogGenerator:
    """Stream raw blog content without structure"""

    def __init__(self):
        self.service = ollama_service

    async def generate_stream(
        self, title: str, content: str
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks as they arrive"""
        prompt = f"""Write a comprehensive blog post about:

Title: {title}
Topic: {content}

Write naturally with:
- Engaging introduction
- Multiple detailed sections with clear headings (use ## for headings)
- Practical examples and insights
- Strong conclusion

Use markdown formatting. Start writing:"""

        try:
            async for chunk in self.service.stream_generate(
                prompt=prompt,
                temperature=0.7,
                max_tokens=2000
            ):
                if not chunk.get("done", False):
                    text = chunk.get("response", "")
                    if text:
                        yield text
        except Exception as e:
            logger.error(f"Stream generation error: {e}")
            raise


ollama_blog_generator = OllamaBlogGenerator()
