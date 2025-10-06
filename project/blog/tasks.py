"""
project/blog/tasks.py

Celery tasks for blog operations
"""

import logging
from celery import shared_task
from datetime import datetime, timezone

from project.database import db_context
from project.blog.models import BlogPost, BlogStatus
from project.celery_utils import custom_celery_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def task_publish_scheduled_posts(self):
    """
    Task to publish scheduled posts
    Run periodically to publish posts with future publish dates
    """
    try:
        with db_context() as session:
            current_time = datetime.now(timezone.utc)

            # Find draft posts with published_at <= now
            posts_to_publish = (
                session.query(BlogPost)
                .filter(
                    BlogPost.status == BlogStatus.DRAFT,
                    BlogPost.published_at <= current_time,
                    BlogPost.published_at.isnot(None),
                )
                .all()
            )

            published_count = 0
            for post in posts_to_publish:
                post.status = BlogStatus.PUBLISHED
                published_count += 1
                logger.info(
                    f"Published scheduled post: {post.id} - {post.title}"
                )

            session.commit()

            return {
                "success": True,
                "published_count": published_count,
                "timestamp": current_time.isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to publish scheduled posts: {e}")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
)
def task_generate_blog_summary(self, post_id: int):
    """
    Generate AI summary for a blog post
    Uses the existing Ollama service if available
    """
    try:
        with db_context() as session:
            post = (
                session.query(BlogPost).filter(BlogPost.id == post_id).first()
            )

            if not post:
                logger.error(f"Post {post_id} not found")
                return {"success": False, "error": "Post not found"}

            # Generate excerpt if not present
            if not post.excerpt:
                # Take first 200 characters of content
                excerpt = post.content[:200].strip()
                if len(post.content) > 200:
                    excerpt += "..."
                post.excerpt = excerpt
                session.commit()

            # If Ollama is available, generate AI summary
            try:
                from project.ollama.service import ollama_service

                prompt = f"""
                Create a concise summary of this blog post:

                Title: {post.title}
                Content: {post.content[:1000]}

                Provide a 2-3 sentence summary.
                """

                summary = ollama_service.generate_text(prompt)

                if summary:
                    post.meta_description = summary[:160]
                    session.commit()

                    return {
                        "success": True,
                        "post_id": post_id,
                        "summary": summary,
                    }

            except ImportError:
                logger.info("Ollama service not available")

            return {
                "success": True,
                "post_id": post_id,
                "message": "Basic excerpt generated",
            }

    except Exception as e:
        logger.error(f"Failed to generate summary for post {post_id}: {e}")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def task_update_blog_analytics(self, post_id: int):
    """
    Update blog post analytics
    Can be triggered after view events
    """
    try:
        with db_context() as session:
            post = (
                session.query(BlogPost).filter(BlogPost.id == post_id).first()
            )

            if not post:
                return {"success": False, "error": "Post not found"}

            # Update read time
            word_count = len(post.content.split())
            post.read_time_minutes = max(1, word_count // 200)

            # Update word count in metadata
            if not post.meta_keywords and post.tags:
                post.meta_keywords = post.tags[:5]

            session.commit()

            return {
                "success": True,
                "post_id": post_id,
                "read_time": post.read_time_minutes,
                "view_count": post.view_count,
            }

    except Exception as e:
        logger.error(f"Failed to update analytics for post {post_id}: {e}")
        raise


@shared_task
def task_cleanup_old_drafts():
    """
    Clean up old draft posts (older than 30 days)
    Run weekly to remove abandoned drafts
    """
    try:
        from datetime import timedelta

        with db_context() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

            old_drafts = (
                session.query(BlogPost)
                .filter(
                    BlogPost.status == BlogStatus.DRAFT,
                    BlogPost.created_at < cutoff_date,
                    BlogPost.published_at.is_(None),
                )
                .all()
            )

            archived_count = 0
            for draft in old_drafts:
                draft.status = BlogStatus.ARCHIVED
                archived_count += 1
                logger.info(f"Archived old draft: {draft.id} - {draft.title}")

            session.commit()

            return {
                "success": True,
                "archived_count": archived_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to cleanup old drafts: {e}")
        raise


@custom_celery_task(max_retries=3)
def task_send_blog_notification(
    post_id: int, notification_type: str = "new_post"
):
    """
    Send notifications for blog events
    (new post, comment, etc.)
    """
    try:
        with db_context() as session:
            post = (
                session.query(BlogPost).filter(BlogPost.id == post_id).first()
            )

            if not post:
                return {"success": False, "error": "Post not found"}

            # Here you would integrate with notification service
            # For now, just log
            logger.info(
                f"Notification: {notification_type} for post {post.title}"
            )

            return {
                "success": True,
                "post_id": post_id,
                "notification_type": notification_type,
            }

    except Exception as e:
        logger.error(f"Failed to send notification for post {post_id}: {e}")
        raise
