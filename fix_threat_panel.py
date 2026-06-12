# fix_threat_panel.py
with open("dashboard/app.py", "r", encoding="utf-8") as f:
    src = f.read()

# Убираем Threat Radar карточку
old = '  <div class="card">\n    <div class="ctitle">Threat Radar \xb7 360\xb0 Scan</div>\n    <div class="radar-container">\n\n    </div>\n    <div class="metric" style="margin-top:4px"><span class="mk">GPS</span><span class="mv g">CLEAN</span></div>\n    <div class="metric"><span class="mk">Jamming</span><span class="mv g">CLEAR</span></div>\n    <div class="metric"><span class="mk">Threats</span><span class="mv g">NONE</span></div>\n  </div>\n</div>\n\n<!-- DRONE FLEET -->'

new = '</div>\n\n<!-- DRONE FLEET -->'

if old in src:
    src = src.replace(old, new, 1)
    print("Threat panel removed")
else:
    print("Pattern not found - checking...")

# Два квадрата на всю ширину
src = src.replace(
    'class="mid-grid">',
    'class="mid-grid" style="grid-template-columns:1fr 1fr">',
    1
)

with open("dashboard/app.py", "w", encoding="utf-8") as f:
    f.write(src)

print("Done")
