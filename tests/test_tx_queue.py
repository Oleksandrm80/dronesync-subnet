"""Tests for TxQueue — including a regression test for the submit_pending race fix."""
import threading
from dronesync.tx_queue import TxQueue


def make_queue(tmp_path):
    return TxQueue(db_path=str(tmp_path / "tx.db"))


def test_enqueue_skips_when_not_on_chain_ready(tmp_path):
    q = make_queue(tmp_path)
    result = q.enqueue({"on_chain_ready": False})
    assert result["status"] == "skipped"
    assert q.get_stats()["total"] == 0


def test_enqueue_queues_ready_transaction(tmp_path):
    q = make_queue(tmp_path)
    result = q.enqueue({
        "on_chain_ready": True, "mission_id": "M1",
        "trajectory_hash": "abc123", "score": 90, "bundle_hash": "def456",
    })
    assert result["status"] == "queued"
    stats = q.get_stats()
    assert stats["total"] == 1
    assert stats["pending"] == 1


def test_submit_pending_marks_transaction_submitted(tmp_path):
    q = make_queue(tmp_path)
    q.enqueue({"on_chain_ready": True, "mission_id": "M1", "score": 90})
    result = q.submit_pending()
    assert result["submitted"] == 1
    stats = q.get_stats()
    assert stats["submitted"] == 1
    assert stats["pending"] == 0


def test_get_pending_lists_unsubmitted(tmp_path):
    q = make_queue(tmp_path)
    q.enqueue({"on_chain_ready": True, "mission_id": "M1", "score": 90})
    pending = q.get_pending()
    assert len(pending) == 1
    assert pending[0]["mission_id"] == "M1"


def test_submit_pending_concurrent_does_not_double_submit(tmp_path):
    """Regression test: TxQueue._lock must actually guard submit_pending,
    otherwise concurrent callers can read and resubmit the same pending rows."""
    q = make_queue(tmp_path)
    for i in range(20):
        q.enqueue({"on_chain_ready": True, "mission_id": f"M{i}", "score": 90})

    results = []
    results_lock = threading.Lock()

    def _run():
        r = q.submit_pending()
        with results_lock:
            results.append(r)

    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_submitted_across_calls = sum(r["submitted"] for r in results)
    assert total_submitted_across_calls == 20
    stats = q.get_stats()
    assert stats["submitted"] == 20
    assert stats["pending"] == 0
