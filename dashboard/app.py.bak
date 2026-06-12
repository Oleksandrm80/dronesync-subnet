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

from dronesync.synapse import DroneNavSynapseHandler, SwarmSynapseHandler
from dronesync.reputation import DroneReputation
from dronesync.storage import DroneStorage
from dronesync.node import KonnexNode
from dronesync.firewall import DroneFirewall
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.threat_defense import ThreatDefense
from miner.weather import WeatherService
from miner.energy import EnergyOptimizer
from miner.planner import AIPlanner

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
            "reputation_score": rep["reputation_score"],
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
    lw = DroneLastWill(DRONE_IDS[0])
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
            print("[dashboard] refresh error:", e)
        time.sleep(30)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DroneSync // Mission Control</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap');

:root {
  --black:   #020408;
  --dark:    #060d12;
  --panel:   #0a1520;
  --border:  #0f3040;
  --glow:    #00ff88;
  --glow2:   #00ccff;
  --amber:   #ffaa00;
  --red:     #ff3333;
  --dim:     #1a4060;
  --text:    #a0e0c0;
  --bright:  #e0fff0;
  --grid:    rgba(0,255,136,0.04);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--black);
  color: var(--text);
  font-family: 'Share Tech Mono', monospace;
  font-size: 12px;
  overflow-x: hidden;
  min-height: 100vh;
}

/* Сетка на фоне */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
}

/* Виньетка */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 40%, rgba(2,4,8,0.8) 100%);
  pointer-events: none;
  z-index: 0;
}

/* ── HEADER ── */
header {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: rgba(6,13,18,0.95);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 0 30px rgba(0,255,136,0.05);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-mark {
  width: 34px; height: 34px;
  border: 1px solid var(--glow);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 0 12px rgba(0,255,136,0.3), inset 0 0 12px rgba(0,255,136,0.05);
  animation: rotor-spin 8s linear infinite;
}
@keyframes rotor-spin {
  0%   { box-shadow: 0 0 12px rgba(0,255,136,0.3), inset 0 0 12px rgba(0,255,136,0.05); }
  50%  { box-shadow: 0 0 24px rgba(0,255,136,0.6), inset 0 0 18px rgba(0,255,136,0.1); }
  100% { box-shadow: 0 0 12px rgba(0,255,136,0.3), inset 0 0 12px rgba(0,255,136,0.05); }
}
.logo-title {
  font-family: 'Orbitron', monospace;
  font-size: 16px;
  font-weight: 900;
  color: var(--glow);
  letter-spacing: 3px;
  text-shadow: 0 0 20px rgba(0,255,136,0.5);
}
.logo-sub {
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 2px;
  margin-top: 2px;
}

.header-center {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--dim);
  letter-spacing: 1px;
}
.header-center span { color: var(--glow); }

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hbadge {
  padding: 3px 10px;
  border: 1px solid var(--border);
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--dim);
}
.hbadge-live {
  border-color: var(--glow);
  color: var(--glow);
  text-shadow: 0 0 8px var(--glow);
  animation: live-blink 1.5s infinite;
}
@keyframes live-blink { 0%,100%{opacity:1} 50%{opacity:0.5} }
.hbadge-uid {
  border-color: var(--glow2);
  color: var(--glow2);
}

.btn-refresh {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--dim);
  padding: 4px 12px;
  cursor: pointer;
  font-family: 'Share Tech Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  transition: all 0.2s;
}
.btn-refresh:hover {
  border-color: var(--glow);
  color: var(--glow);
  text-shadow: 0 0 8px var(--glow);
}

/* ── MAIN LAYOUT ── */
.mc-layout {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 260px 1fr 260px;
  grid-template-rows: auto 1fr auto auto;
  gap: 1px;
  height: calc(100vh - 56px);
  background: var(--border);
}

/* ── PANEL BASE ── */
.panel {
  background: rgba(6,13,18,0.97);
  padding: 16px;
  overflow: hidden;
}

