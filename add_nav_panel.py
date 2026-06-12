# add_nav_panel.py
with open("dashboard/app.py", "r", encoding="utf-8") as f:
    src = f.read()

# 1. CSS для nav панели
nav_css = """
  .nav-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; margin-bottom:20px; }
  .alert-item { display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:6px; margin-bottom:6px; font-size:12px; }
  .alert-item.critical { background:#ff2d4a18; border:1px solid #ff2d4a44; }
  .alert-item.alert    { background:#ffb70018; border:1px solid #ffb70044; }
  .alert-item.notice   { background:#00bfff18; border:1px solid #00bfff44; }
  .alert-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
  .alert-dot.critical { background:#ff2d4a; box-shadow:0 0 6px #ff2d4a; }
  .alert-dot.alert    { background:#ffb700; box-shadow:0 0 6px #ffb700; }
  .alert-dot.notice   { background:#00bfff; box-shadow:0 0 6px #00bfff; }
  .overlay-btns { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }
  .ovbtn { padding:5px 12px; border-radius:6px; font-size:10px; letter-spacing:1px; cursor:pointer;
           font-family:inherit; text-transform:uppercase; border:1px solid var(--border2);
           color:var(--dim); background:transparent; transition:all 0.2s; }
  .ovbtn.on { border-color:var(--cyan); color:var(--cyan); background:var(--cyan)11; }
  .eta-row { display:flex; justify-content:space-between; padding:5px 0;
             border-bottom:1px solid var(--border); font-size:12px; }
  .eta-row:last-child { border-bottom:none; }
"""

old_css_anchor = "  footer { text-align:center;"
src = src.replace(old_css_anchor, nav_css + "  footer { text-align:center;", 1)

# 2. HTML секция перед MISSION LOG
nav_html = """<!-- NAVIGATION INTELLIGENCE -->
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

"""

old_mission_log = "<!-- MISSION LOG -->"
src = src.replace(old_mission_log, nav_html + old_mission_log, 1)

# 3. Генерация данных в render_dashboard()
nav_gen = """
    # Navigation Intelligence
    from dronesync.navigation import NavigationEngine
    nav_engine = NavigationEngine()

    nav_alerts_html = ""
    nav_etas_html = ""
    sim_flight_html = ""
    swarm_targets_html = ""

    for drone_id, d in drones.items():
        wps_raw = [
            {"lat": 47.3769, "lon": 8.5417, "alt": 50, "speed": 10},
            {"lat": 47.3800, "lon": 8.5450, "alt": 55, "speed": 10},
            {"lat": 47.3820, "lon": 8.5460, "alt": 50, "speed": 10},
        ]
        from dronesync.protocol import Waypoint
        wps = [Waypoint(**w) for w in wps_raw]
        sim = nav_engine.sim_flight(wps)
        etas = nav_engine.calculate_etas(sim.segments)

        for a in sim.alerts:
            lv = a.level.value
            nav_alerts_html += f'<div class="alert-item {lv}"><span class="alert-dot {lv}"></span><span>[{drone_id}] {a.message}</span></div>'

        for e in etas:
            import datetime
            eta_str = datetime.datetime.fromtimestamp(e.planned_eta).strftime("%H:%M:%S")
            nav_etas_html += f'<div class="eta-row"><span>{drone_id} · NavPoint {e.waypoint_index}</span><span class="mv c">{eta_str}</span></div>'

    if not nav_alerts_html:
        nav_alerts_html = '<div class="alert-item notice"><span class="alert-dot notice"></span><span>All systems nominal — no active alerts</span></div>'

    s_sum = sim.summary()
    sim_safe_cls = "g" if s_sum["safe"] else "danger"
    sim_safe_txt = "SAFE" if s_sum["safe"] else "UNSAFE"
    sim_flight_html = f\"\"\"
      <div class="metric"><span class="mk">Segments Checked</span><span class="mv">{s_sum["segments"]}</span></div>
      <div class="metric"><span class="mk">Status</span><span class="mv {sim_safe_cls}">{sim_safe_txt}</span></div>
      <div class="metric"><span class="mk">Total Alerts</span><span class="mv">{s_sum["alerts"]}</span></div>
      <div class="metric"><span class="mk">Critical</span><span class="mv {'danger' if s_sum['critical'] else 'g'}">{s_sum["critical"]}</span></div>
      <div class="metric"><span class="mk">Floor Altitude</span><span class="mv">20.0 m</span></div>
      <div class="metric"><span class="mk">Vert. Clearance</span><span class="mv">10.0 m</span></div>
    \"\"\"

    swarm_data = [
        {"drone_id": d, "lat": drones[d].get("lat", 47.38), "lon": drones[d].get("lon", 8.54),
         "alt": 50, "speed": 10, "bearing_deg": 90}
        for d in drones
    ]
    targets = nav_engine.track_swarm(swarm_data)
    if targets:
        swarm_targets_html = '<table class="mtable"><thead><tr><th>Drone ID</th><th>Lat</th><th>Lon</th><th>Alt</th><th>Speed</th><th>Bearing</th><th>Last Seen</th></tr></thead><tbody>'
        for t in targets:
            import datetime
            seen = datetime.datetime.fromtimestamp(t.last_seen).strftime("%H:%M:%S")
            swarm_targets_html += f'<tr><td>{t.drone_id}</td><td>{t.lat}</td><td>{t.lon}</td><td>{t.alt} m</td><td>{t.speed} m/s</td><td>{t.bearing_deg}°</td><td>{seen}</td></tr>'
        swarm_targets_html += '</tbody></table>'
    else:
        swarm_targets_html = '<div style="color:var(--dim);padding:12px;font-size:12px">No swarm targets detected</div>'

"""

old_gen_anchor = "    # Replace placeholders manually"
src = src.replace(old_gen_anchor, nav_gen + "    # Replace placeholders manually", 1)

# 4. Replace calls
old_replace = '    html = html.replace("{drone_cards}",  drone_cards)'
new_replace = """    html = html.replace("{nav_alerts}", nav_alerts_html)
    html = html.replace("{nav_etas}", nav_etas_html)
    html = html.replace("{sim_flight}", sim_flight_html)
    html = html.replace("{swarm_targets}", swarm_targets_html)
    html = html.replace("{drone_cards}",  drone_cards)"""
src = src.replace(old_replace, new_replace, 1)

with open("dashboard/app.py", "w", encoding="utf-8") as f:
    f.write(src)

print("Done")
