import asyncio
import json
import subprocess
import websockets
from datetime import datetime

CLIENTS = set()

async def broadcast(message):
    if CLIENTS:
        await asyncio.gather(*[client.send(message) for client in CLIENTS])

async def read_miner_logs():
    process = subprocess.Popen(
        ["docker", "logs", "knx-subnet-drone-navigation-subnet-miner-1", "-f", "--tail", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, process.stdout.readline)
        if not line:
            await asyncio.sleep(1)
            continue
        if "DRONE_MINER" in line:
            try:
                parts = line.strip().split()
                data = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "task": next((p.split("=")[1] for p in parts if p.startswith("task=")), ""),
                    "action_id": next((p.split("=")[1] for p in parts if p.startswith("action_id=")), ""),
                    "conf": next((p.split("=")[1] for p in parts if p.startswith("conf=")), ""),
                }
                await broadcast(json.dumps(data))
            except Exception as e:
                print(f"Parse error: {e}")

async def handler(websocket):
    CLIENTS.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        CLIENTS.discard(websocket)

async def main():
    print("WebSocket server starting on ws://localhost:8765")
    async with websockets.serve(handler, "localhost", 8765):
        await read_miner_logs()

if __name__ == "__main__":
    asyncio.run(main())