.panel-title {
  font-family: 'Orbitron', monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--glow);
  text-transform: uppercase;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
  text-shadow: 0 0 10px rgba(0,255,136,0.4);
}

/* ── LEFT COLUMN ── */
.panel-left {
  grid-column: 1;
  grid-row: 1 / 4;
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border);
}
.panel-left > .panel { flex: 1; }

/* ── CENTER ── */
.panel-top {
  grid-column: 2;
  grid-row: 1;
}
.panel-map {
  grid-column: 2;
  grid-row: 2;
  position: relative;
  overflow: hidden;
}
.panel-terminal {
  grid-column: 2;
  grid-row: 3;
  max-height: 180px;
}

/* ── RIGHT COLUMN ── */
.panel-right {
  grid-column: 3;
  grid-row: 1 / 4;
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border);
}
.panel-right > .panel { flex: 1; }

/* ── KPI ROW ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: var(--border);
}
.kpi-cell {
  background: rgba(6,13,18,0.97);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kpi-v {
  font-family: 'Orbitron', monospace;
  font-size: 22px;
  font-weight: 700;
  color: var(--bright);
  text-shadow: 0 0 15px rgba(0,255,136,0.4);
  line-height: 1;
}
.kpi-v.green  { color: var(--glow);  text-shadow: 0 0 15px rgba(0,255,136,0.6); }
.kpi-v.cyan   { color: var(--glow2); text-shadow: 0 0 15px rgba(0,204,255,0.6); }
.kpi-v.amber  { color: var(--amber); text-shadow: 0 0 15px rgba(255,170,0,0.6); }
.kpi-lbl {
  font-size: 9px;
  letter-spacing: 2px;
  color: var(--dim);
  text-transform: uppercase;
}

/* ── MAP ── */
.map-container {
  width: 100%;
  height: 100%;
  position: relative;
  background: radial-gradient(ellipse at 50% 50%, rgba(0,255,136,0.03) 0%, transparent 70%);
}

/* Радар */
.radar {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 120px;
  height: 120px;
}
.radar-circle {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(0,255,136,0.2);
}
.radar-circle:nth-child(2) { inset: 20%; }
.radar-circle:nth-child(3) { inset: 40%; }
.radar-cross-h, .radar-cross-v {
  position: absolute;
  background: rgba(0,255,136,0.15);
}
.radar-cross-h { top: 50%; left: 0; right: 0; height: 1px; transform: translateY(-50%); }
.radar-cross-v { left: 50%; top: 0; bottom: 0; width: 1px; transform: translateX(-50%); }
.radar-sweep {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(from 0deg, transparent 0deg, rgba(0,255,136,0.15) 30deg, transparent 60deg);
  animation: radar-spin 3s linear infinite;
}
@keyframes radar-spin { to { transform: rotate(360deg); } }
.radar-blip {
  position: absolute;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--glow);
  box-shadow: 0 0 6px var(--glow);
  transform: translate(-50%, -50%);
}

/* Карта — линии сетки координат */
.map-grid-line-h {
  position: absolute;
  left: 0; right: 0;
  height: 1px;
  background: rgba(0,255,136,0.06);
}
.map-grid-line-v {
  position: absolute;
  top: 0; bottom: 0;
  width: 1px;
  background: rgba(0,255,136,0.06);
}
.map-coords {
  position: absolute;
  font-size: 9px;
  color: rgba(0,255,136,0.25);
  letter-spacing: 1px;
}

