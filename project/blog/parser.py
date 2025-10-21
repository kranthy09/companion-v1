"""
project/blog/parser.py

Minimalistic blog markdown parser with clean section extraction.
"""
import re
from typing import Dict, List, Optional


class BlogContentParser:
    """Parse markdown blog content into structured sections."""

    HEADER_RE = re.compile(r"^(#+)\s+(.+)$", re.MULTILINE)

    @staticmethod
    def parse(content: str) -> Dict[str, Optional[str]]:
        """
        Parse markdown content into title, excerpt, and sections.

        Returns:
            {
                "title": str | None,
                "excerpt": str,
                "sections": [
                    {
                        "title": str | None,
                        "content": str,
                        "type": "text"
                    }
                ]
            }
        """
        if not content or not content.strip():
            return {"title": None, "excerpt": "", "sections": []}

        lines = content.strip().split("\n")

        # Extract main title (first ## or # heading)
        title = BlogContentParser._extract_title(lines)

        # Parse all sections
        sections = BlogContentParser._parse_sections(content)

        # Extract excerpt from first paragraph
        excerpt = BlogContentParser._extract_excerpt(content)

        return {"title": title, "excerpt": excerpt, "sections": sections}

    @staticmethod
    def _extract_title(lines: List[str]) -> Optional[str]:
        """Extract the first heading as the main title."""
        for line in lines:
            if line.strip().startswith("#"):
                return re.sub(r"^#+\s*", "", line).strip()
        return None

    @staticmethod
    def _parse_sections(content: str) -> List[Dict[str, Optional[str]]]:
        """
        Split content by headers and create sections.
        Each section includes everything until the next header.
        """
        sections: List[Dict[str, Optional[str]]] = []

        # Split by headers while preserving them
        parts = BlogContentParser.HEADER_RE.split(content)

        # First part (before any header) is intro if exists
        intro = parts[0].strip()
        if intro:
            sections.append({
                "title": None,
                "content": intro,
                "type": "text"
            })

        # Process header + content pairs
        i = 1
        while i < len(parts):
            if i + 2 <= len(parts):
                # parts[i] = header level (e.g., "##")
                # parts[i+1] = header text
                # parts[i+2] = content until next header
                header_text = parts[i + 1].strip()
                section_content = parts[i + 2].strip()

                if section_content:  # Only add if content exists
                    sections.append({
                        "title": header_text,
                        "content": section_content,
                        "type": "text"
                    })

                i += 3
            else:
                break

        return sections

    @staticmethod
    def _extract_excerpt(content: str, max_len: int = 250) -> str:
        """Extract first paragraph as excerpt."""
        # Remove all headers
        clean = re.sub(r"^#+\s+.+$", "", content, flags=re.MULTILINE)

        # Get first non-empty paragraph
        paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]

        if not paragraphs:
            return ""

        excerpt = paragraphs[0]

        # Truncate if too long
        if len(excerpt) > max_len:
            excerpt = excerpt[:max_len].rsplit(" ", 1)[0] + "..."

        return excerpt
