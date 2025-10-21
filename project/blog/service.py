# project/blog/service.py
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
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
                self.db.query(BlogPost)
                .filter(BlogPost.id == post_id)
                .first()
            )
            if not post:
                raise ValueError("Post not found")

            parsed = BlogContentParser.parse(generated_text)
            post.title = parsed["title"] or post.title
            post.excerpt = parsed["excerpt"]
            post.content = generated_text

            for idx, section_data in enumerate(parsed["sections"]):
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
            self.db.refresh(post)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save content: {e}")
            raise

    def mark_complete(self, post_id: int, user_id: int) -> BlogPost:
        """Mark generation as complete"""
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

        post.generation_status = "complete"
        post.read_time_minutes = self._calculate_read_time(post.content)
        self.db.commit()
        self.db.refresh(post)
        return post

    def mark_failed(self, post_id: int) -> None:
        """Mark generation as failed"""
        post = self.db.query(BlogPost).filter(
            BlogPost.id == post_id
        ).first()
        if post:
            post.generation_status = "failed"
            self.db.commit()

    def list_posts(
        self,
        user_id: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """List posts with filtering, pagination, and sorting"""
        query = self.db.query(BlogPost).filter(
            BlogPost.author_id == user_id
        )

        if search:
            search_filter = or_(
                BlogPost.title.ilike(f"%{search}%"),
                BlogPost.content.ilike(f"%{search}%"),
                BlogPost.excerpt.ilike(f"%{search}%"),
            )
            query = query.filter(search_filter)

        if status:
            query = query.filter(BlogPost.status == status)

        total = query.count()

        sort_col = getattr(BlogPost, sort_by, BlogPost.updated_at)
        if sort_order == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        offset = (page - 1) * page_size
        posts = query.offset(offset).limit(page_size).all()

        return {
            "posts": posts,
            "total_count": total,
            "page": page,
            "page_size": page_size,
        }

    def get_post_by_id(
        self, post_id: int, user_id: int
    ) -> Optional[BlogPost]:
        """Get single post with sections"""
        return (
            self.db.query(BlogPost)
            .options(joinedload(BlogPost.sections))
            .filter(
                BlogPost.id == post_id,
                BlogPost.author_id == user_id,
            )
            .first()
        )

    def update_post(
        self, post_id: int, user_id: int, data: Dict[str, Any]
    ) -> BlogPost:
        """Update post"""
        post = self.get_post_by_id(post_id, user_id)
        if not post:
            raise ValueError("Post not found")

        for key, value in data.items():
            if hasattr(post, key) and value is not None:
                setattr(post, key, value)

        post.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete_post(self, post_id: int, user_id: int) -> None:
        """Delete post"""
        post = self.get_post_by_id(post_id, user_id)
        if not post:
            raise ValueError("Post not found")

        self.db.delete(post)
        self.db.commit()

    def _generate_slug(self, title: str) -> str:
        """Generate unique slug from title"""
        base_slug = slugify(title)
        slug = base_slug
        counter = 1

        while (
            self.db.query(BlogPost)
            .filter(BlogPost.slug == slug)
            .first()
        ):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def _calculate_read_time(self, content: str) -> int:
        """Calculate estimated read time in minutes"""
        words = len(content.split())
        return max(1, words // 200)