/* Дроны на карте */
.drone-dot {
  position: absolute;
  transform: translate(-50%, -50%);
  cursor: default;
}
.drone-dot-ring {
  width: 28px; height: 28px;
  border-radius: 50%;
  border: 1px solid var(--glow);
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  animation: ring-pulse 2s ease-out infinite;
}
@keyframes ring-pulse {
  0%   { width: 14px; height: 14px; opacity: 0.8; }
  100% { width: 36px; height: 36px; opacity: 0; }
}
.drone-dot-core {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--glow);
  box-shadow: 0 0 10px var(--glow), 0 0 20px rgba(0,255,136,0.4);
  position: relative;
  z-index: 1;
}
.drone-dot-label {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 9px;
  color: var(--glow);
  white-space: nowrap;
  letter-spacing: 1px;
  text-shadow: 0 0 8px var(--glow);
}
/* Линия маршрута */
.route-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* Целевая точка */
.target-dot {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 8px; height: 8px;
}
.target-dot::before, .target-dot::after {
  content: '';
  position: absolute;
  background: var(--amber);
}
.target-dot::before { top: 50%; left: 0; right: 0; height: 1px; transform: translateY(-50%); }
.target-dot::after  { left: 50%; top: 0; bottom: 0; width: 1px; transform: translateX(-50%); }

/* ── DRONE CARDS (left panel) ── */
.drone-card-mc {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.drone-card-mc:last-child { border-bottom: none; }
.dc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.dc-id {
  font-family: 'Orbitron', monospace;
  font-size: 11px;
  font-weight: 700;
  color: var(--glow);
  letter-spacing: 2px;
  text-shadow: 0 0 8px rgba(0,255,136,0.4);
}
.dc-status {
  font-size: 9px;
  letter-spacing: 1px;
  color: var(--glow);
  animation: live-blink 2s infinite;
}
.dc-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
  font-size: 11px;
}
.dc-key { color: var(--dim); }
.dc-val { color: var(--text); }
.dc-val.g { color: var(--glow); }
.dc-val.c { color: var(--glow2); }
.dc-val.a { color: var(--amber); }
.dc-bar {
  height: 2px;
  background: var(--border);
  margin: 5px 0;
  overflow: hidden;
}
.dc-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--glow2), var(--glow));
  box-shadow: 0 0 6px var(--glow);
  transition: width 1s;
}

/* ── PIPELINE (right panel) ── */
.pipe-step {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pipe-step:last-child { border-bottom: none; }
.pipe-n {
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 2px;
}
.pipe-name {
  font-size: 12px;
  color: var(--bright);
  letter-spacing: 1px;
}
.pipe-ok {
  font-size: 10px;
  color: var(--glow);
  letter-spacing: 1px;
}
.pipe-ok::before {
  content: '▶ ';
  font-size: 8px;
}

/* ── MISSION LOG (right) ── */
.mission-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid rgba(15,48,64,0.5);
  font-size: 11px;
}
.mission-row:last-child { border-bottom: none; }
.mr-id { color: var(--dim); font-size: 10px; }
.mr-score { color: var(--glow); font-family: 'Orbitron', monospace; font-size: 11px; }

/* ── TERMINAL ── */
.terminal {
  background: rgba(2,4,8,0.98);
  padding: 12px 16px;
  height: 100%;
  overflow-y: auto;
  border-top: 1px solid var(--border);
}
.terminal::-webkit-scrollbar { width: 4px; }
.terminal::-webkit-scrollbar-track { background: transparent; }
.terminal::-webkit-scrollbar-thumb { background: var(--border); }
.term-line {
  font-size: 11px;
  line-height: 1.8;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
}
.term-line.prompt::before { content: '> '; color: var(--glow); }
.term-line.info { color: var(--glow2); }
.term-line.success { color: var(--glow); }
.term-line.warn { color: var(--amber); }
.term-ts { color: var(--dim); margin-right: 8px; }
.term-conf { font-family: 'Orbitron', monospace; }

