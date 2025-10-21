# project/blog/views.py
import json
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from . import blog_router
from project.database import get_db_session
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.blog.service import BlogService
from project.blog.ollama_blog_service import ollama_blog_generator
from project.blog.schemas import GenerateRequest, PostResponse, PostUpdate
from project.schemas.response import APIResponse, success_response

logger = logging.getLogger(__name__)


@blog_router.post("/generate/stream", response_class=StreamingResponse)
async def stream_blog_generation(
    request: GenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Stream and auto-save blog content"""
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


@blog_router.post("/posts/{post_id}/complete", response_model=APIResponse)
def complete_generation(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Mark generation as complete"""
    try:
        service = BlogService(db)
        post = service.mark_complete(post_id, user.id)
        post_response = PostResponse.model_validate(post)
        return success_response(
            data=post_response,
            message="Generation completed successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@blog_router.get("/posts", response_model=APIResponse)
def list_blog_posts(
    search: Optional[str] = Query(None, description="Search title/content"),
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
    """List blog posts with filtering and pagination"""
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

        # Convert SQLAlchemy models to Pydantic schemas
        posts_data = [
            PostResponse.model_validate(post) for post in result["posts"]
        ]

        return success_response(
            data={
                "posts": posts_data,
                "total_count": result["total_count"],
                "page": result["page"],
                "page_size": result["page_size"],
            },
            message="Posts retrieved successfully"
        )
    except Exception as e:
        logger.error(f"List posts error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch posts",
        )


@blog_router.get("/posts/{post_id}", response_model=APIResponse)
def get_blog_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get single blog post with sections"""
    try:
        service = BlogService(db)
        post = service.get_post_by_id(post_id, user.id)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )
        post_response = PostResponse.model_validate(post)
        return success_response(
            data=post_response, message="Post retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get post error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch post",
        )


@blog_router.put("/posts/{post_id}", response_model=APIResponse)
def update_blog_post(
    post_id: int,
    data: PostUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update blog post"""
    try:
        service = BlogService(db)
        post = service.update_post(
            post_id, user.id, data.model_dump(exclude_unset=True)
        )
        post_response = PostResponse.model_validate(post)
        return success_response(
            data=post_response, message="Post updated successfully"
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


@blog_router.delete("/posts/{post_id}", response_model=APIResponse)
def delete_blog_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete blog post"""
    try:
        service = BlogService(db)
        service.delete_post(post_id, user.id)
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
