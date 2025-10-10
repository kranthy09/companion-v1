# ============================================================
# project/blog/views.py - Clean streaming endpoint
# ============================================================
import json
from fastapi import Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from . import blog_router
from project.database import get_db_session
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.blog.service import BlogService
from project.blog.schemas import (
    BlogCreateStreamRequest,
    BlogPostCreate,
    BlogStatus,
)
from project.blog.agent_service import blog_agent


@blog_router.post("/posts/create-stream")
async def create_blog_stream(
    data: BlogCreateStreamRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    async def stream():
        try:
            yield 'data: {"type":"creating"}\n\n'

            service = BlogService(db)
            post = service.create_post(
                user_id=user.id,
                post_data=BlogPostCreate(
                    title=data.title,
                    content=data.content,
                    status=BlogStatus.DRAFT,
                ),
            )

            yield f'data: {{"type":"blog_created","id":{post.id}}}\n\n'

            heading_text = ""
            desc_text = ""
            main_text = ""

            async for event in blog_agent.generate_with_main_section(
                data.title, data.content
            ):
                yield f"data: {json.dumps(event)}\n\n"

                if event["type"] == "heading_done":
                    heading_text = event["heading"]
                elif event["type"] == "description_done":
                    desc_text = event["description"]
                elif event["type"] == "main_done":
                    main_text = event["content"]

            from project.ollama.tasks import task_save_blog_sections_full

            task = task_save_blog_sections_full.delay(
                post.id, heading_text, desc_text, main_text
            )

            yield f'data: {{"type":"saved","task":"{task.id}"}}\n\n'
        except Exception as e:
            yield f'data: {{"type":"error","msg":"{str(e)}"}}\n\n'

    return StreamingResponse(stream(), media_type="text/event-stream")