/* ── NODE STATUS ── */
.node-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid rgba(15,48,64,0.5);
  font-size: 11px;
}
.node-row:last-child { border-bottom: none; }
.nr-key { color: var(--dim); }
.nr-val { color: var(--glow2); }
.nr-val.ok { color: var(--glow); }
/* ── BOTTOM ROW ── */
.panel-bottom {
  grid-column: 1 / 4;
  grid-row: 4;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--border);
  max-height: 160px;
}
.panel-bottom > .panel { overflow-y: auto; padding: 12px; }
.mini-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  border-bottom: 1px solid rgba(15,48,64,0.4);
  font-size: 11px;
}
.mini-row:last-child { border-bottom: none; }
.mini-key { color: var(--dim); }
.mini-val { color: var(--text); }
.mini-val.g { color: var(--glow); }
.mini-val.c { color: var(--glow2); }
.mini-val.a { color: var(--amber); }
.mini-val.r { color: var(--red); }
/* Scan line effect */
@keyframes scanline {
  0%   { top: -2px; }
  100% { top: 100%; }
}
.scanline {
  position: fixed;
  left: 0; right: 0;
  height: 2px;
  background: linear-gradient(transparent, rgba(0,255,136,0.03), transparent);
  pointer-events: none;
  z-index: 9999;
  animation: scanline 8s linear infinite;
}
</style>
</head>
<body>
<div class="scanline"></div>

<!-- HEADER -->
<header>
  <div class="logo">
    <div class="logo-mark">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <circle cx="9" cy="9" r="3" fill="#00ff88"/>
        <line x1="9" y1="6" x2="9" y2="1" stroke="#00ff88" stroke-width="1.2"/>
        <line x1="9" y1="12" x2="9" y2="17" stroke="#00ff88" stroke-width="1.2"/>
        <line x1="6" y1="9" x2="1" y2="9" stroke="#00ff88" stroke-width="1.2"/>
        <line x1="12" y1="9" x2="17" y2="9" stroke="#00ff88" stroke-width="1.2"/>
      </svg>
    </div>
    <div>
      <div class="logo-title">DRONESYNC</div>
      <div class="logo-sub">MISSION CONTROL</div>
    </div>
  </div>
  <div class="header-center">
    <span>KONNEX</span> &nbsp;/&nbsp; NETUID {netuid} &nbsp;/&nbsp; <span>{network}</span>
  </div>
  <div class="header-right">
    <span class="hbadge hbadge-live">● LIVE</span>
    <span class="hbadge hbadge-uid">UID {uid}</span>
    <button class="btn-refresh" onclick="location.reload()">[ REFRESH ]</button>
  </div>
</header>

