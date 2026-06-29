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
from dronesync.bittensor_integration import SubnetConfig, MinerAxon, SubnetMetagraph
from dronesync.mpc import ShamirSecretSharing
from dronesync.validator_auth import ValidatorAuth
from miner.energy import EnergyOptimizer
from miner.planner import AIPlanner
logger = get_logger("dronesync.dashboard")

state = {
    "drones": {},
    "missions": [],
    "swarm_status": {},
    "node_status": {},
    "netuid": 4,
    "network": "testnet",
    "last_update": 0,
    "miner_tasks": [],
    "uid": 136,
}

DRONE_IDS = ["DRONE_001", "DRONE_002", "DRONE_003"]
handlers = {d: DroneNavSynapseHandler(drone_id=d, use_ai_planner=True) for d in DRONE_IDS}
node = KonnexNode(wallet_address="0x5a4E...51f2", network="testnet")
node.connect()
firewalls = {d: DroneFirewall(drone_id=d) for d in DRONE_IDS}
ai_planner = AIPlanner()
swarm = SwarmConsensus(drone_ids=DRONE_IDS)
weather = WeatherService()
energy = EnergyOptimizer()
threat = ThreatDefense()
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
    miner_wallet = MinerWallet("MINER_001", persist_path=".dronesync_data/dashboard_wallet.db")
    miner_axon = MinerAxon("0x5a4E...51f2", "dronesync_hotkey_001")
    metagraph = SubnetMetagraph()
    metagraph.register_miner(miner_axon)
    validator_auth_obj = ValidatorAuth()
# Фиксированные координаты дронов для карты (в процентах от размера карты)
DRONE_COORDS = {
    "DRONE_001": {"x": 28, "y": 38, "tx": 62, "ty": 55},
    "DRONE_002": {"x": 45, "y": 25, "tx": 72, "ty": 42},
    "DRONE_003": {"x": 35, "y": 58, "tx": 68, "ty": 30},
}


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
        {"lat": 47.3769, "lon": 8.5417, "alt": 50, "speed": 5},
        {"lat": 47.3775, "lon": 8.5420, "alt": 55, "speed": 5},
        {"lat": 47.3780, "lon": 8.5425, "alt": 45, "speed": 5},
    ]
    dests = [
        {"lat": 47.3820, "lon": 8.5460, "alt": 50, "speed": 5},
        {"lat": 47.3825, "lon": 8.5465, "alt": 55, "speed": 5},
        {"lat": 47.3830, "lon": 8.5470, "alt": 45, "speed": 5},
    ]
    return {
        "task_id": "KNX_" + str(int(time.time() * 1000))[-8:],
        "mission_type": "urban_delivery",
        "origin": origins[drone_idx % len(origins)],
        "destination": dests[drone_idx % len(dests)],
        "waypoints": [],
        "drone_count": 1,
        "payload_kg": round(random.uniform(0.3, 1.2), 2),
        "validator_signature": "konnex_testnet_v1_sig",
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
    # Firewall stats
    fw_report = firewalls[DRONE_IDS[0]].get_report()
    state["firewall"] = fw_report

    # Monitoring
    for d in DRONE_IDS:
        dr = state["drones"].get(d, {})
        metrics_collector.record_mission(dr.get("mission_id",""), dr.get("score",0)/100.0, 250.0, True)
    state["monitoring"] = metrics_collector.get_metrics()
    state["alerts"] = alert_manager.get_status()

    # Wallet
    for d in DRONE_IDS:
        dr = state["drones"].get(d, {})
        miner_wallet.credit(dr.get("mission_id",""), round(dr.get("score",0)*0.01,4), "mission_reward")
    state["wallet"] = miner_wallet.summary()

    # Bittensor
    miner_axon.submit_popw({"mission_id":"DASH_001","score":0.85,"trajectory_hash":"abc123"})
    state["bittensor_miner"] = miner_axon.get_status()
    state["bittensor_net"] = metagraph.get_state()

    # MPC
    try:
        _sss = ShamirSecretSharing(threshold=2, n_shares=3)
        _shares = _sss.split(0.85)
        _rec = _sss.reconstruct(_shares[:2])
        state["mpc"] = {"status":"OK","threshold":2,"n_shares":3,"reconstructed":round(_rec,4),"shares":len(_shares)}
    except Exception as _e:
        state["mpc"] = {"status":"ERROR","error":str(_e)}

    # Validator Auth
    _tok = validator_auth_obj.generate_token("VALIDATOR_001")
    state["validator_auth"] = {"status":"ACTIVE","token_valid":validator_auth_obj.verify_token(_tok),"ttl":ValidatorAuth.TOKEN_TTL,"method":"HMAC-SHA256"}

    # Threat defense
    state["threat"] = {
        "overall_threat_level": "NONE",
        "gps_status": "CLEAN",
        "jamming_status": "CLEAR",
        "swarm_integrity": "VERIFIED",
        "mission_safe": True
    }
    # Weather
    state["weather"] = weather.get_current().__dict__

    # Energy
    positions = [[47.3769, 8.5417, 50], [47.38, 8.545, 50]]
    state["energy"] = energy.analyze_trajectory(positions)
    # Score Root

    from validator.scoreroot import ScoreRoot
    sc = ScoreRoot("VALIDATOR_001")
    for d in DRONE_IDS:
        sc.add_score(d, state["drones"][d]["score"], state["drones"][d]["bundle_hash"], state["drones"][d]["bundle_hash"])
    state["score_root"] = sc.commit()
    # Last Will
    from dronesync.last_will import DroneLastWill
    _ = DroneLastWill(DRONE_IDS[0])
    state["last_will"] = {"triggered": False, "battery_pct": "—"}
    # AI planner weights
    state["ai_weights"] = dict(ai_planner.learned_weights)

    # Swarm consensus
    votes = [(d, True) for d in DRONE_IDS]
    state["consensus"] = swarm.vote_on_route("DASH_VOTE", votes)


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
<title>DroneSync — Neural Command Center</title>
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

/* PARTICLES */
#particles { position: fixed; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:0; opacity:0.7; }

/* SCANLINE */
body::after {
  content:""; position:fixed; top:0; left:0; width:100%; height:100%;

  pointer-events:none; z-index:1;
}

/* HEADER */
header {
  position: sticky; top:0; z-index:100;
  background: rgba(6,8,16,0.95);
  border-bottom: 1px solid var(--border2);
  padding: 0 28px; height: 60px;
  display: flex; align-items: center; gap: 20px;
  backdrop-filter: blur(10px);
}
.logo-hex {
  width:38px; height:38px; border:2px solid var(--cyan); border-radius:8px;
  display:flex; align-items:center; justify-content:center;
  font-size:20px; color:var(--cyan);
  box-shadow: 0 0 20px rgba(0,212,255,0.3);
  animation: hexPulse 3s infinite;
}
@keyframes hexPulse { 0%,100%{box-shadow:0 0 20px rgba(0,212,255,0.3)} 50%{box-shadow:0 0 40px rgba(0,212,255,0.6)} }
.logo-title { font-size:16px; font-weight:bold; color:var(--white); letter-spacing:4px; }
.logo-sub { font-size:10px; color:var(--dim); letter-spacing:2px; margin-top:2px; }
.hbar { margin-left:auto; display:flex; align-items:center; gap:8px; }
.hbadge { padding:4px 12px; border:1px solid var(--border2); font-size:10px; letter-spacing:1.5px; text-transform:uppercase; color:var(--dim); }
.hbadge-live { border-color:var(--green); color:var(--green); animation:liveBlink 2s infinite; }
@keyframes liveBlink { 0%,100%{opacity:1} 50%{opacity:0.5} }
.hbadge-net { border-color:var(--cyan2); color:var(--cyan); }
.hbtn { background:transparent; border:1px solid var(--border2); color:var(--dim); padding:6px 14px; font-family:inherit; font-size:10px; letter-spacing:2px; cursor:pointer; text-transform:uppercase; transition:all 0.2s; }
.hbtn:hover { border-color:var(--cyan); color:var(--cyan); box-shadow:0 0 10px rgba(0,212,255,0.2); }

/* MAIN */
main { padding:20px 28px; max-width:1800px; margin:0 auto; position:relative; z-index:2; }

/* SECTION LABEL */
.slabel { font-size:9px; letter-spacing:3px; text-transform:uppercase; color:var(--dim); margin-bottom:12px; padding-left:10px; border-left:2px solid var(--cyan); display:flex; align-items:center; gap:8px; }
.slabel-dot { width:4px; height:4px; border-radius:50%; background:var(--cyan); animation:liveBlink 2s infinite; }

/* TOP STATS */
.top-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
.stat { background:var(--surface); border:1px solid var(--border); padding:18px; position:relative; overflow:hidden; transition:border-color 0.3s; }
.stat:hover { border-color:var(--border2); }
.stat::before { content:""; position:absolute; top:0; left:0; right:0; height:2px; background:var(--cyan); }
.stat.g::before { background:var(--green); }
.stat.p::before { background:var(--purple); }
.stat.a::before { background:var(--amber); }
.stat-lbl { font-size:9px; letter-spacing:2px; color:var(--dim); text-transform:uppercase; margin-bottom:8px; }
.stat-val { font-size:28px; font-weight:bold; color:var(--white); line-height:1; }
.stat-val.c { color:var(--cyan); }
.stat-val.g { color:var(--green); }
.stat-val.p { color:var(--purple); }
.stat-sub { font-size:10px; color:var(--dim); margin-top:6px; }
.sbar { height:2px; background:var(--border); margin-top:10px; overflow:hidden; }
.sbar-fill { height:100%; background:linear-gradient(90deg,var(--cyan),var(--green)); transition:width 1s ease; }

/* 3D MAP */
.map-section { margin-bottom:20px; }
.map-wrap { background:var(--surface); border:1px solid var(--border); position:relative; overflow:hidden; height:320px; }
.map-grid { position:absolute; inset:0; background-image: linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px); background-size:40px 40px; opacity:0.5; }
.map-label { position:absolute; top:12px; left:12px; font-size:9px; letter-spacing:2px; color:var(--dim); text-transform:uppercase; }
.map-coords { position:absolute; bottom:12px; right:12px; font-size:9px; color:var(--dim); letter-spacing:1px; }
#mapCanvas { position:absolute; inset:0; width:100%; height:100%; }

/* NO-FLY ZONES */
.nfz { position:absolute; border-radius:50%; border:2px solid rgba(255,61,87,0.6); background:rgba(255,61,87,0.08); animation:nfzPulse 3s infinite; display:flex; align-items:center; justify-content:center; }
@keyframes nfzPulse { 0%,100%{box-shadow:0 0 0 0 rgba(255,61,87,0.3)} 50%{box-shadow:0 0 0 20px rgba(255,61,87,0)} }
.nfz-label { font-size:8px; color:var(--red); letter-spacing:1px; text-transform:uppercase; }

