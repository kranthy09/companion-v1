"""
project/ws/views.py - Enhanced WebSocket with query token
"""

import json
import socketio
from fastapi import FastAPI, WebSocket, Query, WebSocketDisconnect
from socketio.asyncio_namespace import AsyncNamespace

from project.ws.utils import parse_cookies
from project.auth.utils import verify_token
from . import ws_router
from project import broadcast
from project.celery_utils import get_task_info
from project.config import settings


@ws_router.websocket("/ws/task_status/{task_id}")
async def ws_task_status(
    websocket: WebSocket, task_id: str, token: str = Query(None)
):
    """WebSocket for task status with query param token"""

    # Try query param first, fallback to cookie
    if not token:
        cookie_header = websocket.headers.get("cookie", "")
        cookies = parse_cookies(cookie_header)
        token = cookies.get("access_token")

    if not token:
        await websocket.close(code=1008, reason="Not authenticated")
        return

    try:
        payload = verify_token(token)
        if not payload.get("sub"):
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception as e:
        await websocket.close(
            code=1008, reason=f"Token validation failed: {str(e)}"
        )
        return

    await websocket.accept()

    try:
        async with broadcast.subscribe(channel=task_id) as subscriber:
            # Send current status immediately
            data = get_task_info(task_id)
            await websocket.send_json(data)

            # Stream updates
            async for event in subscriber:
                await websocket.send_json(json.loads(event.message))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))


async def update_celery_task_status(task_id: str):
    """Publish task status update (called from Celery)"""
    await broadcast.connect()
    await broadcast.publish(
        channel=task_id, message=json.dumps(get_task_info(task_id))
    )
    await broadcast.disconnect()


class TaskStatusNameSpace(AsyncNamespace):
    """Socket.IO namespace for task status"""

    async def on_join(self, sid, data):
        # Validate token from cookies
        environ = self.get_environ(sid)
        cookie_header = environ.get("HTTP_COOKIE", "")
        cookies = parse_cookies(cookie_header)

        token = cookies.get("access_token")

        if not token:
            await self.disconnect(sid)
            return

        try:
            verify_token(token)
        except Exception:
            await self.disconnect(sid)
            return

        self.enter_room(sid=sid, room=data["task_id"])
        # Send immediate status
        await self.emit(
            "status", get_task_info(data["task_id"]), room=data["task_id"]
        )


def register_socketio_app(app: FastAPI):
    """Register Socket.IO app"""
    mgr = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE)
    sio = socketio.AsyncServer(
        async_mode="asgi",
        client_manager=mgr,
        logger=True,
        engineio_logger=True,
        cors_allowed_origins=settings.CORS_ORIGINS,
    )
    sio.register_namespace(TaskStatusNameSpace("/task_status"))
    asgi = socketio.ASGIApp(socketio_server=sio)
    app.mount("/ws", asgi)


def update_celery_task_status_socketio(task_id):
    """Emit via Socket.IO from Celery worker"""
    external_sio = socketio.RedisManager(
        settings.WS_MESSAGE_QUEUE, write_only=True
    )
    external_sio.emit(
        "status",
        get_task_info(task_id),
        room=task_id,
        namespace="/task_status",
    )
