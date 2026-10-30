// SPDX-License-Identifier: AGPL-3.0-or-later
// The background of the Imersão: the camera (the room behind, as the original Barehands) or "escuro",
// a dark animated scene (a perspective grid and a drifting network of points that connect), approved
// in the hologram lab on 29/10/2026. The camera keeps tracking the hands in both: in escuro the video
// is only shrunk out of sight, as in the original OBS modes. Kept optional for glasses that show the
// real world. 2D canvas on purpose: the GPU is shared with the hand tracker and the hologram.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const CHAVE = "jv-fundo", MODOS = ["camera", "escuro"];
  const pedido = new URLSearchParams(location.search).get("fundo");
  let modo = "camera";
  try { modo = localStorage.getItem(CHAVE) === "escuro" ? "escuro" : "camera"; } catch (_) {}
  if (MODOS.includes(pedido)) modo = pedido;
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)");

  const css = document.createElement("style");
  css.textContent = `
    body.jv-escuro { background:#000 !important; }
    body.jv-escuro #cam { width:2px; height:2px; opacity:.01; pointer-events:none; }
    #jv-fundo-cena { position:fixed; inset:0; width:100%; height:100%; pointer-events:none; display:none; }
    body.jv-escuro #jv-fundo-cena { display:block; }
    body.jv-escuro::after { content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
      background:radial-gradient(ellipse at 50% 45%, transparent 40%, rgb(0 0 0 / .55) 100%),
        repeating-linear-gradient(0deg, rgb(255 255 255 / .018) 0 1px, transparent 1px 3px); }`;
  document.head.appendChild(css);
  const tela = document.createElement("canvas");
  tela.id = "jv-fundo-cena"; tela.setAttribute("aria-hidden", "true");
  const cam = document.getElementById("cam");
  (cam?.parentNode || document.body).insertBefore(tela, cam ? cam.nextSibling : null);
  const ctx = tela.getContext("2d");

  // The theme colour (jarvis-tema.js sets --jv-acento-rgb); read once per second, not per frame.
  let cor = "143 240 228", lidaEm = 0;
  const corDoTema = agora => {
    if (agora - lidaEm < 1000) return cor;
    lidaEm = agora;
    const v = getComputedStyle(document.documentElement).getPropertyValue("--jv-acento-rgb").trim();
    return (cor = v || cor);
  };
  let semente = 11;
  const rnd = () => ((semente = (semente * 16807) % 2147483647) - 1) / 2147483646;
  const NOS = 110, nos = [...Array(NOS)].map(() => ({ x: rnd(), y: rnd() * .62, vx: (rnd() - .5) * .012, vy: (rnd() - .5) * .008, r: .6 + rnd() * 1.4 }));
  let pulsos = [], raf = 0, ultimo = 0, rolagem = 0;

  function desenhar(agora) {
    raf = requestAnimationFrame(desenhar);
    if (modo !== "escuro" || document.hidden) return;
    if (agora - ultimo < 33) return;  // ~30 fps is plenty for a background
    const dt = Math.min(.1, (agora - ultimo) / 1000 || .033); ultimo = agora;
    const W = innerWidth, H = innerHeight;
    if (tela.width !== W || tela.height !== H) { tela.width = W; tela.height = H; }
    const c = corDoTema(agora), mov = reduzir.matches ? 0 : 1;
    ctx.clearRect(0, 0, W, H);
    // The grid floor: lines converge to the horizon and roll slowly towards the viewer.
    const hz = H * .6, fx = W / 2;
    rolagem = (rolagem + dt * .18 * mov) % 1;
    ctx.lineWidth = 1;
    for (let i = -14; i <= 14; i++) {
      const xb = fx + i * W * .09;
      const g = ctx.createLinearGradient(0, hz, 0, H);
      g.addColorStop(0, `rgb(${c} / 0)`); g.addColorStop(1, `rgb(${c} / .16)`);
      ctx.strokeStyle = g; ctx.beginPath(); ctx.moveTo(fx + i * W * .006, hz); ctx.lineTo(xb, H); ctx.stroke();
    }
    for (let k = 0; k < 14; k++) {
      const t = (k + rolagem) / 14, y = hz + (H - hz) * t * t;
      ctx.strokeStyle = `rgb(${c} / ${(.02 + .14 * t * t).toFixed(3)})`;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    // The network: drifting points above the horizon; near pairs join, a pulse now and then runs along.
    for (const n of nos) {
      n.x += n.vx * dt * mov; n.y += n.vy * dt * mov;
      if (n.x < 0 || n.x > 1) n.vx *= -1;
      if (n.y < 0 || n.y > .62) n.vy *= -1;
    }
    const R = Math.min(W, H) * .16, pares = [];
    for (let i = 0; i < NOS; i++) for (let j = i + 1; j < NOS; j++) {
      const a = nos[i], b = nos[j], d = Math.hypot((a.x - b.x) * W, (a.y - b.y) * H);
      if (d > R) continue;
      pares.push([a, b]);
      ctx.strokeStyle = `rgb(${c} / ${((1 - d / R) * .22).toFixed(3)})`;
      ctx.beginPath(); ctx.moveTo(a.x * W, a.y * H); ctx.lineTo(b.x * W, b.y * H); ctx.stroke();
    }
    ctx.fillStyle = `rgb(${c} / .55)`;
    for (const n of nos) { ctx.beginPath(); ctx.arc(n.x * W, n.y * H, n.r, 0, Math.PI * 2); ctx.fill(); }
    if (mov && pares.length && Math.random() < dt * 2.5) pulsos.push({ par: pares[Math.random() * pares.length | 0], t: 0 });
    ctx.fillStyle = "#eafffb"; ctx.shadowColor = `rgb(${c})`; ctx.shadowBlur = 8;
    pulsos = pulsos.filter(p => {
      p.t += dt * 1.4; if (p.t >= 1) return false;
      const [a, b] = p.par; ctx.beginPath();
      ctx.arc((a.x + (b.x - a.x) * p.t) * W, (a.y + (b.y - a.y) * p.t) * H, 1.8, 0, Math.PI * 2); ctx.fill();
      return true;
    });
    ctx.shadowBlur = 0;
  }

  function usar(novo) {
    if (!MODOS.includes(novo)) throw new Error("fundo: camera ou escuro");
    modo = novo;
    document.body.classList.toggle("jv-escuro", modo === "escuro");
    try { localStorage.setItem(CHAVE, modo); } catch (_) {}
    window.dispatchEvent(new Event("jv-fundo"));
    return { fundo: modo };
  }
  addEventListener("keydown", e => {
    if (e.key !== "f" && e.key !== "F") return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.target.closest?.("input, textarea, [contenteditable], #jv-teclado")) return;
    usar(modo === "escuro" ? "camera" : "escuro");
  });
  usar(modo);
  raf = requestAnimationFrame(desenhar);
  window.jarvisFundo = { get modo() { return modo; }, usar, alternar: () => usar(modo === "escuro" ? "camera" : "escuro") };
})();