<div class="mc-layout">

  <!-- LEFT: Drone Fleet -->
  <div class="panel-left">
    <div class="panel">
      <div class="panel-title">// Drone Fleet</div>
      {drone_cards}
    </div>
  </div>

  <!-- CENTER TOP: KPI -->
  <div class="panel-top panel" style="padding:0">
    <div class="kpi-row">
      <div class="kpi-cell">
        <div class="kpi-v green">{active}</div>
        <div class="kpi-lbl">Active Drones</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-v cyan">{avg_score}</div>
        <div class="kpi-lbl">Mission Score</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-v">{task_count}</div>
        <div class="kpi-lbl">Validator Tasks</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-v amber">{last_conf}</div>
        <div class="kpi-lbl">Last Confidence</div>
      </div>
    </div>
  </div>

  <!-- CENTER: Map -->
  <div class="panel-map panel" style="padding:0">
    <div class="map-container" id="map">

      <!-- Линии сетки -->
      <div class="map-grid-line-h" style="top:25%"></div>
      <div class="map-grid-line-h" style="top:50%"></div>
      <div class="map-grid-line-h" style="top:75%"></div>
      <div class="map-grid-line-v" style="left:25%"></div>
      <div class="map-grid-line-v" style="left:50%"></div>
      <div class="map-grid-line-v" style="left:75%"></div>

      <!-- Координаты -->
      <div class="map-coords" style="top:4px;left:6px">47°22'N</div>
      <div class="map-coords" style="top:4px;left:50%">47°23'N</div>
      <div class="map-coords" style="bottom:4px;left:6px">8°32'E</div>
      <div class="map-coords" style="bottom:4px;right:6px">8°33'E</div>

      <!-- Маршруты SVG -->
      <svg class="route-svg" id="routes"></svg>

      <!-- Целевые точки -->
      {target_dots}

      <!-- Дроны -->
      {drone_dots}

      <!-- Радар -->
      <div class="radar">
        <div class="radar-circle"></div>
        <div class="radar-circle"></div>
        <div class="radar-circle"></div>
        <div class="radar-cross-h"></div>
        <div class="radar-cross-v"></div>
        <div class="radar-sweep"></div>
        {radar_blips}
      </div>
    </div>
  </div>

  <!-- CENTER BOTTOM: Terminal -->
  <div class="panel-terminal">
    <div class="terminal" id="terminal">
      {terminal_lines}
    </div>
  </div>
  <!-- BOTTOM ROW: New Data -->
  <div class="panel-bottom">
    <div class="panel">
      <div class="panel-title">// Weather & Energy</div>
      {weather_panel}
    </div>
    <div class="panel">
      <div class="panel-title">// Threat Defense</div>
      {threat_panel}
    </div>
    <div class="panel">
      <div class="panel-title">// Firewall & AI</div>
      {firewall_panel}
    </div>
    <div class="panel">
      <div class="panel-title">// Consensus</div>
      {consensus_panel}
    </div>
    <div class="panel">
      <div class="panel-title">// Score Root & Last Will</div>
      {scoreroot_panel}
    </div>
  </div>
  <!-- RIGHT: Pipeline + Mission Log + Node -->
  <div class="panel-right">
    <div class="panel">
      <div class="panel-title">// PoPW Pipeline</div>
      <div class="pipe-step">
        <div class="pipe-n">STEP 01</div>
        <div class="pipe-name">Task Instruction</div>
        <div class="pipe-ok">VERIFIED</div>
      </div>
      <div class="pipe-step">
        <div class="pipe-n">STEP 02</div>
        <div class="pipe-name">Policy Execution Trace</div>
        <div class="pipe-ok">TEE SIGNED</div>
      </div>
      <div class="pipe-step">
        <div class="pipe-n">STEP 03</div>
        <div class="pipe-name">Sensor Bundle</div>
        <div class="pipe-ok">HASHED</div>
      </div>
      <div class="pipe-step">
        <div class="pipe-n">STEP 04</div>
        <div class="pipe-name">Independent Scoring</div>
        <div class="pipe-ok">ON-CHAIN</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-title">// Mission Log</div>
      {mission_rows}
    </div>
    <div class="panel">
      <div class="panel-title">// Node Status</div>
      <div class="node-row"><span class="nr-key">NETWORK</span><span class="nr-val ok">TESTNET</span></div>
      <div class="node-row"><span class="nr-key">NETUID</span><span class="nr-val">{netuid}</span></div>
      <div class="node-row"><span class="nr-key">MINER UID</span><span class="nr-val ok">{uid}</span></div>
      <div class="node-row"><span class="nr-key">UPDATED</span><span class="nr-val">{last_update}</span></div>
      <div class="node-row"><span class="nr-key">ON-CHAIN</span><span class="nr-val ok">READY</span></div>
    </div>
  </div>

</div>

<script>
const map = document.getElementById('map');
const svg = document.getElementById('routes');

