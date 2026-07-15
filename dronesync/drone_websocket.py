"""
DroneSync - WebSocket server for real-time drone telemetry.
"""
import json
import time
import threading
import asyncio
from dronesync.drone_registry import registry


async def _handle_client(websocket):
    drone_id = None
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "register":
                    drone_id = data.get("drone_id")
                    registry.register(drone_id, source="websocket", metadata=data.get("metadata", {}))
                    await websocket.send(json.dumps({"status": "registered", "drone_id": drone_id}))

                elif msg_type == "telemetry":
                    drone_id = data.get("drone_id", drone_id)
                    registry.update_telemetry(drone_id, data)
                    await websocket.send(json.dumps({"status": "ok"}))

                elif msg_type == "heartbeat":
                    registry.heartbeat(drone_id)
                    await websocket.send(json.dumps({"status": "alive"}))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "invalid_json"}))
    finally:
        if drone_id:
            registry.unregister(drone_id)


def run_websocket(host: str = "0.0.0.0", port: int = 8082):
    try:
        import websockets

        async def _serve():
            async with websockets.serve(_handle_client, host, port):
                print(f"[DroneWS] WebSocket on {host}:{port}")
                await asyncio.Future()

        asyncio.run(_serve())
    except ImportError:
        print("[DroneWS] websockets not installed — skipping")


if __name__ == "__main__":
    run_websocket()
