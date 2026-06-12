# add_sidebar.py
with open("dashboard/app.py", "r", encoding="utf-8") as f:
    src = f.read()

sidebar_css = """
  .sidebar { position:fixed; right:0; top:0; width:260px; height:100vh; background:#070910;
             border-left:1px solid var(--border2); z-index:1000; display:flex;
             flex-direction:column; padding:12px 10px; gap:8px; overflow:hidden; }
  .sb-title { font-size:9px; letter-spacing:2px; color:var(--dim); text-transform:uppercase;
              padding:6px 8px; border-bottom:1px solid var(--border); }
  .sb-radar-wrap { flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; }
  #sideRadar { width:230px; height:230px; }
  .sb-range-btns { display:flex; gap:6px; align-items:center; }
  .sb-rbtn { background:transparent; border:1px solid var(--border2); color:var(--cyan);
             width:28px; height:28px; border-radius:4px; font-size:16px; cursor:pointer;
             font-family:inherit; transition:all 0.2s; display:flex; align-items:center; justify-content:center; }
  .sb-rbtn:hover { border-color:var(--cyan); background:var(--cyan)11; }
  .sb-range-lbl { font-size:11px; color:var(--cyan); letter-spacing:1px; min-width:80px; text-align:center; }
  .sb-stats { width:100%; display:flex; flex-direction:column; gap:4px; }
  .sb-row { display:flex; justify-content:space-between; font-size:10px; padding:3px 6px;
            border-bottom:1px solid var(--border); }
  .sb-row:last-child { border-bottom:none; }
  .sb-key { color:var(--dim); }
  .sb-val { color:var(--white); font-weight:bold; }
  .sb-val.g { color:var(--green); }
  .sb-val.c { color:var(--cyan); }
  .sb-val.r { color:var(--red); }
  body { margin-right:270px; }
"""
src = src.replace("  footer { text-align:center;", sidebar_css + "  footer { text-align:center;", 1)

sidebar_html = """
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
"""
src = src.replace('<div class="sidebar">SIDEBAR_PLACEHOLDER</div>', sidebar_html, 1)
# Generate sidebar data in render_dashboard
sidebar_gen = """
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
"""
src = src.replace("    html = HTML_TEMPLATE", sidebar_gen + "    html = HTML_TEMPLATE", 1)

sidebar_replaces = """    html = html.replace("{sb_threat}", _sb_threat)
    html = html.replace("{sb_gps}", _sb_gps)
    html = html.replace("{sb_reward}", str(_final_r))
    html = html.replace("{sb_sim_status}", sb_sim_status)
    html = html.replace("{sb_drone_positions}", _sb_drone_json)
"""
src = src.replace('    html = html.replace("{economics_panel}"', sidebar_replaces + '    html = html.replace("{economics_panel}"', 1)

with open("dashboard/app.py", "w", encoding="utf-8") as f:
    f.write(src)

print("Done")
