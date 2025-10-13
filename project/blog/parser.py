# project/blog/parser.py
import re
from typing import List, Dict


class BlogContentParser:
    """Parse raw markdown blog into structured sections"""

    @staticmethod
    def parse(content: str) -> List[Dict[str, str]]:
        """
        Split content into sections based on markdown headers
        Returns: [{"title": "...", "content": "...", "type": "..."}]
        """
        sections = []
        lines = content.strip().split("\n")

        current_section = {
            "title": None,
            "content": [],
            "type": "introduction",
        }
        section_count = 0

        for line in lines:
            # Check for ## headers
            header_match = re.match(r"^##\s+(.+)$", line.strip())

            if header_match:
                # Save previous section
                if current_section["content"]:
                    sections.append(
                        {
                            "title": current_section["title"],
                            "content": "\n".join(
                                current_section["content"]
                            ).strip(),
                            "type": current_section["type"],
                        }
                    )

                # Start new section
                section_count += 1
                current_section = {
                    "title": header_match.group(1),
                    "content": [],
                    "type": "body",
                }
            else:
                current_section["content"].append(line)

        # Save final section
        if current_section["content"]:
            content_text = "\n".join(current_section["content"]).strip()
            if content_text:
                # Mark last section as conclusion if it's substantial
                if section_count > 0 and len(content_text) > 100:
                    current_section["type"] = "conclusion"

                sections.append(
                    {
                        "title": current_section["title"],
                        "content": content_text,
                        "type": current_section["type"],
                    }
                )

        # Ensure we have at least introduction
        if not sections:
            sections.append(
                {
                    "title": None,
                    "content": content.strip(),
                    "type": "introduction",
                }
            )

        return sections

    @staticmethod
    def extract_excerpt(content: str, max_length: int = 200) -> str:
        """Extract first paragraph as excerpt"""
        # Remove markdown headers
        clean = re.sub(r"^#+\s+", "", content, flags=re.MULTILINE)
        # Get first paragraph
        paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
        if paragraphs:
            excerpt = paragraphs[0]
            if len(excerpt) > max_length:
                excerpt = excerpt[:max_length].rsplit(" ", 1)[0] + "..."
            return excerpt
        return content[:max_length] + "..."
