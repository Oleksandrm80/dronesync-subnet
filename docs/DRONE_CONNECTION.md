# DroneSync — Connecting a Real Drone

DroneSync supports any drone that speaks MAVLink protocol (ArduPilot, PX4).

## Connection options

### USB / Serial

    python3 demo_mavlink.py /dev/ttyUSB0
    python3 demo_mavlink.py /dev/ttyACM0

Find your device:

    ls /dev/tty*

### WiFi / UDP

    python3 demo_mavlink.py udp:192.168.1.10:14550

Default MAVLink UDP port is 14550.

### 4G / Remote

    python3 demo_mavlink.py udp:0.0.0.0:14550

### ArduPilot SITL (simulator)

    # Install ArduPilot
    git clone https://github.com/ArduPilot/ardupilot.git
    cd ardupilot && ./Tools/environment_install/install-prereqs-ubuntu.sh
    
    # Run SITL
    cd ArduCopter && sim_vehicle.py -v ArduCopter
    
    # Connect DroneSync
    python3 demo_mavlink.py udp:127.0.0.1:14550

### PX4 SITL (simulator)

    # Install PX4
    git clone https://github.com/PX4/PX4-Autopilot.git
    cd PX4-Autopilot && make px4_sitl gazebo
    
    # Connect DroneSync
    python3 demo_mavlink.py udp:127.0.0.1:14550

### Emulator (no drone, no simulator)

    python3 demo_mavlink.py --emulator

## What DroneSync reads from MAVLink

- GPS position (GLOBAL_POSITION_INT)
- Velocity (vx, vy, vz)
- Attitude (roll, pitch, yaw)
- Battery status
- Armed/disarmed state

## PoPW generation from real flight

    from dronesync.mavlink_adapter import MAVLinkAdapter
    
    adapter = MAVLinkAdapter("udp:127.0.0.1:14550")
    adapter.connect()
    trajectory, sensor_data = adapter.record_mission(duration_seconds=60)
    adapter.disconnect()
    
    # trajectory and sensor_data are ready for PoPW pipeline
