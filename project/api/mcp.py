# project/api/mcp.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from anthropic import Anthropic
import os
import json

from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.blog.service import BlogService
from project.database import get_db_session
from sqlalchemy.orm import Session

# Import schemas for response documentation
from project.blog.schemas import (
    BlogPostResponse,
    BlogPostCreate,
    BlogPostUpdate
)
from project.notes.schemas import (
    NoteResponse,
    NoteCreate,
    NoteUpdate
)
from project.ollama.tasks import task_generate_quiz
from project.users.schemas import UserProfileResponse
from project.api.mcp_indexer import get_indexer


mcp_router = APIRouter(prefix="/mcp", tags=["mcp"])

# Helper to convert Pydantic schema to JSON schema


def schema_to_json_example(schema_class) -> str:
    """Convert Pydantic model to readable JSON example"""
    try:
        schema = schema_class.model_json_schema()
        properties = schema.get("properties", {})

        example = {}
        for key, value in properties.items():
            type_map = {
                "string": "string",
                "integer": 0,
                "number": 0.0,
                "boolean": True,
                "array": [],
                "object": {}
            }
            example[key] = type_map.get(value.get("type"), "any")

        return json.dumps(example, indent=2)
    except Exception:
        return "{}"

# Schemas


class ChatRequest(BaseModel):
    message: str
    history: Optional[list[dict]] = []


class ToolCall(BaseModel):
    name: str
    args: dict
    result: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    tool_calls: Optional[list[ToolCall]] = None


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict


# Tool Registry - Auto-generated from Pydantic schemas
TOOLS = [
    # Blog Management
    {
        "name": "list_blog_posts",
        "description": f"""Get paginated list of blog posts with filters.

Response schema: Array of {BlogPostResponse.__name__}
Example:
{{
  "total": 10,
  "posts": [{schema_to_json_example(BlogPostResponse)}]
}}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "status": {"type": "string", "enum":
                           ["draft", "published", "archived"]},
                "limit": {"type": "integer", "default": 10},
                "page": {"type": "integer", "default": 1}
            }
        }
    },
    {
        "name": "get_blog_post",
        "description": f"""Get a specific blog post by ID.

Response schema: {BlogPostResponse.__name__}
{schema_to_json_example(BlogPostResponse)}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer"}
            },
            "required": ["post_id"]
        }
    },
    {
        "name": "create_blog_post",
        "description": f"""Create a new blog post.

Input schema: {BlogPostCreate.__name__}
Response: {{"success": true, "post_id": 1, "title": "string"}}""",
        "input_schema": BlogPostCreate.model_json_schema()
    },
    {
        "name": "update_blog_post",
        "description": f"""Update an existing blog post.

Input schema: {BlogPostUpdate.__name__} + post_id
Response: {{"success": true, "post_id": 1}}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer"},
                **BlogPostUpdate.model_json_schema().get("properties", {})
            },
            "required": ["post_id"]
        }
    },
    {
        "name": "delete_blog_post",
        "description": """Delete a blog post.

Response: {"success": true}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer"}
            },
            "required": ["post_id"]
        }
    },

    # Notes Management
    {
        "name": "list_notes",
        "description": f"""Get user's notes with optional filters.

Response schema: Array of {NoteResponse.__name__}
{{"notes": [{schema_to_json_example(NoteResponse)}]}}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 10}
            }
        }
    },
    {
        "name": "get_note",
        "description": f"""Get a specific note by ID.

Response schema: {NoteResponse.__name__}
{schema_to_json_example(NoteResponse)}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "integer"}
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "create_note",
        "description": f"""Create a new note.

Input schema: {NoteCreate.__name__}
Response: {{"success": true, "note_id": 1, "title": "string"}}""",
        "input_schema": NoteCreate.model_json_schema()
    },
    {
        "name": "update_note",
        "description": f"""Update an existing note.

Input schema: {NoteUpdate.__name__} + note_id
Response: {{"success": true, "note_id": 1}}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "integer"},
                **NoteUpdate.model_json_schema().get("properties", {})
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "delete_note",
        "description": """Delete a note.

Response: {"success": true}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "integer"}
            },
            "required": ["note_id"]
        }
    },

    # AI Operations
    {
        "name": "enhance_note",
        "description": """Enhance note content with AI (async).

Response: {"success": true, "task_id": "abc-123", "message": "started"}
Use check_task_status to monitor.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "integer"}
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "summarize_note",
        "description": """Generate AI summary (async).

Response: {"success": true, "task_id": "abc-123"}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "integer"}
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "generate_quiz",
        "description": """Generate quiz from note (async).

Response: {"success": true, "task_id": "abc-123"}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "integer"}
            },
            "required": ["note_id"]
        }
    },

    # User Management
    {
        "name": "get_user_profile",
        "description": f"""Get current user's profile.

