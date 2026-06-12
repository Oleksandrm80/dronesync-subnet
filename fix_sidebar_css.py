# fix_sidebar_css.py
with open("dashboard/app.py", "r", encoding="utf-8") as f:
    src = f.read()

sidebar_css = """
  .sidebar { position:fixed; right:0; top:0; width:260px; height:100vh; background:#070910;
             border-left:1px solid #223060; z-index:1000; display:flex;
             flex-direction:column; padding:12px 10px; gap:8px; overflow:hidden; }
  .sb-title { font-size:9px; letter-spacing:2px; color:#485a78; text-transform:uppercase;
              padding:6px 8px; border-bottom:1px solid #1a2238; }
  .sb-radar-wrap { flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; }
  #sideRadar { width:230px; height:230px; }
  .sb-range-btns { display:flex; gap:6px; align-items:center; }
  .sb-rbtn { background:transparent; border:1px solid #223060; color:#00bfff;
             width:28px; height:28px; border-radius:4px; font-size:16px; cursor:pointer;
             font-family:inherit; transition:all 0.2s; display:flex; align-items:center; justify-content:center; }
  .sb-rbtn:hover { border-color:#00bfff; background:#00bfff11; }
  .sb-range-lbl { font-size:11px; color:#00bfff; letter-spacing:1px; min-width:80px; text-align:center; }
  .sb-stats { width:100%; display:flex; flex-direction:column; gap:4px; }
  .sb-row { display:flex; justify-content:space-between; font-size:10px; padding:3px 6px;
            border-bottom:1px solid #1a2238; }
  .sb-row:last-child { border-bottom:none; }
  .sb-key { color:#485a78; }
  .sb-val { color:#eef2ff; font-weight:bold; }
  .sb-val.g { color:#00e5a0; }
  .sb-val.c { color:#00bfff; }
  .sb-val.r { color:#ff2d4a; }
  body { margin-right:270px; }
"""

src = src.replace("  footer { text-align:center;", sidebar_css + "  footer { text-align:center;", 1)

with open("dashboard/app.py", "w", encoding="utf-8") as f:
    f.write(src)

print("Done")
