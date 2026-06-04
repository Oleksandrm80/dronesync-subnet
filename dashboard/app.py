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
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from dronesync.synapse import DroneNavSynapseHandler, SwarmSynapseHandler
from dronesync.reputation import DroneReputation
from dronesync.storage import DroneStorage
from dronesync.node import KonnexNode

# Глобальное состояние дашборда
state = {
    "drones": {},
    "missions": [],
    "swarm_status": {},
    "node_status": {},
    "netuid": 4,
    "network": "testnet",
    "last_update": 0,
}

DRONE_IDS = ["DRONE_001", "DRONE_002", "DRONE_003"]
handlers = {d: DroneNavSynapseHandler(drone_id=d, use_ai_planner=True) for d in DRONE_IDS}


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
    """Запускает миссию для каждого дрона и обновляет глобальное состояние."""
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

    # Суммарный статус роя
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

    # Подключение к ноде Konnex
    node = KonnexNode(wallet_address="0x5a4E...51f2", network="testnet")
    node.connect()
    ns = node.get_status()
    state["node_status"] = ns

    # История миссий (последние 10)
    for d in DRONE_IDS:
        state["missions"].append(dict(state["drones"][d]))
    if len(state["missions"]) > 30:
        state["missions"] = state["missions"][-30:]

    state["last_update"] = int(time.time())


