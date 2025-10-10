"""
project/blog/views.py

Blog API endpoints with SSE streaming support
"""

import json
import logging
from typing import Optional
from fastapi import (
    Depends,
    HTTPException,
    status,
    Query,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from . import blog_router
from project.database import get_db_session
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.blog.service import BlogService
from project.blog.schemas import (
    BlogPostCreate,
    BlogPostUpdate,
    BlogPostResponse,
    BlogPostList,
    BlogQueryParams,
    BlogCategoryResponse,
    BlogCommentCreate,
    BlogCommentResponse,
    BlogStatus,
    BlogGenerateRequest
)
from project.schemas.response import APIResponse, success_response
from project.ollama.streaming import streaming_service

logger = logging.getLogger(__name__)


# CREATE endpoints
@blog_router.post(
    "/posts",
    response_model=APIResponse[BlogPostResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_blog_post(
    post_data: BlogPostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create a new blog post"""
    service = BlogService(db)

    try:
        post = service.create_post(
            user_id=current_user.id, post_data=post_data
        )
        print("post: ", post.__dict__)

        response = BlogPostResponse.model_validate(post)

        return success_response(
            data=response, message="Blog post created successfully"
        )

    except Exception as e:
        logger.error(f"Failed to create post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# READ endpoints
@blog_router.get("/posts", response_model=APIResponse[BlogPostList])
def get_blog_posts(
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    tags: Optional[str] = Query(None),
    status: Optional[BlogStatus] = Query(None),
    author_id: Optional[int] = Query(None),
    is_featured: Optional[bool] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Get paginated blog posts with filters

    - **search**: Search in title, content, excerpt
    - **category_id**: Filter by category
    - **tags**: Comma-separated tags
    - **status**: Filter by status (draft/published/archived)
    - **author_id**: Filter by author
    - **is_featured**: Filter featured posts
    - **sort_by**: Sort field
    - **sort_order**: asc or desc
    - **page**: Page number
    - **page_size**: Items per page
    """
    service = BlogService(db)

    # Parse tags
    tags_list = tags.split(",") if tags else None

    # Build query params
    query_params = BlogQueryParams(
        search=search,
        category_id=category_id,
        tags=tags_list,
        status=status,
        author_id=author_id,
        is_featured=is_featured,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    # Filter drafts for non-authors
    if not current_user or (
        query_params.author_id and query_params.author_id != current_user.id
    ):
        query_params.status = BlogStatus.PUBLISHED

    posts, total = service.get_posts(query_params)

    # Build response
    posts_response = [BlogPostResponse.model_validate(post) for post in posts]

    total_pages = (total + page_size - 1) // page_size

    return success_response(
        data=BlogPostList(
            posts=posts_response,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
        message="Posts retrieved successfully",
    )


@blog_router.get(
    "/posts/{post_id}", response_model=APIResponse[BlogPostResponse]
)
def get_blog_post(
    post_id: int,
    increment_view: bool = Query(True),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a specific blog post by ID"""
    service = BlogService(db)

    post = service.get_post_by_id(
        post_id=post_id, increment_view=increment_view
    )

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Check if user can view draft
    if post.status != BlogStatus.PUBLISHED and (
        not current_user or current_user.id != post.author_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this post",
        )

    response = BlogPostResponse.model_validate(post)
    response.comments_count = len(post.comments)

    return success_response(
        data=response, message="Post retrieved successfully"
    )


@blog_router.get(
    "/posts/slug/{slug}", response_model=APIResponse[BlogPostResponse]
)
def get_blog_post_by_slug(
    slug: str,
    increment_view: bool = Query(True),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a specific blog post by slug"""
    service = BlogService(db)

    post = service.get_post_by_slug(slug=slug, increment_view=increment_view)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Check if user can view draft
    if post.status != BlogStatus.PUBLISHED and (
        not current_user or current_user.id != post.author_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this post",
        )

    response = BlogPostResponse.model_validate(post)

    return success_response(
        data=response, message="Post retrieved successfully"
    )


# UPDATE endpoints
@blog_router.put(
    "/posts/{post_id}", response_model=APIResponse[BlogPostResponse]
)
def update_blog_post(
    post_id: int,
    update_data: BlogPostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update an existing blog post (full update)"""
    service = BlogService(db)

    try:
        post = service.update_post(
            post_id=post_id, user_id=current_user.id, update_data=update_data
        )

        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
            )

        response = BlogPostResponse.model_validate(post)

        return success_response(
            data=response, message="Post updated successfully"
        )

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@blog_router.patch(
    "/posts/{post_id}", response_model=APIResponse[BlogPostResponse]
)
def patch_blog_post(
    post_id: int,
    update_data: BlogPostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Partially update a blog post"""
    service = BlogService(db)

    try:
        post = service.update_post(
            post_id=post_id, user_id=current_user.id, update_data=update_data
        )

        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
            )

        response = BlogPostResponse.model_validate(post)

        return success_response(
            data=response, message="Post updated successfully"
        )

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to patch post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# DELETE endpoint
@blog_router.delete("/posts/{post_id}", response_model=APIResponse[dict])
def delete_blog_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete (archive) a blog post"""
    service = BlogService(db)

    try:
        success = service.delete_post(post_id=post_id, user_id=current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
            )

        return success_response(
            data={"deleted": True, "post_id": post_id},
            message="Post deleted successfully",
        )

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@blog_router.post("/generate/stream")
async def stream_blog_generation(
    request: BlogGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Stream AI-generated blog improvements via SSE

    Args:
        blog_id: ID of blog post to enhance
        enhancement_type: Type of enhancement (improve/expand/summarize)

    Returns:
        Server-Sent Events stream with generated content
    """
    service = BlogService(db)

    # Get blog post
    blog = service.get_post_by_id(request.blog_id)

    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )

    # Check ownership
    if blog.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this post"
        )

    async def stream():
        """Generate SSE stream"""
        try:
            # Send initial metadata
            yield f"""data: {json.dumps({
                'type': 'start',
                'blog_id': blog.id,
                'title': blog.title
            })}\n\n"""

            # Stream enhanced content
            async for chunk in streaming_service.stream_blog_content(
                blog.title,
                blog.content,
                request.enhancement_type
            ):
                yield f"""data: {json.dumps({
                    'type': 'chunk',
                    'content': chunk
                })}\n\n"""

            # Send completion
            yield f"""data: {json.dumps({
                'type': 'complete',
                'blog_id': blog.id
            })}\n\n"""

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"""data: {json.dumps({
                'type': 'error',
                'error': str(e)
            })}\n\n"""

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Categories endpoint


@blog_router.get(
    "/categories", response_model=APIResponse[list[BlogCategoryResponse]]
)
def get_categories(db: Session = Depends(get_db_session)):
    """Get all blog categories"""
    service = BlogService(db)

    categories = service.get_categories()

    response = [
        BlogCategoryResponse.model_validate(cat[0]) for cat in categories
    ]

    return success_response(
        data=response, message="Categories retrieved successfully"
    )


# Comments endpoints
@blog_router.post(
    "/posts/{post_id}/comments",
    response_model=APIResponse[BlogCommentResponse],
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    post_id: int,
    comment_data: BlogCommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Add a comment to a blog post"""
    service = BlogService(db)

    try:
        comment = service.add_comment(
            post_id=post_id,
            user_id=current_user.id,
            content=comment_data.content,
            parent_id=comment_data.parent_id,
        )

        response = BlogCommentResponse.model_validate(comment)

        return success_response(
            data=response, message="Comment added successfully"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to add comment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
