'use strict';

const PAGE = `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Timer</title>
<style>
  :root { --bg:#0b0d12; --fg:#f4f6fb; --accent:#ffb020; --muted:#8a93a6; --panel:#151925; }
  * { box-sizing:border-box; }
  body {
    margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:radial-gradient(1200px 800px at 50% -10%, #1b2130, var(--bg));
    color:var(--fg); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  }
  .card {
    background:var(--panel); border:1px solid #222839; border-radius:20px;
    padding:40px 44px; width:min(92vw,440px); text-align:center;
    box-shadow:0 20px 60px rgba(0,0,0,.45);
  }
  h1 { margin:0 0 6px; font-size:20px; font-weight:600; letter-spacing:.3px; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:28px; }
  .display {
    font-size:72px; font-weight:700; font-variant-numeric:tabular-nums;
    letter-spacing:2px; margin:18px 0 26px; line-height:1;
    transition:color .2s;
  }
  .display.done { color:var(--accent); animation:pulse 1s infinite; }
  @keyframes pulse { 50% { opacity:.4; } }
  .inputs { display:flex; gap:8px; justify-content:center; margin-bottom:22px; }
  .field { display:flex; flex-direction:column; align-items:center; gap:6px; }
  .field label { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; }
  input {
    width:80px; padding:12px; font-size:22px; text-align:center; border-radius:12px;
    border:1px solid #2a3143; background:#0e121b; color:var(--fg); font-variant-numeric:tabular-nums;
  }
  input:focus { outline:none; border-color:var(--accent); }
  .btns { display:flex; gap:10px; }
  button {
    flex:1; padding:14px; font-size:15px; font-weight:600; border-radius:12px; cursor:pointer;
    border:none; transition:transform .05s, background .2s;
  }
  button:active { transform:translateY(1px); }
  .start { background:var(--accent); color:#1a1200; }
  .reset { background:#222839; color:var(--fg); }
  .presets { display:flex; gap:8px; justify-content:center; margin-bottom:20px; flex-wrap:wrap; }
  .presets button { flex:none; padding:8px 14px; font-size:13px; background:#1b2130; color:var(--muted); font-weight:500; }
  .presets button:hover { color:var(--fg); }
</style>
</head>
<body>
  <div class="card">
    <h1>⏱️ Timer</h1>
    <div class="sub">Entrez une durée, comptez jusqu'à zéro</div>
    <div id="display" class="display">00:00</div>
    <div class="presets">
      <button data-s="60">1 min</button>
      <button data-s="300">5 min</button>
      <button data-s="600">10 min</button>
      <button data-s="1500">25 min</button>
    </div>
    <div class="inputs">
      <div class="field"><label>Min</label><input id="min" type="number" min="0" max="999" value="0"></div>
      <div class="field"><label>Sec</label><input id="sec" type="number" min="0" max="59" value="30"></div>
    </div>
    <div class="btns">
      <button id="start" class="start">Démarrer</button>
      <button id="reset" class="reset">Réinitialiser</button>
    </div>
  </div>
<script>
  const $ = (id) => document.getElementById(id);
  const display = $('display'), minI = $('min'), secI = $('sec');
  let remaining = 0, tick = null, running = false;

  function fmt(t) {
    const m = Math.floor(t / 60), s = t % 60;
    return String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
  }
  function render() {
    display.textContent = fmt(remaining);
    display.classList.toggle('done', remaining === 0 && !running);
  }
  function readInput() {
    const m = Math.max(0, parseInt(minI.value || '0', 10));
    const s = Math.max(0, Math.min(59, parseInt(secI.value || '0', 10)));
    return m * 60 + s;
  }
  function stop() { clearInterval(tick); tick = null; running = false; }
  function start() {
    if (running) { stop(); $('start').textContent = 'Démarrer'; render(); return; }
    if (remaining <= 0) remaining = readInput();
    if (remaining <= 0) return;
    running = true; $('start').textContent = 'Pause';
    display.classList.remove('done');
    tick = setInterval(() => {
      remaining--;
      render();
      if (remaining <= 0) {
        stop(); $('start').textContent = 'Démarrer';
        display.classList.add('done');
        try { new AudioContext(); } catch (e) {}
        beep();
      }
    }, 1000);
  }
  function reset() { stop(); $('start').textContent = 'Démarrer'; remaining = readInput(); render(); }
  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.frequency.value = 880; o.type = 'sine';
      g.gain.setValueAtTime(0.001, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
      o.start(); o.stop(ctx.currentTime + 0.6);
    } catch (e) {}
  }
  $('start').onclick = start;
  $('reset').onclick = reset;
  document.querySelectorAll('.presets button').forEach((b) => {
    b.onclick = () => { const t = +b.dataset.s; minI.value = Math.floor(t/60); secI.value = t%60; reset(); };
  });
  [minI, secI].forEach((el) => el.oninput = () => { if (!running) reset(); });
  reset();
</script>
</body>
</html>`;

exports.handler = (request) => {
  return [200, PAGE, { 'content-type': 'text/html; charset=utf-8' }];
};