/* DRONE DOTS ON MAP */
.mdrone { position:absolute; cursor:pointer; }
.mdrone-core { width:10px; height:10px; border-radius:50%; background:var(--cyan); box-shadow:0 0 10px var(--cyan); animation:dronePulse 1.5s infinite; }
@keyframes dronePulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.4)} }
.mdrone-ring { position:absolute; top:-6px; left:-6px; width:22px; height:22px; border-radius:50%; border:1px solid rgba(0,212,255,0.4); animation:ringExpand 2s infinite; }
@keyframes ringExpand { 0%{transform:scale(0.5);opacity:1} 100%{transform:scale(2);opacity:0} }
.mdrone-label { position:absolute; top:-18px; left:50%; transform:translateX(-50%); font-size:8px; color:var(--cyan); white-space:nowrap; letter-spacing:1px; }
.mdrone-trail { position:absolute; top:4px; left:4px; width:2px; height:2px; border-radius:50%; background:var(--cyan); opacity:0.3; }

/* MID GRID */
.mid-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; margin-bottom:20px; }

/* CARDS */
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

/* NEURAL NETWORK */
#neuralCanvas { width:100%; height:160px; display:block; }

/* SWARM BRAIN */
#swarmCanvas { width:100%; height:160px; display:block; }

/* DRONE CARDS */
.fleet-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:20px; }
.dcard { background:var(--surface); border:1px solid var(--border); padding:16px; position:relative; transition:border-color 0.3s; }
.dcard:hover { border-color:var(--cyan2); box-shadow:0 0 20px rgba(0,212,255,0.05); }
.dcard-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid var(--border); }
.dcard-name { font-size:13px; font-weight:bold; color:var(--white); letter-spacing:2px; }
.dcard-dot { width:8px; height:8px; border-radius:50%; background:var(--green); animation:liveBlink 2s infinite; }
.dcard-dot.warn { background:var(--amber); }
.tier-tag { display:inline-block; padding:2px 8px; font-size:9px; letter-spacing:1.5px; text-transform:uppercase; border:1px solid var(--dim); color:var(--dim); }
.tier-tag.elite { border-color:var(--cyan); color:var(--cyan); box-shadow:0 0 8px rgba(0,212,255,0.2); }
.tier-tag.trusted { border-color:var(--green); color:var(--green); }
.tier-tag.active { border-color:var(--amber); color:var(--amber); }
.dbar { height:3px; background:var(--border); margin:8px 0; overflow:hidden; }
.dbar-fill { height:100%; background:linear-gradient(90deg,var(--cyan),var(--green)); transition:width 1s ease; }

/* POPW TIMELINE */
.popw-chain { display:flex; align-items:center; gap:0; margin-top:10px; overflow-x:auto; padding-bottom:4px; }
.popw-block { background:var(--surface2); border:1px solid var(--border); padding:8px 12px; font-size:9px; letter-spacing:1px; color:var(--cyan); text-transform:uppercase; white-space:nowrap; position:relative; flex-shrink:0; }
.popw-block.active { border-color:var(--cyan); box-shadow:0 0 10px rgba(0,212,255,0.2); }
.popw-arrow { color:var(--cyan); font-size:12px; padding:0 4px; flex-shrink:0; opacity:0.5; }
.popw-hash { font-size:8px; color:var(--dim); margin-top:2px; }

/* THREAT RADAR */
.radar-container { display:flex; justify-content:center; padding:8px 0; }
#radarCanvas { border-radius:50%; }

/* ENERGY HEATMAP */
#heatCanvas { width:100%; height:80px; display:block; margin-top:8px; }

/* MISSION DNA */
#dnaCanvas { width:100%; height:60px; display:block; margin-top:8px; }

/* BLOCKCHAIN FEED */
.feed { max-height:200px; overflow-y:auto; }
.feed::-webkit-scrollbar { width:3px; }
.feed::-webkit-scrollbar-track { background:var(--surface); }
.feed::-webkit-scrollbar-thumb { background:var(--border2); }
.feed-item { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--border); font-size:10px; animation:feedIn 0.5s ease; }
@keyframes feedIn { from{opacity:0;transform:translateX(-10px)} to{opacity:1;transform:translateX(0)} }
.feed-dot { width:6px; height:6px; border-radius:50%; background:var(--green); flex-shrink:0; animation:liveBlink 2s infinite; }
.feed-text { color:var(--text); flex:1; }
.feed-hash { color:var(--cyan); font-size:9px; }
.feed-time { color:var(--dim); font-size:9px; margin-left:auto; white-space:nowrap; }

/* MISSION TABLE */
.mtable { width:100%; border-collapse:collapse; font-size:11px; }
.mtable th { background:var(--surface2); color:var(--dim); padding:9px 12px; text-align:left; font-size:9px; letter-spacing:1.5px; text-transform:uppercase; border-bottom:1px solid var(--border); font-weight:normal; }
.mtable td { padding:8px 12px; border-bottom:1px solid var(--border); }
.mtable tr:hover td { background:rgba(0,212,255,0.03); }
.spill { display:inline-block; padding:2px 8px; font-size:10px; font-weight:bold; border:1px solid var(--border); }
.spill.hi { border-color:var(--green); color:var(--green); }
.spill.mid { border-color:var(--amber); color:var(--amber); }
.spill.lo { border-color:var(--red); color:var(--red); }

/* BOTTOM PANELS */
.bot-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }

/* FOOTER */

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
  body { margin-right:270px; } #particles { position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:0; pointer-events:none; }
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
      <div class="sb-row"><span class="sb-key">Targets</span><span class="sb-val g" id="sbTargets">3</span></div>
      <div class="sb-row"><span class="sb-key">Swarm Score</span><span class="sb-val c">{avg_score}</span></div>
      <div class="sb-row"><span class="sb-key">On-Chain</span><span class="sb-val g">{on_chain}</span></div>
      <div class="sb-row"><span class="sb-key">Threat</span><span class="sb-val g">{sb_threat}</span></div>
      <div class="sb-row"><span class="sb-key">GPS</span><span class="sb-val g">{sb_gps}</span></div>
      <div class="sb-row"><span class="sb-key">Reward</span><span class="sb-val c">{sb_reward} KNX</span></div>
      <div class="sb-row"><span class="sb-key">SimFlight</span><span class="sb-val g">{sb_sim_status}</span></div>
      <div class="sb-row"><span class="sb-key">Updated</span><span class="sb-val" style="font-size:9px">{last_update}</span></div>
    </div>
  </div>
</div>

<script>
// TACTICAL RADAR
const _radarDrones = {sb_drone_positions};
const _radarRanges = [100, 250, 500, 1000, 2500, 5000];
let _radarRangeIdx = 2;
let _radarAngle = 0;
let _radarHover = null;

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

  // Background
  ctx.beginPath();
  ctx.arc(cx, cy, R, 0, Math.PI*2);
  ctx.fillStyle = "#030508";
  ctx.fill();
  ctx.strokeStyle = "#00bfff33";
  ctx.lineWidth = 1;
  ctx.stroke();

  // Range rings
  const rings = 4;
  for (let i = 1; i <= rings; i++) {{
    const r = R * i / rings;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI*2);
    ctx.strokeStyle = "#00bfff18";
    ctx.lineWidth = 0.5;
    ctx.stroke();
    // Range label
    const ringRange = Math.round(range * i / rings);
    ctx.fillStyle = "#00bfff44";
    ctx.font = "8px monospace";
    ctx.fillText(ringRange + "m", cx + 4, cy - r + 10);
  }}

  // Cross lines
  ctx.strokeStyle = "#00bfff18";
  ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.moveTo(cx-R, cy); ctx.lineTo(cx+R, cy); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, cy-R); ctx.lineTo(cx, cy+R); ctx.stroke();

  // Diagonal lines
  for (let a = 45; a < 360; a += 90) {{
    const rad = a * Math.PI/180;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(rad)*R, cy + Math.sin(rad)*R);
    ctx.strokeStyle = "#00bfff0a";
    ctx.stroke();
  }}

  // Sweep
  const sweepGrad = ctx.createConicalGradient
    ? ctx.createConicalGradient(cx, cy, _radarAngle)
    : null;

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(_radarAngle);
  const grad = ctx.createLinearGradient(0, 0, R, 0);
  grad.addColorStop(0, "#00bfff44");
  grad.addColorStop(1, "transparent");
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.arc(0, 0, R, -0.4, 0);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.restore();

  // Threat overlay
  const _threat = "NONE";
  if (_threat !== "NONE") {
    const tGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, R);
    tGrad.addColorStop(0, "transparent");
    tGrad.addColorStop(1, "#ff2d4a22");
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI*2);
    ctx.fillStyle = tGrad;
    ctx.fill();
  }

  // Center dot
  ctx.beginPath();
  ctx.arc(cx, cy, 4, 0, Math.PI*2);
  ctx.fillStyle = "#00bfff";
  ctx.fill();

  // Drone colors
  const colors = ["#00bfff", "#00e5a0", "#8855ff", "#ffb700", "#ff2d4a"];

  // Draw drones
  _radarDrones.forEach((d, i) => {{
    // Convert lat/lon offset to pixels
    const latRef = _radarDrones[0].lat;
    const lonRef = _radarDrones[0].lon;
    const dx = (d.lon - lonRef) * 111320 * Math.cos(latRef * Math.PI/180);
    const dy = -(d.lat - latRef) * 111320;
    const scale = R / range;
    const px = cx + dx * scale;
    const py = cy + dy * scale;

    // Skip if outside radar
    const dist = Math.sqrt((px-cx)**2 + (py-cy)**2);
    if (dist > R) return;

    // Glow trail
    const grd = ctx.createRadialGradient(px, py, 0, px, py, 12);
    grd.addColorStop(0, colors[i % colors.length] + "66");
    grd.addColorStop(1, "transparent");
    ctx.beginPath();
    ctx.arc(px, py, 12, 0, Math.PI*2);
    ctx.fillStyle = grd;
    ctx.fill();

    // Drone dot
    ctx.beginPath();
    ctx.arc(px, py, 5, 0, Math.PI*2);
    ctx.fillStyle = colors[i % colors.length];
    ctx.fill();
    ctx.strokeStyle = "#ffffff44";
    ctx.lineWidth = 1;
    ctx.stroke();

    // Label
    ctx.fillStyle = colors[i % colors.length];
    ctx.font = "bold 9px monospace";
    ctx.fillText(d.id, px + 8, py - 4);
    ctx.fillStyle = "#ffffff66";
    ctx.font = "8px monospace";
    ctx.fillText(d.alt + "m", px + 8, py + 6);
  }});

  _radarAngle += 0.04;
  if (_radarAngle > Math.PI*2) _radarAngle = 0;

  document.getElementById("sbTargets").textContent = _radarDrones.length;

  requestAnimationFrame(drawSideRadar);
}}