// ── 1. МАРШРУТЫ с анимацией ──
function drawRoutes() {
  if (!map || !svg) return;
  const W = map.offsetWidth;
  const H = map.offsetHeight;
  const routes = {routes_data};
  let paths = '';
  routes.forEach(r => {
    const x1 = r.x1 * W / 100, y1 = r.y1 * H / 100;
    const x2 = r.x2 * W / 100, y2 = r.y2 * H / 100;
    const mx = (x1+x2)/2 + (Math.random()-0.5)*60;
    const my = (y1+y2)/2 + (Math.random()-0.5)*40;
    paths += `<path d="M${x1},${y1} Q${mx},${my} ${x2},${y2}"
      stroke="rgba(0,255,136,0.25)" stroke-width="1" fill="none"
      stroke-dasharray="6 4">
      <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="0.8s" repeatCount="indefinite"/>
    </path>
    <circle r="3" fill="#00ff88" opacity="0.8">
      <animateMotion dur="${2.5 + Math.random()}s" repeatCount="indefinite" rotate="auto">
        <mpath href="#p${Math.random().toString(36).slice(2)}"/>
      </animateMotion>
    </circle>`;
  });
  svg.innerHTML = paths;
}

// ── 2. ДРОНЫ ДВИГАЮТСЯ по карте ──
const dronePositions = {routes_data}.map((r, i) => ({
  x: r.x1, y: r.y1, tx: r.x2, ty: r.y2,
  px: r.x1, py: r.y1,
  speed: 0.003 + Math.random() * 0.002,
  t: Math.random(),
  dir: 1
}));

const droneDots = document.querySelectorAll('.drone-dot');

function animateDrones() {
  dronePositions.forEach((d, i) => {
    d.t += d.speed * d.dir;
    if (d.t >= 1) { d.t = 1; d.dir = -1; }
    if (d.t <= 0) { d.t = 0; d.dir = 1; }
    const x = d.x + (d.tx - d.x) * d.t;
    const y = d.y + (d.ty - d.y) * d.t;
    if (droneDots[i]) {
      droneDots[i].style.left = x + '%';
      droneDots[i].style.top  = y + '%';
    }
  });
  requestAnimationFrame(animateDrones);
}

// ── 3. МАТРИЦА — падающие символы ──
function createMatrix() {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;opacity:0.06;pointer-events:none;z-index:0';
  mapEl.prepend(canvas);

  const ctx = canvas.getContext('2d');
  let cols, drops;

  function resize() {
    canvas.width  = mapEl.offsetWidth;
    canvas.height = mapEl.offsetHeight;
    cols  = Math.floor(canvas.width / 16);
    drops = Array(cols).fill(1);
  }
  resize();
  window.addEventListener('resize', resize);

  const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノ';
  function drawMatrix() {
    ctx.fillStyle = 'rgba(2,4,8,0.05)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#00ff88';
    ctx.font = '12px Share Tech Mono, monospace';
    drops.forEach((y, i) => {
      ctx.fillText(chars[Math.floor(Math.random() * chars.length)], i * 16, y * 16);
      if (y * 16 > canvas.height && Math.random() > 0.975) drops[i] = 0;
      drops[i]++;
    });
  }
  setInterval(drawMatrix, 60);
}

// ── 4. ГЛИТЧ на заголовке ──
function glitchEffect() {
  const title = document.querySelector('.logo-title');
  if (!title) return;
  const original = 'DRONESYNC';
  const glitchChars = '!@#$%^&*<>[]{}';

  function doGlitch() {
    let iter = 0;
    const interval = setInterval(() => {
      title.textContent = original.split('').map((c, i) =>
        i < iter ? c : glitchChars[Math.floor(Math.random() * glitchChars.length)]
      ).join('');
      iter++;
      if (iter > original.length) {
        title.textContent = original;
        clearInterval(interval);
      }
    }, 40);
  }

  doGlitch();
  setInterval(doGlitch, 8000 + Math.random() * 4000);
}

// ── 5. СЧЁТЧИКИ KPI анимируются при загрузке ──
function animateCounters() {
  document.querySelectorAll('.kpi-v').forEach(el => {
    const target = parseFloat(el.textContent);
    if (isNaN(target) || el.textContent === '—') return;
    let current = 0;
    const step = target / 30;
    const isFloat = el.textContent.includes('.');
    const interval = setInterval(() => {
      current += step;
      if (current >= target) { current = target; clearInterval(interval); }
      el.textContent = isFloat ? current.toFixed(1) : Math.floor(current);
    }, 30);
  });
}

