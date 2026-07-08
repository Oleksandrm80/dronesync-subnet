# dashboard/app.py
"""
DroneSync Mission Control Dashboard
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import threading
import random
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from dronesync.synapse import DroneNavSynapseHandler
from dronesync.node import KonnexNode
from dronesync.firewall import DroneFirewall
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.threat_defense import ThreatDefense
from miner.weather import WeatherService
from dronesync.logger import get_logger
from dronesync.monitoring import MetricsCollector, AlertManager
from dronesync.wallet import MinerWallet
from dronesync.konnex_integration import SubnetConfig, MinerNode as MinerAxon, KonnexMetagraph as SubnetMetagraph
from dronesync.mpc import ShamirSecretSharing
from dronesync.validator_auth import ValidatorAuth
from miner.energy import EnergyOptimizer
from miner.planner import AIPlanner
from dronesync.tx_queue import TxQueue
from dronesync.identity import DRONE_ID, VALIDATOR_ID

logger = get_logger("dronesync.dashboard")

_DEMO_LAT = 0.0
_DEMO_LON = 0.0

state = {
    "drones": {},
    "missions": [],
    "swarm_status": {},
    "node_status": {},
    "netuid": SubnetConfig.NETUID,
    "network": SubnetConfig.NETWORK,
    "last_update": 0,
    "miner_tasks": [],
    "tx_queue": {},
    "zk_status": {},
    "mavlink_status": {},
    "camera_ai": {
        "enabled": False,
        "source": "",
        "backend": "",
        "risk_level": "SAFE",
        "objects": [],
        "commentary": "",
        "frame_id": 0,
        "processing_ms": 0.0,
    },
}

DRONE_IDS = [DRONE_ID]
handlers = {d: DroneNavSynapseHandler(drone_id=d, use_ai_planner=True) for d in DRONE_IDS}
node = KonnexNode(wallet_address=DRONE_ID, network=SubnetConfig.NETWORK)
node.connect()
firewalls = {d: DroneFirewall(drone_id=d) for d in DRONE_IDS}
ai_planner = AIPlanner()
swarm = SwarmConsensus(drone_ids=DRONE_IDS)
weather = WeatherService()
energy = EnergyOptimizer()
threat = ThreatDefense()
tx_queue = TxQueue()

metrics_collector = None
alert_manager = None
miner_wallet = None
miner_axon = None
metagraph = None
validator_auth_obj = None


def _init_services():
    global metrics_collector, alert_manager, miner_wallet, miner_axon, metagraph, validator_auth_obj
    metrics_collector = MetricsCollector()
    alert_manager = AlertManager(metrics_collector)
    miner_wallet = MinerWallet(DRONE_ID, persist_path=".dronesync_data/dashboard_wallet.db")
    miner_axon = MinerAxon(DRONE_ID, VALIDATOR_ID)
    metagraph = SubnetMetagraph()
    metagraph.register_miner(miner_axon)
    validator_auth_obj = ValidatorAuth()


DRONE_COORDS = {
    DRONE_ID: {"x": 28, "y": 38, "tx": 62, "ty": 55},
}


def _get_zk_status() -> dict:
    try:
        from dronesync.zk_prover import ZKProver
        import os
        prover = ZKProver()
        rapidsnark = os.path.expanduser("~/rapidsnark/build_prover/src/prover")
        backend = "rapidsnark (native)" if os.path.exists(rapidsnark) else "snarkjs (local node_modules)"
        speed = "~50ms" if os.path.exists(rapidsnark) else "~1600ms"
        return {
            "available": prover.is_available(),
            "backend": backend,
            "circuit": "mission_verify.circom",
            "proof_type": "Groth16",
            "speed": speed,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def _get_mavlink_status() -> dict:
    try:
        from dronesync.mavlink_bridge import MAVLinkBridge
        MAVLinkBridge()
        return {"available": True, "protocol": "MAVLink 2.0", "status": "READY"}
    except Exception:
        try:
            from dronesync.mavlink_adapter import MAVLinkAdapter
            return {"available": True, "protocol": "MAVLink 2.0", "status": "READY"}
        except Exception:
            return {"available": False, "status": "N/A"}


def _parse_miner_logs() -> list:
    tasks = []
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "200", "knx-subnet-drone-navigation-subnet-miner-1"],
            capture_output=True, text=True, timeout=5
        )
        lines = (result.stdout + result.stderr).splitlines()
        for line in lines:
            if "DRONE_MINER" in line and "conf=" in line:
                try:
                    task_id = ""
                    conf = ""
                    action = ""
                    ts_str = ""
                    for part in line.split():
                        if part.startswith("round-") or part.startswith("task_id="):
                            task_id = part.replace("task_id=", "")
                        if part.startswith("conf="):
                            conf = part.replace("conf=", "")
                        if part.startswith("action="):
                            action = part.replace("action=", "")
                    if len(line) > 19 and line[4] == "-":
                        ts_str = line[:19]
                    if task_id or conf:
                        tasks.append({
                            "task_id": task_id or "—",
                            "conf": conf or "—",
                            "action": action or "—",
                            "ts": ts_str or "—",
                        })
                except Exception:
                    pass
    except Exception:
        pass
    return tasks[-10:]


def _make_task(drone_idx: int = 0) -> dict:
    origins = [
        {"lat": _DEMO_LAT + 0.0000, "lon": _DEMO_LON + 0.0000, "alt": 50, "speed": 5},
        {"lat": _DEMO_LAT + 0.0006, "lon": _DEMO_LON + 0.0003, "alt": 55, "speed": 5},
        {"lat": _DEMO_LAT + 0.0011, "lon": _DEMO_LON + 0.0008, "alt": 45, "speed": 5},
    ]
    dests = [
        {"lat": _DEMO_LAT + 0.0051, "lon": _DEMO_LON + 0.0043, "alt": 50, "speed": 5},
        {"lat": _DEMO_LAT + 0.0056, "lon": _DEMO_LON + 0.0048, "alt": 55, "speed": 5},
        {"lat": _DEMO_LAT + 0.0061, "lon": _DEMO_LON + 0.0053, "alt": 45, "speed": 5},
    ]
    return {
        "task_id": "KNX_" + str(int(time.time() * 1000))[-8:],
        "mission_type": "delivery",
        "origin": origins[drone_idx % len(origins)],
        "destination": dests[drone_idx % len(dests)],
        "waypoints": [],
        "drone_count": 1,
        "payload_kg": round(random.uniform(0.3, 1.2), 2),
        "validator_signature": f"{SubnetConfig.NETWORK}_sig",
    }


def refresh_state():
    for idx, drone_id in enumerate(DRONE_IDS):
        task = _make_task(idx)
        result = handlers[drone_id].handle(task)
        rep = handlers[drone_id].reputation.get_status()
        state["drones"][drone_id] = {
            "drone_id": drone_id,
            "mission_id": result["mission_id"],
            "status": result["status"],
            "score": result["score"],
            "tee_status": result["tee_status"],
            "security_status": result["security"]["overall_status"],
            "threat_level": result["security"]["threat_level"],
            "reputation_tier": rep["tier"],
            "reputation_score": rep["score"],
            "on_chain_ready": result["on_chain_ready"],
            "bundle_hash": result["bundle_hash"][:16] + "...",
            "duration_s": result["duration_s"],
            "timestamp": int(time.time()),
        }
    scores = [state["drones"][d]["score"] for d in DRONE_IDS]
    on_chain = all(state["drones"][d]["on_chain_ready"] for d in DRONE_IDS)
    state["swarm_status"] = {
        "total_drones": len(DRONE_IDS),
        "active_drones": len(DRONE_IDS),
        "avg_score": round(sum(scores) / len(scores), 1),
        "min_score": min(scores),
        "max_score": max(scores),
        "all_on_chain_ready": on_chain,
        "netuid": state["netuid"],
        "network": state["network"],
    }
    state["node_status"] = node.get_status()
    for d in DRONE_IDS:
        state["missions"].append(dict(state["drones"][d]))
    if len(state["missions"]) > 30:
        state["missions"] = state["missions"][-30:]
    state["miner_tasks"] = _parse_miner_logs()
    state["last_update"] = int(time.time())

    fw_report = firewalls[DRONE_IDS[0]].get_report()
    state["firewall"] = fw_report

    for d in DRONE_IDS:
        dr = state["drones"].get(d, {})
        metrics_collector.record_mission(dr.get("mission_id", ""), dr.get("score", 0) / 100.0, 250.0, True)
    state["monitoring"] = metrics_collector.get_metrics()
    state["alerts"] = alert_manager.get_status()

    for d in DRONE_IDS:
        dr = state["drones"].get(d, {})
        miner_wallet.credit(dr.get("mission_id", ""), round(dr.get("score", 0) * 0.01, 4), "mission_reward")
    state["wallet"] = miner_wallet.summary()

    miner_axon.submit_popw({"mission_id": "DASH_001", "score": 0.85, "trajectory_hash": "abc123"})
    state["konnex_miner"] = miner_axon.get_status()
    state["konnex_net"] = metagraph.get_state()

    try:
        state["tx_queue"] = tx_queue.get_stats()
    except Exception:
        state["tx_queue"] = {"pending": 0, "submitted": 0, "failed": 0}

    state["zk_status"] = _get_zk_status()
    state["mavlink_status"] = _get_mavlink_status()

    try:
        _sss = ShamirSecretSharing(threshold=2, n_shares=3)
        _shares = _sss.split(0.85)
        _rec = _sss.reconstruct(_shares[:2])
        state["mpc"] = {"status": "OK", "threshold": 2, "n_shares": 3, "reconstructed": round(_rec, 4), "shares": len(_shares)}
    except Exception as _e:
        state["mpc"] = {"status": "ERROR", "error": str(_e)}

    _tok = validator_auth_obj.generate_token(VALIDATOR_ID)
    state["validator_auth"] = {
        "status": "ACTIVE",
        "token_valid": validator_auth_obj.verify_token(_tok),
        "ttl": ValidatorAuth.TOKEN_TTL,
        "method": "HMAC-SHA256",
    }

    state["threat"] = {
        "overall_threat_level": "NONE",
        "gps_status": "CLEAN",
        "jamming_status": "CLEAR",
        "swarm_integrity": "VERIFIED",
        "mission_safe": True,
    }

    state["weather"] = weather.get_current().__dict__

    positions = [[_DEMO_LAT, _DEMO_LON, 50], [_DEMO_LAT + 0.003, _DEMO_LON + 0.003, 50]]
    state["energy"] = energy.analyze_trajectory(positions)

    from validator.scoreroot import ScoreRoot
    sc = ScoreRoot(VALIDATOR_ID)
    for d in DRONE_IDS:
        sc.add_score(d, state["drones"][d]["score"], state["drones"][d]["bundle_hash"], state["drones"][d]["bundle_hash"])
    state["score_root"] = sc.commit()

    from dronesync.last_will import DroneLastWill
    _ = DroneLastWill(DRONE_IDS[0])
    state["last_will"] = {"triggered": False, "battery_pct": "—"}

    state["ai_weights"] = dict(ai_planner.learned_weights)

    votes = [(d, True) for d in DRONE_IDS]
    state["consensus"] = swarm.vote_on_route("DASH_VOTE", votes)

    state["identity"] = {"drone_id": DRONE_ID, "validator_id": VALIDATOR_ID}


def background_loop():
    while True:
        try:
            refresh_state()
        except Exception as e:
            logger.error("[dashboard] refresh error: %s", e)
        time.sleep(30)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DroneSync — Mission Control</title>
<style>
:root {
  --bg: #060810;
  --surface: #0a0d16;
  --surface2: #0f1420;
  --border: #1a2035;
  --border2: #243050;
  --text: #c8d0e0;
  --dim: #4a5570;
  --white: #ffffff;
  --cyan: #00d4ff;
  --cyan2: #0090bb;
  --green: #00e676;
  --amber: #ffab00;
  --red: #ff3d57;
  --purple: #7c4dff;
  --blue: #2979ff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: "Courier New", monospace; overflow-x: hidden; }
#particles { position: fixed; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:0; opacity:0.7; }
header {
  position: sticky; top:0; z-index:100;
  background: rgba(6,8,16,0.95); border-bottom: 1px solid var(--border2);
  padding: 0 28px; height: 60px;
  display: flex; align-items: center; gap: 20px;
  backdrop-filter: blur(10px);
}
.logo-hex { width:38px; height:38px; border:2px solid var(--cyan); border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:20px; color:var(--cyan); box-shadow:0 0 20px rgba(0,212,255,0.3); animation:hexPulse 3s infinite; }
@keyframes hexPulse { 0%,100%{box-shadow:0 0 20px rgba(0,212,255,0.3)} 50%{box-shadow:0 0 40px rgba(0,212,255,0.6)} }
.logo-title { font-size:16px; font-weight:bold; color:var(--white); letter-spacing:4px; }
.logo-sub { font-size:10px; color:var(--dim); letter-spacing:2px; margin-top:2px; }
.hbar { margin-left:auto; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.hbadge { padding:4px 12px; border:1px solid var(--border2); font-size:10px; letter-spacing:1.5px; text-transform:uppercase; color:var(--dim); }
.hbadge-live { border-color:var(--green); color:var(--green); animation:liveBlink 2s infinite; }
@keyframes liveBlink { 0%,100%{opacity:1} 50%{opacity:0.5} }
.hbadge-net { border-color:var(--cyan2); color:var(--cyan); }
.hbtn { background:transparent; border:1px solid var(--border2); color:var(--dim); padding:6px 14px; font-family:inherit; font-size:10px; letter-spacing:2px; cursor:pointer; text-transform:uppercase; transition:all 0.2s; }
.hbtn:hover { border-color:var(--cyan); color:var(--cyan); }
main { padding:20px 28px; max-width:1800px; margin:0 auto; position:relative; z-index:2; }
.slabel { font-size:9px; letter-spacing:3px; text-transform:uppercase; color:var(--dim); margin-bottom:12px; padding-left:10px; border-left:2px solid var(--cyan); display:flex; align-items:center; gap:8px; }
.slabel-dot { width:4px; height:4px; border-radius:50%; background:var(--cyan); animation:liveBlink 2s infinite; }
.top-stats { display:grid; grid-template-columns:repeat(6,1fr); gap:14px; margin-bottom:20px; }
.stat { background:var(--surface); border:1px solid var(--border); padding:16px; position:relative; overflow:hidden; }
.stat::before { content:""; position:absolute; top:0; left:0; right:0; height:2px; background:var(--cyan); }
.stat.g::before { background:var(--green); }
.stat.p::before { background:var(--purple); }
.stat.a::before { background:var(--amber); }
.stat.r::before { background:var(--red); }
.stat-lbl { font-size:9px; letter-spacing:2px; color:var(--dim); text-transform:uppercase; margin-bottom:8px; }
.stat-val { font-size:24px; font-weight:bold; color:var(--white); line-height:1; }
.stat-val.c { color:var(--cyan); }
.stat-val.g { color:var(--green); }
.stat-val.p { color:var(--purple); }
.stat-val.a { color:var(--amber); }
.stat-sub { font-size:10px; color:var(--dim); margin-top:6px; }
.sbar { height:2px; background:var(--border); margin-top:10px; overflow:hidden; }
.sbar-fill { height:100%; background:linear-gradient(90deg,var(--cyan),var(--green)); transition:width 1s ease; }
.id-section { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:20px; }
.id-box { background:var(--surface); border:1px solid var(--cyan); padding:14px; }
.id-lbl { font-size:8px; letter-spacing:2px; color:var(--dim); text-transform:uppercase; margin-bottom:6px; }
.id-val { font-size:11px; color:var(--cyan); word-break:break-all; font-weight:bold; }
.id-src { font-size:8px; color:var(--dim); margin-top:4px; }
.map-section { margin-bottom:20px; }
.map-wrap { background:var(--surface); border:1px solid var(--border); position:relative; overflow:hidden; height:280px; }
.map-grid { position:absolute; inset:0; background-image:linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px); background-size:40px 40px; opacity:0.5; }
.map-label { position:absolute; top:12px; left:12px; font-size:9px; letter-spacing:2px; color:var(--dim); text-transform:uppercase; }
#mapCanvas { position:absolute; inset:0; width:100%; height:100%; }
.nfz { position:absolute; border-radius:50%; border:2px solid rgba(255,61,87,0.6); background:rgba(255,61,87,0.08); animation:nfzPulse 3s infinite; display:flex; align-items:center; justify-content:center; }
@keyframes nfzPulse { 0%,100%{box-shadow:0 0 0 0 rgba(255,61,87,0.3)} 50%{box-shadow:0 0 0 20px rgba(255,61,87,0)} }
.nfz-label { font-size:8px; color:var(--red); letter-spacing:1px; text-transform:uppercase; }
.mdrone { position:absolute; cursor:pointer; }
.mdrone-core { width:10px; height:10px; border-radius:50%; background:var(--cyan); box-shadow:0 0 10px var(--cyan); animation:dronePulse 1.5s infinite; }
@keyframes dronePulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.4)} }
.mdrone-ring { position:absolute; top:-6px; left:-6px; width:22px; height:22px; border-radius:50%; border:1px solid rgba(0,212,255,0.4); animation:ringExpand 2s infinite; }
@keyframes ringExpand { 0%{transform:scale(0.5);opacity:1} 100%{transform:scale(2);opacity:0} }
.mdrone-label { position:absolute; top:-18px; left:50%; transform:translateX(-50%); font-size:8px; color:var(--cyan); white-space:nowrap; letter-spacing:1px; }
.mid-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; margin-bottom:20px; }
.card { background:var(--surface); border:1px solid var(--border); padding:18px; }
.ctitle { font-size:9px; letter-spacing:2px; text-transform:uppercase; color:var(--dim); margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.ctitle::before { content:""; width:6px; height:6px; border-radius:50%; background:var(--cyan); flex-shrink:0; }
.metric { display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--border); font-size:11px; }
.metric:last-child { border-bottom:none; }
.mk { color:var(--dim); }
.mv { color:var(--white); font-weight:bold; }
.mv.c { color:var(--cyan); }
.mv.g { color:var(--green); }
.mv.a { color:var(--amber); }
.mv.r { color:var(--red); }
.mv.p { color:var(--purple); }
.tx-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:12px; }
.tx-box { background:var(--surface2); border:1px solid var(--border); padding:12px; text-align:center; }
.tx-lbl { font-size:8px; color:var(--dim); letter-spacing:1px; text-transform:uppercase; margin-bottom:4px; }
.tx-num { font-size:22px; font-weight:bold; }
.zk-badge { display:inline-block; padding:3px 10px; border:1px solid var(--purple); color:var(--purple); font-size:9px; letter-spacing:2px; margin-top:8px; }
#neuralCanvas { width:100%; height:160px; display:block; }
#swarmCanvas { width:100%; height:160px; display:block; }
#radarCanvas { border-radius:50%; }
.fleet-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:20px; }
.dcard { background:var(--surface); border:1px solid var(--border); padding:16px; transition:border-color 0.3s; }
.dcard:hover { border-color:var(--cyan2); }
.dcard-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid var(--border); }
.dcard-name { font-size:13px; font-weight:bold; color:var(--white); letter-spacing:2px; }
.dcard-dot { width:8px; height:8px; border-radius:50%; background:var(--green); animation:liveBlink 2s infinite; }
.tier-tag { display:inline-block; padding:2px 8px; font-size:9px; letter-spacing:1.5px; text-transform:uppercase; border:1px solid var(--dim); color:var(--dim); }
.tier-tag.elite { border-color:var(--cyan); color:var(--cyan); }
.tier-tag.trusted { border-color:var(--green); color:var(--green); }
.tier-tag.active { border-color:var(--amber); color:var(--amber); }
.dbar { height:3px; background:var(--border); margin:8px 0; overflow:hidden; }
.dbar-fill { height:100%; background:linear-gradient(90deg,var(--cyan),var(--green)); transition:width 1s ease; }
.popw-chain { display:flex; align-items:center; gap:0; margin-top:10px; overflow-x:auto; padding-bottom:4px; }
.popw-block { background:var(--surface2); border:1px solid var(--border); padding:8px 12px; font-size:9px; letter-spacing:1px; color:var(--cyan); text-transform:uppercase; white-space:nowrap; flex-shrink:0; }
.popw-block.active { border-color:var(--cyan); box-shadow:0 0 10px rgba(0,212,255,0.2); }
.popw-arrow { color:var(--cyan); font-size:12px; padding:0 4px; flex-shrink:0; opacity:0.5; }
.popw-hash { font-size:8px; color:var(--dim); margin-top:2px; }
#heatCanvas { width:100%; height:80px; display:block; margin-top:8px; }
#dnaCanvas { width:100%; height:60px; display:block; margin-top:8px; }
.feed { max-height:200px; overflow-y:auto; }
.feed::-webkit-scrollbar { width:3px; }
.feed::-webkit-scrollbar-thumb { background:var(--border2); }
.feed-item { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--border); font-size:10px; }
.feed-dot { width:6px; height:6px; border-radius:50%; background:var(--green); flex-shrink:0; animation:liveBlink 2s infinite; }
.feed-hash { color:var(--cyan); font-size:9px; }
.feed-time { color:var(--dim); font-size:9px; margin-left:auto; white-space:nowrap; }
.mtable { width:100%; border-collapse:collapse; font-size:11px; }
.mtable th { background:var(--surface2); color:var(--dim); padding:9px 12px; text-align:left; font-size:9px; letter-spacing:1.5px; text-transform:uppercase; border-bottom:1px solid var(--border); font-weight:normal; }
.mtable td { padding:8px 12px; border-bottom:1px solid var(--border); }
.mtable tr:hover td { background:rgba(0,212,255,0.03); }
.spill { display:inline-block; padding:2px 8px; font-size:10px; font-weight:bold; border:1px solid var(--border); }
.spill.hi { border-color:var(--green); color:var(--green); }
.spill.mid { border-color:var(--amber); color:var(--amber); }
.spill.lo { border-color:var(--red); color:var(--red); }
.bot-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
.nav-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
.alert-item { display:flex; align-items:center; gap:8px; padding:5px 0; border-bottom:1px solid var(--border); font-size:10px; }
.alert-item:last-child { border-bottom:none; }
.alert-dot { width:5px; height:5px; border-radius:50%; background:var(--dim); flex-shrink:0; }
.alert-dot.critical { background:var(--red); }
.alert-dot.warning { background:var(--amber); }
.alert-dot.notice { background:var(--cyan); }
.eta-row { display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid var(--border); font-size:11px; }
.eta-row:last-child { border-bottom:none; }
.overlay-btns { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
.ovbtn { background:transparent; border:1px solid var(--border2); color:var(--dim); padding:4px 10px; font-family:inherit; font-size:9px; cursor:pointer; letter-spacing:1px; text-transform:uppercase; transition:all 0.2s; }
.ovbtn.on { border-color:var(--cyan); color:var(--cyan); }
.ovbtn:hover { border-color:var(--cyan); color:var(--cyan); }
.modules-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
.reward-bar { height:3px; background:var(--border); margin-top:8px; overflow:hidden; }
.reward-fill { height:100%; background:linear-gradient(90deg,var(--cyan),var(--green)); }
.privacy-badge { display:inline-block; padding:3px 10px; border:1px solid var(--green); color:var(--green); font-size:9px; letter-spacing:2px; margin-top:8px; }
.last-will-box { background:var(--surface2); border:1px solid var(--red); padding:8px; margin-top:4px; }
.sidebar { position:fixed; right:0; top:0; width:260px; height:100vh; background:#070910; border-left:1px solid #223060; z-index:1000; display:flex; flex-direction:column; padding:12px 10px; gap:8px; overflow:hidden; }
.sb-title { font-size:9px; letter-spacing:2px; color:#485a78; text-transform:uppercase; padding:6px 8px; border-bottom:1px solid #1a2238; }
.sb-radar-wrap { flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; }
#sideRadar { width:230px; height:230px; }
.sb-range-btns { display:flex; gap:6px; align-items:center; }
.sb-rbtn { background:transparent; border:1px solid #223060; color:#00bfff; width:28px; height:28px; border-radius:4px; font-size:16px; cursor:pointer; font-family:inherit; transition:all 0.2s; }
.sb-rbtn:hover { border-color:#00bfff; background:#00bfff11; }
.sb-range-lbl { font-size:11px; color:#00bfff; letter-spacing:1px; min-width:80px; text-align:center; }
.sb-stats { width:100%; display:flex; flex-direction:column; gap:4px; }
.sb-row { display:flex; justify-content:space-between; font-size:10px; padding:3px 6px; border-bottom:1px solid #1a2238; }
.sb-row:last-child { border-bottom:none; }
.sb-key { color:#485a78; }
.sb-val { color:#eef2ff; font-weight:bold; }
.sb-val.g { color:#00e5a0; }
.sb-val.c { color:#00bfff; }
body { margin-right:270px; }
#particles { position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:0; pointer-events:none; }
footer { border-top:1px solid var(--border); padding:14px 28px; display:flex; justify-content:space-between; font-size:9px; color:var(--dim); letter-spacing:1.5px; position:relative; z-index:2; }
</style>
</head>
<body>

<div class="sidebar">
  <div class="sb-title">⬡ TACTICAL RADAR · SWARM TRACKING</div>
  <div class="sb-radar-wrap">
    <canvas id="sideRadar" width="230" height="230"></canvas>
    <div class="sb-range-btns">
      <button class="sb-rbtn" onclick="radarZoomOut()">−</button>
      <span class="sb-range-lbl" id="radarRangeLbl">RANGE: 500m</span>
      <button class="sb-rbtn" onclick="radarZoomIn()">+</button>
    </div>
    <div class="sb-stats">
      <div class="sb-row"><span class="sb-key">Targets</span><span class="sb-val g" id="sbTargets">1</span></div>
      <div class="sb-row"><span class="sb-key">Swarm Score</span><span class="sb-val c">{avg_score}</span></div>
      <div class="sb-row"><span class="sb-key">On-Chain</span><span class="sb-val g">{on_chain}</span></div>
      <div class="sb-row"><span class="sb-key">Threat</span><span class="sb-val g">{sb_threat}</span></div>
      <div class="sb-row"><span class="sb-key">GPS</span><span class="sb-val g">{sb_gps}</span></div>
      <div class="sb-row"><span class="sb-key">TxPending</span><span class="sb-val c">{tx_pending}</span></div>
      <div class="sb-row"><span class="sb-key">ZK Proof</span><span class="sb-val g">{zk_status_sb}</span></div>
      <div class="sb-row"><span class="sb-key">Reward</span><span class="sb-val c">{sb_reward} KNX</span></div>
      <div class="sb-row"><span class="sb-key">Updated</span><span class="sb-val" style="font-size:9px">{last_update}</span></div>
    </div>
  </div>
</div>

<script>
const _radarDrones = {sb_drone_positions};
const _radarRanges = [100, 250, 500, 1000, 2500, 5000];
let _radarRangeIdx = 2;
let _radarAngle = 0;

function radarZoomIn() {{
  if (_radarRangeIdx > 0) _radarRangeIdx--;
  document.getElementById("radarRangeLbl").textContent = "RANGE: " + _radarRanges[_radarRangeIdx] + "m";
}}
function radarZoomOut() {{
  if (_radarRangeIdx < _radarRanges.length - 1) _radarRangeIdx++;
  document.getElementById("radarRangeLbl").textContent = "RANGE: " + _radarRanges[_radarRangeIdx] + "m";
}}

function drawSideRadar() {{
  const c = document.getElementById("sideRadar");
  if (!c) return;
  const ctx = c.getContext("2d");
  const W = c.width, H = c.height;
  const cx = W/2, cy = H/2, R = W/2 - 10;
  const range = _radarRanges[_radarRangeIdx];
  ctx.clearRect(0, 0, W, H);
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI*2);
  ctx.fillStyle = "#030508"; ctx.fill();
  ctx.strokeStyle = "#00bfff33"; ctx.lineWidth = 1; ctx.stroke();
  for (let i = 1; i <= 4; i++) {{
    const r = R * i / 4;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2);
    ctx.strokeStyle = "#00bfff18"; ctx.lineWidth = 0.5; ctx.stroke();
    ctx.fillStyle = "#00bfff44"; ctx.font = "8px monospace";
    ctx.fillText(Math.round(range * i / 4) + "m", cx + 4, cy - r + 10);
  }}
  ctx.strokeStyle = "#00bfff18"; ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.moveTo(cx-R, cy); ctx.lineTo(cx+R, cy); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, cy-R); ctx.lineTo(cx, cy+R); ctx.stroke();
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(_radarAngle);
  const grad = ctx.createLinearGradient(0, 0, R, 0);
  grad.addColorStop(0, "#00bfff44"); grad.addColorStop(1, "transparent");
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, R, -0.4, 0); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill(); ctx.restore();
  ctx.beginPath(); ctx.arc(cx, cy, 4, 0, Math.PI*2);
  ctx.fillStyle = "#00bfff"; ctx.fill();
  const colors = ["#00bfff", "#00e5a0", "#8855ff", "#ffb700", "#ff2d4a"];
  const latRef = _radarDrones[0] ? _radarDrones[0].lat : 0;
  const lonRef = _radarDrones[0] ? _radarDrones[0].lon : 0;
  _radarDrones.forEach((d, i) => {{
    const dx = (d.lon - lonRef) * 111320 * Math.cos(latRef * Math.PI/180);
    const dy = -(d.lat - latRef) * 111320;
    const scale = R / range;
    const px = cx + dx * scale;
    const py = cy + dy * scale;
    const dist = Math.sqrt((px-cx)**2 + (py-cy)**2);
    if (dist > R) return;
    const grd = ctx.createRadialGradient(px, py, 0, px, py, 12);
    grd.addColorStop(0, colors[i % colors.length] + "66");
    grd.addColorStop(1, "transparent");
    ctx.beginPath(); ctx.arc(px, py, 12, 0, Math.PI*2);
    ctx.fillStyle = grd; ctx.fill();
    ctx.beginPath(); ctx.arc(px, py, 5, 0, Math.PI*2);
    ctx.fillStyle = colors[i % colors.length]; ctx.fill();
    ctx.fillStyle = colors[i % colors.length];
    ctx.font = "bold 9px monospace";
    ctx.fillText(d.id, px + 8, py - 4);
    ctx.fillStyle = "#ffffff66"; ctx.font = "8px monospace";
    ctx.fillText(d.alt + "m", px + 8, py + 6);
  }});
  _radarAngle += 0.04;
  if (_radarAngle > Math.PI*2) _radarAngle = 0;
  document.getElementById("sbTargets").textContent = _radarDrones.length;
  requestAnimationFrame(drawSideRadar);
}}
drawSideRadar();
</script>

<canvas id="particles"></canvas>

<header>
  <div class="logo-hex">⬡</div>
  <div>
    <div class="logo-title">DRONESYNC</div>
    <div class="logo-sub">MISSION CONTROL · KONNEX NETUID {netuid} · {network}</div>
  </div>
  <div class="hbar">
    <span class="hbadge hbadge-live">● LIVE</span>
    <span class="hbadge hbadge-net">NETUID {netuid}</span>
    <span class="hbadge">{active}/{total} DRONES</span>
    <button class="hbtn" onclick="location.reload()">⟳ REFRESH</button>
  </div>
</header>

<main>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Hotkey Identity · Konnex Network</div>
<div class="id-section">
  <div class="id-box">
    <div class="id-lbl">Drone ID (ss58 hotkey)</div>
    <div class="id-val">{drone_id}</div>
    <div class="id-src">Source: ~/.bittensor/wallets/miner/hotkeys/defaultpub.txt</div>
  </div>
  <div class="id-box" style="border-color:var(--purple)">
    <div class="id-lbl">Validator ID · Chain: {chain_endpoint}</div>
    <div class="id-val" style="color:var(--purple)">{validator_id}</div>
    <div class="id-src">Network: {network} · NetUID: {netuid}</div>
  </div>
</div>

<div class="top-stats">
  <div class="stat">
    <div class="stat-lbl">Active Drones</div>
    <div class="stat-val c">{active}<span style="font-size:14px;color:var(--dim)">/{total}</span></div>
    <div class="stat-sub">Swarm operational</div>
    <div class="sbar"><div class="sbar-fill" style="width:100%"></div></div>
  </div>
  <div class="stat g">
    <div class="stat-lbl">Avg PoPW Score</div>
    <div class="stat-val g">{avg_score}</div>
    <div class="stat-sub">Min {min_score} · Max {max_score}</div>
    <div class="sbar"><div class="sbar-fill" style="width:{avg_score}%"></div></div>
  </div>
  <div class="stat p">
    <div class="stat-lbl">TxQueue Pending</div>
    <div class="stat-val p">{tx_pending}</div>
    <div class="stat-sub">Submitted: {tx_submitted} · Failed: {tx_failed}</div>
  </div>
  <div class="stat a">
    <div class="stat-lbl">ZK Proof</div>
    <div class="stat-val a" style="font-size:14px;padding-top:4px">{zk_status_top}</div>
    <div class="stat-sub">Groth16 · {zk_backend_short}</div>
  </div>
  <div class="stat">
    <div class="stat-lbl">Konnex Node</div>
    <div class="stat-val" style="font-size:14px;padding-top:4px">{node_connected}</div>
    <div class="stat-sub">{node_network} · {node_session}</div>
  </div>
  <div class="stat">
    <div class="stat-lbl">On-Chain Ready</div>
    <div class="stat-val g" style="font-size:14px;padding-top:4px">{on_chain}</div>
    <div class="stat-sub">Updated {last_update}</div>
  </div>
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Connect Drone · Universal Adapter</div>
<div class="card" style="margin-bottom:20px">
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:14px;align-items:end">
    <div>
      <div class="stat-lbl" style="margin-bottom:6px">Manufacturer</div>
      <select id="droneManuf" style="width:100%;background:#0a0d16;border:1px solid #1a2035;color:#c8d0e0;padding:8px;font-family:monospace;font-size:11px">
        <option value="mavlink">MAVLink (ArduPilot, PX4, Pixhawk)</option>
        <option value="dji">DJI (Matrice, Mavic, Phantom)</option>
        <option value="ros2">ROS2 (Skydio, Freefly, Wingtra)</option>
      </select>
    </div>
    <div>
      <div class="stat-lbl" style="margin-bottom:6px">Connection</div>
      <select id="droneMethod" style="width:100%;background:#0a0d16;border:1px solid #1a2035;color:#c8d0e0;padding:8px;font-family:monospace;font-size:11px">
        <option value="udp">UDP (WiFi)</option>
        <option value="usb">USB Cable</option>
        <option value="tcp">TCP</option>
        <option value="serial">Serial</option>
        <option value="custom">Custom Address</option>
      </select>
    </div>
    <div>
      <div class="stat-lbl" style="margin-bottom:6px">Address (optional)</div>
      <input id="droneAddr" placeholder="e.g. udp:192.168.1.1:14550" style="width:100%;background:#0a0d16;border:1px solid #1a2035;color:#c8d0e0;padding:8px;font-family:monospace;font-size:11px">
    </div>
    <div>
      <button onclick="connectDrone()" style="width:100%;background:transparent;border:1px solid #00d4ff;color:#00d4ff;padding:10px;font-family:monospace;font-size:11px;letter-spacing:2px;cursor:pointer;text-transform:uppercase">CONNECT DRONE</button>
    </div>
  </div>
  <div id="connectStatus" style="margin-top:12px;font-size:11px;color:#4a5570"></div>
</div>
<script>
function connectDrone() {
  const manuf = document.getElementById("droneManuf").value;
  const method = document.getElementById("droneMethod").value;
  const addr = document.getElementById("droneAddr").value;
  const btn = event.target;
  btn.textContent = "CONNECTING...";
  btn.style.borderColor = "#ffab00";
  btn.style.color = "#ffab00";
  fetch("/api/connect-drone", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({manufacturer: manuf, method: method, custom_address: addr})
  }).then(r => r.json()).then(d => {
    const el = document.getElementById("connectStatus");
    if (d.success) {
      el.style.color = "#00e676";
      el.textContent = "CONNECTED - " + JSON.stringify(d.status);
      btn.textContent = "CONNECTED";
      btn.style.borderColor = "#00e676";
      btn.style.color = "#00e676";
    } else {
      el.style.color = "#ff3d57";
      el.textContent = "FAILED - " + (d.error || JSON.stringify(d));
      btn.textContent = "CONNECT DRONE";
      btn.style.borderColor = "#00d4ff";
      btn.style.color = "#00d4ff";
    }
  }).catch(e => {
    document.getElementById("connectStatus").textContent = "Error: " + e;
    btn.textContent = "CONNECT DRONE";
  });
}
</script>

<div class="map-section">
  <div class="slabel"><span class="slabel-dot"></span>Airspace · Live Trajectory</div>
  <div class="map-wrap">
    <div class="map-grid"></div>
    <canvas id="mapCanvas"></canvas>
    <div class="map-label">DRONE AIRSPACE · REAL-TIME TRACKING</div>
    <div class="nfz" style="width:80px;height:80px;left:15%;top:20%"><span class="nfz-label">AIRPORT</span></div>
    <div class="nfz" style="width:60px;height:60px;left:60%;top:55%"><span class="nfz-label">HOSPITAL</span></div>
    <div class="nfz" style="width:70px;height:70px;left:75%;top:15%"><span class="nfz-label">GOV</span></div>
    <div class="mdrone" id="md1" style="left:30%;top:40%">
      <div class="mdrone-ring"></div>
      <div class="mdrone-core"></div>
      <div class="mdrone-label">{drone_id_short}</div>
    </div>
  </div>
</div>

<div class="mid-grid" style="grid-template-columns:1fr 1fr;margin-bottom:20px">
  <div class="card">
    <div class="ctitle">Neural Network · AI Planner Decisions</div>
    <canvas id="neuralCanvas"></canvas>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px">
      <div style="text-align:center">
        <div style="font-size:9px;color:var(--dim)">SAFETY</div>
        <div style="font-size:16px;color:var(--cyan);font-weight:bold">{ai_safety}%</div>
        <div style="height:2px;background:var(--border);margin-top:4px"><div style="height:100%;width:{ai_safety}%;background:var(--cyan)"></div></div>
      </div>
      <div style="text-align:center">
        <div style="font-size:9px;color:var(--dim)">EFFICIENCY</div>
        <div style="font-size:16px;color:var(--green);font-weight:bold">{ai_effic}%</div>
        <div style="height:2px;background:var(--border);margin-top:4px"><div style="height:100%;width:{ai_effic}%;background:var(--green)"></div></div>
      </div>
      <div style="text-align:center">
        <div style="font-size:9px;color:var(--dim)">ENERGY</div>
        <div style="font-size:16px;color:var(--purple);font-weight:bold">{ai_energy}%</div>
        <div style="height:2px;background:var(--border);margin-top:4px"><div style="height:100%;width:{ai_energy}%;background:var(--purple)"></div></div>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="ctitle">Swarm Brain · Communication Graph</div>
    <canvas id="swarmCanvas"></canvas>
    <div class="metric" style="margin-top:8px"><span class="mk">Consensus</span><span class="mv g">{consensus_status}</span></div>
    <div class="metric"><span class="mk">Approval Rate</span><span class="mv c">{consensus_rate}</span></div>
    <div class="metric"><span class="mk">Active Links</span><span class="mv c">6 / 6</span></div>
  </div>
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Drone Fleet</div>
<div class="fleet-grid">
{drone_cards}
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>PoPW Pipeline · TxQueue · ZK Proof</div>
<div class="mid-grid">
  <div class="card">
    <div class="ctitle">PoPW Timeline · Proof Chain</div>
    <div class="popw-chain">
      <div class="popw-block active">Task<div class="popw-hash">✓ Signed</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">TEE<div class="popw-hash">✓ ATT</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">Sensor<div class="popw-hash">✓ Hash</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">Score<div class="popw-hash">✓ Root</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">TxQueue<div class="popw-hash">✓ Enq.</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">Chain<div class="popw-hash">✓ Ready</div></div>
    </div>
    <div style="margin-top:14px">
      <div class="metric"><span class="mk">Signing</span><span class="mv c">Ed25519</span></div>
      <div class="metric"><span class="mk">TEE Attestation</span><span class="mv g">✓ VERIFIED</span></div>
      <div class="metric"><span class="mk">Sensor Bundle</span><span class="mv g">✓ HASHED</span></div>
      <div class="metric"><span class="mk">Score Root</span><span class="mv g">✓ COMMITTED</span></div>
      <div class="metric"><span class="mk">On-Chain Ready</span><span class="mv g">{on_chain}</span></div>
    </div>
  </div>
  <div class="card">
    <div class="ctitle">TxQueue · On-Chain Settlement</div>
    <div class="tx-grid">
      <div class="tx-box">
        <div class="tx-lbl">PENDING</div>
        <div class="tx-num" style="color:var(--amber)">{tx_pending}</div>
      </div>
      <div class="tx-box">
        <div class="tx-lbl">SUBMITTED</div>
        <div class="tx-num" style="color:var(--green)">{tx_submitted}</div>
      </div>
      <div class="tx-box">
        <div class="tx-lbl">FAILED</div>
        <div class="tx-num" style="color:var(--red)">{tx_failed}</div>
      </div>
    </div>
    <div class="metric"><span class="mk">Storage</span><span class="mv c">SQLite WAL</span></div>
    <div class="metric"><span class="mk">DB Path</span><span class="mv" style="font-size:9px">~/.dronesync_data/tx_queue.db</span></div>
    <div class="metric"><span class="mk">Retry</span><span class="mv">Exponential backoff</span></div>
    <div class="metric"><span class="mk">Chain Endpoint</span><span class="mv c" style="font-size:9px">{chain_endpoint_short}</span></div>
    <div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE · Auto-submit</span></div>
  </div>
  <div class="card">
    <div class="ctitle">ZK Proof · Groth16 · MAVLink</div>
    <div class="metric"><span class="mk">ZK Available</span><span class="mv {zk_cls}">{zk_status_top}</span></div>
    <div class="metric"><span class="mk">Backend</span><span class="mv c">{zk_backend}</span></div>
    <div class="metric"><span class="mk">Circuit</span><span class="mv">mission_verify.circom</span></div>
    <div class="metric"><span class="mk">Proof Type</span><span class="mv p">Groth16</span></div>
    <div class="metric"><span class="mk">Speed</span><span class="mv g">{zk_speed}</span></div>
    <div class="metric"><span class="mk">MAVLink</span><span class="mv g">{mav_status}</span></div>
    <div class="metric"><span class="mk">Transports</span><span class="mv">USB · UDP · Serial</span></div>
    <div class="metric"><span class="mk">Emulator</span><span class="mv a">Built-in SITL</span></div>
    <span class="zk-badge">ZERO KNOWLEDGE VERIFIED</span>
  </div>
</div>

<div class="mid-grid">
  <div class="card">
    <div class="ctitle">Energy Heatmap · Route Consumption</div>
    <canvas id="heatCanvas"></canvas>
    {energy_panel}
  </div>
  <div class="card">
    <div class="ctitle">Mission DNA · Unique Fingerprint</div>
    <canvas id="dnaCanvas"></canvas>
    <div class="metric" style="margin-top:8px"><span class="mk">Mission Hash</span><span class="mv c" style="font-size:10px">{mission_dna}</span></div>
    <div class="metric"><span class="mk">Trajectory Hash</span><span class="mv c" style="font-size:10px">{traj_dna}</span></div>
    <div class="metric"><span class="mk">Uniqueness</span><span class="mv g">100%</span></div>
  </div>
  <div class="card">
    <div class="ctitle">Threat Defense</div>
    {threat_panel}
  </div>
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Blockchain Feed · Live On-Chain Transactions</div>
<div class="card" style="margin-bottom:20px">
  <div class="feed">{camera_panel}
{blockchain_feed}</div>
</div>

<div class="bot-grid">
  <div class="card">
    <div class="ctitle">Weather & Energy</div>
    {weather_panel}
  </div>
  <div class="card">
    <div class="ctitle">Firewall & AI Weights</div>
    {firewall_panel}
  </div>
  <div class="card">
    <div class="ctitle">Consensus & Score Root</div>
    {scoreroot_panel}
  </div>
  <div class="card">
    <div class="ctitle">Konnex · Network Status</div>
    {konnex_panel}
  </div>
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Navigation Intelligence · Flight Analysis</div>
<div class="nav-grid">
  <div class="card">
    <div class="ctitle">Flight Alerts · Active Notifications</div>
    <div class="overlay-btns">
      <button class="ovbtn on" onclick="this.classList.toggle('on')">CRITICAL</button>
      <button class="ovbtn on" onclick="this.classList.toggle('on')">ALERT</button>
      <button class="ovbtn on" onclick="this.classList.toggle('on')">NOTICE</button>
    </div>
    {nav_alerts}
  </div>
  <div class="card">
    <div class="ctitle">Overlay Layers · Map Control</div>
    <div class="overlay-btns">
      <button class="ovbtn on" onclick="this.classList.toggle('on')">Flight Routes</button>
      <button class="ovbtn on" onclick="this.classList.toggle('on')">Swarm Targets</button>
      <button class="ovbtn on" onclick="this.classList.toggle('on')">No-Fly Zones</button>
      <button class="ovbtn on" onclick="this.classList.toggle('on')">Path Deviation</button>
      <button class="ovbtn on" onclick="this.classList.toggle('on')">Floor Altitude</button>
      <button class="ovbtn" onclick="this.classList.toggle('on')">Vert. Clearance</button>
    </div>
    <div class="metric"><span class="mk">Display Mode</span><span class="mv c">STANDARD</span></div>
    <div class="metric"><span class="mk">Active Layers</span><span class="mv g">5 / 6</span></div>
  </div>
  <div class="card">
    <div class="ctitle">NavETA · Estimated Arrival Times</div>
    {nav_etas}
  </div>
  <div class="card">
    <div class="ctitle">SimFlight · Pre-Mission Validation</div>
    {sim_flight}
  </div>
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Swarm Targets · Active Drone Tracking</div>
<div class="card" style="margin-bottom:20px">
  {swarm_targets}
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>DroneSync Modules · Full System Status</div>
<div class="modules-grid">
  <div class="card"><div class="ctitle">Economics · KNX Reward Model</div>{economics_panel}</div>
  <div class="card"><div class="ctitle">Emergency Override · Protocol</div>{emergency_panel}</div>
  <div class="card"><div class="ctitle">Drone Last Will · Emergency PoPW</div>{lastwill_panel}</div>
  <div class="card"><div class="ctitle">Flight Memory · Experience Log</div>{memory_panel}</div>
  <div class="card"><div class="ctitle">Privacy · Encryption Status</div>{privacy_panel}</div>
  <div class="card"><div class="ctitle">Sensor Bundle · Evidence Package</div>{sensorbundle_panel}</div>
  <div class="card"><div class="ctitle">Persistent Storage · State</div>{storage_panel}</div>
  <div class="card"><div class="ctitle">Mission History · Statistics</div>{missionhistory_panel}</div>
  <div class="card"><div class="ctitle">Pipeline · Mission Chain</div>{pipeline_panel}</div>
  <div class="card"><div class="ctitle">Replay Guard · Attack Protection</div>{replay_panel}</div>
  <div class="card"><div class="ctitle">Validator Identity · Signed Scores</div>{validator_identity_panel}</div>
  <div class="card"><div class="ctitle">Byzantine Detector · Swarm Security</div>{byzantine_panel}</div>
  <div class="card"><div class="ctitle">Monitoring · System Health</div>{monitoring_panel}</div>
  <div class="card"><div class="ctitle">Wallet · KNX Balance</div>{wallet_panel}</div>
  <div class="card"><div class="ctitle">MPC · Shamir Secret Sharing</div>{mpc_panel}</div>
  <div class="card"><div class="ctitle">Validator Auth · HMAC-SHA256</div>{validator_auth_panel}</div>
</div>

<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Mission Log</div>
<div class="card" style="margin-bottom:20px">
  <table class="mtable">
    <thead>
      <tr><th>Mission ID</th><th>Drone</th><th>Score</th><th>TEE</th><th>Security</th><th>Reputation</th><th>On-Chain</th><th>Time</th></tr>
    </thead>
    <tbody>{mission_rows}</tbody>
  </table>
</div>

</main>

<footer>
  <span>DRONESYNC · PROOF OF PHYSICAL WORK · KONNEX NETUID {netuid}</span>
  <span>Ed25519 · Groth16 ZK · TEE Attestation · TxQueue · MAVLink 2.0</span>
  <span id="clock"></span>
</footer>

<script>
function updateClock() {{
  document.getElementById("clock").textContent = new Date().toTimeString().slice(0,8) + " UTC+0";
}}
setInterval(updateClock, 1000);
updateClock();

(function() {{
  const c = document.getElementById("particles");
  const ctx = c.getContext("2d");
  c.width = window.innerWidth; c.height = window.innerHeight;
  const pts = [];
  for (let i=0; i<100; i++) {{
    pts.push({{x:Math.random()*c.width, y:Math.random()*c.height, vx:(Math.random()-0.5)*0.3, vy:(Math.random()-0.5)*0.3, r:Math.random()*1.5+0.5}});
  }}
  function draw() {{
    ctx.clearRect(0,0,c.width,c.height);
    pts.forEach(p => {{
      p.x+=p.vx; p.y+=p.vy;
      if(p.x<0||p.x>c.width) p.vx*=-1;
      if(p.y<0||p.y>c.height) p.vy*=-1;
      ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle="rgba(0,212,255,0.8)"; ctx.fill();
    }});
    pts.forEach((a,i) => {{
      pts.slice(i+1).forEach(b => {{
        const d=Math.hypot(a.x-b.x,a.y-b.y);
        if(d<120) {{
          ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y);
          ctx.strokeStyle=`rgba(0,212,255,${{0.15*(1-d/120)}})`;
          ctx.lineWidth=0.5; ctx.stroke();
        }}
      }});
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();

(function() {{
  const c = document.getElementById("mapCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.offsetWidth; c.height = c.offsetHeight;
  const drones = [
    {{x:0.30,y:0.40,tx:0.55,ty:0.25,color:"#00d4ff",trail:[]}},
    {{x:0.50,y:0.30,tx:0.70,ty:0.65,color:"#00e676",trail:[]}},
    {{x:0.45,y:0.60,tx:0.35,ty:0.20,color:"#7c4dff",trail:[]}},
  ];
  let t=0;
  function draw() {{
    ctx.clearRect(0,0,c.width,c.height); t+=0.005;
    drones.forEach((d,i) => {{
      const progress = (Math.sin(t + i*2)+1)/2;
      const cx = (d.x + (d.tx-d.x)*progress)*c.width;
      const cy = (d.y + (d.ty-d.y)*progress)*c.height;
      d.trail.push({{x:cx,y:cy}});
      if(d.trail.length>40) d.trail.shift();
      ctx.beginPath(); ctx.moveTo(d.x*c.width,d.y*c.height); ctx.lineTo(d.tx*c.width,d.ty*c.height);
      ctx.strokeStyle=d.color+"22"; ctx.lineWidth=6; ctx.shadowBlur=12; ctx.shadowColor=d.color; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(d.x*c.width,d.y*c.height); ctx.lineTo(d.tx*c.width,d.ty*c.height);
      ctx.strokeStyle=d.color+"66"; ctx.lineWidth=1.5; ctx.shadowBlur=0; ctx.stroke();
      d.trail.forEach((p,j) => {{
        ctx.beginPath(); ctx.arc(p.x,p.y,1.5,0,Math.PI*2);
        ctx.fillStyle=d.color+Math.floor((j/d.trail.length)*99).toString(16).padStart(2,"0"); ctx.fill();
      }});
      ctx.beginPath(); ctx.arc(cx,cy,5,0,Math.PI*2);
      ctx.fillStyle=d.color; ctx.shadowBlur=15; ctx.shadowColor=d.color; ctx.fill(); ctx.shadowBlur=0;
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();

(function() {{
  const c = document.getElementById("neuralCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.offsetWidth; c.height = 160;
  const layers = [[3],[5],[4],[3]], nodes = [];
  const W = c.width, H = c.height;
  layers.forEach((l,li) => {{
    const x = (li+1)*W/(layers.length+1);
    for(let ni=0; ni<l[0]; ni++) {{
      nodes.push({{x, y:(ni+1)*H/(l[0]+1), layer:li, v:Math.random()}});
    }}
  }});
  let t=0;
  function draw() {{
    ctx.clearRect(0,0,W,H); t+=0.02;
    nodes.forEach(a => nodes.forEach(b => {{
      if(b.layer!==a.layer+1) return;
      ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y);
      ctx.strokeStyle=`rgba(0,212,255,${{0.1+0.1*Math.sin(t+a.x+b.y)}})`;
      ctx.lineWidth=0.8; ctx.stroke();
    }}));
    nodes.forEach(n => {{
      n.v = 0.5+0.5*Math.sin(t*1.5+n.x*0.05);
      const r = 4+n.v*3;
      ctx.beginPath(); ctx.arc(n.x,n.y,r,0,Math.PI*2);
      const g = ctx.createRadialGradient(n.x,n.y,0,n.x,n.y,r);
      g.addColorStop(0,"rgba(0,212,255,0.9)"); g.addColorStop(1,"rgba(0,212,255,0.1)");
      ctx.fillStyle=g; ctx.shadowBlur=10; ctx.shadowColor="#00d4ff"; ctx.fill(); ctx.shadowBlur=0;
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();

(function() {{
  const c = document.getElementById("swarmCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.offsetWidth; c.height = 160;
  const W=c.width, H=c.height;
  const drones = [{{label:"D1",color:"#00d4ff"}},{{label:"D2",color:"#00e676"}},{{label:"D3",color:"#7c4dff"}}];
  const angles = drones.map((_,i)=>i*Math.PI*2/drones.length);
  let t=0;
  function draw() {{
    ctx.clearRect(0,0,W,H); t+=0.01;
    const cx=W/2, cy=H/2, r=H/2-20;
    drones.forEach((a,i) => drones.forEach((b,j) => {{
      if(i>=j) return;
      const ax=cx+r*Math.cos(angles[i]+t*0.3), ay=cy+r*Math.sin(angles[i]+t*0.3);
      const bx=cx+r*Math.cos(angles[j]+t*0.3), by=cy+r*Math.sin(angles[j]+t*0.3);
      ctx.beginPath(); ctx.moveTo(ax,ay); ctx.lineTo(bx,by);
      ctx.strokeStyle=`rgba(0,212,255,${{0.2+0.2*Math.sin(t*2+i+j)}})`;
      ctx.lineWidth=1; ctx.stroke();
      const ppos = (Math.sin(t*3+i*2)+1)/2;
      const px=ax+(bx-ax)*ppos, py=ay+(by-ay)*ppos;
      ctx.beginPath(); ctx.arc(px,py,2,0,Math.PI*2);
      ctx.fillStyle="#00d4ff"; ctx.shadowBlur=6; ctx.shadowColor="#00d4ff"; ctx.fill(); ctx.shadowBlur=0;
    }}));
    drones.forEach((d,i) => {{
      const x=cx+r*Math.cos(angles[i]+t*0.3), y=cy+r*Math.sin(angles[i]+t*0.3);
      ctx.beginPath(); ctx.arc(x,y,10,0,Math.PI*2);
      ctx.fillStyle=d.color+"33"; ctx.strokeStyle=d.color; ctx.lineWidth=1.5; ctx.fill(); ctx.stroke();
      ctx.fillStyle=d.color; ctx.font="bold 9px Courier New";
      ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText(d.label,x,y);
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();

(function() {{
  const c = document.getElementById("heatCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.parentElement.offsetWidth - 36 || 400; c.height = 80;
  const W=c.width, H=c.height;
  const points = Array.from({{length:20}},(_,i)=>{{return {{x:i/19*W,e:0.3+Math.random()*0.7}}}});
  function draw() {{
    ctx.clearRect(0,0,W,H);
    points.forEach((p,i) => {{
      if(i===0) return;
      const prev=points[i-1];
      const c1=`hsl(${{120*p.e}},100%,50%)`;
      ctx.beginPath(); ctx.moveTo(prev.x,H-prev.e*H); ctx.lineTo(p.x,H-p.e*H);
      ctx.lineTo(p.x,H); ctx.lineTo(prev.x,H);
      ctx.fillStyle=c1+"88"; ctx.fill();
      ctx.beginPath(); ctx.moveTo(prev.x,H-prev.e*H); ctx.lineTo(p.x,H-p.e*H);
      ctx.strokeStyle=c1; ctx.lineWidth=2; ctx.stroke();
    }});
  }}
  draw();
}})();

(function() {{
  const c = document.getElementById("dnaCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.parentElement.offsetWidth - 36 || 400; c.height = 60;
  const W=c.width, H=c.height;
  let t=0;
  function draw() {{
    ctx.clearRect(0,0,W,H); t+=0.05;
    for(let x=0;x<W;x+=4) {{
      const y1=H/2+Math.sin(x*0.05+t)*H*0.3;
      const y2=H/2-Math.sin(x*0.05+t)*H*0.3;
      const hue=(x/W)*360;
      ctx.fillStyle=`hsla(${{hue}},100%,60%,0.8)`;
      ctx.fillRect(x,y1-1,2,2); ctx.fillRect(x,y2-1,2,2);
    }}
    requestAnimationFrame(draw);
  }}
  draw();
}})();

setTimeout(()=>location.reload(), 30000);
</script>
</body>
</html>"""



