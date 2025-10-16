# project/blog/views.py
import logging
from fastapi import Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from . import blog_router
from project.database import get_db_session
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.blog.service import BlogService
from project.blog.ollama_blog_service import ollama_blog_generator
from project.blog.schemas import (
    GenerateRequest,
    PostResponse,
    PostUpdate,
    # SectionResponse
)
from project.schemas.response import APIResponse, success_response


logger = logging.getLogger(__name__)


@blog_router.post("/generate/stream", response_class=StreamingResponse)
async def stream_blog_generation(
    request: GenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Stream and auto-save blog content"""

    # Create initial post before streaming
    service = BlogService(db)
    post = service.create_initial_post(
        user_id=user.id, title=request.title, original_content=request.content
    )

    async def event_stream():
        full_text = ""
        try:
            # Send post_id first
            yield f"event: created\ndata: {post.id}\n\n"

            # Stream content
            async for text_chunk in ollama_blog_generator.generate_stream(
                title=request.title, content=request.content
            ):
                full_text += text_chunk
                yield f"data: {text_chunk}\n\n"

            # Save generated text and parse sections
            service.save_generated_content(post.id, full_text)
            print("save_generate: ", full_text)

            yield f"event: complete\ndata: {post.id}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            service.mark_failed(post.id)
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@blog_router.post(
    "/posts/{post_id}/complete", response_model=APIResponse[PostResponse]
)
def complete_generation(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Mark generation as complete"""
    try:
        service = BlogService(db)
        post = service.mark_complete(post_id, user.id)
        # print("get post: ", post.__dict__)
        post_response = PostResponse.model_validate(post)
        return success_response(
            data=post_response,
            message="Generation completed successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@blog_router.post("/posts/{post_id}/publish", response_model=PostResponse)
def publish_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Publish post (change status to published)"""
    try:
        service = BlogService(db)
        post = service.publish_post(post_id, user.id)
        return post
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )


@blog_router.get("/posts/{post_id}", response_model=APIResponse[PostResponse])
def get_post(
    post_id: int,
    increment_view: bool = False,
    db: Session = Depends(get_db_session),
):
    """Get single post"""
    service = BlogService(db)
    post = service.get_post_by_id(post_id, increment_view)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    data = PostResponse.model_validate(post)

    return success_response(data=data)


@blog_router.patch("/posts/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    update_data: PostUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update post"""
    try:
        service = BlogService(db)
        update_dict = update_data.model_dump(exclude_unset=True)
        post = service.update_post(post_id, user.id, **update_dict)
        return post
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )


@blog_router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete post"""
    try:
        service = BlogService(db)
        service.delete_post(post_id, user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
