# fix_nav.py
with open("dashboard/app.py", "r", encoding="utf-8") as f:
    src = f.read()

nav_gen = '''
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
            nav_alerts_html += f\'<div class="alert-item {lv}"><span class="alert-dot {lv}"></span><span>[{drone_id}] {a.message}</span></div>\'
        for e in _etas:
            eta_str = _dt.datetime.fromtimestamp(e.planned_eta).strftime("%H:%M:%S")
            nav_etas_html += f\'<div class="eta-row"><span>{drone_id} · NavPoint {e.waypoint_index}</span><span class="mv c">{eta_str}</span></div>\'
    if not nav_alerts_html:
        nav_alerts_html = \'<div class="alert-item notice"><span class="alert-dot notice"></span><span>All systems nominal — no active alerts</span></div>\'
    _s = _sim.summary()
    _safe_cls = "g" if _s["safe"] else "danger"
    _safe_txt = "SAFE" if _s["safe"] else "UNSAFE"
    _crit_cls = "danger" if _s["critical"] else "g"
    sim_flight_html = (
        f\'<div class="metric"><span class="mk">Segments</span><span class="mv">{_s["segments"]}</span></div>\'
        f\'<div class="metric"><span class="mk">Status</span><span class="mv {_safe_cls}">{_safe_txt}</span></div>\'
        f\'<div class="metric"><span class="mk">Total Alerts</span><span class="mv">{_s["alerts"]}</span></div>\'
        f\'<div class="metric"><span class="mk">Critical</span><span class="mv {_crit_cls}">{_s["critical"]}</span></div>\'
        f\'<div class="metric"><span class="mk">Floor Altitude</span><span class="mv">20.0 m</span></div>\'
        f\'<div class="metric"><span class="mk">Vert. Clearance</span><span class="mv">10.0 m</span></div>\'
    )
    _swarm_data = [
        {"drone_id": d, "lat": 47.38, "lon": 8.54, "alt": 50, "speed": 10, "bearing_deg": 90}
        for d in drones
    ]
    _targets = nav_engine.track_swarm(_swarm_data)
    if _targets:
        swarm_targets_html = \'<table class="mtable"><thead><tr><th>Drone ID</th><th>Lat</th><th>Lon</th><th>Alt</th><th>Speed</th><th>Bearing</th><th>Last Seen</th></tr></thead><tbody>\'
        for t in _targets:
            _seen = _dt.datetime.fromtimestamp(t.last_seen).strftime("%H:%M:%S")
            swarm_targets_html += f\'<tr><td>{t.drone_id}</td><td>{t.lat}</td><td>{t.lon}</td><td>{t.alt} m</td><td>{t.speed} m/s</td><td>{t.bearing_deg}°</td><td>{_seen}</td></tr>\'
        swarm_targets_html += \'</tbody></table>\'
    else:
        swarm_targets_html = \'<div style="color:var(--dim);padding:12px;font-size:12px">No swarm targets detected</div>\'

'''

anchor = '    html = HTML_TEMPLATE'
src = src.replace(anchor, nav_gen + anchor, 1)

with open("dashboard/app.py", "w", encoding="utf-8") as f:
    f.write(src)

print("Done")