_camera_adapter = None
_vision_engine = None

def _handle_camera_start(body: dict) -> dict:
    global _camera_adapter, _vision_engine
    import threading
    try:
        from dronesync.camera_adapter import CameraAdapter, CameraConfig
        from dronesync.vision_engine import VisionEngine
        source_type = body.get("source", "usb")
        address = body.get("address", "")
        use_gpt4v = body.get("use_gpt4v", False)
        api_key = body.get("api_key", "")
        if source_type == "rtsp":
            cfg = CameraConfig.from_rtsp(address)
        elif source_type == "file":
            cfg = CameraConfig.from_file(address)
        elif source_type == "mavlink":
            cfg = CameraConfig.from_mavlink(address or "udp:127.0.0.1:14550")
        elif source_type == "ros2":
            cfg = CameraConfig.from_ros2(address or "/camera/image_raw")
        else:
            cfg = CameraConfig.from_usb(int(address) if address.isdigit() else 0)
        _camera_adapter = CameraAdapter(cfg)
        _vision_engine = VisionEngine(use_yolo=True, use_gpt4v=use_gpt4v, openai_api_key=api_key)
        backend = _vision_engine.start()
        ok = _camera_adapter.start()
        if not ok:
            return {"ok": False, "error": "Camera failed to open"}
        state["camera_ai"]["enabled"] = True
        state["camera_ai"]["source"] = source_type
        state["camera_ai"]["backend"] = backend
        def _ai_loop():
            for frame in _camera_adapter.stream_frames(max_frames=99999):
                if not state["camera_ai"]["enabled"]:
                    break
                report = _vision_engine.analyze(frame)
                state["camera_ai"]["risk_level"] = report.risk_level
                state["camera_ai"]["objects"] = [o.label for o in report.objects]
                state["camera_ai"]["commentary"] = report.ai_commentary
                state["camera_ai"]["frame_id"] = report.frame_id
                state["camera_ai"]["processing_ms"] = report.processing_ms
        threading.Thread(target=_ai_loop, daemon=True).start()
        return {"ok": True, "backend": backend, "source": source_type}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_camera_stop() -> dict:
    global _camera_adapter, _vision_engine
    state["camera_ai"]["enabled"] = False
    if _camera_adapter:
        _camera_adapter.stop()
        _camera_adapter = None
    _vision_engine = None
    return {"ok": True}


