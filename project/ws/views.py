"""
project/ws/views.py
"""

import json
import socketio
from fastapi import FastAPI, WebSocket, Query, WebSocketDisconnect
from socketio.asyncio_namespace import AsyncNamespace

from project.ws.utils import parse_cookies
from project.auth.supabase_client import supabase_admin
from . import ws_router
from project import broadcast
from project.celery_utils import get_task_info
from project.config import settings


async def verify_ws_token(token: str) -> bool:
    """Verify Supabase token"""
    try:
        response = supabase_admin.auth.get_user(token)
        return response.user is not None
    except Exception:
        return False


@ws_router.websocket("/ws/task_status/{task_id}")
async def ws_task_status(
    websocket: WebSocket, task_id: str, token: str = Query(None)
):
    """WebSocket for task status"""
    if not token:
        cookie_header = websocket.headers.get("cookie", "")
        cookies = parse_cookies(cookie_header)
        token = cookies.get("access_token")

    if not token or not await verify_ws_token(token):
        await websocket.close(code=1008, reason="Not authenticated")
        return

    await websocket.accept()

    try:
        async with broadcast.subscribe(channel=task_id) as subscriber:
            await websocket.send_json(get_task_info(task_id))

            async for event in subscriber:
                await websocket.send_json(json.loads(event.message))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))


async def update_celery_task_status(task_id: str):
    """Publish task status update"""
    await broadcast.connect()
    await broadcast.publish(
        channel=task_id, message=json.dumps(get_task_info(task_id))
    )
    await broadcast.disconnect()


class TaskStatusNameSpace(AsyncNamespace):
    """Socket.IO namespace"""

    async def on_join(self, sid, data):
        environ = self.get_environ(sid)
        cookies = parse_cookies(environ.get("HTTP_COOKIE", ""))
        token = cookies.get("access_token")

        if not token or not await verify_ws_token(token):
            await self.disconnect(sid)
            return

        self.enter_room(sid=sid, room=data["task_id"])
        await self.emit(
            "status", get_task_info(data["task_id"]), room=data["task_id"]
        )


def register_socketio_app(app: FastAPI):
    """Register Socket.IO"""
    mgr = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE)
    sio = socketio.AsyncServer(
        async_mode="asgi",
        client_manager=mgr,
        logger=True,
        cors_allowed_origins=settings.CORS_ORIGINS,
    )
    sio.register_namespace(TaskStatusNameSpace("/task_status"))
    asgi = socketio.ASGIApp(socketio_server=sio)
    app.mount("/ws", asgi)


def update_celery_task_status_socketio(task_id):
    """Emit via Socket.IO from Celery"""
    external_sio = socketio.RedisManager(
        settings.WS_MESSAGE_QUEUE, write_only=True
    )
    external_sio.emit(
        "status",
        get_task_info(task_id),
        room=task_id,
        namespace="/task_status",
    )
