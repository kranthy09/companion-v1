# project/blog/service.py
import logging
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
from slugify import slugify

from project.blog.models import BlogPost, BlogSection
from project.blog.parser import BlogContentParser

logger = logging.getLogger(__name__)


class BlogService:
    def __init__(self, db: Session):
        self.db = db
        self.parser = BlogContentParser()

    def create_initial_post(
        self, user_id: int, title: str, original_content: str
    ) -> BlogPost:
        """Create empty post before streaming"""
        try:
            post = BlogPost(
                author_id=user_id,
                title=title,
                slug=self._generate_slug(title),
                excerpt=None,
                content="",
                status="draft",
                generation_status="generating",
                is_featured=False,
                is_commentable=True,
                view_count=0,
                read_time_minutes=0,
                raw_response={"original_prompt": original_content},
                tags=[],
                meta_keywords=[],
            )

            self.db.add(post)
            self.db.commit()
            self.db.refresh(post)
            return post
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create initial post: {e}")
            raise

    def save_generated_content(
        self, post_id: int, generated_text: str
    ) -> None:
        """Save generated text and parse into sections"""
        try:
            post = (
                self.db.query(BlogPost).filter(BlogPost.id == post_id).first()
            )
            if not post:
                raise ValueError("Post not found")

            # Parse sections
            parsed_sections = self.parser.parse(generated_text)
            excerpt = self.parser.extract_excerpt(generated_text)
            word_count = len(generated_text.split())
            read_time = max(1, word_count // 200)

            # Update post
            post.content = generated_text
            post.excerpt = excerpt
            post.read_time_minutes = read_time

            # Create sections
            for idx, section_data in enumerate(parsed_sections):
                section = BlogSection(
                    post_id=post.id,
                    title=section_data["title"],
                    content=section_data["content"],
                    section_type=section_data["type"],
                    order=idx,
                    meta_info={},
                )
                self.db.add(section)

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save content: {e}")
            raise

    def mark_complete(self, post_id: int, user_id: int) -> BlogPost:
        """Mark generation as complete"""
        # Fetch post with sections eagerly loaded
        post = (
            self.db.query(BlogPost)
            .options(joinedload(BlogPost.sections))
            .filter(
                BlogPost.id == post_id,
                BlogPost.author_id == user_id,
            )
            .first()
        )
        if not post:
            raise ValueError("Post not found")

        if post.author_id != user_id:
            raise ValueError("Not authorized")

        post.generation_status = "complete"
        post.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(post)
        return post

    def mark_failed(self, post_id: int) -> None:
        """Mark generation as failed"""
        try:
            post = (
                self.db.query(BlogPost).filter(BlogPost.id == post_id).first()
            )
            if post:
                post.generation_status = "failed"
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to mark as failed: {e}")

    def publish_post(self, post_id: int, user_id: int) -> BlogPost:
        """Publish post"""
        post = self.get_post_by_id(post_id)

        if not post:
            raise ValueError("Post not found")

        if post.author_id != user_id:
            raise ValueError("Not authorized")

        post.status = "published"
        post.published_at = datetime.now(timezone.utc)
        post.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(post)
        return post

    def get_post_by_id(
        self, post_id: int, increment_view: bool = False
    ) -> Optional[BlogPost]:
        """Fetch post with sections"""
        post = (
            self.db.query(BlogPost)
            .options(
                joinedload(BlogPost.author),
                joinedload(BlogPost.sections),
            )
            .filter(BlogPost.id == post_id)
            .first()
        )

        if post and increment_view:
            post.view_count += 1
            self.db.commit()

        return post

    def update_post(self, post_id: int, user_id: int, **updates) -> BlogPost:
        """Update post fields"""
        post = self.get_post_by_id(post_id)

        if not post:
            raise ValueError("Post not found")

        if post.author_id != user_id:
            raise ValueError("Not authorized")

        for key, value in updates.items():
            if hasattr(post, key) and value is not None:
                setattr(post, key, value)

        post.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete_post(self, post_id: int, user_id: int) -> None:
        """Delete post and sections"""
        post = self.get_post_by_id(post_id)

        if not post:
            raise ValueError("Post not found")

        if post.author_id != user_id:
            raise ValueError("Not authorized")

        self.db.delete(post)
        self.db.commit()

    def _generate_slug(self, title: str) -> str:
        """Generate unique slug"""
        base_slug = slugify(title)
        slug = base_slug
        counter = 1

        while self.db.query(BlogPost).filter(BlogPost.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug
