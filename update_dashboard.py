with open('dashboard/app.py', 'r') as f:
    content = f.read()

# Add sound + laser routes to JS section
old = '''// AUTO REFRESH
setTimeout(()=>location.reload(), 30000);'''

new = '''// LASER ROUTES on map
(function() {
  const c = document.getElementById("mapCanvas");
  if(!c) return;
  // Override map draw to add laser effect
  const origDraw = window._mapDraw;
})();

// SOUND ENGINE
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function initAudio() {
  if(audioCtx) return;
  audioCtx = new AudioCtx();
}

function playDroneBuzz(freq=80, duration=0.3) {
  if(!audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(freq*0.7, audioCtx.currentTime+duration);
  gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime+duration);
  osc.start();
  osc.stop(audioCtx.currentTime+duration);
}

function playRadarPing() {
  if(!audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = "sine";
  osc.frequency.setValueAtTime(1200, audioCtx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(600, audioCtx.currentTime+0.3);
  gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime+0.3);
  osc.start();
  osc.stop(audioCtx.currentTime+0.3);
}

function playBlockchainBeep() {
  if(!audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = "square";
  osc.frequency.setValueAtTime(880, audioCtx.currentTime);
  gain.gain.setValueAtTime(0.03, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime+0.1);
  osc.start();
  osc.stop(audioCtx.currentTime+0.1);
}

// Sound toggle button
document.addEventListener("DOMContentLoaded", function() {
  const hbar = document.querySelector(".hbar");
  if(hbar) {
    const btn = document.createElement("button");
    btn.className = "hbtn";
    btn.id = "soundBtn";
    btn.textContent = "♪ SOUND OFF";
    btn.style.borderColor = "var(--dim)";
    let soundOn = false;
    btn.onclick = function() {
      initAudio();
      soundOn = !soundOn;
      btn.textContent = soundOn ? "♪ SOUND ON" : "♪ SOUND OFF";
      btn.style.borderColor = soundOn ? "var(--green)" : "var(--dim)";
      btn.style.color = soundOn ? "var(--green)" : "";
      if(soundOn) {
        // Start ambient drone hum
        window._soundInterval = setInterval(function() {
          playDroneBuzz(60 + Math.random()*20, 0.5);
        }, 2000);
        // Radar ping every 3s
        window._radarInterval = setInterval(playRadarPing, 3000);
        // Blockchain beep every 5s
        window._chainInterval = setInterval(playBlockchainBeep, 5000);
      } else {
        clearInterval(window._soundInterval);
        clearInterval(window._radarInterval);
        clearInterval(window._chainInterval);
      }
    };
    hbar.insertBefore(btn, hbar.lastElementChild);
  }
});

// AUTO REFRESH
setTimeout(()=>location.reload(), 30000);'''

if old in content:
    content = content.replace(old, new)
    print("OK: sound added")
else:
    print("ERROR: pattern not found")

# Add laser effect to map canvas draw function
old2 = '''      // Draw route line
      ctx.beginPath();
      ctx.setLineDash([4,4]);
      ctx.moveTo(d.x*c.width, d.y*c.height);
      ctx.lineTo(d.tx*c.width, d.ty*c.height);
      ctx.strokeStyle=d.color+"33";
      ctx.lineWidth=1;
      ctx.stroke();
      ctx.setLineDash([]);'''

new2 = '''      // Draw laser route line
      const lx1=d.x*c.width, ly1=d.y*c.height, lx2=d.tx*c.width, ly2=d.ty*c.height;
      // Outer glow
      ctx.beginPath();
      ctx.moveTo(lx1,ly1); ctx.lineTo(lx2,ly2);
      ctx.strokeStyle=d.color+"22";
      ctx.lineWidth=6;
      ctx.shadowBlur=12;
      ctx.shadowColor=d.color;
      ctx.stroke();
      // Core laser line
      ctx.beginPath();
      ctx.moveTo(lx1,ly1); ctx.lineTo(lx2,ly2);
      ctx.strokeStyle=d.color+"66";
      ctx.lineWidth=1.5;
      ctx.shadowBlur=0;
      ctx.stroke();
      ctx.setLineDash([]);'''

if old2 in content:
    content = content.replace(old2, new2)
    print("OK: laser routes added")
else:
    print("ERROR: laser pattern not found")

with open('dashboard/app.py', 'w') as f:
    f.write(content)
print("DONE")