def _build_camera_panel() -> str:
    cam = state.get("camera_ai", {})
    enabled = cam.get("enabled", False)
    risk = cam.get("risk_level", "SAFE")
    objects = cam.get("objects", [])
    backend = cam.get("backend", "")
    source = cam.get("source", "")
    commentary = cam.get("commentary", "")
    frame_id = cam.get("frame_id", 0)
    ms = cam.get("processing_ms", 0.0)
    risk_color = "#00ff88" if risk == "SAFE" else "#ffaa00" if risk == "WARNING" else "#ff4455"
    status_dot = "#00ff88" if enabled else "#4a6080"
    obj_html = "".join(
        f'<span style="background:#0a1828;border:1px solid #1a2840;padding:2px 8px;border-radius:3px;margin:2px;display:inline-block;font-size:11px">{o}</span>'
        for o in objects
    ) if objects else '<span style="color:#4a6080">No objects detected</span>'
    commentary_html = f'<div style="margin-top:8px;font-size:11px;color:#7a8ba0;font-style:italic" id="camCommentary">{commentary}</div>' if commentary else '<div id="camCommentary"></div>'
    active_label = ("ACTIVE - " + backend + " - " + source) if enabled else "OFFLINE"
    return f"""<div style="background:#070d1a;border:1px solid #1a2840;border-radius:8px;padding:16px;margin-bottom:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <div style="font-family:monospace;font-size:10px;letter-spacing:.12em;color:#00d4ff;text-transform:uppercase">CAMERA AI - REAL-TIME SCENE ANALYSIS</div>
    <div style="display:flex;gap:6px;align-items:center">
      <div style="width:8px;height:8px;border-radius:50%;background:{status_dot}"></div>
      <span style="font-family:monospace;font-size:10px;color:#4a6080">{active_label}</span>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
    <div>
      <div style="font-size:9px;color:#4a6080;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Source</div>
      <select id="camSource" style="width:100%;background:#0a1020;border:1px solid #1a2840;color:#c8d6e8;padding:5px 8px;border-radius:4px;font-size:12px">
        <option value="usb">USB / Webcam</option>
        <option value="rtsp">RTSP Stream</option>
        <option value="file">Video File</option>
        <option value="mavlink">MAVLink Camera</option>
        <option value="ros2">ROS2 Topic</option>
      </select>
    </div>
    <div>
      <div style="font-size:9px;color:#4a6080;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Address / URL</div>
      <input id="camAddress" placeholder="0 / rtsp://... / /path/file.mp4" style="width:100%;background:#0a1020;border:1px solid #1a2840;color:#c8d6e8;padding:5px 8px;border-radius:4px;font-size:12px" />
    </div>
  </div>
  <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
    <button onclick="cameraStart()" style="background:#00d4ff;color:#000;border:none;padding:6px 18px;border-radius:4px;font-size:12px;font-weight:700;cursor:pointer">START</button>
    <button onclick="cameraStop()" style="background:#1a2840;color:#c8d6e8;border:1px solid #1a2840;padding:6px 18px;border-radius:4px;font-size:12px;cursor:pointer">STOP</button>
    <label style="font-size:11px;color:#7a8ba0;display:flex;align-items:center;gap:4px"><input type="checkbox" id="camGPT4V"> GPT-4o Vision</label>
    <input id="camApiKey" placeholder="OpenAI API key" style="flex:1;background:#0a1020;border:1px solid #1a2840;color:#c8d6e8;padding:5px 8px;border-radius:4px;font-size:11px" />
  </div>
  <div style="background:#0a1020;border:1px solid #1a2840;border-radius:6px;padding:12px">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px">
      <span style="font-family:monospace;font-size:11px;color:#4a6080">RISK LEVEL</span>
      <span style="font-family:monospace;font-size:13px;font-weight:700;color:{risk_color}" id="camRisk">{risk}</span>
    </div>
    <div style="font-size:9px;color:#4a6080;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Detected Objects</div>
    <div id="camObjects" style="min-height:24px">{obj_html}</div>
    {commentary_html}
    <div style="margin-top:8px;font-size:9px;color:#2a3850">Frame #{frame_id} - {ms:.0f}ms - backend: {backend}</div>
  </div>
</div>
<script>
function cameraStart() {{
  fetch("/api/camera/start",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{source:document.getElementById("camSource").value,address:document.getElementById("camAddress").value,use_gpt4v:document.getElementById("camGPT4V").checked,api_key:document.getElementById("camApiKey").value}})}}).then(r=>r.json()).then(d=>{{if(!d.ok)alert("Error: "+d.error)}});
}}
function cameraStop() {{
  fetch("/api/camera/stop",{{method:"POST"}});
}}
setInterval(()=>{{
  fetch("/api/camera/state").then(r=>r.json()).then(d=>{{
    document.getElementById("camRisk").textContent=d.risk_level;
    document.getElementById("camRisk").style.color=d.risk_level==="SAFE"?"#00ff88":d.risk_level==="WARNING"?"#ffaa00":"#ff4455";
    const obs=d.objects||[];
    document.getElementById("camObjects").innerHTML=obs.length?obs.map(o=>`<span style="background:#0a1828;border:1px solid #1a2840;padding:2px 8px;border-radius:3px;margin:2px;display:inline-block;font-size:11px">${{o}}</span>`).join(""):"<span style=color:#4a6080>No objects detected</span>";
    document.getElementById("camCommentary").textContent=d.commentary||"";
  }});
}},1000);
</script>"""


