"""
generate_test_tlog.py
Generates a realistic MAVLink telemetry log for testing.
Simulates a drone flying from Kyiv center to 500m north.
"""

import struct
import time
import math
import os

# MAVLink message IDs
GLOBAL_POSITION_INT = 33
ATTITUDE = 30
BATTERY_STATUS = 147
HEARTBEAT = 0

def pack_uint8(v): return struct.pack('B', v & 0xFF)
def pack_uint16(v): return struct.pack('<H', v & 0xFFFF)
def pack_uint32(v): return struct.pack('<I', v & 0xFFFFFFFF)
def pack_int16(v): return struct.pack('<h', v)
def pack_int32(v): return struct.pack('<i', v)
def pack_float(v): return struct.pack('<f', v)

def mavlink_checksum(data):
    crc = 0xFFFF
    for b in data:
        tmp = b ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF
    return crc

def write_frame(f, msg_id, payload, ts):
    # Write timestamp prefix (8 bytes, microseconds)
    ts_us = int(ts * 1e6)
    f.write(struct.pack('<Q', ts_us))
    
    seq = 0
    sys_id = 1
    comp_id = 1
    header = bytes([0xFE, len(payload), seq, sys_id, comp_id, msg_id])
    crc_extra = {GLOBAL_POSITION_INT: 104, ATTITUDE: 49,
                 BATTERY_STATUS: 154, HEARTBEAT: 50}
    data_for_crc = header[1:] + payload
    crc_input = data_for_crc + bytes([crc_extra.get(msg_id, 0)])
    crc = mavlink_checksum(crc_input)
    frame = header + payload + struct.pack('<H', crc)
    f.write(frame)

def generate_tlog(path, duration=30, hz=5):
    # Kyiv coordinates
    base_lat = 50.4501
    base_lon = 30.5234
    base_alt = 50.0

    n_frames = duration * hz
    
    with open(path, 'wb') as f:
        for i in range(n_frames):
            ts = time.time() - duration + i / hz
            progress = i / n_frames
            
            # Fly north 500m
            lat = base_lat + progress * 0.0045  # ~500m north
            lon = base_lon
            alt = base_alt + math.sin(progress * math.pi) * 20  # climb then descend
            vx = int(3.0 * 100)  # 3 m/s north
            vy = 0
            vz = 0
            hdg = 0

            # GLOBAL_POSITION_INT
            payload = (pack_uint32(int(ts * 1000)) +
                      pack_int32(int(lat * 1e7)) +
                      pack_int32(int(lon * 1e7)) +
                      pack_int32(int(alt * 1000)) +
                      pack_int32(int(alt * 1000)) +
                      pack_int16(vx) +
                      pack_int16(vy) +
                      pack_int16(vz) +
                      pack_uint16(hdg))
            write_frame(f, GLOBAL_POSITION_INT, payload, ts)

            # ATTITUDE
            roll = 0.02
            pitch = 0.01
            yaw = 0.0
            payload = (pack_uint32(int(ts * 1000)) +
                      pack_float(roll) +
                      pack_float(pitch) +
                      pack_float(yaw) +
                      pack_float(0.0) +
                      pack_float(0.0) +
                      pack_float(0.0))
            write_frame(f, ATTITUDE, payload, ts)

    print(f"Generated {n_frames} frames → {path}")
    print(f"File size: {os.path.getsize(path)} bytes")

if __name__ == "__main__":
    path = "zk/test_flight.tlog"
    generate_tlog(path, duration=30, hz=5)
