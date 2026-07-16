"""
Regression test: the dashboard's HTTP server is single-request-at-a-time
per connection (http.server), so _handle_camera_start must never block
indefinitely. cv2.VideoCapture() has no built-in connect timeout and can
hang forever on an unreachable/slow RTSP source -- this once froze the
entire dashboard (every client, not just the one that started the camera)
on the rented server for hours.
"""
import time
import dashboard.app as app


def test_camera_start_times_out_instead_of_hanging_forever(monkeypatch):
    class HangingCameraAdapter:
        def __init__(self, cfg):
            pass

        def start(self):
            time.sleep(30)
            return True

    class FakeVisionEngine:
        def __init__(self, *a, **kw):
            pass

        def start(self):
            return "yolov8"

    import dronesync.camera_adapter as camera_adapter
    import dronesync.vision_engine as vision_engine
    monkeypatch.setattr(camera_adapter, "CameraAdapter", HangingCameraAdapter)
    monkeypatch.setattr(vision_engine, "VisionEngine", FakeVisionEngine)

    start = time.time()
    result = app._handle_camera_start({"source": "rtsp", "address": "rtsp://unreachable-host/stream"})
    elapsed = time.time() - start

    assert elapsed < 10, f"handler blocked the request thread for {elapsed:.1f}s"
    assert result["ok"] is False
    assert "timed out" in result["error"].lower()
