"""
DroneSync - Connector: links all drone sources to dashboard state.
Starts HTTP API, WebSocket, MQTT, MAVLink in background threads.
"""
import threading
import time
from dronesync.drone_registry import registry


def start_all(mavlink_port: int = 14550, http_port: int = 8081,
              ws_port: int = 8082, mqtt_broker: str = "localhost"):

    # HTTP API
    from dronesync.drone_api import run_api
    threading.Thread(target=run_api, kwargs={"port": http_port}, daemon=True).start()

    # WebSocket
    from dronesync.drone_websocket import run_websocket
    threading.Thread(target=run_websocket, kwargs={"port": ws_port}, daemon=True).start()

    # MQTT
    from dronesync.drone_mqtt import run_mqtt
    threading.Thread(target=run_mqtt, kwargs={"broker": mqtt_broker}, daemon=True).start()

    # MAVLink
    threading.Thread(target=_mavlink_listener, args=(mavlink_port,), daemon=True).start()

    # PoPW Export API
    from dronesync.popw_export import run_popw_api
    threading.Thread(target=run_popw_api, kwargs={"port": 8083}, daemon=True).start()

    print(f"[Connector] HTTP:{http_port} WS:{ws_port} MQTT:{mqtt_broker} MAVLink:{mavlink_port} PoPW:8083")


def _mavlink_listener(port: int = 14550):
    try:
        from pymavlink import mavutil
        while True:
            try:
                mav = mavutil.mavlink_connection(f"udpin:0.0.0.0:{port}", source_system=255)
                mav.wait_heartbeat(timeout=30)
                drone_id = f"MAV_{mav.target_system}_{mav.target_component}"
                registry.register(drone_id, source="mavlink")
                print(f"[Connector] MAVLink drone registered: {drone_id}")
                while True:
                    msg = mav.recv_match(
                        type=["GLOBAL_POSITION_INT", "VFR_HUD", "HEARTBEAT"],
                        blocking=True, timeout=5
                    )
                    if not msg:
                        continue
                    mt = msg.get_type()
                    telem = registry.get_drone(drone_id).get("telemetry", {})
                    if mt == "GLOBAL_POSITION_INT":
                        telem.update({
                            "lat": msg.lat / 1e7,
                            "lon": msg.lon / 1e7,
                            "alt": msg.relative_alt / 1000.0,
                        })
                    elif mt == "VFR_HUD":
                        telem.update({
                            "speed": round(msg.groundspeed, 2),
                            "heading": msg.heading,
                        })
                    elif mt == "HEARTBEAT":
                        telem["armed"] = bool(msg.base_mode & 0x80)
                    registry.update_telemetry(drone_id, telem)
            except Exception as e:
                print(f"[Connector] MAVLink lost: {e} — retry in 10s")
                time.sleep(10)
    except ImportError:
        print("[Connector] pymavlink not installed")


def get_dashboard_drones() -> dict:
    """Returns registry drones formatted for dashboard state."""
    active = registry.get_active_drones()
    result = {}
    for drone_id, d in active.items():
        t = d.get("telemetry", {})
        result[drone_id] = {
            "drone_id":       drone_id,
            "source":         d.get("source", "unknown"),
            "connected":      d.get("connected", False),
            "lat":            t.get("lat", 0.0),
            "lon":            t.get("lon", 0.0),
            "alt":            t.get("alt", 0.0),
            "speed":          t.get("speed", 0.0),
            "heading":        t.get("heading", 0),
            "armed":          t.get("armed", False),
            "last_seen":      d.get("last_seen", 0),
            "mavlink_live":   d.get("connected", False) and d.get("source") == "mavlink",
        }
    return result
