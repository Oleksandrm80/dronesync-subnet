# dashboard/app.py
"""
DroneSync Live Swarm Dashboard
Веб-интерфейс для демо Konnex NETUID 4 (testnet)
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
from urllib.parse import urlparse, parse_qs

from dronesync.synapse import DroneNavSynapseHandler, SwarmSynapseHandler
from dronesync.reputation import DroneReputation
from dronesync.storage import DroneStorage
from dronesync.node import KonnexNode

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

    node = KonnexNode(wallet_address="0x5a4E...51f2", network="testnet")
    node.connect()
    state["node_status"] = node.get_status()

    for d in DRONE_IDS:
        state["missions"].append(dict(state["drones"][d]))
    if len(state["missions"]) > 30:
        state["missions"] = state["missions"][-30:]

    state["miner_tasks"] = _parse_miner_logs()
    state["last_update"] = int(time.time())


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
<title>DroneSync — Konnex NETUID 4</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

  :root {
    --bg:       #0c0c0e;
    --bg2:      #111114;
    --bg3:      #18181c;
    --border:   #2a2a30;
    --border2:  #3a3a44;
    --text:     #e8e8ec;
    --muted:    #6b6b78;
    --dim:      #3a3a44;
    --accent:   #c8c8d4;
    --green:    #4ade80;
    --amber:    #fbbf24;
    --red:      #f87171;
    --purple:   #a78bfa;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Space Grotesk', -apple-system, sans-serif;
    font-size: 13px;
    line-height: 1.5;
  }

  /* ── HEADER ── */
  header {
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 0 32px;
    height: 58px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  /* Drone SVG icon */
  .logo-icon {
    width: 30px;
    height: 30px;
    flex-shrink: 0;
  }
  .logo-name {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--text);
  }
  .logo-slash {
    color: var(--muted);
    font-weight: 300;
    margin: 0 2px;
  }
  .logo-sub {
    font-size: 13px;
    font-weight: 400;
    color: var(--muted);
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-left: auto;
  }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border: 1px solid var(--border);
    color: var(--muted);
    background: var(--bg2);
  }
  .tag-live {
    border-color: var(--green);
    color: var(--green);
    background: rgba(74,222,128,0.06);
  }
  .tag-live .dot {
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--green);
    animation: pulse 2s infinite;
  }
  .tag-uid {
    border-color: var(--purple);
    color: var(--purple);
    background: rgba(167,139,250,0.06);
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

  .btn-refresh {
    background: var(--bg3);
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 5px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    font-weight: 500;
    transition: all 0.15s;
    letter-spacing: 0.03em;
  }
  .btn-refresh:hover { border-color: var(--border2); color: var(--text); }

  /* ── LAYOUT ── */
  main {
    max-width: 1300px;
    margin: 0 auto;
    padding: 32px 32px 48px;
  }

  .section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
    margin-top: 36px;
  }
  .section-label:first-child { margin-top: 0; }

  /* ── KPI STRIP ── */
  .kpi-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  @media (max-width: 700px) { .kpi-strip { grid-template-columns: repeat(2, 1fr); } }

  .kpi {
    background: var(--bg2);
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
    line-height: 1;
  }
  .kpi-value.green { color: var(--green); }
  .kpi-value.purple { color: var(--purple); }
  .kpi-label {
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
    margin-top: 2px;
  }

  /* ── PIPELINE ── */
  .pipeline {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  @media (max-width: 700px) { .pipeline { grid-template-columns: repeat(2, 1fr); } }

  .pipe {
    background: var(--bg2);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .pipe-n {
    font-size: 10px;
    font-weight: 700;
    color: var(--dim);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .pipe-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
  }
  .pipe-ok {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: var(--green);
    font-weight: 500;
  }
  .pipe-ok::before {
    content: "";
    display: inline-block;
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--green);
  }

  /* ── DRONE GRID ── */
  .drone-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  @media (max-width: 900px) { .drone-grid { grid-template-columns: 1fr; } }

  .drone-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    transition: border-color 0.2s;
  }
  .drone-card:hover { border-color: var(--border2); }

  /* top "image" area — drone silhouette */
  .drone-visual {
    background: var(--bg3);
    border-bottom: 1px solid var(--border);
    height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }
  .drone-visual svg {
    width: 80px;
    height: 80px;
    opacity: 0.55;
    filter: drop-shadow(0 0 18px rgba(167,139,250,0.18));
  }
  .drone-visual-id {
    position: absolute;
    bottom: 8px;
    left: 12px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .drone-visual-status {
    position: absolute;
    top: 10px;
    right: 10px;
  }

  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .status-active {
    background: rgba(74,222,128,0.1);
    border: 1px solid rgba(74,222,128,0.3);
    color: var(--green);
  }
  .status-active .dot { width:4px;height:4px;border-radius:50%;background:var(--green);animation:pulse 2s infinite; }
  .status-idle {
    background: rgba(251,191,36,0.1);
    border: 1px solid rgba(251,191,36,0.3);
    color: var(--amber);
  }

  .drone-body { padding: 14px 16px; }
  .drone-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
  }
  .drone-row:last-child { border-bottom: none; }
  .drone-row-key { color: var(--muted); }
  .drone-row-val { font-weight: 600; color: var(--text); }
  .drone-row-val.green { color: var(--green); }
  .drone-row-val.amber { color: var(--amber); }
  .drone-row-val.purple { color: var(--purple); font-size: 11px; }
  .drone-row-val.mono { font-family: monospace; font-size: 10px; color: var(--muted); }

  .score-track {
    height: 2px;
    background: var(--border);
    border-radius: 1px;
    margin: 8px 0;
    overflow: hidden;
  }
  .score-fill {
    height: 100%;
    border-radius: 1px;
    background: linear-gradient(90deg, var(--purple), var(--green));
    transition: width 0.6s;
  }

  /* ── TASKS TABLE ── */
  .table-wrap {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  table { width: 100%; border-collapse: collapse; }
  thead { background: var(--bg3); }
  th {
    padding: 10px 16px;
    text-align: left;
    font-size: 10px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
    color: var(--text);
  }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,0.015); }

  .conf-high { color: var(--green); font-weight: 700; }
  .conf-mid  { color: var(--amber); font-weight: 700; }
  .conf-low  { color: var(--red);   font-weight: 700; }
  .mono { font-family: monospace; font-size: 11px; color: var(--muted); }

  .chip-tee {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    background: rgba(167,139,250,0.12);
    border: 1px solid rgba(167,139,250,0.25);
    color: var(--purple);
  }
  .chip-ok {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 700;
    background: rgba(74,222,128,0.1);
    border: 1px solid rgba(74,222,128,0.25);
    color: var(--green);
  }

  /* ── FOOTER ── */
  footer {
    text-align: center;
    padding: 24px 32px;
    color: var(--dim);
    font-size: 11px;
    border-top: 1px solid var(--border);
    margin-top: 48px;
    letter-spacing: 0.04em;
  }
</style>
</head>
<body>

<header>
  <div class="logo">
    <!-- Drone SVG icon -->
    <svg class="logo-icon" viewBox="0 0 30 30" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="15" cy="15" r="4" fill="#6b6b78"/>
      <circle cx="15" cy="15" r="2" fill="#a78bfa"/>
      <!-- arms -->
      <line x1="15" y1="11" x2="15" y2="4"  stroke="#6b6b78" stroke-width="1.2"/>
      <line x1="15" y1="19" x2="15" y2="26" stroke="#6b6b78" stroke-width="1.2"/>
      <line x1="11" y1="15" x2="4"  y2="15" stroke="#6b6b78" stroke-width="1.2"/>
      <line x1="19" y1="15" x2="26" y2="15" stroke="#6b6b78" stroke-width="1.2"/>
      <!-- rotors -->
      <circle cx="15" cy="4"  r="3" stroke="#3a3a44" stroke-width="1.2" fill="none"/>
      <circle cx="15" cy="26" r="3" stroke="#3a3a44" stroke-width="1.2" fill="none"/>
      <circle cx="4"  cy="15" r="3" stroke="#3a3a44" stroke-width="1.2" fill="none"/>
      <circle cx="26" cy="15" r="3" stroke="#3a3a44" stroke-width="1.2" fill="none"/>
    </svg>
    <span class="logo-name">DroneSync</span>
    <span class="logo-slash">/</span>
    <span class="logo-sub">Konnex</span>
  </div>

  <div class="header-right">
    <span class="tag tag-live"><span class="dot"></span>Live</span>
    <span class="tag">NETUID {netuid} · {network}</span>
    <span class="tag tag-uid">UID {uid}</span>
    <button class="btn-refresh" onclick="location.reload()">↻ Refresh</button>
  </div>
</header>

<main>

  <!-- KPI -->
  <div class="section-label">Overview</div>
  <div class="kpi-strip">
    <div class="kpi">
      <div class="kpi-value">{active}</div>
      <div class="kpi-label">Active Drones</div>
    </div>
    <div class="kpi">
      <div class="kpi-value green">{avg_score}</div>
      <div class="kpi-label">Avg Mission Score</div>
    </div>
    <div class="kpi">
      <div class="kpi-value">{task_count}</div>
      <div class="kpi-label">Validator Tasks</div>
    </div>
    <div class="kpi">
      <div class="kpi-value purple">{last_conf}</div>
      <div class="kpi-label">Last Confidence</div>
    </div>
  </div>

  <!-- PoPW Pipeline -->
  <div class="section-label">PoPW Pipeline</div>
  <div class="pipeline">
    <div class="pipe">
      <div class="pipe-n">Step 01</div>
      <div class="pipe-name">Task Instruction</div>
      <div class="pipe-ok">Verified</div>
    </div>
    <div class="pipe">
      <div class="pipe-n">Step 02</div>
      <div class="pipe-name">Policy Execution Trace</div>
      <div class="pipe-ok">TEE Signed</div>
    </div>
    <div class="pipe">
      <div class="pipe-n">Step 03</div>
      <div class="pipe-name">Sensor Bundle</div>
      <div class="pipe-ok">Hashed</div>
    </div>
    <div class="pipe">
      <div class="pipe-n">Step 04</div>
      <div class="pipe-name">Independent Scoring</div>
      <div class="pipe-ok">On-Chain</div>
    </div>
  </div>

  <!-- Validator Tasks -->
  <div class="section-label">Validator Tasks — real data</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Task ID</th><th>Confidence</th><th>Action</th><th>Timestamp</th></tr>
      </thead>
      <tbody>{task_rows}</tbody>
    </table>
  </div>

  <!-- Drone Fleet -->
  <div class="section-label">Drone Fleet</div>
  <div class="drone-grid">{drone_cards}</div>

  <!-- Recent Missions -->
  <div class="section-label">Recent Missions</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Mission ID</th><th>Drone</th><th>Score</th><th>TEE</th><th>Security</th><th>On-Chain</th><th>Time</th></tr>
      </thead>
      <tbody>{mission_rows}</tbody>
    </table>
  </div>

</main>

<footer>
  DroneSync — Proof of Concept on Konnex NETUID 4 Testnet &nbsp;·&nbsp;
  Miner UID {uid} &nbsp;·&nbsp; PoPW: Task · Trace · Sensor · Score &nbsp;·&nbsp;
  {last_update}
</footer>

<script>setTimeout(() => location.reload(), 30000);</script>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Drone SVG (quadcopter top-down view) used inside drone cards
# ──────────────────────────────────────────────────────────────────────────────
DRONE_SVG = """<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="40" cy="40" r="10" fill="#2a2a30"/>
  <circle cx="40" cy="40" r="5" fill="#a78bfa" opacity="0.6"/>
  <line x1="40" y1="30" x2="40" y2="12" stroke="#3a3a44" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="40" y1="50" x2="40" y2="68" stroke="#3a3a44" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="30" y1="40" x2="12" y2="40" stroke="#3a3a44" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="50" y1="40" x2="68" y2="40" stroke="#3a3a44" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="40" cy="10" r="7" stroke="#4a4a54" stroke-width="1.5" fill="none"/>
  <circle cx="40" cy="70" r="7" stroke="#4a4a54" stroke-width="1.5" fill="none"/>
  <circle cx="10" cy="40" r="7" stroke="#4a4a54" stroke-width="1.5" fill="none"/>
  <circle cx="70" cy="40" r="7" stroke="#4a4a54" stroke-width="1.5" fill="none"/>
