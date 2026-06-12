# fix_radar_particles.py
with open("dashboard/app.py", "r", encoding="utf-8") as f:
    src = f.read()

# 1. Исправляем частицы — canvas particles должен быть на всю ширину включая sidebar
src = src.replace(
    "body { margin-right:270px; }",
    "body { margin-right:270px; } #particles { position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:0; pointer-events:none; }",
    1
)

# 2. Убираем канвас Threat Radar — заменяем на текст
old_threat = """    <canvas id="radarCanvas"></canvas>"""
new_threat = ""
src = src.replace(old_threat, new_threat, 1)

# 3. Обновляем JS радара сбоку — добавляем визуализацию угроз
old_draw = "  // Center dot\n  ctx.beginPath();\n  ctx.arc(cx, cy, 4, 0, Math.PI*2);\n  ctx.fillStyle = \"#00bfff\";\n  ctx.fill();"

new_draw = """  // Threat overlay
  const _threat = \"""" + "{sb_threat_js}" + """\";
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
  ctx.fill();"""

src = src.replace(old_draw, new_draw, 1)

with open("dashboard/app.py", "w", encoding="utf-8") as f:
    f.write(src)

print("Done")
