"""Blog views with comprehensive caching"""

import json
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from . import blog_router
from project.database import get_db_session
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.blog.service import BlogService
from project.blog.ollama_blog_service import ollama_blog_generator
from project.blog.schemas import GenerateRequest, PostResponse, PostUpdate
from project.schemas.response import success_response
from project.middleware.cache import cache

logger = logging.getLogger(__name__)


async def invalidate_blog_caches(user_id: str, post_id: int = None):
    """Helper to invalidate blog-related caches"""
    patterns = [
        f"blog_posts:{user_id}:*",
    ]
    if post_id:
        patterns.append(f"blog_post:{post_id}")

    for pattern in patterns:
        await cache.delete(pattern)


@blog_router.post("/generate/stream", response_class=StreamingResponse)
async def stream_blog_generation(
    request: GenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Stream blog generation (no caching - real-time)"""
    service = BlogService(db)
    post = service.create_initial_post(
        user_id=user.id,
        title=request.title,
        original_content=request.content,
    )

    async def event_stream():
        full_text = ""
        try:
            yield f"data: {json.dumps({'post_id': post.id})}\n\n"

            async for text_chunk in ollama_blog_generator.generate_stream(
                title=request.title, content=request.content
            ):
                full_text += text_chunk
                yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"

            service.save_generated_content(post.id, full_text)

            # Invalidate list cache after generation
            await invalidate_blog_caches(str(user.id), post.id)

            yield f"data: {json.dumps({'done': True, 'post_id': post.id})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            service.mark_failed(post.id)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@blog_router.post("/posts/{post_id}/complete")
async def complete_generation(
    post_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Mark generation complete and invalidate caches"""
    try:
        service = BlogService(db)
        post = service.mark_complete(post_id, user.id)

        # Invalidate caches
        background_tasks.add_task(
            invalidate_blog_caches, str(user.id), post_id
        )

        return success_response(
            data=PostResponse.model_validate(post),
            message="Generation completed successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@blog_router.get("/posts")
async def list_blog_posts(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(
        None, pattern="^(draft|published|archived)$", alias="status"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(
        "updated_at", pattern="^(created_at|updated_at|title)$"
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List blog posts with 60s cache"""
    user_id = str(user.id)

    # Build cache key
    cache_key = (
        f"blog_posts:{user_id}:{page}:{page_size}:{sort_by}:{sort_order}"
    )
    if search:
        cache_key += f":search:{search}"
    if status_filter:
        cache_key += f":status:{status_filter}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data={
                "posts": [PostResponse(**p) for p in cached_data["posts"]],
                "total_count": cached_data["total_count"],
                "page": cached_data["page"],
                "page_size": cached_data["page_size"],
            },
            message="Posts retrieved successfully",
        )

    # Cache miss - query DB
    try:
        service = BlogService(db)
        result = service.list_posts(
            user_id=user.id,
            search=search,
            status=status_filter,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Convert to dicts for caching
        posts_data = [
            PostResponse.model_validate(post).model_dump()
            for post in result["posts"]
        ]

        response_data = {
            "posts": posts_data,
            "total_count": result["total_count"],
            "page": result["page"],
            "page_size": result["page_size"],
        }

        # Cache for 60 seconds
        await cache.set(cache_key, response_data, ttl=60)

        return success_response(
            data={
                "posts": [PostResponse(**p) for p in posts_data],
                "total_count": result["total_count"],
                "page": result["page"],
                "page_size": result["page_size"],
            },
            message="Posts retrieved successfully",
        )

    except Exception as e:
        logger.error(f"List posts error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch posts",
        )


@blog_router.get("/posts/{post_id}")
async def get_blog_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get single post with 5min cache"""
    cache_key = f"blog_post:{post_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=PostResponse(**cached_data),
            message="Post retrieved successfully",
        )

    # Cache miss
    try:
        service = BlogService(db)
        post = service.get_post_by_id(post_id, user.id)

        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
            )

        # Cache for 5 minutes
        post_data = PostResponse.model_validate(post).model_dump()
        await cache.set(cache_key, post_data, ttl=300)

        return success_response(
            data=PostResponse(**post_data),
            message="Post retrieved successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get post error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch post",
        )


@blog_router.put("/posts/{post_id}")
async def update_blog_post(
    post_id: int,
    data: PostUpdate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update post and invalidate caches"""
    try:
        service = BlogService(db)
        post = service.update_post(
            post_id, user.id, data.model_dump(exclude_unset=True)
        )

        # Invalidate caches
        background_tasks.add_task(
            invalidate_blog_caches, str(user.id), post_id
        )

        return success_response(
            data=PostResponse.model_validate(post),
            message="Post updated successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Update post error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update post",
        )


@blog_router.delete("/posts/{post_id}")
async def delete_blog_post(
    post_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete post and invalidate caches"""
    try:
        service = BlogService(db)
        service.delete_post(post_id, user.id)

        # Invalidate caches
        background_tasks.add_task(
            invalidate_blog_caches, str(user.id), post_id
        )

        return success_response(
            data={"deleted": True}, message="Post deleted successfully"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Delete post error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete post",
        )


@blog_router.get("/stats")
async def get_blog_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get blog statistics with 5min cache"""
    user_id = str(user.id)
    cache_key = f"blog_stats:{user_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=cached_data, message="Statistics retrieved"
        )

    # Cache miss
    try:
        service = BlogService(db)

        # Get stats
        total_posts = service.count_user_posts(user.id)
        draft_count = service.count_by_status(user.id, "draft")
        published_count = service.count_by_status(user.id, "published")

        stats = {
            "total_posts": total_posts,
            "draft": draft_count,
            "published": published_count,
            "archived": total_posts - draft_count - published_count,
        }

        # Cache for 5 minutes
        await cache.set(cache_key, stats, ttl=300)

        return success_response(data=stats, message="Statistics retrieved")

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics",
        )


@blog_router.post("/posts/{post_id}/publish")
async def publish_post(
    post_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Publish post and invalidate caches"""
    try:
        service = BlogService(db)
        post = service.update_post(post_id, user.id, {"status": "published"})

        # Invalidate caches
        background_tasks.add_task(
            invalidate_blog_caches, str(user.id), post_id
        )

        return success_response(
            data=PostResponse.model_validate(post),
            message="Post published successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )


@blog_router.post("/cache/clear")
async def clear_blog_cache(user: User = Depends(get_current_user)):
    """Clear all blog caches for user (admin/debug)"""
    user_id = str(user.id)
    await invalidate_blog_caches(user_id)

    return success_response(message="Blog cache cleared successfully")
