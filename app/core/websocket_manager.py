from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger


logger = get_logger(__name__)


class WebSocketManager:
    def __init__(self):
        # 维护活跃连接列表
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict[str, Any]):
        """向所有连接广播消息"""
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send WS message: {e}")
                self.disconnect(connection)


# 全局单例
ws_manager = WebSocketManager()