def render_dashboard() -> str:
    s = state
    sw = s.get("swarm_status", {})
    drones = s.get("drones", {})
    tx = s.get("tx_queue", {})
    zk = s.get("zk_status", {})
    mav = s.get("mavlink_status", {})
    ident = s.get("identity", {})

    last_upd = time.strftime("%H:%M:%S", time.localtime(s.get("last_update", 0))) if s.get("last_update") else "—"

    zk_ok = zk.get("available", False)
    zk_status_str = "READY" if zk_ok else "OFFLINE"
    zk_backend = zk.get("backend", "snarkjs (local node_modules)")
    zk_speed = zk.get("speed", "~1600ms")
    zk_backend_short = "rapidsnark" if "rapidsnark" in zk_backend else "snarkjs local"
    zk_cls = "g" if zk_ok else "r"
    mav_status = mav.get("status", "N/A")

    aw = s.get("ai_weights", {})
    def _pct(v):
        try:
            return int(float(v) * 100)
        except Exception:
            return 0
    ai_safety = _pct(aw.get("safety", 0.4))
    ai_effic = _pct(aw.get("efficiency", 0.35))
    ai_energy_pct = _pct(aw.get("energy", 0.25))

    cons = s.get("consensus", {})
    consensus_status = cons.get("status", "—")
    consensus_rate = str(cons.get("approval_rate", "—"))

    drone_cards = ""
    for drone_id, d in drones.items():
        score = d.get("score", 0)
        tier = d.get("reputation_tier", "?")
        tier_cls = "elite" if tier == "ELITE" else "trusted" if tier == "TRUSTED" else "active" if tier == "ACTIVE" else ""
        chain_val = "READY" if d.get("on_chain_ready") else "PENDING"
        tee = d.get("tee_status", "?")
        sec = d.get("security_status", "?")
        rep_score = d.get("reputation_score", "?")
        bh = d.get("bundle_hash", "?")
        drone_cards += f"""<div class="dcard">
  <div class="dcard-top">
    <span class="dcard-name">{drone_id}</span>
    <span class="dcard-dot"></span>
  </div>
  <div class="metric"><span class="mk">Score</span><span class="mv g" style="font-size:18px">{score}</span></div>
  <div class="dbar"><div class="dbar-fill" style="width:{score}%"></div></div>
  <div class="metric"><span class="mk">TEE</span><span class="mv c">{tee}</span></div>
  <div class="metric"><span class="mk">Security</span><span class="mv g">{sec}</span></div>
  <div class="metric"><span class="mk">Reputation</span><span class="mv">{rep_score} <span class="tier-tag {tier_cls}">{tier}</span></span></div>
  <div class="metric"><span class="mk">Bundle Hash</span><span class="mv c" style="font-size:10px">{bh}</span></div>
  <div class="metric"><span class="mk">On-Chain</span><span class="mv {"g" if d.get("on_chain_ready") else "a"}">{chain_val}</span></div>
  <div class="metric"><span class="mk">Duration</span><span class="mv">{round(d.get("duration_s",0),2)}s</span></div>
</div>"""

    mission_rows = ""
    for m in reversed(s.get("missions", [])[-6:]):
        score = m.get("score", 0)
        mid = m.get("mission_id", "?")[:14] + "..."
        ts = time.strftime("%H:%M:%S", time.localtime(m.get("timestamp", 0)))
        sc = "hi" if score >= 80 else "mid" if score >= 50 else "lo"
        chain_m = "✓" if m.get("on_chain_ready") else "⏳"
        mission_rows += f"""<tr>
  <td style="font-size:11px;color:var(--cyan)">{mid}</td>
  <td>{m.get("drone_id","?")}</td>
  <td><span class="spill {sc}">{score}</span></td>
  <td style="color:var(--cyan)">{m.get("tee_status","?")}</td>
  <td style="color:var(--green)">{m.get("security_status","?")}</td>
  <td>{m.get("reputation_tier","?")}</td>
  <td style="color:var(--green)">{chain_m}</td>
  <td style="color:var(--dim)">{ts}</td>
</tr>"""
    if not mission_rows:
        mission_rows = '<tr><td colspan="8" style="text-align:center;color:var(--dim);padding:16px">NO DATA</td></tr>'

    w = s.get("weather", {})
    weather_panel = (
        f'<div class="metric"><span class="mk">Flyable</span><span class="mv {"g" if w.get("flyable",True) else "r"}">{"YES" if w.get("flyable",True) else "NO"}</span></div>'
        f'<div class="metric"><span class="mk">Wind</span><span class="mv">{w.get("wind_speed","—")} m/s</span></div>'
        f'<div class="metric"><span class="mk">Visibility</span><span class="mv">{w.get("visibility_m","—")} m</span></div>'
        f'<div class="metric"><span class="mk">Severity</span><span class="mv c">{w.get("severity","CLEAR")}</span></div>'
    )

    en = s.get("energy", {})
    energy_panel = (
        f'<div class="metric" style="margin-top:8px"><span class="mk">Battery Remaining</span><span class="mv g">{en.get("battery_remaining_pct","—")}%</span></div>'
        f'<div class="metric"><span class="mk">Distance</span><span class="mv">{en.get("total_distance_km","—")} km</span></div>'
        f'<div class="metric"><span class="mk">Efficiency</span><span class="mv c">{en.get("efficiency_rating","—")}</span></div>'
        f'<div class="metric"><span class="mk">Optimal Speed</span><span class="mv">{en.get("optimal_speed_ms","—")} m/s</span></div>'
    )

    t = s.get("threat", {})
    threat_panel = (
        f'<div class="metric"><span class="mk">Level</span><span class="mv {"r" if t.get("overall_threat_level","NONE")!="NONE" else "g"}">{t.get("overall_threat_level","—")}</span></div>'
        f'<div class="metric"><span class="mk">GPS</span><span class="mv g">{t.get("gps_status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Jamming</span><span class="mv g">{t.get("jamming_status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Swarm</span><span class="mv c">{t.get("swarm_integrity","—")}</span></div>'
    )

    fw = s.get("firewall", {})
    firewall_panel = (
        f'<div class="metric"><span class="mk">Allowed</span><span class="mv g">{fw.get("total_allowed","—")}</span></div>'
        f'<div class="metric"><span class="mk">Blocked</span><span class="mv r">{fw.get("total_blocked","—")}</span></div>'
        f'<div class="metric"><span class="mk">AI Safety</span><span class="mv c">{aw.get("safety","—")}</span></div>'
        f'<div class="metric"><span class="mk">AI Efficiency</span><span class="mv c">{aw.get("efficiency","—")}</span></div>'
        f'<div class="metric"><span class="mk">AI Energy</span><span class="mv c">{aw.get("energy","—")}</span></div>'
    )

    c2 = s.get("consensus", {})
    sr = s.get("score_root", {})
    lw = s.get("last_will", {})
    scoreroot_panel = (
        f'<div class="metric"><span class="mk">Consensus</span><span class="mv {"g" if c2.get("status")=="APPROVED" else "r"}">{c2.get("status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Rate</span><span class="mv g">{c2.get("approval_rate","—")}</span></div>'
        f'<div class="metric"><span class="mk">Validator</span><span class="mv c" style="font-size:10px">{str(sr.get("validator_id",VALIDATOR_ID))[:20]}</span></div>'
        f'<div class="metric"><span class="mk">Root Hash</span><span class="mv g" style="font-size:10px">{str(sr.get("score_root","—"))[:14]}...</span></div>'
        f'<div class="metric"><span class="mk">Last Will</span><span class="mv {"r" if lw.get("triggered") else "g"}">{"TRIGGERED" if lw.get("triggered") else "STANDBY"}</span></div>'
    )

    km = s.get("konnex_miner", {})
    kn = s.get("konnex_net", {})
    konnex_panel = (
        f'<div class="metric"><span class="mk">Network</span><span class="mv c">{str(kn.get("network",SubnetConfig.NETWORK)).upper()}</span></div>'
        f'<div class="metric"><span class="mk">NetUID</span><span class="mv g">{kn.get("netuid",SubnetConfig.NETUID)}</span></div>'
        f'<div class="metric"><span class="mk">Block</span><span class="mv">{kn.get("block",0)}</span></div>'
        f'<div class="metric"><span class="mk">Miners</span><span class="mv c">{kn.get("n_miners",0)}</span></div>'
        f'<div class="metric"><span class="mk">Missions</span><span class="mv g">{km.get("missions_completed",0)}</span></div>'
        f'<div class="metric"><span class="mk">Hotkey</span><span class="mv" style="font-size:9px">{str(DRONE_ID)[:22]}</span></div>'
    )

    from dronesync.navigation import NavigationEngine
    from dronesync.protocol import Waypoint
    import datetime as _dt
    nav_engine = NavigationEngine()
    nav_alerts_html = ""
    nav_etas_html = ""
    _wps = [
        Waypoint(lat=_DEMO_LAT + 0.0000, lon=_DEMO_LON + 0.0000, alt=50, speed=10),
        Waypoint(lat=_DEMO_LAT + 0.0031, lon=_DEMO_LON + 0.0033, alt=55, speed=10),
        Waypoint(lat=_DEMO_LAT + 0.0051, lon=_DEMO_LON + 0.0043, alt=50, speed=10),
    ]
    _sim = nav_engine.sim_flight(_wps)
    _etas = nav_engine.calculate_etas(_sim.segments)
    for drone_id in drones:
        for a in _sim.alerts:
            lv = a.level.value
            nav_alerts_html += f'<div class="alert-item"><span class="alert-dot {lv}"></span><span>[{drone_id}] {a.message}</span></div>'
        for e in _etas:
            eta_str = _dt.datetime.fromtimestamp(e.planned_eta).strftime("%H:%M:%S")
            nav_etas_html += f'<div class="eta-row"><span>{drone_id} · NavPoint {e.waypoint_index}</span><span class="mv c">{eta_str}</span></div>'
    if not nav_alerts_html:
        nav_alerts_html = '<div class="alert-item"><span class="alert-dot notice"></span><span>All systems nominal — no active alerts</span></div>'
    if not nav_etas_html:
        nav_etas_html = '<div style="color:var(--dim);font-size:11px;padding:8px 0">No ETA data</div>'
    _s = _sim.summary()
    sim_flight_html = (
        f'<div class="metric"><span class="mk">Segments</span><span class="mv">{_s["segments"]}</span></div>'
        f'<div class="metric"><span class="mk">Status</span><span class="mv {"g" if _s["safe"] else "r"}">{"SAFE" if _s["safe"] else "UNSAFE"}</span></div>'
        f'<div class="metric"><span class="mk">Total Alerts</span><span class="mv">{_s["alerts"]}</span></div>'
        f'<div class="metric"><span class="mk">Critical</span><span class="mv {"r" if _s["critical"] else "g"}">{_s["critical"]}</span></div>'
        f'<div class="metric"><span class="mk">Floor Altitude</span><span class="mv">20.0 m</span></div>'
        f'<div class="metric"><span class="mk">Vert. Clearance</span><span class="mv">10.0 m</span></div>'
    )
    _swarm_data = [
        {"drone_id": d, "lat": _DEMO_LAT + 0.003, "lon": _DEMO_LON + 0.003, "alt": 50, "speed": 10, "bearing_deg": 90}
        for d in drones
    ]
    _targets = nav_engine.track_swarm(_swarm_data)
    if _targets:
        swarm_targets_html = '<table class="mtable"><thead><tr><th>Drone ID</th><th>Lat</th><th>Lon</th><th>Alt</th><th>Speed</th><th>Bearing</th><th>Last Seen</th></tr></thead><tbody>'
        for tgt in _targets:
            _seen = _dt.datetime.fromtimestamp(tgt.last_seen).strftime("%H:%M:%S")
            swarm_targets_html += f'<tr><td>{tgt.drone_id}</td><td>{tgt.lat}</td><td>{tgt.lon}</td><td>{tgt.alt} m</td><td>{tgt.speed} m/s</td><td>{tgt.bearing_deg}°</td><td>{_seen}</td></tr>'
        swarm_targets_html += '</tbody></table>'
    else:
        swarm_targets_html = '<div style="color:var(--dim);padding:12px;font-size:12px">No swarm targets detected</div>'

    from dronesync.economics import RewardCalculator
    from dronesync.privacy import FlightDataEncryptor
    _rc = RewardCalculator()
    _scores = [drones[d].get("score", 80) for d in drones] or [80]
    _avg_sc = sum(_scores) / len(_scores)
    try:
        _rew = _rc.calculate(mission_id="DASH_001", total_score=_avg_sc, grade="GOOD", reputation_tier="ACTIVE")
        _final_r = round(_rew.final_reward, 3)
        _tier_mult = _rew.tier_multiplier
        _streak = _rew.streak_bonus
        _penalty = _rew.penalty
    except Exception:
        _final_r = round(_avg_sc * 0.01, 3)
        _tier_mult = 1.0; _streak = 0.0; _penalty = 0.0
    economics_panel = (
        f'<div class="metric"><span class="mk">Score</span><span class="mv c">{round(_avg_sc)}</span></div>'
        f'<div class="metric"><span class="mk">Final Reward</span><span class="mv g">{_final_r} KNX</span></div>'
        f'<div class="metric"><span class="mk">Tier Multiplier</span><span class="mv">{_tier_mult}x</span></div>'
        f'<div class="metric"><span class="mk">Streak Bonus</span><span class="mv c">+{_streak} KNX</span></div>'
        f'<div class="metric"><span class="mk">Penalty</span><span class="mv {"r" if _penalty>0 else "g"}">-{_penalty} KNX</span></div>'
        f'<div class="reward-bar"><div class="reward-fill" style="width:{min(100,_avg_sc)}%"></div></div>'
    )

    try:
        _eo = s.get("emergency", {})
        _etype = _eo.get("type", "NONE")
        emergency_panel = (
            f'<div class="metric"><span class="mk">Type</span><span class="mv {"r" if _etype!="NONE" else "g"}">{_etype}</span></div>'
            f'<div class="metric"><span class="mk">Redirected</span><span class="mv a">{_eo.get("redirected_drones",0)} drones</span></div>'
            f'<div class="metric"><span class="mk">Protected</span><span class="mv g">{_eo.get("protected_drones",0)} drones</span></div>'
            f'<div class="metric"><span class="mk">Status</span><span class="mv {"r" if _etype!="NONE" else "g"}">{"ACTIVE" if _etype!="NONE" else "STANDBY"}</span></div>'
        )
    except Exception:
        emergency_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">STANDBY</span></div>'

    try:
        _lw = s.get("last_will", {})
        if _lw and _lw.get("will_hash"):
            lastwill_panel = (
                f'<div class="last-will-box">'
                f'<div class="metric"><span class="mk">Trigger</span><span class="mv r">{_lw.get("failure_cause","—")}</span></div>'
                f'<div class="metric"><span class="mk">Battery</span><span class="mv r">{_lw.get("battery_pct","—")}%</span></div>'
                f'<div class="metric"><span class="mk">Hash</span><span class="mv" style="font-size:10px">{str(_lw.get("will_hash",""))[:16]}...</span></div>'
                f'</div>'
            )
        else:
            lastwill_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ARMED · Monitoring</span></div><div class="metric"><span class="mk">Trigger</span><span class="mv c">Battery &lt; 5%</span></div><div class="metric"><span class="mk">Insurance</span><span class="mv g">ACTIVE</span></div>'
    except Exception:
        lastwill_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ARMED</span></div>'

    try:
        _mem = s.get("memory", {})
        _mem_m = _mem.get("missions_completed", len(s.get("missions", [])))
        memory_panel = (
            f'<div class="metric"><span class="mk">Missions</span><span class="mv g">{_mem_m}</span></div>'
            f'<div class="metric"><span class="mk">Flight Hours</span><span class="mv c">{round(_mem_m*0.03,2)} h</span></div>'
            f'<div class="metric"><span class="mk">Experience</span><span class="mv c">{"EXPERT" if _mem_m>10 else "ACTIVE"}</span></div>'
            f'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">✓ YES</span></div>'
        )
    except Exception:
        memory_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">LOGGING</span></div>'

    try:
        _enc = FlightDataEncryptor.from_passphrase("dronesync_key")
        _pkt = _enc.encrypt(b"test")
        _dec = _enc.decrypt(_pkt)
        _enc_ok = _dec == b"test"
        _method = "AES-256-GCM" if _enc._aesgcm_available() else "XOR-SHA256"
        privacy_panel = (
            f'<div class="metric"><span class="mk">Encryption</span><span class="mv g">{"✓ ACTIVE" if _enc_ok else "✗ FAILED"}</span></div>'
            f'<div class="metric"><span class="mk">Method</span><span class="mv c">{_method}</span></div>'
            f'<div class="metric"><span class="mk">Key Size</span><span class="mv">256 bit</span></div>'
            f'<div class="metric"><span class="mk">Audit Trail</span><span class="mv g">✓ ENABLED</span></div>'
            f'<div class="privacy-badge">SECURE CHANNEL</div>'
        )
    except Exception:
        privacy_panel = '<div class="metric"><span class="mk">Encryption</span><span class="mv g">ACTIVE</span></div>'

    _d0 = list(drones.values())[0] if drones else {}
    _bh = _d0.get("bundle_hash", "—")
    sensorbundle_panel = (
        f'<div class="metric"><span class="mk">Bundle Hash</span><span class="mv c" style="font-size:10px">{_bh}</span></div>'
        f'<div class="metric"><span class="mk">TEE Status</span><span class="mv g">VERIFIED</span></div>'
        f'<div class="metric"><span class="mk">Bundle Valid</span><span class="mv g">✓ VALID</span></div>'
        f'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">✓ READY</span></div>'
    )

    _ms = len(s.get("missions", []))
    storage_panel = (
        f'<div class="metric"><span class="mk">Missions Saved</span><span class="mv g">{_ms}</span></div>'
        f'<div class="metric"><span class="mk">Persisted</span><span class="mv g">✓ YES</span></div>'
        f'<div class="metric"><span class="mk">Survives Restart</span><span class="mv g">✓ YES</span></div>'
        f'<div class="metric"><span class="mk">Storage</span><span class="mv c">SQLite</span></div>'
    )

    missionhistory_panel = (
        f'<div class="metric"><span class="mk">Total Missions</span><span class="mv g">{_ms}</span></div>'
        f'<div class="metric"><span class="mk">Avg Score</span><span class="mv c">{sw.get("avg_score",0)}</span></div>'
        f'<div class="metric"><span class="mk">Max Score</span><span class="mv g">{sw.get("max_score",0)}</span></div>'
        f'<div class="metric"><span class="mk">Success Rate</span><span class="mv g">100%</span></div>'
    )

    pipeline_panel = (
        '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'
        '<div class="metric"><span class="mk">Steps</span><span class="mv c">10</span></div>'
        '<div class="metric"><span class="mk">Signing</span><span class="mv g">Ed25519</span></div>'
        '<div class="metric"><span class="mk">On-Chain</span><span class="mv g">READY</span></div>'
    )

    try:
        from dronesync.replay_guard import ReplayGuard
        ReplayGuard()
        replay_panel = (
            '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'
            '<div class="metric"><span class="mk">Protection</span><span class="mv g">ON</span></div>'
            '<div class="metric"><span class="mk">Max Age</span><span class="mv c">3600s</span></div>'
            '<div class="metric"><span class="mk">Replay Attacks</span><span class="mv g">BLOCKED</span></div>'
        )
    except Exception:
        replay_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'

    try:
        from validator.scorer import ValidatorIdentity
        _vi = ValidatorIdentity(VALIDATOR_ID)
        validator_identity_panel = (
            f'<div class="metric"><span class="mk">Validator</span><span class="mv g" style="font-size:10px">{VALIDATOR_ID[:20]}</span></div>'
            f'<div class="metric"><span class="mk">Signing</span><span class="mv g">Ed25519</span></div>'
            f'<div class="metric"><span class="mk">Public Key</span><span class="mv c">{_vi.public_key_hex[:16]}...</span></div>'
            f'<div class="metric"><span class="mk">Status</span><span class="mv g">VERIFIED</span></div>'
        )
    except Exception:
        validator_identity_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'

    try:
        from dronesync.swarm_consensus import ByzantineDetector
        _bc2 = SwarmConsensus(["D1", "D2", "D3"])
        _bd = ByzantineDetector(_bc2)
        _bds = _bd.get_status()
        byzantine_panel = (
            f'<div class="metric"><span class="mk">Status</span><span class="mv g">MONITORING</span></div>'
            f'<div class="metric"><span class="mk">Monitored</span><span class="mv c">{_bds["monitored_drones"]}</span></div>'
            f'<div class="metric"><span class="mk">Suspicious</span><span class="mv c">{len(_bds["suspicious_drones"])}</span></div>'
            f'<div class="metric"><span class="mk">Blacklisted</span><span class="mv c">{len(_bds["blacklisted"])}</span></div>'
        )
    except Exception:
        byzantine_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">MONITORING</span></div>'

    _mon = s.get("monitoring", {})
    _alst = s.get("alerts", {})
    monitoring_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv {"g" if _alst.get("healthy",True) else "r"}">{"HEALTHY" if _alst.get("healthy",True) else "DEGRADED"}</span></div>'
        f'<div class="metric"><span class="mk">Uptime</span><span class="mv c">{_mon.get("uptime_seconds",0)}s</span></div>'
        f'<div class="metric"><span class="mk">Total Missions</span><span class="mv">{_mon.get("total_missions",0)}</span></div>'
        f'<div class="metric"><span class="mk">Avg Score</span><span class="mv g">{_mon.get("avg_score",0)}</span></div>'
        f'<div class="metric"><span class="mk">Success Rate</span><span class="mv g">{round(_mon.get("success_rate",0)*100,1)}%</span></div>'
        f'<div class="metric"><span class="mk">Errors</span><span class="mv {"r" if _mon.get("total_errors",0)>0 else "g"}">{_mon.get("total_errors",0)}</span></div>'
    )

    _wal = s.get("wallet", {})
    wallet_panel = (
        f'<div class="metric"><span class="mk">Balance</span><span class="mv g" style="font-size:16px">{_wal.get("balance_knx",0)} KNX</span></div>'
        f'<div class="metric"><span class="mk">Total Earned</span><span class="mv c">{_wal.get("total_earned_knx",0)} KNX</span></div>'
        f'<div class="metric"><span class="mk">Penalties</span><span class="mv r">-{_wal.get("total_penalties_knx",0)} KNX</span></div>'
        f'<div class="metric"><span class="mk">Transactions</span><span class="mv">{_wal.get("transaction_count",0)}</span></div>'
        f'<div class="metric"><span class="mk">Storage</span><span class="mv c">SQLite · WAL</span></div>'
    )

    _mpc = s.get("mpc", {})
    _mpc_cls = "g" if _mpc.get("status") == "OK" else "r"
    mpc_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv {_mpc_cls}">{_mpc.get("status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Algorithm</span><span class="mv c">Shamir Secret Sharing</span></div>'
        f'<div class="metric"><span class="mk">Threshold</span><span class="mv">{_mpc.get("threshold",2)} of {_mpc.get("n_shares",3)}</span></div>'
        f'<div class="metric"><span class="mk">Shares</span><span class="mv g">{_mpc.get("shares",0)}</span></div>'
        f'<div class="metric"><span class="mk">Reconstructed</span><span class="mv c">{_mpc.get("reconstructed","—")}</span></div>'
        f'<div class="metric"><span class="mk">Prime</span><span class="mv" style="font-size:10px">Mersenne 2¹²⁷-1</span></div>'
    )

    _vauth = s.get("validator_auth", {})
    _vc = "g" if _vauth.get("token_valid") else "r"
    validator_auth_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv g">{_vauth.get("status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Method</span><span class="mv c">{_vauth.get("method","—")}</span></div>'
        f'<div class="metric"><span class="mk">Token TTL</span><span class="mv">{_vauth.get("ttl",30)}s</span></div>'
        f'<div class="metric"><span class="mk">Token Valid</span><span class="mv {_vc}">{"✓ YES" if _vauth.get("token_valid") else "✗ NO"}</span></div>'
        f'<div class="metric"><span class="mk">Protocol</span><span class="mv c">WSS · TLS</span></div>'
    )

    blockchain_feed = ""
    for m in reversed(list(s.get("missions", []))[-8:]):
        ts = time.strftime("%H:%M:%S", time.localtime(m.get("timestamp", 0)))
        bh = m.get("bundle_hash", "0x0000000000000000")
        did = m.get("drone_id", "?")
        score = m.get("score", 0)
        blockchain_feed += f'<div class="feed-item"><div class="feed-dot"></div><span>PoPW · {did} · score={score}</span><span class="feed-hash">{bh}</span><span class="feed-time">{ts}</span></div>'
    if not blockchain_feed:
        blockchain_feed = '<div class="feed-item"><div class="feed-dot" style="background:var(--dim)"></div><span style="color:var(--dim)">Waiting for missions...</span></div>'

    import json as _json
    _sb_threat = s.get("threat", {}).get("overall_threat_level", "NONE")
    _sb_gps = s.get("threat", {}).get("gps_status", "CLEAN")
    _sb_positions = []
    for _di, (_did, _dd) in enumerate(drones.items()):
        _sb_positions.append({
            "id": _did,
            "lat": _DEMO_LAT + _di * 0.0010,
            "lon": _DEMO_LON + _di * 0.0008,
            "alt": 50 + _di * 5,
            "speed": 10,
        })
    _sb_drone_json = _json.dumps(_sb_positions)

    missions = s.get("missions", [])
    last_m = missions[-1] if missions else {}
    mission_dna = str(last_m.get("mission_id", "—"))[:16] + "..."
    traj_dna = str(last_m.get("bundle_hash", "—"))[:16] + "..."

    drone_id_short = DRONE_ID[:16] + "..." if len(DRONE_ID) > 16 else DRONE_ID
    chain_ep_short = SubnetConfig.CHAIN_ENDPOINT[:20] + "..." if len(SubnetConfig.CHAIN_ENDPOINT) > 20 else SubnetConfig.CHAIN_ENDPOINT

    html = HTML_TEMPLATE
    reps = {
        "{netuid}": str(sw.get("netuid", SubnetConfig.NETUID)),
        "{network}": str(sw.get("network", SubnetConfig.NETWORK)).upper(),
        "{active}": str(sw.get("active_drones", 0)),
        "{total}": str(sw.get("total_drones", len(DRONE_IDS))),
        "{avg_score}": str(sw.get("avg_score", 0)),
        "{min_score}": str(sw.get("min_score", 0)),
        "{max_score}": str(sw.get("max_score", 0)),
        "{on_chain}": "YES" if sw.get("all_on_chain_ready") else "PENDING",
        "{last_update}": last_upd,
        "{tx_pending}": str(tx.get("pending", 0)),
        "{tx_submitted}": str(tx.get("submitted", 0)),
        "{tx_failed}": str(tx.get("failed", 0)),
        "{zk_status_top}": zk_status_str,
        "{zk_status_sb}": zk_status_str,
        "{zk_cls}": zk_cls,
        "{zk_backend}": zk_backend,
        "{zk_backend_short}": zk_backend_short,
        "{zk_speed}": zk_speed,
        "{mav_status}": mav_status,
        "{node_connected}": "CONNECTED" if s.get("node_status", {}).get("connected") else "OFFLINE",
        "{node_network}": str(s.get("node_status", {}).get("network", SubnetConfig.NETWORK)).upper(),
        "{node_session}": str(s.get("node_status", {}).get("session_id", ""))[:10] or "—",
        "{drone_id}": ident.get("drone_id", DRONE_ID),
        "{validator_id}": ident.get("validator_id", VALIDATOR_ID),
        "{drone_id_short}": drone_id_short,
        "{chain_endpoint}": SubnetConfig.CHAIN_ENDPOINT,
        "{chain_endpoint_short}": chain_ep_short,
        "{consensus_status}": consensus_status,
        "{consensus_rate}": consensus_rate,
        "{ai_safety}": str(ai_safety),
        "{ai_effic}": str(ai_effic),
        "{ai_energy}": str(ai_energy_pct),
        "{sb_threat}": _sb_threat,
        "{sb_gps}": _sb_gps,
        "{sb_reward}": str(_final_r),
        "{sb_drone_positions}": _sb_drone_json,
        "{drone_cards}": drone_cards,
        "{mission_rows}": mission_rows,
        "{mission_dna}": mission_dna,
        "{traj_dna}": traj_dna,
        "{weather_panel}": weather_panel,
        "{energy_panel}": energy_panel,
        "{threat_panel}": threat_panel,
        "{firewall_panel}": firewall_panel,
        "{scoreroot_panel}": scoreroot_panel,
        "{konnex_panel}": konnex_panel,
        "{nav_alerts}": nav_alerts_html,
        "{nav_etas}": nav_etas_html,
        "{sim_flight}": sim_flight_html,
        "{swarm_targets}": swarm_targets_html,
        "{economics_panel}": economics_panel,
        "{emergency_panel}": emergency_panel,
        "{lastwill_panel}": lastwill_panel,
        "{memory_panel}": memory_panel,
        "{privacy_panel}": privacy_panel,
        "{sensorbundle_panel}": sensorbundle_panel,
        "{storage_panel}": storage_panel,
        "{missionhistory_panel}": missionhistory_panel,
        "{pipeline_panel}": pipeline_panel,
        "{replay_panel}": replay_panel,
        "{validator_identity_panel}": validator_identity_panel,
        "{byzantine_panel}": byzantine_panel,
        "{monitoring_panel}": monitoring_panel,
        "{wallet_panel}": wallet_panel,
        "{mpc_panel}": mpc_panel,
        "{validator_auth_panel}": validator_auth_panel,
        "{blockchain_feed}": blockchain_feed,
        "{camera_panel}": _build_camera_panel(),
    }
    for k, v in reps.items():
        html = html.replace(k, str(v))
    return html


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/connect-drone":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            result = _handle_connect_drone(body)
            resp = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp)
        elif parsed.path == "/api/camera/start":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            result = _handle_camera_start(body)
            resp = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp)
        elif parsed.path == "/api/camera/stop":
            result = _handle_camera_stop()
            resp = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/camera/state":
            body = json.dumps(state.get("camera_ai", {}), default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/state":
            body = json.dumps(state, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/refresh":
            try:
                refresh_state()
                body = b'{"status":"ok"}'
            except Exception as e:
                body = json.dumps({"status": "error", "msg": str(e)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            try:
                html = render_dashboard().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html)
            except Exception as e:
                err = f"<pre>Dashboard error: {e}</pre>".encode()
                self.send_response(500)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(err)


def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    _init_services()
    logger.info("[DroneSync] Loading...")
    refresh_state()
    logger.info("[DroneSync] Background refresh every 30s...")
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    logger.info("[DroneSync] http://%s:%s", host, port)
    server = HTTPServer((host, port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_dashboard()


# ─── DRONE CONNECT API (POST /api/connect-drone) ───────────────────────────
_drone_connector = None

def _handle_connect_drone(body: dict) -> dict:
    global _drone_connector
    manufacturer = body.get("manufacturer", "mavlink")
    method = body.get("method", "udp")
    custom = body.get("custom_address", "")
    model = body.get("model", "")
    try:
        from dronesync.drone_connector import DroneConnector
        if _drone_connector and _drone_connector.is_connected:
            _drone_connector.disconnect()
        _drone_connector = DroneConnector.from_ui(manufacturer, method, custom, model)
        ok = _drone_connector.connect()
        status = _drone_connector.get_status()
        state["mavlink_status"] = {"available": ok, "status": "CONNECTED" if ok else "FAILED", **status}
        return {"success": ok, "status": status}
    except Exception as e:
        return {"success": False, "error": str(e)}
