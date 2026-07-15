"""
DroneSync Dashboard - HTML/CSS/JS template.
Pulled out of app.py because it is pure markup with no logic --
keeping it separate keeps app.py to the actual server/state code.
"""

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