</svg>"""


def render_dashboard() -> str:
    s = state
    sw = s.get("swarm_status", {})
    drones = s.get("drones", {})
    miner_tasks = s.get("miner_tasks", [])
    uid = s.get("uid", 136)

    last_conf = "—"
    if miner_tasks:
        last_conf = miner_tasks[-1].get("conf", "—")

    # Validator task rows
    task_rows = ""
    if miner_tasks:
        for t in reversed(miner_tasks):
            conf_val = t.get("conf", "—")
            try:
                cf = float(conf_val)
                conf_cls = "conf-high" if cf >= 0.80 else ("conf-mid" if cf >= 0.60 else "conf-low")
            except Exception:
                conf_cls = ""
            task_rows += f"""<tr>
          <td class="mono">{t.get("task_id","—")}</td>
          <td><span class="{conf_cls}">{conf_val}</span></td>
          <td>{t.get("action","—")}</td>
          <td class="mono">{t.get("ts","—")}</td>
        </tr>"""
    else:
        task_rows = '<tr><td colspan="4" style="text-align:center;color:var(--dim);padding:24px">Waiting for validator tasks...</td></tr>'

    # Drone cards
    drone_cards = ""
    for drone_id, d in drones.items():
        score = d.get("score", 0)
        tier = d.get("reputation_tier", "?")
        is_active = score >= 80
        status_html = (
            '<span class="status-chip status-active"><span class="dot"></span>Active</span>'
            if is_active else
            '<span class="status-chip status-idle">Idle</span>'
        )
        chain_val = "Ready"  if d.get("on_chain_ready") else "Pending"
        chain_cls = "green"  if d.get("on_chain_ready") else "amber"
        drone_cards += f"""<div class="drone-card">
          <div class="drone-visual">
            {DRONE_SVG}
            <div class="drone-visual-id">{drone_id}</div>
            <div class="drone-visual-status">{status_html}</div>
          </div>
          <div class="drone-body">
            <div class="drone-row">
              <span class="drone-row-key">Score</span>
              <span class="drone-row-val green">{score}</span>
            </div>
            <div class="score-track"><div class="score-fill" style="width:{score}%"></div></div>
            <div class="drone-row">
              <span class="drone-row-key">TEE</span>
              <span class="drone-row-val purple">{d.get("tee_status","?")}</span>
            </div>
            <div class="drone-row">
              <span class="drone-row-key">Security</span>
              <span class="drone-row-val">{d.get("security_status","?")}</span>
            </div>
            <div class="drone-row">
              <span class="drone-row-key">Reputation</span>
              <span class="drone-row-val">{d.get("reputation_score","?")} <span style="color:var(--muted)">({tier})</span></span>
            </div>
            <div class="drone-row">
              <span class="drone-row-key">On-Chain</span>
              <span class="drone-row-val {chain_cls}">{chain_val}</span>
            </div>
            <div class="drone-row">
              <span class="drone-row-key">Bundle</span>
              <span class="drone-row-val mono">{d.get("bundle_hash","?")}</span>
            </div>
          </div>
        </div>"""

    # Mission rows
    mission_rows = ""
    for m in reversed(s.get("missions", [])[-15:]):
        score = m.get("score", 0)
        score_cls = "conf-high" if score >= 80 else ("conf-mid" if score >= 50 else "conf-low")
        chain = '<span class="chip-ok">✓</span>' if m.get("on_chain_ready") else "⏳"
        ts = time.strftime("%H:%M:%S", time.localtime(m.get("timestamp", 0)))
        mission_rows += f"""<tr>
          <td class="mono">{m.get("mission_id","?")[:22]}...</td>
          <td>{m.get("drone_id","?")}</td>
          <td><span class="{score_cls}">{score}</span></td>
          <td><span class="chip-tee">{m.get("tee_status","?")}</span></td>
          <td>{m.get("security_status","?")}</td>
          <td>{chain}</td>
          <td class="mono">{ts}</td>
        </tr>"""

    if not mission_rows:
        mission_rows = '<tr><td colspan="7" style="text-align:center;color:var(--dim);padding:24px">No data — press Refresh</td></tr>'

    last_upd = time.strftime("%H:%M:%S", time.localtime(s.get("last_update", 0))) if s.get("last_update") else "—"

    html = HTML_TEMPLATE
    html = html.replace("{netuid}",    str(sw.get("netuid", 4)))
    html = html.replace("{network}",   str(sw.get("network", "testnet")))
    html = html.replace("{active}",    str(sw.get("active_drones", 0)))
    html = html.replace("{avg_score}", str(sw.get("avg_score", 0)))
    html = html.replace("{last_conf}", str(last_conf))
    html = html.replace("{task_count}",str(len(miner_tasks)))
    html = html.replace("{uid}",       str(uid))
    html = html.replace("{last_update}", last_upd)
    html = html.replace("{drone_cards}",  drone_cards)
    html = html.replace("{mission_rows}", mission_rows)
    html = html.replace("{task_rows}",    task_rows)
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
    print(f"[DroneSync Dashboard] Loading data...")
    refresh_state()
    print(f"[DroneSync Dashboard] Background refresh every 30s...")
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    print(f"[DroneSync Dashboard] http://{host}:{port}")
    server = HTTPServer((host, port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_dashboard()