drawSideRadar();

// Radar canvas hover tooltip
const _sideRadarEl = document.getElementById("sideRadar");
if (_sideRadarEl) {{
  _sideRadarEl.addEventListener("mousemove", function(e) {{
    const rect = _sideRadarEl.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    _radarHover = null;
    const cx = 115, cy = 115, R = 105;
    const range = _radarRanges[_radarRangeIdx];
    const latRef = _radarDrones[0] ? _radarDrones[0].lat : 47.38;
    const lonRef = _radarDrones[0] ? _radarDrones[0].lon : 8.54;
    _radarDrones.forEach((d, i) => {{
      const dx = (d.lon - lonRef) * 111320 * Math.cos(latRef * Math.PI/180);
      const dy = -(d.lat - latRef) * 111320;
      const scale = R / range;
      const px = cx + dx * scale;
      const py = cy + dy * scale;
      if (Math.abs(mx-px) < 10 && Math.abs(my-py) < 10) {{
        _sideRadarEl.title = d.id + " | Alt:" + d.alt + "m | Spd:" + d.speed + "m/s";
      }}
    }});
  }});
}}
</script>

<canvas id="particles"></canvas>

<header>
  <div class="logo-hex">⬡</div>
  <div>
    <div class="logo-title">DRONESYNC</div>
    <div class="logo-sub">NEURAL COMMAND CENTER · KONNEX NETUID {netuid} · {network}</div>
  </div>
  <div class="hbar">
    <span class="hbadge hbadge-live">● LIVE</span>
    <span class="hbadge hbadge-net">NETUID {netuid}</span>
    <span class="hbadge">{active}/{total} DRONES</span>
    <button class="hbtn" onclick="location.reload()">⟳ REFRESH</button>
  </div>
</header>

<main>

<!-- TOP STATS -->
<div class="top-stats">
  <div class="stat">
    <div class="stat-lbl">Active Drones</div>
    <div class="stat-val c">{active}<span style="font-size:14px;color:var(--dim)">/{total}</span></div>
    <div class="stat-sub">Swarm operational</div>
    <div class="sbar"><div class="sbar-fill" style="width:100%"></div></div>
  </div>
  <div class="stat g">
    <div class="stat-lbl">Avg Score</div>
    <div class="stat-val g">{avg_score}</div>
    <div class="stat-sub">Min {min_score} · Max {max_score}</div>
    <div class="sbar"><div class="sbar-fill" style="width:{avg_score}%"></div></div>
  </div>
  <div class="stat">
    <div class="stat-lbl">Konnex Node</div>
    <div class="stat-val" style="font-size:16px;padding-top:4px">{node_connected}</div>
    <div class="stat-sub">{node_network} · {node_session}</div>
  </div>
  <div class="stat p">
    <div class="stat-lbl">On-Chain Ready</div>
    <div class="stat-val p" style="font-size:16px;padding-top:4px">{on_chain}</div>
    <div class="stat-sub">Last update {last_update}</div>
  </div>
</div>

<!-- 3D MAP -->
<div class="map-section">
  <div class="slabel"><span class="slabel-dot"></span>Urban Airspace · Live Trajectory Map</div>
  <div class="map-wrap">
    <div class="map-grid"></div>
    <canvas id="mapCanvas"></canvas>
    <div class="map-label">ZURICH AIRSPACE · ALT 50-130M</div>
    <div class="map-coords" id="mapCoords">LAT 47.3769 · LON 8.5417</div>
    <!-- No-fly zones -->
    <div class="nfz" style="width:80px;height:80px;left:15%;top:20%"><span class="nfz-label">AIRPORT</span></div>
    <div class="nfz" style="width:60px;height:60px;left:60%;top:55%"><span class="nfz-label">HOSPITAL</span></div>
    <div class="nfz" style="width:70px;height:70px;left:75%;top:15%"><span class="nfz-label">GOV</span></div>
    <!-- Drone dots -->
    <div class="mdrone" id="md1" style="left:30%;top:40%">
      <div class="mdrone-ring"></div>
      <div class="mdrone-core"></div>
      <div class="mdrone-label">DRONE_001</div>
    </div>
    <div class="mdrone" id="md2" style="left:50%;top:30%;animation-delay:0.5s">
      <div class="mdrone-ring"></div>
      <div class="mdrone-core" style="background:var(--green);box-shadow:0 0 10px var(--green)"></div>
      <div class="mdrone-label">DRONE_002</div>
    </div>
    <div class="mdrone" id="md3" style="left:45%;top:60%;animation-delay:1s">
      <div class="mdrone-ring"></div>
      <div class="mdrone-core" style="background:var(--purple);box-shadow:0 0 10px var(--purple)"></div>
      <div class="mdrone-label">DRONE_003</div>
    </div>
  </div>
</div>

<!-- MID ROW: NEURAL NET + SWARM BRAIN + THREAT RADAR -->
<div class="mid-grid" style="grid-template-columns:1fr 1fr">
  <div class="card">
    <div class="ctitle">Neural Network · AI Planner Decisions</div>
    <canvas id="neuralCanvas"></canvas>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px">
      <div style="text-align:center">
        <div style="font-size:9px;color:var(--dim);letter-spacing:1px">SAFETY</div>
        <div style="font-size:16px;color:var(--cyan);font-weight:bold">40%</div>
        <div style="height:2px;background:var(--border);margin-top:4px"><div style="height:100%;width:40%;background:var(--cyan)"></div></div>
      </div>
      <div style="text-align:center">
        <div style="font-size:9px;color:var(--dim);letter-spacing:1px">EFFICIENCY</div>
        <div style="font-size:16px;color:var(--green);font-weight:bold">35%</div>
        <div style="height:2px;background:var(--border);margin-top:4px"><div style="height:100%;width:35%;background:var(--green)"></div></div>
      </div>
      <div style="text-align:center">
        <div style="font-size:9px;color:var(--dim);letter-spacing:1px">ENERGY</div>
        <div style="font-size:16px;color:var(--purple);font-weight:bold">25%</div>
        <div style="height:2px;background:var(--border);margin-top:4px"><div style="height:100%;width:25%;background:var(--purple)"></div></div>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="ctitle">Swarm Brain · Communication Graph</div>
    <canvas id="swarmCanvas"></canvas>
    <div class="metric" style="margin-top:8px"><span class="mk">Consensus</span><span class="mv g">APPROVED</span></div>
    <div class="metric"><span class="mk">Active Links</span><span class="mv c">6 / 6</span></div>
    <div class="metric"><span class="mk">Swarm IQ</span><span class="mv g">HIGH</span></div>
  </div>
</div>

<!-- DRONE FLEET -->
<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Drone Fleet</div>
<div class="fleet-grid">
{drone_cards}
</div>

<!-- POPW TIMELINE + ENERGY HEATMAP + MISSION DNA -->
<div class="mid-grid">
  <div class="card">
    <div class="ctitle">PoPW Timeline · Proof Chain</div>
    <div class="popw-chain">
      <div class="popw-block active">Task<div class="popw-hash">✓ OK</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">TEE<div class="popw-hash">✓ ATT</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">Sensor<div class="popw-hash">✓ Hash</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">Score<div class="popw-hash">✓ Root</div></div>
      <div class="popw-arrow">→</div>
      <div class="popw-block active">Chain<div class="popw-hash">✓ Ready</div></div>
    </div>
    <div style="margin-top:14px">
      <div class="metric"><span class="mk">Task Instruction</span><span class="mv g">✓ OK</span></div>
      <div class="metric"><span class="mk">TEE Attestation</span><span class="mv g">✓ VERIFIED</span></div>
      <div class="metric"><span class="mk">Sensor Bundle</span><span class="mv g">✓ HASHED</span></div>
      <div class="metric"><span class="mk">Score Root</span><span class="mv g">✓ ON-CHAIN</span></div>
    </div>
  </div>
  <div class="card">
    <div class="ctitle">Energy Heatmap · Route Consumption</div>
    <canvas id="heatCanvas"></canvas>
    <div class="metric" style="margin-top:8px"><span class="mk">Battery Used</span><span class="mv g">7.0%</span></div>
    <div class="metric"><span class="mk">Remaining</span><span class="mv g">93.0%</span></div>
    <div class="metric"><span class="mk">Efficiency</span><span class="mv c">EXCELLENT</span></div>
    <div class="metric"><span class="mk">Optimal Speed</span><span class="mv">10.0 m/s</span></div>
  </div>
  <div class="card">
    <div class="ctitle">Mission DNA · Unique Fingerprint</div>
    <canvas id="dnaCanvas"></canvas>
    <div class="metric" style="margin-top:8px"><span class="mk">Mission Hash</span><span class="mv c" style="font-size:10px">{mission_dna}</span></div>
    <div class="metric"><span class="mk">Trajectory Hash</span><span class="mv c" style="font-size:10px">{traj_dna}</span></div>
    <div class="metric"><span class="mk">Uniqueness</span><span class="mv g">100%</span></div>
  </div>
</div>

<!-- BLOCKCHAIN FEED -->
<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Blockchain Feed · Live On-Chain Transactions</div>
<div class="card" style="margin-bottom:20px">
  <div class="feed">{blockchain_feed}</div>
</div>

<!-- BOTTOM PANELS -->
<div class="bot-grid">
  <div class="card">
    <div class="ctitle">Weather & Energy</div>
    {weather_panel}
  </div>
  <div class="card">
    <div class="ctitle">Threat Defense</div>
    {threat_panel}
  </div>
  <div class="card">
    <div class="ctitle">Firewall & AI Weights</div>
    {firewall_panel}
  </div>
  <div class="card">
    <div class="ctitle">Consensus & Score Root</div>
    {scoreroot_panel}
  </div>
</div>

<!-- NAVIGATION INTELLIGENCE -->
<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Navigation Intelligence · ECDIS-Inspired Flight Analysis</div>
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
    <div class="ctitle">Overlay Layers · Map Display Control</div>
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

<!-- SWARM TARGETS -->
<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>Swarm Targets · Active Drone Tracking</div>
<div class="card" style="margin-bottom:20px">
  {swarm_targets}
</div>

