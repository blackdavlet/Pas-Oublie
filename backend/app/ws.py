import os, json, asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis

router = APIRouter()
_r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

async def broadcast_event(workspace_id: int, event: dict):
    await _r.publish(f"workspace:{workspace_id}", json.dumps(event))


@router.websocket("/ws/workspace/{workspace_id}")
async def ws_workspace(ws: WebSocket, workspace_id: int):
    await ws.accept()
    pubsub = _r.pubsub()
    await pubsub.subscribe(f"workspace:{workspace_id}")
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "message":
                continue
            await ws.send_text(msg["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"workspace:{workspace_id}")
        await pubsub.close()