def background_loop():
    """Обновляет состояние каждые 30 секунд."""
    while True:
        try:
            refresh_state()
        except Exception as e:
            print("[dashboard] refresh error:", e)
        time.sleep(30)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DroneSync Live Dashboard — Konnex NETUID 4</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0a0e1a; color: #e0e6f0; font-family: 'Courier New', monospace; }
  header { background: linear-gradient(90deg, #0d1b2a, #1a3a5c); padding: 20px 30px;
           border-bottom: 2px solid #00d4ff; display: flex; align-items: center; gap: 16px; }
  .logo { font-size: 28px; font-weight: bold; color: #00d4ff; letter-spacing: 2px; }
  .subtitle { font-size: 13px; color: #7fa8c9; }
  .badge { background: #00d4ff22; border: 1px solid #00d4ff; color: #00d4ff;
           padding: 4px 12px; border-radius: 12px; font-size: 12px; margin-left: auto; }
  .badge.live { background: #00ff8822; border-color: #00ff88; color: #00ff88; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
  main { padding: 24px 30px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 24px; }
  .card { background: #111827; border: 1px solid #1e3a5f; border-radius: 12px; padding: 20px; }
  .card h3 { color: #00d4ff; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 14px; }
  .metric { display: flex; justify-content: space-between; padding: 6px 0;
            border-bottom: 1px solid #1e2a3a; font-size: 13px; }
  .metric:last-child { border-bottom: none; }
  .metric .val { color: #00ff88; font-weight: bold; }
  .metric .val.warn { color: #ffaa00; }
  .metric .val.danger { color: #ff4444; }
  .score-bar { height: 6px; background: #1e3a5f; border-radius: 3px; margin-top: 8px; overflow: hidden; }
  .score-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #00d4ff, #00ff88); transition: width 0.5s; }
  .drone-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
  .drone-card { background: #0d1b2a; border: 1px solid #1e4a6f; border-radius: 10px; padding: 16px; }
  .drone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .drone-id { font-weight: bold; color: #00d4ff; font-size: 15px; }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #00ff88; animation: pulse 2s infinite; }
  .status-dot.warn { background: #ffaa00; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px;
         background: #00ff8822; color: #00ff88; border: 1px solid #00ff8844; margin-right: 4px; }
  .tag.blue { background: #00d4ff22; color: #00d4ff; border-color: #00d4ff44; }
  .tag.warn { background: #ffaa0022; color: #ffaa00; border-color: #ffaa0044; }
  .missions-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .missions-table th { background: #0d1b2a; color: #7fa8c9; padding: 8px 10px; text-align: left; border-bottom: 1px solid #1e3a5f; }
  .missions-table td { padding: 7px 10px; border-bottom: 1px solid #111827; }
  .missions-table tr:hover td { background: #0d1b2a33; }
  .refresh-btn { background: #00d4ff22; border: 1px solid #00d4ff; color: #00d4ff;
                 padding: 8px 20px; border-radius: 8px; cursor: pointer; font-family: inherit;
                 font-size: 13px; transition: all 0.2s; }
  .refresh-btn:hover { background: #00d4ff33; }
  footer { text-align: center; padding: 20px; color: #3a5a7a; font-size: 12px; border-top: 1px solid #1e3a5f; }
</style>
</head>
<body>
<header>
  <div>
    <div class="logo">⬡ DroneSync</div>
    <div class="subtitle">Konnex Subnet · NETUID {netuid} · {network}</div>
  </div>
  <div class="badge live">● LIVE</div>
  <div class="badge">{active}/{total} DRONES</div>
  <button class="refresh-btn" onclick="location.reload()">⟳ Refresh</button>
</header>
<main>

  <div class="grid">
    <div class="card">
      <h3>Swarm Status</h3>
      <div class="metric"><span>Active Drones</span><span class="val">{active} / {total}</span></div>
      <div class="metric"><span>Avg Score</span><span class="val">{avg_score}</span></div>
      <div class="metric"><span>Min / Max Score</span><span class="val">{min_score} / {max_score}</span></div>
      <div class="metric"><span>On-Chain Ready</span><span class="val {chain_cls}">{on_chain}</span></div>
      <div class="score-bar"><div class="score-fill" style="width:{avg_score}%"></div></div>
    </div>
    <div class="card">
      <h3>Konnex Node</h3>
      <div class="metric"><span>Connected</span><span class="val">{node_connected}</span></div>
      <div class="metric"><span>Network</span><span class="val">{node_network}</span></div>
      <div class="metric"><span>Session ID</span><span class="val">{node_session}</span></div>
      <div class="metric"><span>Last Update</span><span class="val">{last_update}</span></div>
    </div>
    <div class="card">
      <h3>PoPW Pipeline</h3>
      <div class="metric"><span>Task Instruction</span><span class="val tag blue">✓ OK</span></div>
      <div class="metric"><span>Policy Execution Trace</span><span class="val tag blue">✓ TEE</span></div>
      <div class="metric"><span>Sensor Bundle</span><span class="val tag blue">✓ Hashed</span></div>
      <div class="metric"><span>Independent Scoring</span><span class="val tag blue">✓ On-Chain</span></div>
    </div>
  </div>

  <h3 style="color:#00d4ff;margin-bottom:14px;font-size:14px;letter-spacing:1px;text-transform:uppercase;">
    Drone Fleet
  </h3>
  <div class="drone-grid">{drone_cards}</div>

  <h3 style="color:#00d4ff;margin:24px 0 14px;font-size:14px;letter-spacing:1px;text-transform:uppercase;">
    Recent Missions
  </h3>
  <div class="card">
    <table class="missions-table">
      <thead>
        <tr>
          <th>Mission ID</th><th>Drone</th><th>Score</th><th>TEE</th>
          <th>Security</th><th>On-Chain</th><th>Time</th>
        </tr>
      </thead>
      <tbody>{mission_rows}</tbody>
    </table>
  </div>

</main>
<footer>
  DroneSync — Proof of Concept on Konnex NETUID 4 Testnet &nbsp;|&nbsp;
  PoPW: Task Instruction · Policy Trace · Sensor Bundle · Independent Scoring
</footer>
<script>
  setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>"""


def render_dashboard() -> str:
    s = state
    sw = s.get("swarm_status", {})
    ns = s.get("node_status", {})
    drones = s.get("drones", {})

    # Drone cards
    drone_cards = ""
    for drone_id, d in drones.items():
        score = d.get("score", 0)
        tier = d.get("reputation_tier", "?")
        status_cls = "" if score >= 80 else "warn"
        chain_tag = "✓ Ready" if d.get("on_chain_ready") else "⏳ Pending"
        chain_cls = "" if d.get("on_chain_ready") else "warn"
        drone_cards += f"""
        <div class="drone-card">
          <div class="drone-header">
            <span class="drone-id">{drone_id}</span>
            <span class="status-dot {status_cls}"></span>
          </div>
          <div class="metric"><span>Mission ID</span><span class="val" style="font-size:11px">{d.get("mission_id","?")[:18]}...</span></div>
          <div class="metric"><span>Score</span><span class="val">{score}</span></div>
          <div class="score-bar"><div class="score-fill" style="width:{score}%"></div></div>
          <div class="metric" style="margin-top:8px"><span>TEE Status</span><span class="val">{d.get("tee_status","?")}</span></div>
          <div class="metric"><span>Security</span><span class="val">{d.get("security_status","?")}</span></div>
          <div class="metric"><span>Threat Level</span><span class="val">{d.get("threat_level","?")}</span></div>
          <div class="metric"><span>Reputation</span><span class="val">{d.get("reputation_score","?")} ({tier})</span></div>
          <div class="metric"><span>Bundle Hash</span><span class="val" style="font-size:11px">{d.get("bundle_hash","?")}</span></div>
          <div class="metric"><span>On-Chain</span><span class="val {chain_cls}">{chain_tag}</span></div>
        </div>"""

    # Mission rows
    mission_rows = ""
    for m in reversed(s.get("missions", [])[-15:]):
        score = m.get("score", 0)
        score_cls = "" if score >= 80 else ("warn" if score >= 50 else "danger")
        chain = "✓" if m.get("on_chain_ready") else "⏳"
        ts = time.strftime("%H:%M:%S", time.localtime(m.get("timestamp", 0)))
        mission_rows += f"""
        <tr>
          <td style="font-size:11px">{m.get("mission_id","?")[:20]}...</td>
          <td>{m.get("drone_id","?")}</td>
          <td><span class="val {score_cls}">{score}</span></td>
          <td>{m.get("tee_status","?")}</td>
          <td>{m.get("security_status","?")}</td>
          <td>{chain}</td>
          <td>{ts}</td>
        </tr>"""

    if not mission_rows:
        mission_rows = '<tr><td colspan="7" style="text-align:center;color:#3a5a7a;padding:20px">Нет данных — нажмите Refresh</td></tr>'

    chain_cls = "" if sw.get("all_on_chain_ready") else "warn"
    last_upd = time.strftime("%H:%M:%S", time.localtime(s.get("last_update", 0))) if s.get("last_update") else "—"
    netuid = sw.get("netuid", 4)
    network = sw.get("network", "testnet")
    active = sw.get("active_drones", 0)
    total = sw.get("total_drones", len(DRONE_IDS))
    avg_score = sw.get("avg_score", 0)
    min_score = sw.get("min_score", 0)
    max_score = sw.get("max_score", 0)
    on_chain = "✓ YES" if sw.get("all_on_chain_ready") else "⏳ Pending"
    node_connected = "✓ Yes" if ns.get("connected") else "✗ No"
    node_network = ns.get("network", "testnet")
    raw_sid = ns.get("session_id")
    node_session = str(raw_sid)[:12] if raw_sid else "—"

    # Replace placeholders manually to avoid CSS brace conflicts
    html = HTML_TEMPLATE
    html = html.replace("{netuid}", str(netuid))
    html = html.replace("{network}", str(network))
    html = html.replace("{active}", str(active))
    html = html.replace("{total}", str(total))
    html = html.replace("{avg_score}", str(avg_score))
    html = html.replace("{min_score}", str(min_score))
    html = html.replace("{max_score}", str(max_score))
    html = html.replace("{on_chain}", on_chain)
    html = html.replace("{chain_cls}", chain_cls)
    html = html.replace("{node_connected}", node_connected)
    html = html.replace("{node_network}", node_network)
    html = html.replace("{node_session}", node_session)
    html = html.replace("{last_update}", last_upd)
    html = html.replace("{drone_cards}", drone_cards)
    html = html.replace("{mission_rows}", mission_rows)
    return html


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # тихий режим

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
    print(f"[DroneSync Dashboard] Первичная загрузка данных...")
    refresh_state()

    print(f"[DroneSync Dashboard] Запуск фонового обновления каждые 30 сек...")
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()

    print(f"[DroneSync Dashboard] http://{host}:{port}")
    server = HTTPServer((host, port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_dashboard()