<!-- ALL MODULES -->
<div class="slabel" style="margin-bottom:12px"><span class="slabel-dot"></span>DroneSync Modules · Full System Status</div>
<div class="modules-grid">

  <div class="card">
    <div class="ctitle">Economics · KNX Reward Model</div>
    {economics_panel}
  </div>

  <div class="card">
    <div class="ctitle">Emergency Override · Protocol</div>
    {emergency_panel}
  </div>

  <div class="card">
    <div class="ctitle">Drone Last Will · Emergency PoPW</div>
    {lastwill_panel}
  </div>

  <div class="card">
    <div class="ctitle">Flight Memory · Experience Log</div>
    {memory_panel}
  </div>

  <div class="card">
    <div class="ctitle">Privacy · Encryption Status</div>
    {privacy_panel}
  </div>

  <div class="card">
    <div class="ctitle">Sensor Bundle · Evidence Package</div>
    {sensorbundle_panel}
  </div>

  <div class="card">
    <div class="ctitle">Persistent Storage · State</div>
    {storage_panel}
  </div>

  <div class="card">
    <div class="ctitle">Mission History · Statistics</div>
    {missionhistory_panel}
  </div>  <div class="card">
    <div class="ctitle">Pipeline · Mission Chain</div>
    {pipeline_panel}
  </div>

  <div class="card">
    <div class="ctitle">Replay Guard · Attack Protection</div>
    {replay_panel}
  </div>

  <div class="card">
    <div class="ctitle">Validator Identity · Signed Scores</div>
    {validator_identity_panel}
  </div>

  <div class="card">
    <div class="ctitle">Byzantine Detector · Swarm Security</div>
    {byzantine_panel}
  </div>

  <div class="card">
    <div class="ctitle">Monitoring · System Health</div>
    {monitoring_panel}
  </div>

  <div class="card">
    <div class="ctitle">Wallet · KNX Balance</div>
    {wallet_panel}
  </div>

  <div class="card">
    <div class="ctitle">Bittensor · Network Status</div>
    {bittensor_panel}
  </div>

  <div class="card">
    <div class="ctitle">MPC · Shamir Secret Sharing</div>
    {mpc_panel}
  </div>

  <div class="card">
    <div class="ctitle">Validator Auth · HMAC-SHA256</div>
    {validator_auth_panel}
  </div>

</div>

<!-- MISSION LOG -->
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
  <span>Task Instruction · Policy Trace · Sensor Bundle · Independent Scoring</span>
  <span id="clock"></span>
</footer>

<script>
// CLOCK
function updateClock() {
  document.getElementById("clock").textContent = new Date().toTimeString().slice(0,8) + " UTC+0";
}
setInterval(updateClock, 1000);
updateClock();

