"""
DroneSync - MQTT client for industrial drone telemetry.
"""
import json
import time
from dronesync.drone_registry import registry


def run_mqtt(broker: str = "localhost", port: int = 1883):
    try:
        import paho.mqtt.client as mqtt

        def on_connect(client, userdata, flags, rc):
            print(f"[DroneMQTT] Connected to broker {broker}:{port}")
            client.subscribe("dronesync/+/register")
            client.subscribe("dronesync/+/telemetry")
            client.subscribe("dronesync/+/heartbeat")

        def on_message(client, userdata, msg):
            try:
                topic_parts = msg.topic.split("/")
                if len(topic_parts) < 3:
                    return
                drone_id = topic_parts[1]
                action   = topic_parts[2]
                data     = json.loads(msg.payload.decode())

                if action == "register":
                    registry.register(drone_id, source="mqtt", metadata=data)
                    print(f"[DroneMQTT] Registered {drone_id}")
                elif action == "telemetry":
                    registry.update_telemetry(drone_id, data)
                elif action == "heartbeat":
                    registry.heartbeat(drone_id)
            except Exception as e:
                print(f"[DroneMQTT] Error: {e}")

        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(broker, port, 60)
        client.loop_forever()

    except ImportError:
        print("[DroneMQTT] paho-mqtt not installed — skipping")
    except Exception as e:
        print(f"[DroneMQTT] Could not connect to broker: {e}")


if __name__ == "__main__":
    run_mqtt()
