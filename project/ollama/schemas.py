"""
project/ollama/schemas.py
Ollama API schemas
"""

from pydantic import BaseModel
from typing import Optional


class HealthCheckResponse(BaseModel):
    status: str
    available: bool


class TaskResponse(BaseModel):
    task_id: str
    note_id: int
    streaming: bool
    message: str
    stream_channel: Optional[str] = None
    ws_url: Optional[str] = None


class TaskStatusResponse(BaseModel):
    state: str
    result: Optional[dict] = None
    error: Optional[str] = None
