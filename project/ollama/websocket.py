"""
companion/project/ollama/websocket.py

WebSocket endpoint for streaming
"""

from fastapi import WebSocket
from . import ollama_router
from project import broadcast
import json


@ollama_router.websocket("/ws/stream/{task_id}")
async def ws_ollama_stream(websocket: WebSocket):
    """WebSocket endpoint for Ollama streaming"""
    await websocket.accept()

    task_id = websocket.scope["path_params"]["task_id"]
    channel = f"stream:{task_id}"

    async with broadcast.subscribe(channel=channel) as subscriber:
        async for event in subscriber:
            data = json.loads(event.message)
            await websocket.send_json(data)

            # Close connection when done
            if data.get("done"):
                break

    await websocket.close()