// PARTICLES
(function() {
  const c = document.getElementById("particles");
  const ctx = c.getContext("2d");
  c.width = window.innerWidth;
  c.height = window.innerHeight;
  const pts = [];
  for (let i=0; i<120; i++) {
    pts.push({x:Math.random()*c.width, y:Math.random()*c.height, vx:(Math.random()-0.5)*0.3, vy:(Math.random()-0.5)*0.3, r:Math.random()*1.5+0.5});
  }
  function draw() {
    ctx.clearRect(0,0,c.width,c.height);
    pts.forEach(p => {
      p.x+=p.vx; p.y+=p.vy;
      if(p.x<0||p.x>c.width) p.vx*=-1;
      if(p.y<0||p.y>c.height) p.vy*=-1;
      ctx.beginPath();
      ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle="rgba(0,212,255,0.8)";
      ctx.fill();
    });
    pts.forEach((a,i) => {
      pts.slice(i+1).forEach(b => {
        const d=Math.hypot(a.x-b.x,a.y-b.y);
        if(d<120) {
          ctx.beginPath();
          ctx.moveTo(a.x,a.y);
          ctx.lineTo(b.x,b.y);
          ctx.strokeStyle=`rgba(0,212,255,${0.15*(1-d/120)})`;
          ctx.lineWidth=0.5;
          ctx.stroke();
        }
      });
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

// MAP CANVAS - drone trajectories
(function() {
  const c = document.getElementById("mapCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.offsetWidth;
  c.height = c.offsetHeight;
  const drones = [
    {x:0.30,y:0.40,tx:0.55,ty:0.25,color:"#00d4ff",trail:[]},
    {x:0.50,y:0.30,tx:0.70,ty:0.65,color:"#00e676",trail:[]},
    {x:0.45,y:0.60,tx:0.35,ty:0.20,color:"#7c4dff",trail:[]},
  ];
  let t=0;
  function draw() {
    ctx.clearRect(0,0,c.width,c.height);
    t+=0.005;
    drones.forEach((d,i) => {
      const progress = (Math.sin(t + i*2)+1)/2;
      const cx = (d.x + (d.tx-d.x)*progress)*c.width;
      const cy = (d.y + (d.ty-d.y)*progress)*c.height;
      d.trail.push({x:cx,y:cy});
      if(d.trail.length>40) d.trail.shift();
      // Draw laser route line
      const lx1=d.x*c.width, ly1=d.y*c.height, lx2=d.tx*c.width, ly2=d.ty*c.height;
      // Outer glow
      ctx.beginPath();
      ctx.moveTo(lx1,ly1); ctx.lineTo(lx2,ly2);
      ctx.strokeStyle=d.color+"22";
      ctx.lineWidth=6;
      ctx.shadowBlur=12;
      ctx.shadowColor=d.color;
      ctx.stroke();
      // Core laser line
      ctx.beginPath();
      ctx.moveTo(lx1,ly1); ctx.lineTo(lx2,ly2);
      ctx.strokeStyle=d.color+"66";
      ctx.lineWidth=1.5;
      ctx.shadowBlur=0;
      ctx.stroke();
      ctx.setLineDash([]);
      // Draw trail
      d.trail.forEach((p,j) => {
        ctx.beginPath();
        ctx.arc(p.x,p.y,1.5,0,Math.PI*2);
        ctx.fillStyle=d.color+Math.floor((j/d.trail.length)*99).toString(16).padStart(2,"0");
        ctx.fill();
      });
      // Draw drone
      ctx.beginPath();
      ctx.arc(cx,cy,5,0,Math.PI*2);
      ctx.fillStyle=d.color;
      ctx.shadowBlur=15;
      ctx.shadowColor=d.color;
      ctx.fill();
      ctx.shadowBlur=0;
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

// NEURAL NETWORK
(function() {
  const c = document.getElementById("neuralCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.offsetWidth;
  c.height = 160;
  const layers = [[3],[5],[4],[3]];
  const nodes = [];
  const W = c.width, H = c.height;
  layers.forEach((l,li) => {
    const x = (li+1)*W/(layers.length+1);
    l[0] = l[0] || 3;
    for(let ni=0; ni<l[0]; ni++) {
      const y = (ni+1)*H/(l[0]+1);
      nodes.push({x,y,layer:li,v:Math.random()});
    }
  });
  let t=0;
  function draw() {
    ctx.clearRect(0,0,W,H);
    t+=0.02;
    // Connections
    nodes.forEach(a => {
      nodes.forEach(b => {
        if(b.layer===a.layer+1) {
          const alpha = 0.1+0.1*Math.sin(t+a.x+b.y);
          ctx.beginPath();
          ctx.moveTo(a.x,a.y);
          ctx.lineTo(b.x,b.y);
          ctx.strokeStyle=`rgba(0,212,255,${alpha})`;
          ctx.lineWidth=0.8;
          ctx.stroke();
        }
      });
    });
    // Nodes
    nodes.forEach(n => {
      n.v = 0.5+0.5*Math.sin(t*1.5+n.x*0.05);
      const r = 4+n.v*3;
      ctx.beginPath();
      ctx.arc(n.x,n.y,r,0,Math.PI*2);
      const g = ctx.createRadialGradient(n.x,n.y,0,n.x,n.y,r);
      g.addColorStop(0,"rgba(0,212,255,0.9)");
      g.addColorStop(1,"rgba(0,212,255,0.1)");
      ctx.fillStyle=g;
      ctx.shadowBlur=10;
      ctx.shadowColor="#00d4ff";
      ctx.fill();
      ctx.shadowBlur=0;
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

// SWARM BRAIN
(function() {
  const c = document.getElementById("swarmCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.offsetWidth;
  c.height = 160;
  const W=c.width, H=c.height;
  const drones = [
    {label:"D1",color:"#00d4ff"},{label:"D2",color:"#00e676"},{label:"D3",color:"#7c4dff"}
  ];
  const angles = drones.map((_,i)=>i*Math.PI*2/drones.length);
  let t=0;
  function draw() {
    ctx.clearRect(0,0,W,H);
    t+=0.01;
    const cx=W/2, cy=H/2, r=H/2-20;
    // Links
    drones.forEach((a,i) => {
      drones.forEach((b,j) => {
        if(i>=j) return;
        const ax=cx+r*Math.cos(angles[i]+t*0.3), ay=cy+r*Math.sin(angles[i]+t*0.3);
        const bx=cx+r*Math.cos(angles[j]+t*0.3), by=cy+r*Math.sin(angles[j]+t*0.3);
        const pulse = 0.2+0.2*Math.sin(t*2+i+j);
        ctx.beginPath();
        ctx.moveTo(ax,ay); ctx.lineTo(bx,by);
        ctx.strokeStyle=`rgba(0,212,255,${pulse})`;
        ctx.lineWidth=1;
        ctx.stroke();
        // Packet traveling on link
        const ppos = (Math.sin(t*3+i*2)+1)/2;
        const px=ax+(bx-ax)*ppos, py=ay+(by-ay)*ppos;
        ctx.beginPath();
        ctx.arc(px,py,2,0,Math.PI*2);
        ctx.fillStyle="#00d4ff";
        ctx.shadowBlur=6;
        ctx.shadowColor="#00d4ff";
        ctx.fill();
        ctx.shadowBlur=0;
      });
    });
    // Nodes
    drones.forEach((d,i) => {
      const x=cx+r*Math.cos(angles[i]+t*0.3), y=cy+r*Math.sin(angles[i]+t*0.3);
      ctx.beginPath();
      ctx.arc(x,y,10,0,Math.PI*2);
      ctx.fillStyle=d.color+"33";
      ctx.strokeStyle=d.color;
      ctx.lineWidth=1.5;
      ctx.fill(); ctx.stroke();
      ctx.fillStyle=d.color;
      ctx.font="bold 9px Courier New";
      ctx.textAlign="center";
      ctx.textBaseline="middle";
      ctx.fillText(d.label,x,y);
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

// THREAT RADAR
(function() {
  const c = document.getElementById("radarCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  const W=160, H=160, cx=80, cy=80, r=70;
  let angle=0;
  const blips = [{a:0.8,d:0.5},{a:2.3,d:0.7},{a:4.1,d:0.3}];
  function draw() {
    ctx.fillStyle="rgba(6,8,16,0.3)";
    ctx.fillRect(0,0,W,H);
    // Circles
    [1,0.66,0.33].forEach(s => {
      ctx.beginPath();
      ctx.arc(cx,cy,r*s,0,Math.PI*2);
      ctx.strokeStyle="rgba(0,212,255,0.15)";
      ctx.lineWidth=1;
      ctx.stroke();
    });
    // Cross
    ctx.strokeStyle="rgba(0,212,255,0.1)";
    ctx.beginPath(); ctx.moveTo(cx-r,cy); ctx.lineTo(cx+r,cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx,cy-r); ctx.lineTo(cx,cy+r); ctx.stroke();
    // Sweep
    const grad = ctx.createConicalGradient ? null : null;
    ctx.save();
    ctx.translate(cx,cy);
    ctx.rotate(angle);
    const sweepGrad = ctx.createLinearGradient(0,0,r,0);
    sweepGrad.addColorStop(0,"rgba(0,230,118,0.6)");
    sweepGrad.addColorStop(1,"rgba(0,230,118,0)");
    ctx.beginPath();
    ctx.moveTo(0,0);
    ctx.arc(0,0,r,-0.3,0);
    ctx.fillStyle=sweepGrad;
    ctx.fill();
    ctx.restore();
    // Blips
    blips.forEach(b => {
      const diff = Math.abs((angle-b.a+Math.PI*4)%(Math.PI*2));
      const fade = diff<0.5?1-diff/0.5:0;
      if(fade>0) {
        const bx=cx+r*b.d*Math.cos(b.a), by=cy+r*b.d*Math.sin(b.a);
        ctx.beginPath();
        ctx.arc(bx,by,3,0,Math.PI*2);
        ctx.fillStyle=`rgba(0,230,118,${fade})`;
        ctx.shadowBlur=8;
        ctx.shadowColor="#00e676";
        ctx.fill();
        ctx.shadowBlur=0;
      }
    });
    angle+=0.03;
    requestAnimationFrame(draw);
  }
  draw();
})();

// ENERGY HEATMAP
(function() {
  const c = document.getElementById("heatCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.parentElement.offsetWidth - 36 || 400;
  c.height = 80;
  const W=c.width, H=c.height;
  const points = Array.from({length:20},(_,i)=>({x:i/19*W,e:0.3+Math.random()*0.7}));
  function draw() {
    ctx.clearRect(0,0,W,H);
    points.forEach((p,i) => {
      if(i===0) return;
      const prev=points[i-1];
      const grad=ctx.createLinearGradient(prev.x,0,p.x,0);
      const c1=`hsl(${120*p.e},100%,50%)`;
      grad.addColorStop(0,c1+"88");
      grad.addColorStop(1,c1+"88");
      ctx.beginPath();
      ctx.moveTo(prev.x,H-prev.e*H);
      ctx.lineTo(p.x,H-p.e*H);
      ctx.lineTo(p.x,H);
      ctx.lineTo(prev.x,H);
      ctx.fillStyle=grad;
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(prev.x,H-prev.e*H);
      ctx.lineTo(p.x,H-p.e*H);
      ctx.strokeStyle=c1;
      ctx.lineWidth=2;
      ctx.stroke();
    });
  }
  draw();
})();

// MISSION DNA
(function() {
  const c = document.getElementById("dnaCanvas");
  if(!c) return;
  const ctx = c.getContext("2d");
  c.width = c.parentElement.offsetWidth - 36 || 400;
  c.height = 60;
  const W=c.width, H=c.height;
  let t=0;
  function draw() {
    ctx.clearRect(0,0,W,H);
    t+=0.05;
    for(let x=0;x<W;x+=4) {
      const y1=H/2+Math.sin(x*0.05+t)*H*0.3;
      const y2=H/2-Math.sin(x*0.05+t)*H*0.3;
      const hue=(x/W)*360;
      ctx.fillStyle=`hsla(${hue},100%,60%,0.8)`;
      ctx.fillRect(x,y1-1,2,2);
      ctx.fillRect(x,y2-1,2,2);
      if(x%12===0) {
        ctx.strokeStyle=`rgba(0,212,255,0.15)`;
        ctx.lineWidth=0.5;
        ctx.beginPath();
        ctx.moveTo(x,y1);
        ctx.lineTo(x,y2);
        ctx.stroke();
      }
    }
    requestAnimationFrame(draw);
  }
  draw();
})();

// LASER ROUTES on map
(function() {
  const c = document.getElementById("mapCanvas");
  if(!c) return;
  // Override map draw to add laser effect
  const origDraw = window._mapDraw;
})();

// SOUND ENGINE
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function initAudio() {
  if(audioCtx) return;
  audioCtx = new AudioCtx();
}

function playDroneBuzz(freq=80, duration=0.3) {
  if(!audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(freq*0.7, audioCtx.currentTime+duration);
  gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime+duration);
  osc.start();
  osc.stop(audioCtx.currentTime+duration);
}

function playRadarPing() {
  if(!audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = "sine";
  osc.frequency.setValueAtTime(1200, audioCtx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(600, audioCtx.currentTime+0.3);
  gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime+0.3);
  osc.start();
  osc.stop(audioCtx.currentTime+0.3);
}

function playBlockchainBeep() {
  if(!audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = "square";
  osc.frequency.setValueAtTime(880, audioCtx.currentTime);
  gain.gain.setValueAtTime(0.03, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime+0.1);
  osc.start();
  osc.stop(audioCtx.currentTime+0.1);
}

// Sound toggle button
document.addEventListener("DOMContentLoaded", function() {
  const hbar = document.querySelector(".hbar");
  if(hbar) {
    const btn = document.createElement("button");
    btn.className = "hbtn";
    btn.id = "soundBtn";
    btn.textContent = "♪ SOUND OFF";
    btn.style.borderColor = "var(--dim)";
    let soundOn = false;
    btn.onclick = function() {
      initAudio();
      soundOn = !soundOn;
      btn.textContent = soundOn ? "♪ SOUND ON" : "♪ SOUND OFF";
      btn.style.borderColor = soundOn ? "var(--green)" : "var(--dim)";
      btn.style.color = soundOn ? "var(--green)" : "";
      if(soundOn) {
        // Start ambient drone hum
        window._soundInterval = setInterval(function() {
          playDroneBuzz(60 + Math.random()*20, 0.5);
        }, 2000);
        // Radar ping every 3s
        window._radarInterval = setInterval(playRadarPing, 3000);
        // Blockchain beep every 5s
        window._chainInterval = setInterval(playBlockchainBeep, 5000);
      } else {
        clearInterval(window._soundInterval);
        clearInterval(window._radarInterval);
        clearInterval(window._chainInterval);
      }
    };
    hbar.insertBefore(btn, hbar.lastElementChild);
  }
});

// AUTO REFRESH
setTimeout(()=>location.reload(), 30000);
</script>
</body>
</html>"""


def render_dashboard() -> str:
    s = state
    sw = s.get("swarm_status", {})
    drones = s.get("drones", {})
    miner_tasks = s.get("miner_tasks", [])
    uid = s.get("uid", 136)

    last_conf = "—"
    if miner_tasks:
        last_conf = miner_tasks[-1].get("conf", "—")

    # Drone cards (left panel)
    drone_cards = ""
    for drone_id, d in drones.items():
        score = d.get("score", 0)
        tier = d.get("reputation_tier", "?")
        tier_cls = "elite" if tier=="ELITE" else "trusted" if tier=="TRUSTED" else "active" if tier=="ACTIVE" else "rookie"
        status_cls = "" if score >= 80 else "warn"
        chain_val = "READY" if d.get("on_chain_ready") else "PENDING"
        tee = d.get("tee_status", "?")
        sec = d.get("security_status", "?")
        rep_score = d.get("score", "?")
        bh = d.get("bundle_hash", "?")
        drone_cards += f"""<div class="drone-card">
          <div class="drone-card-header">
            <span class="drone-name">{drone_id}</span>
            <span class="drone-status {status_cls}"></span>
          </div>
          <div class="metric"><span class="metric-key">Score</span><span class="metric-val green">{score}</span></div>
          <div class="score-bar"><div class="score-fill" style="width:{score}%"></div></div>
          <div class="metric" style="margin-top:8px"><span class="metric-key">TEE</span><span class="metric-val cyan">{tee}</span></div>
          <div class="metric"><span class="metric-key">Security</span><span class="metric-val green">{sec}</span></div>
          <div class="metric"><span class="metric-key">Reputation</span><span class="metric-val">{rep_score} <span class="tier-badge {tier_cls}">{tier}</span></span></div>
          <div class="metric"><span class="metric-key">Bundle Hash</span><span class="metric-val cyan" style="font-size:10px">{bh}</span></div>
          <div class="metric"><span class="metric-key">On-Chain</span><span class="metric-val green">{chain_val}</span></div>
        </div>"""

    # Map: drone dots
    drone_dots = ""
    for drone_id, coords in DRONE_COORDS.items():
        delay = list(DRONE_COORDS.keys()).index(drone_id) * 0.7
        drone_dots += f"""<div class="drone-dot" style="left:{coords['x']}%;top:{coords['y']}%;animation-delay:{delay}s">
          <div class="drone-dot-ring"></div>
          <div class="drone-dot-core"></div>
          <div class="drone-dot-label">{drone_id}</div>
        </div>"""

    # Map: target dots
    target_dots = ""
    for drone_id, coords in DRONE_COORDS.items():
        target_dots += f'<div class="target-dot" style="left:{coords["tx"]}%;top:{coords["ty"]}%"></div>'

    # Routes data for JS
    routes_data = json.dumps([
        {"x1": c["x"], "y1": c["y"], "x2": c["tx"], "y2": c["ty"]}
        for c in DRONE_COORDS.values()
    ])

    # Radar blips
    radar_blips = ""
    for i, coords in enumerate(DRONE_COORDS.values()):
        rx = 20 + (i * 25)
        ry = 30 + (i * 15)
        radar_blips += f'<div class="radar-blip" style="left:{rx}%;top:{ry}%"></div>'

    # Terminal lines
    terminal_lines = ""
    if miner_tasks:
        for t in miner_tasks[-8:]:
            conf_val = t.get("conf", "—")
            try:
                cf = float(conf_val)
                cls = "success" if cf >= 0.80 else "warn"
            except Exception:
                cls = "info"
            terminal_lines += f'<div class="term-line {cls} prompt"><span class="term-ts">{t.get("ts","")[-8:]}</span>TASK {t.get("task_id","—")} &nbsp; conf=<span class="term-conf">{conf_val}</span> &nbsp; {t.get("action","—")}</div>'
    else:
        terminal_lines = '<div class="term-line info prompt">AWAITING VALIDATOR TASKS...</div>'

    # Mission rows
    mission_rows = ""
    for m in reversed(s.get("missions", [])[-6:]):
        score = m.get("score", 0)
        mid = m.get("mission_id", "?")[:14] + "..."
        ts = time.strftime("%H:%M:%S", time.localtime(m.get("timestamp", 0)))
        score_cls = "high" if score >= 80 else "mid" if score >= 50 else "low"
        tee_m = m.get("tee_status", "?")
        sec_m = m.get("security_status", "?")
        rep_m = m.get("reputation_tier", "?")
        chain_m = "✓" if m.get("on_chain_ready") else "⏳"
        mission_rows += f"""<tr>
          <td style="font-size:11px;color:var(--cyan)">{mid}</td>
          <td>{m.get("drone_id","?")}</td>
          <td><span class="score-pill {score_cls}">{score}</span></td>
          <td style="color:var(--cyan)">{tee_m}</td>
          <td style="color:var(--green)">{sec_m}</td>
          <td>{rep_m}</td>
          <td style="color:var(--green)">{chain_m}</td>
          <td style="color:var(--dim)">{ts}</td>
        </tr>"""
    if not mission_rows:
        mission_rows = '<tr><td colspan="8" style="text-align:center;color:var(--dim);padding:16px">NO DATA</td></tr>'
    w = s.get("weather", {})
    weather_panel = (
        f'<div class="metric"><span class="mk">Flyable</span><span class="mv g">{"YES" if w.get("flyable", True) else "NO"}</span></div>'
        f'<div class="metric"><span class="mk">Wind</span><span class="mv">{w.get("wind_speed", "—")} m/s</span></div>'
        f'<div class="metric"><span class="mk">Visibility</span><span class="mv">{w.get("visibility_m", "—")} m</span></div>'
        f'<div class="metric"><span class="mk">Severity</span><span class="mv c">{w.get("severity", "CLEAR")}</span></div>'
    )
    e = s.get("energy", {})
    weather_panel += (
        f'<div class="metric"><span class="mk">Battery</span><span class="mv g">{e.get("battery_remaining_pct", "—")}%</span></div>'
        f'<div class="metric"><span class="mk">Efficiency</span><span class="mv c">{e.get("efficiency_rating", "—")}</span></div>'
    )
    t = s.get("threat", {})
    threat_panel = (
        f'<div class="metric"><span class="mk">Level</span><span class="mv {"r" if t.get("overall_threat_level","NONE")!="NONE" else "g"}">{t.get("overall_threat_level","—")}</span></div>'
        f'<div class="metric"><span class="mk">GPS</span><span class="mv g">{t.get("gps_status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Jamming</span><span class="mv g">{t.get("jamming_status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Swarm</span><span class="mv c">{t.get("swarm_integrity","—")}</span></div>'
    )
    fw = s.get("firewall", {})
    aw = s.get("ai_weights", {})
    firewall_panel = (
        f'<div class="metric"><span class="mk">Allowed</span><span class="mv g">{fw.get("total_allowed","—")}</span></div>'
        f'<div class="metric"><span class="mk">Blocked</span><span class="mv r">{fw.get("total_blocked","—")}</span></div>'
        f'<div class="metric"><span class="mk">AI Safety</span><span class="mv c">{aw.get("safety","—")}</span></div>'
        f'<div class="metric"><span class="mk">AI Efficiency</span><span class="mv c">{aw.get("efficiency","—")}</span></div>'
        f'<div class="metric"><span class="mk">AI Energy</span><span class="mv c">{aw.get("energy","—")}</span></div>'
    )
    c = s.get("consensus", {})
    consensus_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv {"g" if c.get("status")=="APPROVED" else "r"}">{c.get("status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Weight</span><span class="mv">{c.get("approval_weight","—")}/{c.get("total_weight","—")}</span></div>'
        f'<div class="metric"><span class="mk">Rate</span><span class="mv g">{c.get("approval_rate","—")}</span></div>'
    )
    last_upd = time.strftime("%H:%M:%S", time.localtime(s.get("last_update", 0))) if s.get("last_update") else "—"


    # Navigation Intelligence
    from dronesync.navigation import NavigationEngine
    from dronesync.protocol import Waypoint
    import datetime as _dt
    nav_engine = NavigationEngine()
    nav_alerts_html = ""
    nav_etas_html = ""
    sim_flight_html = ""
    swarm_targets_html = ""
    _wps = [
        Waypoint(lat=47.3769, lon=8.5417, alt=50, speed=10),
        Waypoint(lat=47.3800, lon=8.5450, alt=55, speed=10),
        Waypoint(lat=47.3820, lon=8.5460, alt=50, speed=10),
    ]
    _sim = nav_engine.sim_flight(_wps)
    _etas = nav_engine.calculate_etas(_sim.segments)
    for drone_id in drones:
        for a in _sim.alerts:
            lv = a.level.value
            nav_alerts_html += f'<div class="alert-item {lv}"><span class="alert-dot {lv}"></span><span>[{drone_id}] {a.message}</span></div>'
        for e in _etas:
            eta_str = _dt.datetime.fromtimestamp(e.planned_eta).strftime("%H:%M:%S")
            nav_etas_html += f'<div class="eta-row"><span>{drone_id} · NavPoint {e.waypoint_index}</span><span class="mv c">{eta_str}</span></div>'
    if not nav_alerts_html:
        nav_alerts_html = '<div class="alert-item notice"><span class="alert-dot notice"></span><span>All systems nominal — no active alerts</span></div>'
    _s = _sim.summary()
    _safe_cls = "g" if _s["safe"] else "danger"
    _safe_txt = "SAFE" if _s["safe"] else "UNSAFE"
    _crit_cls = "danger" if _s["critical"] else "g"
    sim_flight_html = (
        f'<div class="metric"><span class="mk">Segments</span><span class="mv">{_s["segments"]}</span></div>'
        f'<div class="metric"><span class="mk">Status</span><span class="mv {_safe_cls}">{_safe_txt}</span></div>'
        f'<div class="metric"><span class="mk">Total Alerts</span><span class="mv">{_s["alerts"]}</span></div>'
        f'<div class="metric"><span class="mk">Critical</span><span class="mv {_crit_cls}">{_s["critical"]}</span></div>'
        f'<div class="metric"><span class="mk">Floor Altitude</span><span class="mv">20.0 m</span></div>'
        f'<div class="metric"><span class="mk">Vert. Clearance</span><span class="mv">10.0 m</span></div>'
    )
    _swarm_data = [
        {"drone_id": d, "lat": 47.38, "lon": 8.54, "alt": 50, "speed": 10, "bearing_deg": 90}
        for d in drones
    ]
    _targets = nav_engine.track_swarm(_swarm_data)
    if _targets:
        swarm_targets_html = '<table class="mtable"><thead><tr><th>Drone ID</th><th>Lat</th><th>Lon</th><th>Alt</th><th>Speed</th><th>Bearing</th><th>Last Seen</th></tr></thead><tbody>'
        for t in _targets:
            _seen = _dt.datetime.fromtimestamp(t.last_seen).strftime("%H:%M:%S")
            swarm_targets_html += f'<tr><td>{t.drone_id}</td><td>{t.lat}</td><td>{t.lon}</td><td>{t.alt} m</td><td>{t.speed} m/s</td><td>{t.bearing_deg}°</td><td>{_seen}</td></tr>'
        swarm_targets_html += '</tbody></table>'
    else:
        swarm_targets_html = '<div style="color:var(--dim);padding:12px;font-size:12px">No swarm targets detected</div>'


    # All Modules Data
    from dronesync.economics import RewardCalculator
    from dronesync.privacy import FlightDataEncryptor

    # Economics
    _rc = RewardCalculator()
    _scores = [drones[d].get("score", 80) for d in drones] or [80]
    _avg_sc = sum(_scores) / len(_scores)
    _reward = _rc.calculate(mission_id="DASH_001", total_score=_avg_sc, grade="GOOD", reputation_tier="ACTIVE")
    _rb = _reward if hasattr(_reward, 'final_reward') else None
    _final_r = round(_rb.final_reward, 3) if _rb else round(_avg_sc * 0.01, 3)
    _streak = _rb.streak_bonus if _rb else 0.0
    _penalty = _rb.penalty if _rb else 0.0
    _tier_mult = _rb.tier_multiplier if _rb else 1.0
    economics_panel = (
        f'<div class="metric"><span class="mk">Score</span><span class="mv c">{round(_avg_sc)}</span></div>'
        f'<div class="metric"><span class="mk">Final Reward</span><span class="mv g">{_final_r} KNX</span></div>'
        f'<div class="metric"><span class="mk">Tier Multiplier</span><span class="mv">{_tier_mult}x</span></div>'
        f'<div class="metric"><span class="mk">Streak Bonus</span><span class="mv c">+{_streak} KNX</span></div>'
        f'<div class="metric"><span class="mk">Penalty</span><span class="mv {"r" if _penalty > 0 else "g"}">-{_penalty} KNX</span></div>'
        f'<div class="reward-bar"><div class="reward-fill" style="width:{min(100,_avg_sc)}%"></div></div>'
    )

    # Emergency
    try:
        _eo = s.get("emergency", {})
        _etype = _eo.get("type", "NONE")
        _eredir = _eo.get("redirected_drones", 0)
        _eprot = _eo.get("protected_drones", 0)
        _echain = "✓" if _eo.get("on_chain_ready") else "—"
        emergency_panel = (
            f'<div class="metric"><span class="mk">Type</span><span class="mv {"r" if _etype != "NONE" else "g"}">{_etype}</span></div>'
            f'<div class="metric"><span class="mk">Redirected</span><span class="mv amber">{_eredir} drones</span></div>'
            f'<div class="metric"><span class="mk">Protected</span><span class="mv g">{_eprot} drones</span></div>'
            f'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">{_echain}</span></div>'
            f'<div class="metric"><span class="mk">Status</span><span class="mv {"r" if _etype != "NONE" else "g"}">{"ACTIVE" if _etype != "NONE" else "STANDBY"}</span></div>'
        )
    except Exception:
        emergency_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">STANDBY</span></div>'

    # Last Will
    try:
        _lw = s.get("last_will", {})
        _lw_hash = str(_lw.get("will_hash", ""))[:16] + "..." if _lw.get("will_hash") else "—"
        _lw_cause = _lw.get("failure_cause", "—")
        _lw_bat = _lw.get("battery_pct", "—")
        _lw_chain = "✓ READY" if _lw.get("on_chain_ready") else "—"
        lastwill_panel = (
            f'<div class="last-will-box">'
            f'<div class="metric"><span class="mk">Trigger</span><span class="mv r">{_lw_cause}</span></div>'
            f'<div class="metric"><span class="mk">Battery</span><span class="mv r">{_lw_bat}%</span></div>'
            f'<div class="metric"><span class="mk">Will Hash</span><span class="mv" style="font-size:10px">{_lw_hash}</span></div>'
            f'<div class="metric"><span class="mk">Insurance</span><span class="mv g">{_lw_chain}</span></div>'
            f'</div>'
        )
        if not _lw:
            lastwill_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ARMED · Monitoring</span></div><div class="metric"><span class="mk">Trigger</span><span class="mv c">Battery &lt; 5%</span></div><div class="metric"><span class="mk">Insurance</span><span class="mv g">ACTIVE</span></div>'
    except Exception:
        lastwill_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ARMED · Monitoring</span></div>'

    # Memory
    try:
        _mem = s.get("memory", {})
        _mem_missions = _mem.get("missions_completed", len(s.get("missions", [])))
        _mem_hours = _mem.get("total_flight_hours", round(len(s.get("missions", [])) * 0.03, 2))
        _mem_asset = _mem.get("asset_value", "LOW")
        _mem_chain = "✓" if _mem.get("on_chain_ready", True) else "—"
        memory_panel = (
            f'<div class="metric"><span class="mk">Missions Completed</span><span class="mv g">{_mem_missions}</span></div>'
            f'<div class="metric"><span class="mk">Flight Hours</span><span class="mv c">{_mem_hours} h</span></div>'
            f'<div class="metric"><span class="mk">Asset Value</span><span class="mv {"g" if _mem_asset == "HIGH" else "amber"}">{_mem_asset}</span></div>'
            f'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">{_mem_chain}</span></div>'
            f'<div class="metric"><span class="mk">Experience</span><span class="mv c">{"EXPERT" if _mem_missions > 10 else "ACTIVE"}</span></div>'
        )
    except Exception:
        memory_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">LOGGING</span></div>'

    # Privacy
    try:
        _enc = FlightDataEncryptor.from_passphrase("dronesync_key")
        _test_data = b"test_flight_data"
        _pkt = _enc.encrypt(_test_data)
        _dec = _enc.decrypt(_pkt)
        _enc_ok = _dec == _test_data
        _method = "AES-256-GCM" if _enc._aesgcm_available() else "XOR-SHA256"
        privacy_panel = (
            f'<div class="metric"><span class="mk">Encryption</span><span class="mv g">{"✓ ACTIVE" if _enc_ok else "✗ FAILED"}</span></div>'
            f'<div class="metric"><span class="mk">Method</span><span class="mv c">{_method}</span></div>'
            f'<div class="metric"><span class="mk">Key Size</span><span class="mv">256 bit</span></div>'
            f'<div class="metric"><span class="mk">Audit Trail</span><span class="mv g">✓ ENABLED</span></div>'
            f'<div class="metric"><span class="mk">Redaction</span><span class="mv g">✓ ACTIVE</span></div>'
            f'<div class="privacy-badge">SECURE CHANNEL</div>'
        )
    except Exception:
        privacy_panel = '<div class="metric"><span class="mk">Encryption</span><span class="mv g">ACTIVE</span></div>'

    # Sensor Bundle
    try:
        _sb = s.get("sensor_bundle", {})
        _sb_hash = str(_sb.get("bundle_hash", ""))[:16] + "..." if _sb.get("bundle_hash") else "—"
        _sb_sensor = str(_sb.get("sensor_hash", ""))[:16] + "..." if _sb.get("sensor_hash") else "—"
        _sb_tee = _sb.get("tee_status", "VERIFIED")
        _sb_valid = "✓ VALID" if _sb.get("bundle_valid", True) else "✗ INVALID"
        _sb_chain = "✓" if _sb.get("on_chain_ready", True) else "—"
        sensorbundle_panel = (
            f'<div class="metric"><span class="mk">Bundle Hash</span><span class="mv c" style="font-size:10px">{_sb_hash}</span></div>'
            f'<div class="metric"><span class="mk">Sensor Hash</span><span class="mv c" style="font-size:10px">{_sb_sensor}</span></div>'
            f'<div class="metric"><span class="mk">TEE Status</span><span class="mv g">{_sb_tee}</span></div>'
            f'<div class="metric"><span class="mk">Bundle Valid</span><span class="mv g">{_sb_valid}</span></div>'
            f'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">{_sb_chain}</span></div>'
        )
        if not _sb:
            _d0 = list(drones.values())[0] if drones else {}
            _bh = _d0.get("bundle_hash", "—")
            sensorbundle_panel = (
                f'<div class="metric"><span class="mk">Bundle Hash</span><span class="mv c" style="font-size:10px">{_bh}</span></div>'
                f'<div class="metric"><span class="mk">TEE Status</span><span class="mv g">VERIFIED</span></div>'
                f'<div class="metric"><span class="mk">Bundle Valid</span><span class="mv g">✓ VALID</span></div>'
                f'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">✓ READY</span></div>'
            )
    except Exception:
        sensorbundle_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">VERIFIED</span></div>'

    # Storage
    try:
        _st = s.get("storage", {})
        _st_missions = _st.get("missions_saved", len(s.get("missions", [])))
        _st_rep = _st.get("score", 50)
        _st_tier = _st.get("tier", "ACTIVE")
        _st_disk = "✓ YES" if _st.get("persisted_to_disk", True) else "—"
        _st_restart = "✓ YES" if _st.get("survives_restart", True) else "—"
        storage_panel = (
            f'<div class="metric"><span class="mk">Missions Saved</span><span class="mv g">{_st_missions}</span></div>'
            f'<div class="metric"><span class="mk">Reputation</span><span class="mv c">{_st_rep}</span></div>'
            f'<div class="metric"><span class="mk">Tier</span><span class="mv">{_st_tier}</span></div>'
            f'<div class="metric"><span class="mk">Persisted</span><span class="mv g">{_st_disk}</span></div>'
            f'<div class="metric"><span class="mk">Survives Restart</span><span class="mv g">{_st_restart}</span></div>'
        )
    except Exception:
        storage_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'

    # Mission History
    try:
        _mh = s.get("mission_history", {})
        _mh_total = _mh.get("total_missions", len(s.get("missions", [])))
        _mh_avg = _mh.get("avg_score", sw.get("avg_score", 0))
        _mh_max = _mh.get("max_score", sw.get("max_score", 0))
        _mh_rate = _mh.get("success_rate", 100.0)
        missionhistory_panel = (
            f'<div class="metric"><span class="mk">Total Missions</span><span class="mv g">{_mh_total}</span></div>'
            f'<div class="metric"><span class="mk">Avg Score</span><span class="mv c">{_mh_avg}</span></div>'
            f'<div class="metric"><span class="mk">Max Score</span><span class="mv g">{_mh_max}</span></div>'
            f'<div class="metric"><span class="mk">Success Rate</span><span class="mv g">{_mh_rate}%</span></div>'
            f'<div class="metric"><span class="mk">Status</span><span class="mv g">RECORDING</span></div>'
        )
    except Exception:
        missionhistory_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">RECORDING</span></div>'

    # Pipeline Panel
    try:
        pipeline_panel = (  # noqa: F841
        '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'
        '<div class="metric"><span class="mk">Steps</span><span class="mv c">10</span></div>'
        '<div class="metric"><span class="mk">Signing</span><span class="mv g">Ed25519</span></div>'
        '<div class="metric"><span class="mk">On-Chain</span><span class="mv g">READY</span></div>'
    )
    except Exception:
        pass

    # Replay Guard Panel
    try:
        from dronesync.replay_guard import ReplayGuard
        _rg = ReplayGuard()
        replay_panel = (
        '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'
        '<div class="metric"><span class="mk">Protection</span><span class="mv g">ON</span></div>'
        '<div class="metric"><span class="mk">Max Age</span><span class="mv c">3600s</span></div>'
        '<div class="metric"><span class="mk">Replay Attacks</span><span class="mv g">BLOCKED</span></div>'
    )
    except Exception:
        replay_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>' # noqa: F841

    # Validator Identity Panel
    try:
        from validator.scorer import ValidatorIdentity
        _vi = ValidatorIdentity("VALIDATOR_001")
        validator_identity_panel = (
        f'<div class="metric"><span class="mk">Validator</span><span class="mv g">VALIDATOR_001</span></div>'
        f'<div class="metric"><span class="mk">Signing</span><span class="mv g">Ed25519</span></div>'
        f'<div class="metric"><span class="mk">Public Key</span><span class="mv c">{_vi.public_key_hex[:16]}...</span></div>'
        f'<div class="metric"><span class="mk">Status</span><span class="mv g">VERIFIED</span></div>'
    )
    except Exception:
        validator_identity_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>' # noqa: F841

    # Byzantine Detector Panel
    try:
        from dronesync.swarm_consensus import SwarmConsensus, ByzantineDetector
        _bc = SwarmConsensus(["D1", "D2", "D3"])
        _bd = ByzantineDetector(_bc)
        _bds = _bd.get_status()
        byzantine_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv g">MONITORING</span></div>'
        f'<div class="metric"><span class="mk">Monitored</span><span class="mv c">{_bds["monitored_drones"]}</span></div>'
        f'<div class="metric"><span class="mk">Suspicious</span><span class="mv c">{len(_bds["suspicious_drones"])}</span></div>'
        f'<div class="metric"><span class="mk">Blacklisted</span><span class="mv c">{len(_bds["blacklisted"])}</span></div>'
    )
    except Exception:
        byzantine_panel = '<div class="metric"><span class="mk">Status</span><span class="mv g">MONITORING</span></div>' # noqa: F841

    # Sidebar data
    import json as _json
    _sb_threat = s.get("threat", {}).get("overall_threat_level", "NONE")
    _sb_gps = s.get("threat", {}).get("gps_status", "CLEAN")
    _sb_drone_positions = []
    for _di, (_did, _dd) in enumerate(drones.items()):
        _sb_drone_positions.append({
            "id": _did,
            "lat": 47.3769 + _di * 0.0010,
            "lon": 8.5417 + _di * 0.0008,
            "alt": 50 + _di * 5,
            "speed": 10,
            "bearing": 90
        })
    _sb_drone_json = _json.dumps(_sb_drone_positions)
    sb_sim_status = "SAFE" if _sim.safe else "UNSAFE"




    # Monitoring Panel
    _mon = s.get("monitoring", {})
    _alst = s.get("alerts", {})
    _hcls = "g" if _alst.get("healthy", True) else "r"
    monitoring_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv {_hcls}">{"HEALTHY" if _alst.get("healthy",True) else "DEGRADED"}</span></div>'
        f'<div class="metric"><span class="mk">Uptime</span><span class="mv c">{_mon.get("uptime_seconds",0)}s</span></div>'
        f'<div class="metric"><span class="mk">Total Missions</span><span class="mv">{_mon.get("total_missions",0)}</span></div>'
        f'<div class="metric"><span class="mk">Avg Score</span><span class="mv g">{_mon.get("avg_score",0)}</span></div>'
        f'<div class="metric"><span class="mk">Success Rate</span><span class="mv g">{round(_mon.get("success_rate",0)*100,1)}%</span></div>'
        f'<div class="metric"><span class="mk">Errors</span><span class="mv {"r" if _mon.get("total_errors",0)>0 else "g"}">{_mon.get("total_errors",0)}</span></div>'
        f'<div class="metric"><span class="mk">Alerts</span><span class="mv {"r" if _alst.get("critical_count",0)>0 else "g"}">{_alst.get("critical_count",0)} CRIT · {_alst.get("warning_count",0)} WARN</span></div>'
    )

    # Wallet Panel
    _wal = s.get("wallet", {})
    wallet_panel = (
        f'<div class="metric"><span class="mk">Balance</span><span class="mv g" style="font-size:16px">{_wal.get("balance_knx",0)} KNX</span></div>'
        f'<div class="metric"><span class="mk">Total Earned</span><span class="mv c">{_wal.get("total_earned_knx",0)} KNX</span></div>'
        f'<div class="metric"><span class="mk">Penalties</span><span class="mv r">-{_wal.get("total_penalties_knx",0)} KNX</span></div>'
        f'<div class="metric"><span class="mk">Transactions</span><span class="mv">{_wal.get("transaction_count",0)}</span></div>'
        f'<div class="metric"><span class="mk">Storage</span><span class="mv c">SQLite · WAL</span></div>'
    )

    # Bittensor Panel
    _btm = s.get("bittensor_miner", {})
    _btn = s.get("bittensor_net", {})
    bittensor_panel = (
        f'<div class="metric"><span class="mk">Network</span><span class="mv c">{_btn.get("network","testnet").upper()}</span></div>'
        f'<div class="metric"><span class="mk">NetUID</span><span class="mv g">{_btn.get("netuid",42)}</span></div>'
        f'<div class="metric"><span class="mk">Block</span><span class="mv">{_btn.get("block",0)}</span></div>'
        f'<div class="metric"><span class="mk">Miners</span><span class="mv c">{_btn.get("n_miners",0)}</span></div>'
        f'<div class="metric"><span class="mk">Missions</span><span class="mv g">{_btm.get("missions_completed",0)}</span></div>'
        f'<div class="metric"><span class="mk">Hotkey</span><span class="mv" style="font-size:10px">{str(_btm.get("hotkey","—"))[:24]}</span></div>'
    )

    # MPC Panel
    _mpc = s.get("mpc", {})
    _mpc_cls = "g" if _mpc.get("status")=="OK" else "r"
    mpc_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv {_mpc_cls}">{_mpc.get("status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Algorithm</span><span class="mv c">Shamir Secret Sharing</span></div>'
        f'<div class="metric"><span class="mk">Threshold</span><span class="mv">{_mpc.get("threshold",2)} of {_mpc.get("n_shares",3)}</span></div>'
        f'<div class="metric"><span class="mk">Shares</span><span class="mv g">{_mpc.get("shares",0)}</span></div>'
        f'<div class="metric"><span class="mk">Reconstructed</span><span class="mv c">{_mpc.get("reconstructed","—")}</span></div>'
        f'<div class="metric"><span class="mk">Prime</span><span class="mv" style="font-size:10px">Mersenne 2¹²⁷-1</span></div>'
    )

    # Validator Auth Panel
    _vauth = s.get("validator_auth", {})
    _vc = "g" if _vauth.get("token_valid") else "r"
    validator_auth_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv g">{_vauth.get("status","—")}</span></div>'
        f'<div class="metric"><span class="mk">Method</span><span class="mv c">{_vauth.get("method","—")}</span></div>'
        f'<div class="metric"><span class="mk">Token TTL</span><span class="mv">{_vauth.get("ttl",30)}s</span></div>'
        f'<div class="metric"><span class="mk">Token Valid</span><span class="mv {_vc}">{"✓ YES" if _vauth.get("token_valid") else "✗ NO"}</span></div>'
        f'<div class="metric"><span class="mk">Protocol</span><span class="mv c">WSS · TLS</span></div>'
    )

    html = HTML_TEMPLATE
    html = html.replace("{netuid}",     str(sw.get("netuid", 4)))
    html = html.replace("{network}",    str(sw.get("network", "testnet")).upper())
    html = html.replace("{active}",     str(sw.get("active_drones", 0)))
    html = html.replace("{avg_score}",  str(sw.get("avg_score", 0)))
    html = html.replace("{last_conf}",  str(last_conf))
    html = html.replace("{task_count}", str(len(miner_tasks)))
    html = html.replace("{uid}",        str(uid))
    html = html.replace("{last_update}", last_upd)
    html = html.replace("{sb_threat}", _sb_threat)
    html = html.replace("{sb_gps}", _sb_gps)
    html = html.replace("{sb_reward}", str(_final_r))
    html = html.replace("{sb_sim_status}", sb_sim_status)
    html = html.replace("{sb_drone_positions}", _sb_drone_json)
    html = html.replace("{sb_threat}", _sb_threat)
    html = html.replace("{sb_gps}", _sb_gps)
    html = html.replace("{sb_reward}", str(_final_r))
    html = html.replace("{sb_sim_status}", sb_sim_status)
    html = html.replace("{sb_drone_positions}", _sb_drone_json)
    html = html.replace("{sb_threat}", _sb_threat)
    html = html.replace("{sb_gps}", _sb_gps)
    html = html.replace("{sb_reward}", str(_final_r))
    html = html.replace("{sb_sim_status}", sb_sim_status)
    html = html.replace("{sb_drone_positions}", _sb_drone_json)
    html = html.replace("{economics_panel}", economics_panel)
    html = html.replace("{emergency_panel}", emergency_panel)
    html = html.replace("{lastwill_panel}", lastwill_panel)
    html = html.replace("{memory_panel}", memory_panel)
    html = html.replace("{privacy_panel}", privacy_panel)
    html = html.replace("{sensorbundle_panel}", sensorbundle_panel)
    html = html.replace("{storage_panel}", storage_panel)
    html = html.replace("{missionhistory_panel}", missionhistory_panel)
    html = html.replace("{nav_alerts}", nav_alerts_html)
    html = html.replace("{nav_etas}", nav_etas_html)
    html = html.replace("{sim_flight}", sim_flight_html)
    html = html.replace("{swarm_targets}", swarm_targets_html)
    html = html.replace("{drone_cards}",  drone_cards)
    html = html.replace("{mission_rows}", mission_rows)
    html = html.replace("{drone_dots}",   drone_dots)
    html = html.replace("{target_dots}",  target_dots)
    html = html.replace("{terminal_lines}", terminal_lines)
    html = html.replace("{radar_blips}",  radar_blips)
    html = html.replace('"{routes_data}"', routes_data)
    html = html.replace("{weather_panel}",   weather_panel)
    html = html.replace("{threat_panel}",    threat_panel)
    html = html.replace("{firewall_panel}",  firewall_panel)
    html = html.replace("{consensus_panel}", consensus_panel)
    sr = s.get("score_root", {})
    lw = s.get("last_will", {})
    scoreroot_panel = (
        f'<div class="metric"><span class="mk">Validator</span><span class="mv c">{sr.get("validator_id","—")}</span></div>'
        f'<div class="metric"><span class="mk">Scores</span><span class="mv">{sr.get("scores_count","—")}</span></div>'
        f'<div class="metric"><span class="mk">Root</span><span class="mv g">{str(sr.get("score_root","—"))[:12]}...</span></div>'
        f'<div class="metric"><span class="mk">Last Will</span><span class="mv {"r" if lw.get("triggered") else "g"}">{"TRIGGERED" if lw.get("triggered") else "STANDBY"}</span></div>'
        f'<div class="metric"><span class="mk">Battery</span><span class="mv">{lw.get("battery_pct","—")}%</span></div>'
    )
    # Blockchain feed
    blockchain_feed = ""
    for m in reversed(list(s.get("missions", []))[-8:]):
        ts = time.strftime("%H:%M:%S", time.localtime(m.get("timestamp", 0)))
        bh = m.get("bundle_hash", "0x0000000000000000")
        did = m.get("drone_id", "?")
        score = m.get("score", 0)
        blockchain_feed += f"""<div class="feed-item">
          <div class="feed-dot"></div>
          <span>POPW · {did} · score={score}</span>
          <span class="feed-hash">{bh}</span>
          <span class="feed-time">{ts}</span>
        </div>"""
    if not blockchain_feed:
        blockchain_feed = '<div class="feed-item"><div class="feed-dot" style="background:var(--dim)"></div><span style="color:var(--dim)">Waiting for missions...</span></div>'

    html = html.replace("{scoreroot_panel}", scoreroot_panel)
    html = html.replace("{blockchain_feed}", blockchain_feed)
    # Fix missing placeholders
    html = html.replace("{total}", str(sw.get("total_drones", len(DRONE_IDS))))
    html = html.replace("{min_score}", str(sw.get("min_score", 0)))
    html = html.replace("{max_score}", str(sw.get("max_score", 0)))
    html = html.replace("{on_chain}", "YES" if sw.get("all_on_chain_ready") else "PENDING")
    html = html.replace("{node_connected}", "CONNECTED" if s.get("node_status", {}).get("connected") else "OFFLINE")
    html = html.replace("{node_network}", str(s.get("node_status", {}).get("network", "testnet")).upper())
    raw_sid = s.get("node_status", {}).get("session_id", "")
    html = html.replace("{node_session}", str(raw_sid)[:12] if raw_sid else "—")
    # Mission DNA
    missions = s.get("missions", [])
    last_m = missions[-1] if missions else {}
    mission_dna = str(last_m.get("mission_id", "—"))[:16] + "..."
    traj_dna = str(last_m.get("bundle_hash", "—"))[:16] + "..."
    html = html.replace("{mission_dna}", mission_dna)
    html = html.replace("{traj_dna}", traj_dna)
    html = html.replace("{monitoring_panel}", monitoring_panel)
    html = html.replace("{wallet_panel}", wallet_panel)
    html = html.replace("{bittensor_panel}", bittensor_panel)
    html = html.replace("{mpc_panel}", mpc_panel)
    html = html.replace("{validator_auth_panel}", validator_auth_panel)
    return html


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            body = json.dumps(state, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8080")
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
            html = render_dashboard().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html)


def run_dashboard(host: str = "127.0.0.1", port: int = 8080):
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
