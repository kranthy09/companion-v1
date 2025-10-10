# ============================================================
# project/blog/agent_service.py
# ============================================================
"""Blog AI agent service"""

import logging
from typing import AsyncGenerator, Dict

from project.ollama.service import ollama_service

logger = logging.getLogger(__name__)


class BlogAgentService:
    """AI agents for blog operations"""

    def __init__(self):
        self.model = "gemma2:2b"

    async def generate_with_main_section(
        self, title: str, content: str
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Generate heading, description, and main section"""
        try:
            # Heading
            yield {"type": "start", "stage": "heading"}
            heading_prompt = f"""
            Generate TItle for a blog post
            with the help of Title: {title}
            Content: {content[:500]}
            Provide Heading only, No reason needed or no introduction Needed,
            straight forward content.
            Heading:
            """

            heading = ""
            async for chunk in ollama_service.stream_generate(
                prompt=heading_prompt, temperature=0.7, max_tokens=50
            ):
                if chunk.get("done"):
                    break
                text = chunk.get("response", "")
                heading += text
                yield {"type": "heading_chunk", "content": text}

            heading = heading.strip()[:100]
            yield {"type": "heading_done", "heading": heading}

            # Description
            yield {"type": "start", "stage": "description"}
            desc_prompt = f"""
            Generate description for blog contains:
            Title: {title}
            Content: {content[:800]}
            Provide Description only, No reason needed,
            straight forward content.
            Description:
            """

            description = ""
            async for chunk in ollama_service.stream_generate(
                prompt=desc_prompt, temperature=0.7, max_tokens=100
            ):
                if chunk.get("done"):
                    break
                text = chunk.get("response", "")
                description += text
                yield {"type": "description_chunk", "content": text}

            description = description.strip()[:160]
            yield {"type": "description_done", "description": description}

            # Main Section
            yield {"type": "start", "stage": "main"}
            main_prompt = f"""
            Enhance this blog with:
            - 3-4 structured sections with headings
            - Practical examples
            - Actionable conclusion

            Title: {title}
            Content: {content}

            Enhanced Blog:
            """

            main_content = ""
            async for chunk in ollama_service.stream_generate(
                prompt=main_prompt, temperature=0.8, max_tokens=2000
            ):
                if chunk.get("done"):
                    break
                text = chunk.get("response", "")
                main_content += text
                yield {"type": "main_chunk", "content": text}

            yield {"type": "main_done", "content": main_content}
            yield {
                "type": "complete",
                "heading": heading,
                "description": description,
                "main": main_content,
            }
        except Exception as e:
            yield {"type": "error", "message": str(e)}


blog_agent = BlogAgentService()