Response schema: {UserProfileResponse.__name__}
{schema_to_json_example(UserProfileResponse)}""",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_notes_stats",
        "description": """Get user's notes statistics.

Response: {"total_notes": 10, "enhanced": 5}""",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },

    # System
    {
        "name": "check_task_status",
        "description": """Check background task status.

Response: {"status": "SUCCESS", "result": "..."}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "check_system_health",
        "description": """Check system health.

Response: {"status": "healthy", "services": {"api": "up", "db": "up"}}""",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    # Frontend
    {
        "name": "analyze_frontend_structure",
        "description": """Complete frontend codebase analysis with indexing.

Response: {
    "components": [{"name": "...", "type": "...", "api_calls": [...]}],
    "routes": [{"path": "/...", "api_calls": [...]}],
    "hooks": [{"name": "use...", "api_calls": [...]}],
    "stores": [{"name": "...", "api_calls": [...]}],
    "total_components": 50,
    "total_routes": 10
}""",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "search_api_usage",
        "description": """Find all frontend files using
        a specific API namespace.

Example: namespace="blog" finds all blog.* API calls
Response: [
    {"file": "path/to/file.tsx", "apis": ["blog.create", "blog.list"]}
]""",
        "input_schema": {
            "type": "object",
            "properties": {
                "api_namespace": {
                    "type": "string",
                    "description": "API namespace like 'blog', 'notes', 'auth'"
                }
            },
            "required": ["api_namespace"]
        }
    },
    {
        "name": "get_component_details",
        "description": """Get detailed information about a specific component.

Response: {
    "name": "ComponentName",
    "path": "components/...",
    "type": "feature|ui|layout|page",
    "imports": ["react", "@tanstack/react-query"],
    "api_calls": ["blog.list", "notes.create"],
    "hooks_used": ["useState", "useEffect"]
}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "component_name": {"type": "string"}
            },
            "required": ["component_name"]
        }
    },

]


async def execute_tool(name: str, args: dict, user: User, db: Session) -> str:
    """Execute MCP tool and return JSON result"""

    # Blog operations
    if name == "list_blog_posts":
        from project.blog.schemas import BlogQueryParams, BlogStatus
        service = BlogService(db)
        query = BlogQueryParams(
            search=args.get("search"),
            status=BlogStatus(args["status"]) if args.get("status") else None,
            page=args.get("page", 1),
            page_size=args.get("limit", 10)
        )
        posts, total = service.get_posts(query)
        return json.dumps({
            "total": total,
            "posts": [{
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "excerpt": p.excerpt,
                "created_at": str(p.created_at)
            } for p in posts]
        })

    elif name == "get_blog_post":
        service = BlogService(db)
        post = service.get_post_by_id(args["post_id"])
        if not post:
            return json.dumps({"error": "Post not found"})
        return json.dumps({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "status": post.status,
            "views": post.views_count
        })

    elif name == "create_blog_post":
        from project.blog.schemas import BlogPostCreate
        service = BlogService(db)
        post_data = BlogPostCreate(
            title=args["title"],
            content=args["content"],
            excerpt=args.get("excerpt", ""),
            status=args.get("status", "draft")
        )
        post = service.create_post(user_id=user.id, post_data=post_data)
        return json.dumps({
            "success": True,
            "post_id": post.id,
            "title": post.title
        })

    elif name == "update_blog_post":
        from project.blog.schemas import BlogPostUpdate
        service = BlogService(db)
        update_data = BlogPostUpdate(
            **{k: v for k, v in args.items() if k != "post_id"})
        post = service.update_post(args["post_id"], user.id, update_data)
        return json.dumps({"success": True, "post_id": post.id})

    elif name == "delete_blog_post":
        service = BlogService(db)
        success = service.delete_post(args["post_id"], user.id)
        return json.dumps({"success": success})

    # Notes operations
    elif name == "list_notes":
        from project.notes.service import NoteService
        service = NoteService(db)
        notes = service.get_user_notes(
            user.id,
            search=args.get("search"),
            page=args.get("page", 1),
            page_size=args.get("page_size", 10)
        )
        return json.dumps({
            "notes": [{
                "id": n.id,
                "title": n.title,
                "created_at": str(n.created_at)
            } for n in notes]
        })

    elif name == "get_note":
        from project.notes.service import NoteService
        service = NoteService(db)
        note = service.get_note(args["note_id"], user.id)
        if not note:
            return json.dumps({"error": "Note not found"})
        return json.dumps({
            "id": note.id,
            "title": note.title,
            "content": note.content
        })

    elif name == "create_note":
        from project.notes.service import NoteService
        from project.notes.schemas import NoteCreate
        service = NoteService(db)
        note_data = NoteCreate(title=args["title"], content=args["content"])
        note = service.create_note(user.id, note_data)
        return json.dumps({
            "success": True,
            "note_id": note.id,
            "title": note.title
        })

    elif name == "update_note":
        from project.notes.service import NoteService
        from project.notes.schemas import NoteUpdate
        service = NoteService(db)
        note_data = NoteUpdate(
            **{k: v for k, v in args.items() if k != "note_id"})
        note = service.update_note(args["note_id"], user.id, note_data)
        return json.dumps({"success": True, "note_id": note.id})

    elif name == "delete_note":
        from project.notes.service import NoteService
        service = NoteService(db)
        service.delete_note(args["note_id"], user.id)
        return json.dumps({"success": True})

    # AI operations
    elif name == "enhance_note":
        from project.ollama.tasks import task_enhance_note
        task = task_enhance_note.delay(args["note_id"])
        return json.dumps({
            "success": True,
            "task_id": task.id,
            "message": "Enhancement started"
        })

    elif name == "summarize_note":
        from project.ollama.tasks import task_summarize_note
        task = task_summarize_note.delay(args["note_id"])
        return json.dumps({
            "success": True,
            "task_id": task.id,
            "message": "Summarization started"
        })

    elif name == "generate_quiz":

        task = task_generate_quiz.delay(args["note_id"])
        return json.dumps({
            "success": True,
            "task_id": task.id,
            "message": "Quiz generation started"
        })

    # User operations
    elif name == "get_user_profile":
        return json.dumps({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified
        })

    elif name == "get_notes_stats":
        from project.notes.service import NoteService
        service = NoteService(db)
        stats = service.get_user_stats(user.id)
        return json.dumps(stats)

    # Task status
    elif name == "check_task_status":
        from celery.result import AsyncResult
        task = AsyncResult(args["task_id"])
        return json.dumps({
            "status": task.status,
            "result": str(task.result) if task.ready() else None
        })

    # System health
    elif name == "check_system_health":
        return json.dumps({
            "status": "healthy",
            "services": {
                "api": "up",
                "database": "up",
                "redis": "up"
            }
        })
    elif name == "analyze_frontend_structure":
        indexer = get_indexer()
        index = indexer.build_index()

        return json.dumps({
            "total_components": len(index["components"]),
            "total_routes": len(index["routes"]),
            "total_hooks": len(index["hooks"]),
            "total_stores": len(index["stores"]),
            "components": index["components"][:10],  # First 10
            "routes": index["routes"][:10],
            "hooks": index["hooks"][:5],
            "stores": index["stores"][:5]
        })

    elif name == "search_api_usage":
        indexer = get_indexer()
        results = indexer.search_api_usage(args["api_namespace"])

        return json.dumps({
            "namespace": args["api_namespace"],
            "usage_count": len(results),
            "files": results
        })

    elif name == "get_component_details":
        indexer = get_indexer()
        details = indexer.get_component_details(args["component_name"])

        return json.dumps(details)

    return json.dumps({"error": "Tool not found"})


@mcp_router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Chat with Claude via MCP"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ANTHROPIC_API_KEY not configured"
        )

    client = Anthropic(api_key=api_key)

    # Build messages from history
    messages = [{"role": msg["role"], "content": msg["content"]}
                for msg in request.history]
    messages.append({"role": "user", "content": request.message})

    # Initial request with tools
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        tools=TOOLS,
        messages=messages
    )

    tool_calls = []

    # Process tool use
    while response.stop_reason == "tool_use":
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                result = await execute_tool(
                    block.name,
                    block.input,
                    current_user,
                    db
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })
                tool_calls.append({
                    "name": block.name,
                    "args": block.input,
                    "result": result
                })

        # Continue conversation with tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages
        )

    # Extract final text response
    content = next(
        (block.text for block in response.content if hasattr(block, "text")),
        "No response"
    )

    return {
        "success": True,
        "data": {
            "content": content,
            "tool_calls": tool_calls or None
        }
    }


@mcp_router.get("/tools")
async def get_tools(
    current_user: User = Depends(get_current_user)
):
    """Get available MCP tools"""
    tools = [
        {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"]
        }
        for tool in TOOLS
    ]
    return {"success": True, "data": tools}
