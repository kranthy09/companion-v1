# project/blog/parser.py
import re
from typing import List, Dict, Optional


class BlogContentParser:
    """
    Advanced blog markdown parser.
    Parses AI-generated blog content into structured sections:
    title, excerpt, introduction, body sections, insights, and conclusion.
    """

    HEADER_RE = re.compile(r"^(#+)\s+(.+)$")
    PRACTICAL_RE = re.compile(r"^\*\*Practical\s+(.+?):\*\*", re.IGNORECASE)
    BULLET_RE = re.compile(r"^\s*[\*\-]\s+")

    @staticmethod
    def parse(content: str) -> Dict[str, Optional[str]]:
        """
        Parse the markdown blog content into a structured dictionary.
        Returns:
        {
          "title": str,
          "excerpt": str,
          "sections": [ {"title": str, "content": str, "type": str}, ... ]
        }
        """
        lines = [line.rstrip() for line in content.strip().split("\n")]
        if not lines:
            return {"title": None, "excerpt": "", "sections": []}

        # 1️⃣ Extract top-level title (## or #)
        title = None
        if lines and lines[0].startswith("##"):
            title = re.sub(r"^##+\s*", "", lines[0]).strip()
            lines = lines[1:]

        sections: List[Dict[str, str]] = []
        current = {"title": None, "content": [], "type": "introduction"}
        section_count = 0

        for line in lines:
            # --- Detect headers ---
            header_match = BlogContentParser.HEADER_RE.match(line)
            if header_match:
                level, header_text = header_match.groups()
                level = len(level)

                # Save previous section
                BlogContentParser._save_section(current, sections)

                # Determine type
                section_type = "body"
                if re.search(r"conclusion", header_text, re.IGNORECASE):
                    section_type = "conclusion"
                elif section_count == 0:
                    section_type = "introduction"

                section_count += 1
                current = {
                    "title": header_text.strip(),
                    "content": [],
                    "type": section_type,
                }
                continue

            # --- Detect practical insights ---
            if BlogContentParser.PRACTICAL_RE.match(line):
                BlogContentParser._save_section(current, sections)
                title_text = BlogContentParser.PRACTICAL_RE.match(
                    line).group(1)
                current = {
                    "title": f"Practical {title_text.title()}",
                    "content": [],
                    "type": "insight",
                }
                continue

            # --- Detect bullet lists ---
            if BlogContentParser.BULLET_RE.match(line):
                if current["type"] not in ("insight", "list"):
                    BlogContentParser._save_section(current, sections)
                    current = {
                        "title": current.get("title") or "Key Insights",
                        "content": [],
                        "type": "insight",
                    }

            current["content"].append(line)

        # Save the final section
        BlogContentParser._save_section(current, sections)

        # 2️⃣ Extract excerpt (first paragraph after title)
        excerpt = BlogContentParser.extract_excerpt(content)

        return {"title": title, "excerpt": excerpt, "sections": sections}

    # ---------------------------------------------------------------------
    @staticmethod
    def _save_section(current: Dict[str, any], sections: List[Dict[str, str]]):
        """Utility to finalize and store a section."""
        text = "\n".join(current.get("content", [])).strip()
        if not text:
            return
        sections.append(
            {
                "title": current.get("title"),
                "content": text,
                "type": current.get("type", "body"),
            }
        )

    # ---------------------------------------------------------------------
    @staticmethod
    def extract_excerpt(content: str, max_length: int = 250) -> str:
        """Extract the first readable paragraph as an excerpt."""
        clean = re.sub(r"^#+\s+", "", content, flags=re.MULTILINE)
        paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
        if not paragraphs:
            return ""
        excerpt = paragraphs[0]
        if len(excerpt) > max_length:
            excerpt = excerpt[:max_length].rsplit(" ", 1)[0] + "..."
        return excerpt