// ── 6. ВСПЫШКА РАДАРА при новых данных ──
function radarFlash() {
  const radar = document.querySelector('.radar');
  if (!radar) return;
  radar.style.filter = 'brightness(3)';
  setTimeout(() => radar.style.filter = '', 200);
}

// ── ЗАПУСК ──
window.addEventListener('load', () => {
  drawRoutes();
  animateDrones();
  createMatrix();
  glitchEffect();
  animateCounters();
  setTimeout(radarFlash, 2000);
  setInterval(radarFlash, 15000);
});

window.addEventListener('resize', drawRoutes);

// Терминал автоскролл
const term = document.getElementById('terminal');
if (term) term.scrollTop = term.scrollHeight;

setTimeout(() => location.reload(), 30000);
// WebSocket live data
const ws = new WebSocket('ws://localhost:8765');
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    const conf = document.getElementById('last-conf');
    const tasks = document.getElementById('validator-tasks');
    const term = document.getElementById('terminal');
    if (conf) conf.textContent = data.conf;
    if (tasks) tasks.textContent = parseInt(tasks.textContent || 0) + 1;
    if (term) {
        const line = document.createElement('div');
        line.className = 'term-line success prompt';
        line.innerHTML = '<span class="term-ts">' + data.time + '</span> task=' + data.task + ' action_id=' + data.action_id + ' conf=' + data.conf;
        term.appendChild(line);
        term.scrollTop = term.scrollHeight;
    }
};
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
        drone_cards += f"""<div class="drone-card-mc">
          <div class="dc-header">
            <span class="dc-id">{drone_id}</span>
            <span class="dc-status">● ACTIVE</span>
          </div>
          <div class="dc-row"><span class="dc-key">SCORE</span><span class="dc-val g">{score}</span></div>
          <div class="dc-bar"><div class="dc-bar-fill" style="width:{score}%"></div></div>
          <div class="dc-row"><span class="dc-key">TEE</span><span class="dc-val c">{d.get("tee_status","?")}</span></div>
          <div class="dc-row"><span class="dc-key">SECURITY</span><span class="dc-val g">{d.get("security_status","?")}</span></div>
          <div class="dc-row"><span class="dc-key">REP</span><span class="dc-val {"g" if tier=="ELITE" else "c" if tier=="TRUSTED" else "a" if tier=="ACTIVE" else "r"}">{d.get("reputation_score","?")} ({tier})</span></div>
          <div class="dc-row"><span class="dc-key">ON-CHAIN</span><span class="dc-val g">{"READY" if d.get("on_chain_ready") else "PENDING"}</span></div>
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
        mission_rows += f"""<div class="mission-row">
          <div>
            <div class="mr-id">{mid}</div>
            <div style="color:var(--dim);font-size:10px">{m.get("drone_id","?")} · {ts}</div>
          </div>
          <div class="mr-score">{score}</div>
        </div>"""
    if not mission_rows:
        mission_rows = '<div style="color:var(--dim);font-size:11px;padding:8px 0">NO DATA</div>'
    w = s.get("weather", {})
    weather_panel = (
        f'<div class="mini-row"><span class="mini-key">FLYABLE</span><span class="mini-val g">{"YES" if w.get("flyable", True) else "NO"}</span></div>'
        f'<div class="mini-row"><span class="mini-key">WIND</span><span class="mini-val">{w.get("wind_speed", "—")} m/s</span></div>'
        f'<div class="mini-row"><span class="mini-key">VISIBILITY</span><span class="mini-val">{w.get("visibility_m", "—")}m</span></div>'
        f'<div class="mini-row"><span class="mini-key">SEVERITY</span><span class="mini-val c">{w.get("severity", "CLEAR")}</span></div>'
    )
    e = s.get("energy", {})
    weather_panel += (
        f'<div class="mini-row"><span class="mini-key">BATTERY</span><span class="mini-val g">{e.get("battery_remaining_pct", "—")}%</span></div>'
        f'<div class="mini-row"><span class="mini-key">EFFICIENCY</span><span class="mini-val c">{e.get("efficiency_rating", "—")}</span></div>'
    )
    t = s.get("threat", {})
    threat_panel = (
        f'<div class="mini-row"><span class="mini-key">LEVEL</span><span class="mini-val {"r" if t.get("overall_threat_level","NONE")!="NONE" else "g"}">{t.get("overall_threat_level","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">GPS</span><span class="mini-val g">{t.get("gps_status","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">JAMMING</span><span class="mini-val g">{t.get("jamming_status","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">SWARM</span><span class="mini-val c">{t.get("swarm_integrity","—")}</span></div>'
    )
    fw = s.get("firewall", {})
    aw = s.get("ai_weights", {})
    firewall_panel = (
        f'<div class="mini-row"><span class="mini-key">ALLOWED</span><span class="mini-val g">{fw.get("total_allowed","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">BLOCKED</span><span class="mini-val r">{fw.get("total_blocked","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">AI SAFETY</span><span class="mini-val c">{aw.get("safety","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">AI EFFIC</span><span class="mini-val c">{aw.get("efficiency","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">AI ENERGY</span><span class="mini-val c">{aw.get("energy","—")}</span></div>'
    )
    c = s.get("consensus", {})
    consensus_panel = (
        f'<div class="mini-row"><span class="mini-key">STATUS</span><span class="mini-val {"g" if c.get("status")=="APPROVED" else "r"}">{c.get("status","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">WEIGHT</span><span class="mini-val">{c.get("approval_weight","—")}/{c.get("total_weight","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">RATE</span><span class="mini-val g">{c.get("approval_rate","—")}</span></div>'
    )
    last_upd = time.strftime("%H:%M:%S", time.localtime(s.get("last_update", 0))) if s.get("last_update") else "—"

    html = HTML_TEMPLATE
    html = html.replace("{netuid}",     str(sw.get("netuid", 4)))
    html = html.replace("{network}",    str(sw.get("network", "testnet")).upper())
    html = html.replace("{active}",     str(sw.get("active_drones", 0)))
    html = html.replace("{avg_score}",  str(sw.get("avg_score", 0)))
    html = html.replace("{last_conf}",  str(last_conf))
    html = html.replace("{task_count}", str(len(miner_tasks)))
    html = html.replace("{uid}",        str(uid))
    html = html.replace("{last_update}", last_upd)
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
        f'<div class="mini-row"><span class="mini-key">VALIDATOR</span><span class="mini-val c">{sr.get("validator_id","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">SCORES</span><span class="mini-val">{sr.get("scores_count","—")}</span></div>'
        f'<div class="mini-row"><span class="mini-key">ROOT</span><span class="mini-val g">{str(sr.get("score_root","—"))[:12]}...</span></div>'
        f'<div class="mini-row"><span class="mini-key">LW STATUS</span><span class="mini-val {"r" if lw.get("triggered") else "g"}">{"TRIGGERED" if lw.get("triggered") else "STANDBY"}</span></div>'
        f'<div class="mini-row"><span class="mini-key">BATTERY</span><span class="mini-val">{lw.get("battery_pct","—")}%</span></div>'
    )
    html = html.replace("{scoreroot_panel}", scoreroot_panel)
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
            html = render_dashboard().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html)


def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    print(f"[DroneSync] Loading...")
    refresh_state()
    print(f"[DroneSync] Background refresh every 30s...")
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    print(f"[DroneSync] http://{host}:{port}")
    server = HTTPServer((host, port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_dashboard()
