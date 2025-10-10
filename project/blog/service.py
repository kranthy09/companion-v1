"""
project/blog/service.py

Blog service layer with business logic
"""

import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc, func
from datetime import datetime, timezone

from project.blog.models import (
    BlogPost,
    BlogCategory,
    BlogComment,
    BlogSection,
)
from project.blog.schemas import (
    BlogPostCreate,
    BlogPostUpdate,
    BlogQueryParams,
    BlogStatus,
)
from uuid import UUID

logger = logging.getLogger(__name__)


class BlogService:
    """Service class for blog operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_post(
        self, user_id: UUID, post_data: BlogPostCreate
    ) -> BlogPost:
        """Create a new blog post with sections"""
        try:
            # Calculate read time
            word_count = len(post_data.content.split())
            read_time = max(1, word_count // 200)

            # Create post
            post = BlogPost(
                author_id=user_id,
                title=post_data.title,
                slug=post_data.slug or self._generate_slug(post_data.title),
                excerpt=post_data.excerpt,
                content=post_data.content,
                featured_image=post_data.featured_image,
                category_id=post_data.category_id,
                tags=post_data.tags,
                meta_description=post_data.meta_description,
                meta_keywords=post_data.meta_keywords,
                status=post_data.status,
                is_featured=post_data.is_featured,
                is_commentable=post_data.is_commentable,
                read_time_minutes=read_time,
            )

            # Set published_at if publishing
            post_data.status = BlogStatus.PUBLISHED
            post.published_at = datetime.now(timezone.utc)

            self.db.add(post)
            self.db.flush()  # Get post ID before adding sections

            # Add sections if provided
            if post_data.sections:
                for idx, section_data in enumerate(post_data.sections):
                    section = BlogSection(
                        post_id=post.id,
                        title=section_data.title,
                        content=section_data.content,
                        section_type=section_data.section_type,
                        metadata=section_data.jsonmeta,
                        order=section_data.order or idx,
                    )
                    self.db.add(section)

            self.db.commit()
            self.db.refresh(post)
            return post

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create post: {e}")
            raise

    def get_post_by_id(
        self, post_id: int, increment_view: bool = False
    ) -> Optional[BlogPost]:
        """Get a specific post by ID"""
        post = (
            self.db.query(BlogPost)
            .options(
                joinedload(BlogPost.author),
                joinedload(BlogPost.category),
                joinedload(BlogPost.sections),
                joinedload(BlogPost.comments),
            )
            .filter(BlogPost.id == post_id)
            .first()
        )

        if post and increment_view:
            post.view_count += 1
            self.db.commit()

        return post

    def get_post_by_slug(
        self, slug: str, increment_view: bool = False
    ) -> Optional[BlogPost]:
        """Get a specific post by slug"""
        post = (
            self.db.query(BlogPost)
            .options(
                joinedload(BlogPost.author),
                joinedload(BlogPost.category),
                joinedload(BlogPost.sections),
            )
            .filter(BlogPost.slug == slug)
            .first()
        )

        if post and increment_view:
            post.view_count += 1
            self.db.commit()

        return post

    def get_posts(
        self, query_params: BlogQueryParams
    ) -> Tuple[List[BlogPost], int]:
        """Get paginated posts with filters"""
        query = self.db.query(BlogPost).options(
            joinedload(BlogPost.author), joinedload(BlogPost.category)
        )

        # Apply filters
        if query_params.search:
            search_term = f"%{query_params.search}%"
            query = query.filter(
                or_(
                    BlogPost.title.ilike(search_term),
                    BlogPost.content.ilike(search_term),
                    BlogPost.excerpt.ilike(search_term),
                )
            )

        if query_params.category_id:
            query = query.filter(
                BlogPost.category_id == query_params.category_id
            )

        if query_params.tags:
            # Filter posts that have any of the specified tags
            for tag in query_params.tags:
                query = query.filter(BlogPost.tags.contains([tag]))

        if query_params.status:
            query = query.filter(BlogPost.status == query_params.status)

        if query_params.author_id:
            query = query.filter(BlogPost.author_id == query_params.author_id)

        if query_params.is_featured is not None:
            query = query.filter(
                BlogPost.is_featured == query_params.is_featured
            )

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(BlogPost, query_params.sort_by, None)
        if sort_column:
            if query_params.sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

        # Apply pagination
        offset = (query_params.page - 1) * query_params.page_size
        posts = query.offset(offset).limit(query_params.page_size).all()

        return posts, total

    def update_post(
        self, post_id: int, user_id: UUID, update_data: BlogPostUpdate
    ) -> Optional[BlogPost]:
        """Update an existing post"""
        post = self.get_post_by_id(post_id)

        if not post:
            return None

        # Check ownership
        if post.author_id != user_id:
            raise PermissionError("Not authorized to update this post")

        try:
            # Update fields
            update_dict = update_data.model_dump(exclude_unset=True)

            for field, value in update_dict.items():
                setattr(post, field, value)

            # Update read time if content changed
            if "content" in update_dict:
                post.read_time_minutes = post.calculate_read_time()

            # Update published_at if status changed to published
            if (
                "status" in update_dict
                and update_dict["status"] == BlogStatus.PUBLISHED
                and not post.published_at
            ):
                post.published_at = datetime.now(timezone.utc)

            post.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(post)
            return post

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update post: {e}")
            raise

    def delete_post(self, post_id: int, user_id: UUID) -> bool:
        """Delete a post (soft delete by archiving)"""
        post = self.get_post_by_id(post_id)

        if not post:
            return False

        # Check ownership
        if post.author_id != user_id:
            raise PermissionError("Not authorized to delete this post")

        try:
            # Soft delete by archiving
            post.status = BlogStatus.ARCHIVED
            post.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete post: {e}")
            raise

    def _generate_slug(self, title: str) -> str:
        """Generate unique slug from title"""
        import re

        # Basic slug generation
        slug = title.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)

        # Ensure uniqueness
        base_slug = slug[:200]
        counter = 1

        while self.db.query(BlogPost).filter(BlogPost.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    # Category operations
    def get_categories(self) -> List[BlogCategory]:
        """Get all categories with post counts"""
        categories = (
            self.db.query(
                BlogCategory, func.count(BlogPost.id).label("posts_count")
            )
            .outerjoin(BlogPost)
            .group_by(BlogCategory.id)
            .all()
        )

        return categories

    # Comment operations
    def add_comment(
        self,
        post_id: int,
        user_id: UUID,
        content: str,
        parent_id: Optional[int] = None,
    ) -> BlogComment:
        """Add a comment to a post"""
        post = self.get_post_by_id(post_id)

        if not post:
            raise ValueError("Post not found")

        if not post.is_commentable:
            raise ValueError("Comments are disabled for this post")

        try:
            comment = BlogComment(
                post_id=post_id,
                user_id=user_id,
                content=content,
                parent_id=parent_id,
                is_approved=True,  # Auto-approve for now
            )

            self.db.add(comment)
            self.db.commit()
            self.db.refresh(comment)

            return comment

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add comment: {e}")
            raise
