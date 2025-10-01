"""
companion/project/ollama/websocket.py

WebSocket endpoint for streaming
"""

import json
from fastapi import WebSocket

from project.ws.utils import parse_cookies
from . import ollama_router
from project import broadcast


@ollama_router.websocket("/ws/stream/{task_id}")
async def ws_ollama_stream(websocket: WebSocket):
    # Extract token from cookie
    cookie_header = websocket.headers.get("cookie", "")
    cookies = {}
    if cookie_header:
        cookies = parse_cookies(cookie_header=cookie_header)
    token = cookies.get("access_token")
    print(f"Extracted token: {token}")  # Add this

    if not token:
        print("No token found, closing")  # Add this
        await websocket.close(code=1008, reason="Not authenticated")
        return

    try:
        from project.auth.utils import verify_token

        payload = verify_token(token)
        if not payload.get("sub"):
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception as e:
        await websocket.close(
            code=1008, reason=f"{str(e)}, Token validation failed"
        )
        return

    await websocket.accept()

    task_id = websocket.scope["path_params"]["task_id"]
    channel = f"stream:{task_id}"

    async with broadcast.subscribe(channel=channel) as subscriber:
        async for event in subscriber:
            data = json.loads(event.message)
            await websocket.send_json(data)

            if data.get("done"):
                break

    await websocket.close()
