"""
companion/project/ws/views.py

"""

import json

import socketio
from fastapi import FastAPI, WebSocket
from socketio.asyncio_namespace import AsyncNamespace

from project.auth.utils import verify_token
from . import ws_router
from project import broadcast
from project.celery_utils import get_task_info
from project.config import settings


@ws_router.websocket("/ws/task_status/{task_id}")
async def ws_task_status(websocket: WebSocket):
    # Extract token from cookie
    cookie_header = websocket.headers.get("cookie", "")
    cookies = {}
    if cookie_header:
        cookies = dict(
            item.split("=", 1)
            for item in cookie_header.split("; ")
            if "=" in item
        )

    token = cookies.get("access_token")

    if not token:
        await websocket.close(code=1008, reason="Not authenticated")
        return

    try:
        payload = verify_token(token)
        email = payload.get("sub")
        if not email:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception as e:
        await websocket.close(
            code=1008, reason=f"{str(e)}, sToken validation failed"
        )
        return
    await websocket.accept()

    task_id = websocket.scope["path_params"]["task_id"]

    async with broadcast.subscribe(channel=task_id) as subscriber:
        # just in case the task already finish
        data = get_task_info(task_id)
        await websocket.send_json(data)

        async for event in subscriber:
            await websocket.send_json(json.loads(event.message))


async def update_celery_task_status(task_id: str):
    """
    This function is called by Celery worker in task_postrun signal handler
    """
    await broadcast.connect()
    await broadcast.publish(
        channel=task_id,
        message=json.dumps(
            get_task_info(task_id)
        ),  # RedisProtocol.publish expect str
    )
    await broadcast.disconnect()


class TaskStatusNameSpace(AsyncNamespace):

    async def on_join(self, sid, data):
        # Validate token from cookies
        environ = self.get_environ(sid)
        cookie_header = environ.get("HTTP_COOKIE", "")
        cookies = {}
        if cookie_header:
            cookies = dict(
                item.split("=", 1)
                for item in cookie_header.split("; ")
                if "=" in item
            )

        token = cookies.get("access_token")

        if not token:
            await self.disconnect(sid)
            return

        try:
            verify_token(token)
        except Exception as e:
            print(str(e))
            await self.disconnect(sid)
            return
        self.enter_room(sid=sid, room=data["task_id"])
        # just in case the task already finish
        await self.emit(
            "status", get_task_info(data["task_id"]), room=data["task_id"]
        )


def register_socketio_app(app: FastAPI):
    mgr = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE)
    # https://python-socketio.readthedocs.io/en/latest/server.html#uvicorn-daphne-and-other-asgi-servers
    # https://github.com/tiangolo/fastapi/issues/129#issuecomment-714636723
    sio = socketio.AsyncServer(
        async_mode="asgi",
        client_manager=mgr,
        logger=True,
        engineio_logger=True,
    )
    sio.register_namespace(TaskStatusNameSpace("/task_status"))
    asgi = socketio.ASGIApp(
        socketio_server=sio,
    )
    app.mount("/ws", asgi)


def update_celery_task_status_socketio(task_id):
    """
    This function would be called in Celery worker
    https://python-socketio.readthedocs.io/en/latest/server.html#emitting-from-external-processes
    """
    # connect to the redis queue as an external process
    external_sio = socketio.RedisManager(
        settings.WS_MESSAGE_QUEUE, write_only=True
    )
    # emit an event
    external_sio.emit(
        "status",
        get_task_info(task_id),
        room=task_id,
        namespace="/task_status",
    )
