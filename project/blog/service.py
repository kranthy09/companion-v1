"""Production-optimized Blog Service with maximum performance"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from sqlalchemy import select, func, and_, or_, case, exists
from sqlalchemy.orm import Session, selectinload, load_only
from slugify import slugify

from project.blog.models import BlogPost, BlogSection
from project.blog.parser import BlogContentParser

logger = logging.getLogger(__name__)


class BlogService:
    """High-performance blog service with optimized queries"""

    def __init__(self, db: Session):
        self.db = db
        self.db.expire_on_commit = False
        self.parser = BlogContentParser()

    # ==================== CREATE ====================

    def create_initial_post(
        self, user_id: int, title: str, original_content: str
    ) -> BlogPost:
        """Create post efficiently"""
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
            self.db.flush()
            self.db.refresh(post)
            self.db.commit()

            return post

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create post: {e}")
            raise

    def save_generated_content(
        self, post_id: int, generated_text: str
    ) -> None:
        """Save content with bulk section insert"""
        try:
            # Get post
            post = self.db.scalar(
                select(BlogPost).where(BlogPost.id == post_id)
            )

            if not post:
                raise ValueError("Post not found")

            # Parse content
            parsed = BlogContentParser.parse(generated_text)

            # Update post
            post.title = parsed["title"] or post.title
            post.excerpt = parsed["excerpt"]
            post.content = generated_text

            # Bulk insert sections
            sections = [
                BlogSection(
                    post_id=post.id,
                    title=section_data["title"],
                    content=section_data["content"],
                    section_type=section_data["type"],
                    order=idx,
                    meta_info={},
                )
                for idx, section_data in enumerate(parsed["sections"])
            ]

            if sections:
                self.db.bulk_save_objects(sections)

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save content: {e}")
            raise

    # ==================== READ ====================

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
        """Optimized list with window function for count"""

        # Base query with selective loading
        query = (
            select(BlogPost)
            .where(BlogPost.author_id == user_id)
            .options(
                load_only(
                    BlogPost.id,
                    BlogPost.title,
                    BlogPost.slug,
                    BlogPost.excerpt,
                    BlogPost.status,
                    BlogPost.generation_status,
                    BlogPost.created_at,
                    BlogPost.updated_at,
                    BlogPost.read_time_minutes,
                    BlogPost.view_count,
                )
            )
        )

        # Apply filters
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    BlogPost.title.ilike(search_pattern),
                    BlogPost.content.ilike(search_pattern),
                    BlogPost.excerpt.ilike(search_pattern),
                )
            )

        if status:
            query = query.where(BlogPost.status == status)

        # Get total count efficiently
        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query)

        # Apply sorting
        sort_col = getattr(BlogPost, sort_by, BlogPost.updated_at)
        query = query.order_by(
            sort_col.desc() if sort_order == "desc" else sort_col.asc()
        )

        # Paginate
        offset = (page - 1) * page_size
        posts = list(self.db.scalars(query.offset(offset).limit(page_size)))

        return {
            "posts": posts,
            "total_count": total,
            "page": page,
            "page_size": page_size,
        }

    def get_post_by_id(
        self, post_id: int, user_id: int, load_sections: bool = True
    ) -> Optional[BlogPost]:
        """Get post with optional section loading"""
        query = select(BlogPost).where(
            and_(BlogPost.id == post_id, BlogPost.author_id == user_id)
        )

        if load_sections:
            query = query.options(
                selectinload(BlogPost.sections).load_only(
                    BlogSection.id,
                    BlogSection.title,
                    BlogSection.content,
                    BlogSection.section_type,
                    BlogSection.order,
                )
            )

        return self.db.scalars(query).first()

    # ==================== STATISTICS ====================

    def count_user_posts(self, user_id: int) -> int:
        """Fast count query"""
        return self.db.scalar(
            select(func.count(BlogPost.id)).where(
                BlogPost.author_id == user_id
            )
        )

    def count_by_status(self, user_id: int, status: str) -> int:
        """Count posts by status"""
        return self.db.scalar(
            select(func.count(BlogPost.id)).where(
                and_(BlogPost.author_id == user_id, BlogPost.status == status)
            )
        )

    def get_blog_stats(self, user_id: int) -> Dict[str, Any]:
        """Get all stats in single query"""
        result = self.db.execute(
            select(
                func.count(BlogPost.id).label("total"),
                func.count(case((BlogPost.status == "draft", 1))).label(
                    "draft"
                ),
                func.count(case((BlogPost.status == "published", 1))).label(
                    "published"
                ),
                func.count(case((BlogPost.status == "archived", 1))).label(
                    "archived"
                ),
                func.coalesce(func.sum(BlogPost.view_count), 0).label(
                    "total_views"
                ),
                func.coalesce(func.avg(BlogPost.read_time_minutes), 0).label(
                    "avg_read_time"
                ),
            ).where(BlogPost.author_id == user_id)
        ).first()

        return {
            "total_posts": result.total or 0,
            "draft": result.draft or 0,
            "published": result.published or 0,
            "archived": result.archived or 0,
            "total_views": result.total_views or 0,
            "avg_read_time": round(result.avg_read_time or 0, 1),
        }

    # ==================== UPDATE ====================

    def mark_complete(self, post_id: int, user_id: int) -> BlogPost:
        """Mark complete with optimized update"""
        post = self.get_post_by_id(post_id, user_id, load_sections=True)

        if not post:
            raise ValueError("Post not found")

        post.generation_status = "complete"
        post.read_time_minutes = self._calculate_read_time(post.content)

        self.db.commit()
        self.db.refresh(post)

        return post

    def mark_failed(self, post_id: int) -> None:
        """Mark failed with direct update"""
        stmt = (
            BlogPost.__table__.update()
            .where(BlogPost.id == post_id)
            .values(generation_status="failed")
        )

        self.db.execute(stmt)
        self.db.commit()

    def update_post(
        self, post_id: int, user_id: int, data: Dict[str, Any]
    ) -> BlogPost:
        """Optimized update"""
        # Filter valid fields
        update_data = {
            k: v
            for k, v in data.items()
            if hasattr(BlogPost, k) and v is not None
        }

        if not update_data:
            return self.get_post_by_id(post_id, user_id)

        update_data["updated_at"] = datetime.now(timezone.utc)

        # Execute update
        stmt = (
            BlogPost.__table__.update()
            .where(and_(BlogPost.id == post_id, BlogPost.author_id == user_id))
            .values(**update_data)
        )

        result = self.db.execute(stmt)

        if result.rowcount == 0:
            raise ValueError("Post not found")

        self.db.commit()

        return self.get_post_by_id(post_id, user_id)

    def increment_view_count(self, post_id: int) -> None:
        """Atomic view count increment"""
        stmt = (
            BlogPost.__table__.update()
            .where(BlogPost.id == post_id)
            .values(view_count=BlogPost.view_count + 1)
        )

        self.db.execute(stmt)
        self.db.commit()

    # ==================== DELETE ====================

    def delete_post(self, post_id: int, user_id: int) -> None:
        """Delete with cascade"""
        stmt = BlogPost.__table__.delete().where(
            and_(BlogPost.id == post_id, BlogPost.author_id == user_id)
        )

        result = self.db.execute(stmt)

        if result.rowcount == 0:
            raise ValueError("Post not found")

        self.db.commit()

    def delete_posts_batch(self, post_ids: List[int], user_id: int) -> int:
        """Bulk delete"""
        stmt = BlogPost.__table__.delete().where(
            and_(BlogPost.id.in_(post_ids), BlogPost.author_id == user_id)
        )

        result = self.db.execute(stmt)
        self.db.commit()

        return result.rowcount

    # ==================== UTILITY ====================

    def _generate_slug(self, title: str) -> str:
        """Generate unique slug efficiently"""
        base_slug = slugify(title)

        # Check if base slug is available
        exists_query = select(exists().where(BlogPost.slug == base_slug))

        if not self.db.scalar(exists_query):
            return base_slug

        # Find next available slug with counter
        max_counter = self.db.scalar(
            select(
                func.coalesce(
                    func.max(
                        func.cast(
                            func.split_part(BlogPost.slug, "-", -1),
                            type_=func.INTEGER,
                        )
                    ),
                    0,
                )
            ).where(BlogPost.slug.like(f"{base_slug}-%"))
        )

        return f"{base_slug}-{max_counter + 1}"

    def _calculate_read_time(self, content: str) -> int:
        """Calculate read time (200 words/min)"""
        if not content:
            return 1

        words = len(content.split())
        return max(1, words // 200)

    def post_exists(self, post_id: int, user_id: int) -> bool:
        """Fast existence check"""
        return self.db.scalar(
            select(
                exists().where(
                    and_(BlogPost.id == post_id, BlogPost.author_id == user_id)
                )
            )
        )

    def get_recent_posts(self, user_id: int, limit: int = 5) -> List[BlogPost]:
        """Get recent posts efficiently"""
        return list(
            self.db.scalars(
                select(BlogPost)
                .where(BlogPost.author_id == user_id)
                .options(
                    load_only(BlogPost.id, BlogPost.title, BlogPost.created_at)
                )
                .order_by(BlogPost.created_at.desc())
                .limit(limit)
            )
        )
