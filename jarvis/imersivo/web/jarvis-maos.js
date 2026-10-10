// SPDX-License-Identifier: AGPL-3.0-or-later
// barehands-jarvis: the hands calibrator, the camera check and the light.
//
// - PADRAO is the original tuning of stage.html. It lives only here, is never
//   written anywhere, and wins whenever a profile is missing or out of bounds.
// - The guided calibration (K, the ✋ chip or "calibrar as mãos" by voice)
//   measures this hand on this camera: tremor, quick pinches and the fist.
//   A new profile is kept only if it recognises the pinches at least as well
//   as the original and still rejects every fist.
// - Daily use refines it slowly: a pinch that just missed (moved or lasted a
//   little too much) and is repeated at once on the same spot is evidence.
// - The light: the camera's own gain/exposure are steered so the hand stays
//   well exposed with a short shutter (no blur at 60 fps). Originals are
//   backed up by the server and restored by "voltar ao padrão" (Shift+K) or
//   when this page stops. In a very dark room a soft brightness lift is
//   applied to the frame the tracker sees.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const Q = new URLSearchParams(location.search);

  const PADRAO = Object.freeze({ versao: 1, pincaFrontal: 0.32, pincaPerfil: 0.38, contraste: 0.18,
    arco: 1.30, soltar: 0.55, soltarRapido: 0.70, tremor: 16, fantasma: 900, toqueMs: 350, toque3: 0 });
  const LIMITES = { pincaFrontal: [0.22, 0.40], pincaPerfil: [0.30, 0.42], contraste: [0.08, 0.28],
    arco: [1.15, 1.40], soltar: [0.45, 0.65], soltarRapido: [0.60, 0.85], tremor: [12, 48],
    fantasma: [700, 1800], toqueMs: [300, 900], toque3: [0, 0.40] };   // toque3 0 = off (original)
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const limitar = (k, v) => clamp(v, LIMITES[k][0], LIMITES[k][1]);
  const quantil = (xs, q) => {
    if (!xs.length) return NaN;
    const s = [...xs].sort((a, b) => a - b), i = (s.length - 1) * q, lo = Math.floor(i);
    return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (i - lo);
  };
  function valido(p) {
    if (!p || typeof p !== "object") return false;
    for (const [k, [a, b]] of Object.entries(LIMITES))
      if (typeof p[k] !== "number" || !Number.isFinite(p[k]) || p[k] < a || p[k] > b) return false;
    return p.soltar >= Math.max(p.pincaFrontal, p.pincaPerfil) + 0.08;
  }
  const esc = s => String(s).replace(/[&<>"]/g, x => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[x]);
  async function api(url, corpo) {
    const r = await fetch(url, corpo ? { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo) } : { cache: "no-store" });
    return r.json();
  }
  function aviso(msg, ms = 3500) {
    const t = document.getElementById("toast");
    if (!t) return;
    t.textContent = msg; t.style.display = "block";
    clearTimeout(t._h); t._h = setTimeout(() => t.style.display = "none", ms);
  }
  const guardado = (k, padrao) => { try { return localStorage.getItem(k) ?? padrao; } catch (e) { return padrao; } };
  const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };

  // ---------- profile --------------------------------------------------------
  let perfil = PADRAO, origem = "padrao", resumo = {};
  function usar(d) {
    if (d && d.perfil && valido({ ...PADRAO, ...d.perfil })) {
      perfil = Object.freeze({ ...PADRAO, ...d.perfil }); origem = d.origem || "calibrado"; resumo = d.resumo || {};
    } else { perfil = PADRAO; origem = "padrao"; resumo = {}; }
  }
  async function carregar() { try { usar(await api("/maos/perfil")); } catch (e) { usar(null); } }
  async function salvar(novo, org, res) {
    if (!valido(novo)) return false;
    try {
      const d = await api("/maos/perfil", { perfil: novo, origem: org, resumo: res });
      if (!d.perfil) return false;
      usar(d); return true;
    } catch (e) { return false; }
  }

  // ---------- camera: frames per second, inference, best mode -----------------
  const cam = document.getElementById("cam");
  let qps = 0, quadros = 0, tQps = performance.now(), contando = false, inferencia = 0;
  function contar() {
    quadros++;
    const t = performance.now();
    if (t - tQps >= 1000) { qps = quadros * 1000 / (t - tQps); quadros = 0; tQps = t; }
    cam.requestVideoFrameCallback(contar);
  }
  const trilha = () => cam?.srcObject?.getVideoTracks?.()[0] || null;
  const auto = !Q.get("fps") || Q.get("fps") === "auto";
  let lento = 0, folga = 0, espera = 60, modoMedido = "";
  async function conferirCamera() {
    const t = trilha();
    if (!t) return;
    // Another camera (C cycles them): its controls are looked up again.
    if (hw?.nome && hw.nome !== t.label) { hw = null; alvoHw = null; enviadoHw = ""; }
    if (!contando && cam.requestVideoFrameCallback) { contando = true; cam.requestVideoFrameCallback(contar); }
    const perf = window.barehandsPerformance;
    if (perf && Number.isFinite(perf.inferenceMs)) inferencia = inferencia ? inferencia * 0.9 + perf.inferenceMs * 0.1 : perf.inferenceMs;
    const s = t.getSettings(), cap = t.getCapabilities?.() || {};
    modoMedido = `${s.width}×${s.height}`;
    if (!auto) return;
    // The best mode for tracking is the highest frame rate the camera and this
    // machine sustain; MediaPipe works on a small crop, so 720p is plenty.
    if ((cap.frameRate?.max || 0) >= 59 && (s.frameRate || 0) < 55 && inferencia < 12 && !lento) {
      try { await t.applyConstraints({ width: { ideal: s.width }, height: { ideal: s.height }, frameRate: { ideal: 60, max: 60 } }); } catch (e) {}
    }
    // The tracker must keep up: above ~14 ms per frame, 60 fps only adds lag.
    if ((s.frameRate || 0) > 45 && inferencia > 14) {
      if (++lento >= 5) {
        try { await t.applyConstraints({ width: { ideal: s.width }, height: { ideal: s.height }, frameRate: { ideal: 30, max: 30 } }); } catch (e) {}
        aviso("Câmera em 30 quadros: a placa de vídeo não acompanha 60");
      }
    } else if (inferencia <= 14) lento = Math.min(lento, 4);
    // Fell back to 30 earlier? Try 60 again after a calm minute (longer after each try).
    if (lento >= 5 && inferencia < 10) {
      if (++folga >= espera) { lento = 0; folga = 0; espera = Math.min(espera * 2, 1800); }
    } else folga = 0;
  }

  // ---------- light ----------------------------------------------------------
  const medidor = document.createElement("canvas");
  medidor.width = 64; medidor.height = 36;
  const mctx = medidor.getContext("2d", { willReadFrequently: true });
  let luzLigada = guardado("jv-luz", "1") === "1";
  let luma = NaN, lumaMao = NaN, caixa = null, maoEm = 0, reforco = 1;
  let hw = null, alvoHw = null, enviadoHw = "", ultimoEnvio = 0;
  function medir() {
    if (!cam || cam.readyState < 2) return;
    mctx.drawImage(cam, 0, 0, 64, 36);
    const px = mctx.getImageData(0, 0, 64, 36).data;
    const y = i => (0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2]) / 255;
    // Centre-weighted: the person in front matters more than a bright window.
    let soma = 0, centro = 0, nc = 0;
    for (let i = 0; i < px.length; i += 4) {
      const v = y(i), xx = (i / 4) % 64, yy = Math.floor(i / 256);
      soma += v;
      if (xx >= 16 && xx < 48 && yy >= 6 && yy < 30) { centro += v; nc++; }
    }
    luma = 0.65 * (centro / nc) + 0.35 * (soma / (px.length / 4));
    if (caixa && performance.now() - maoEm < 1000) {
      const [x0, y0, x1, y1] = caixa, mx = (x1 - x0) * 0.15, my = (y1 - y0) * 0.15;
      const a = Math.floor(clamp(x0 - mx, 0, 1) * 63), b = Math.ceil(clamp(x1 + mx, 0, 1) * 63);
      const c = Math.floor(clamp(y0 - my, 0, 1) * 35), d = Math.ceil(clamp(y1 + my, 0, 1) * 35);
      let s2 = 0, n = 0;
      for (let yy = c; yy <= d; yy++) for (let xx = a; xx <= b; xx++) { s2 += y((yy * 64 + xx) * 4); n++; }
      lumaMao = n ? s2 / n : luma;
    } else lumaMao = NaN;
  }
  const lumaAlvo = () => Number.isFinite(lumaMao) ? lumaMao : luma;
  function estadoLuz() {
    const l = lumaAlvo();
    if (!Number.isFinite(l)) return "—";
    return l < 0.30 ? "fraca" : l < 0.42 ? "baixa" : l > 0.70 ? "forte" : "boa";
  }
  async function prepararHw() {
    const t = trilha();
    if (!t || hw !== null) return;
    hw = "consultando";
    let achado = false;
    try {
      const info = await api("/camera/info?nome=" + encodeURIComponent(t.label));
      if (info.disponivel) achado = { nome: t.label, c: info.controles };
    } catch (e) {}
    hw = achado;
  }
  // The light is SET, then HELD. It settles once (at start, in the first step
  // of the calibration, or when the room really changes) and then stays still:
  // a brightness that keeps moving is worse than a slightly imperfect one.
  // A short shutter freezes the moving hand; the gain buys the light back.
  // The brightness the person chooses (B, the ☀ chip or by voice). Each level
  // asks the camera itself for more light (longer shutter within the frame
  // time, then gain) and adds a gentle picture filter on top.
  const BRILHOS = [
    { nome: "DESLIGADO", alvo: 0.48, f: 1, c: 1, s: 1 },
    { nome: "SUAVE", alvo: 0.54, f: 1.1, c: 1.04, s: 1.08 },
    { nome: "MÉDIO", alvo: 0.60, f: 1.2, c: 1.06, s: 1.12 },
    { nome: "FORTE", alvo: 0.66, f: 1.35, c: 1.08, s: 1.15 },
  ];
  let brilho = clamp(Math.round(Number(guardado("jv-brilho", "0")) || 0), 0, 3);
  const alvoLuz = () => BRILHOS[brilho].alvo, PERTO = 0.05;
  const faixa = () => [alvoLuz() - 0.18, alvoLuz() + 0.20];
  let modoLuz = "ajustando", passoEm = 0, foraDesde = 0, lumaSuave = NaN, passos = 0;
  function luzMudou() { modoLuz = "ajustando"; passos = 0; foraDesde = 0; }
  function passoHw(agora) {
    // The whole picture, smoothed: a hand coming and going must not move it.
    if (Number.isFinite(luma)) lumaSuave = Number.isFinite(lumaSuave) ? lumaSuave * 0.6 + luma * 0.4 : luma;
    if (!hw?.c || !luzLigada || !Number.isFinite(lumaSuave)) return;
    const c = hw.c, fpsAlvo = (trilha()?.getSettings().frameRate || 30) > 45 ? 60 : 30;
    const eMax = Math.floor(10000 / fpsAlvo * 0.8);   // 100 µs units: 13 ms at 60 fps, 26 ms at 30
    if (!alvoHw) {
      if (!c.auto_exposure || !c.exposure_time_absolute || !c.gain) { hw = false; return; }
      const manual = c.auto_exposure.valor === 1;
      alvoHw = { auto_exposure: 1, gain: c.gain.valor,
        exposure_time_absolute: Math.min(eMax, manual ? c.exposure_time_absolute.valor : 100) };
      for (const k of ["brightness", "contrast", "gamma"]) if (c[k]) alvoHw[k] = c[k].padrao;
      luzMudou(); passoEm = agora;   // let the camera show the start before the first step
    }
    const a = alvoHw, gMax = c.gain.max, eMin = Math.max(c.exposure_time_absolute.min, 10);
    if (a.exposure_time_absolute > eMax) { a.exposure_time_absolute = eMax; luzMudou(); }
    if (modoLuz === "fixo") {
      // Only a lasting change of the room (5 s outside the wide band) re-opens it.
      const fora = lumaSuave < faixa()[0] || lumaSuave > faixa()[1];
      foraDesde = fora ? foraDesde || agora : 0;
      if (fora && agora - foraDesde > 5000) luzMudou();
    } else if (agora - passoEm > 900) {
      // One damped step, then wait for the camera to show it before the next.
      passoEm = agora;
      if (Math.abs(lumaSuave - alvoLuz()) < PERTO || ++passos > 14) { modoLuz = "fixo"; decidirReforco(); }
      else {
        const k = clamp(Math.sqrt(alvoLuz() / Math.max(lumaSuave, 0.03)), 0.7, 1.5);
        if (k > 1) {
          const e = Math.min(eMax, Math.round(a.exposure_time_absolute * k));
          const resto = k * a.exposure_time_absolute / e;
          a.exposure_time_absolute = e;
          if (resto > 1.03) a.gain = Math.min(gMax, a.gain + Math.max(1, Math.round((resto - 1) * gMax * 0.5)));
        } else if (a.gain > 0) a.gain = Math.max(0, a.gain - Math.max(1, Math.round((1 - k) * gMax * 0.6)));
        else a.exposure_time_absolute = Math.max(eMin, Math.round(a.exposure_time_absolute * k));
      }
    }
    const chave = JSON.stringify(a);
    if (chave !== enviadoHw || agora - ultimoEnvio > 5000) {
      enviadoHw = chave; ultimoEnvio = agora;
      api("/camera/ajustar", { nome: hw.nome, valores: a }).catch(() => {});
    }
  }
  // Last resort in a dark room, decided once when the light settles: lift the
  // frame the tracker sees. Fixed until the light is adjusted again.
  function decidirReforco() {
    const noLimite = hw === false || (!!hw?.c && !!alvoHw && alvoHw.gain >= hw.c.gain.max * 0.95);
    reforco = luzLigada && noLimite && Number.isFinite(lumaSuave) && lumaSuave < 0.32 ? +clamp(alvoLuz() / lumaSuave, 1, 2).toFixed(1) : 1;
    aplicarFiltro();
  }
  // What is on screen: the chosen level times the dark-room lift.
  function aplicarFiltro() {
    const b = BRILHOS[brilho], f = Math.min(2.4, b.f * reforco);
    const filtro = f > 1.001 || b.c > 1 ? `brightness(${f.toFixed(2)}) contrast(${b.c}) saturate(${b.s})` : "";
    if (cam && cam.style.filter !== filtro) cam.style.filter = filtro;
  }
  function mudarBrilho(n) {
    brilho = clamp(n, 0, 3); guardar("jv-brilho", String(brilho));
    luzMudou(); aplicarFiltro();
    aviso(`Brilho da câmera: ${BRILHOS[brilho].nome.toLowerCase()}`, 2000);
  }
  function acionar(acao) {
    if (acao === "brilho") mudarBrilho((brilho + 1) % BRILHOS.length);
    else if (acao === "tema") window.jarvisTema?.alternar();
    else calibrar();
  }
  const copia = document.createElement("canvas"), cctx = copia.getContext("2d");
  function entrada(video) {
    if (reforco <= 1 || !video.videoWidth) return null;
    if (copia.width !== video.videoWidth) { copia.width = video.videoWidth; copia.height = video.videoHeight; }
    cctx.filter = `brightness(${reforco.toFixed(2)}) contrast(1.06)`;
    cctx.drawImage(video, 0, 0);
    return copia;
  }
  async function luzPadrao() {
    alvoHw = null; enviadoHw = ""; reforco = 1;
    aplicarFiltro();
    try { await api("/camera/restaurar", { nome: hw?.nome || trilha()?.label || "" }); } catch (e) {}
  }

  // ---------- daily refinement and diagnostics ---------------------------------
  const eventos = [], contagem = {};
  let evidencias = { tremor: 0, toqueMs: 0, fantasma: 0 }, ultimoAjuste = 0, diagMudou = false;
  const assinatura = new Map();
  function registrar(ev) {
    const e = { ...ev, t: Date.now() };
    eventos.push(e); if (eventos.length > 200) eventos.shift();
    contagem[e.resultado] = (contagem[e.resultado] || 0) + 1; diagMudou = true;
    if (e.resultado !== "abriu") return;
    // The miss right before this success, on the same spot: what stopped it?
    const antes = eventos.slice(-6, -1).reverse().find(x => e.t - x.t < 4000 && Math.hypot(x.x - e.x, x.y - e.y) < 90);
    if (!antes || antes.quase) return;
    let tipo = null;
    if (antes.resultado === "moveu" && antes.viagem < perfil.tremor * 3 && antes.dur < perfil.toqueMs * 2.5) tipo = "tremor";
    else if (antes.resultado === "demorou" && antes.dur < perfil.toqueMs * 2.5 && antes.viagem < perfil.tremor * 1.5) tipo = "toqueMs";
    else if (antes.resultado === "fantasma") tipo = "fantasma";
    if (!tipo) return;
    antes.quase = tipo;
    if (++evidencias[tipo] < 3 || Date.now() - ultimoAjuste < 120000) return;
    evidencias[tipo] = 0; ultimoAjuste = Date.now();
    const passo = { tremor: 3, toqueMs: 60, fantasma: 100 }[tipo];
    const novo = { ...perfil, [tipo]: limitar(tipo, perfil[tipo] + passo) };
    if (novo[tipo] === perfil[tipo]) return;
    salvar(novo, "ajustado", { ...resumo, ajuste: { campo: tipo, de: perfil[tipo], para: novo[tipo], em: Date.now() } });
  }
  setInterval(() => {
    if (!diagMudou) return;
    diagMudou = false;
    api("/maos/diagnostico", { origem, perfil, contagem, eventos: eventos.slice(-60),
      luz: { luma, lumaMao, estado: estadoLuz(), reforco, camera: alvoHw, ligada: luzLigada },
      camera: { qps: Math.round(qps), modo: modoMedido, inferenciaMs: +inferencia.toFixed(1) } }).catch(() => {});
  }, 30000);

  // ---------- guided calibration -----------------------------------------------
  const ui = document.createElement("div");
  ui.id = "jv-calibra"; ui.hidden = true;
  ui.setAttribute("role", "dialog"); ui.setAttribute("aria-label", "Calibrar as mãos");
  ui.innerHTML = '<div class="alvo" aria-hidden="true"><i></i></div><div class="cartao"><small class="passo"></small>' +
    '<h2></h2><p class="texto"></p><div class="pontos" aria-hidden="true"></div><div class="barra"><i></i></div>' +
    '<dl class="leitura"></dl><div class="acoes"><button data-a="padrao">Voltar ao padrão</button><button data-a="fechar">Cancelar</button></div></div>';
  const estilo = document.createElement("style");
  estilo.textContent = `
  #jv-calibra { position:fixed; inset:0; z-index:1200; display:grid; place-items:center; pointer-events:none;
    background:radial-gradient(circle at 50% 46%, transparent, var(--jv-escuro) 70%);
    font:14px/1.5 -apple-system, 'Segoe UI', sans-serif; color:var(--jv-texto); }
  #jv-calibra[hidden] { display:none; }
  #jv-calibra .alvo { position:absolute; left:50%; top:46%; width:120px; height:120px; margin:-60px 0 0 -60px; border-radius:50%;
    border:2px solid rgb(var(--jv-borda-rgb) / .75); box-shadow:0 0 30px rgb(var(--jv-borda-rgb) / .35), inset 0 0 24px rgb(var(--jv-borda-rgb) / .18); }
  #jv-calibra .alvo i { position:absolute; inset:44px; border-radius:50%; background:rgb(var(--jv-borda-rgb) / .85); transition:transform .12s; }
  #jv-calibra.toque .alvo i { transform:scale(1.9); }
  #jv-calibra.punho .alvo { border-color:rgba(239,190,124,.8); box-shadow:0 0 30px rgba(239,190,124,.35); }
  #jv-calibra .cartao { position:absolute; left:50%; bottom:13%; transform:translateX(-50%); width:min(460px, calc(100vw - 32px));
    padding:18px 22px; border-radius:18px; background:var(--jv-painel); border:1px solid rgb(var(--jv-borda-rgb) / .35);
    box-shadow:0 0 34px rgb(var(--jv-borda-rgb) / .12); pointer-events:auto; }
  #jv-calibra small.passo { color:var(--jv-suave); font:600 11px/1 'SF Mono', Menlo, monospace; letter-spacing:.14em; }
  #jv-calibra h2 { margin:8px 0 4px; font:650 20px/1.3 -apple-system, 'Segoe UI', sans-serif; text-wrap:balance; }
  #jv-calibra .texto { margin:0; color:var(--jv-texto); }
  #jv-calibra .pontos { display:flex; gap:8px; margin:12px 0 0; min-height:12px; }
  #jv-calibra .pontos b { width:12px; height:12px; border-radius:50%; border:1.5px solid rgb(var(--jv-borda-rgb) / .7); }
  #jv-calibra .pontos b.ok { background:var(--jv-acento); box-shadow:0 0 10px rgb(var(--jv-borda-rgb) / .8); }
  #jv-calibra .barra { height:4px; margin:14px 0 0; border-radius:2px; background:rgb(var(--jv-borda-rgb) / .16); overflow:hidden; }
  #jv-calibra .barra i { display:block; height:100%; width:0; background:var(--jv-acento); transition:width .2s linear; }
  #jv-calibra dl { display:grid; grid-template-columns:auto 1fr; gap:3px 14px; margin:12px 0 0; font-size:12.5px; }
  #jv-calibra dl:empty { display:none; }
  #jv-calibra dt { color:var(--jv-suave); } #jv-calibra dd { margin:0; font-family:'SF Mono', Menlo, monospace; font-variant-numeric:tabular-nums; }
  #jv-calibra dd.quente { color:#efbe7c; }
  #jv-calibra .acoes { display:flex; gap:8px; justify-content:flex-end; margin:14px 0 0; }
  #jv-calibra button { font:600 12px/1 -apple-system, 'Segoe UI', sans-serif; letter-spacing:.04em; color:var(--jv-texto); cursor:pointer;
    min-height:36px; padding:0 14px; border-radius:10px; background:rgb(var(--jv-borda-rgb) / .08); border:1px solid rgb(var(--jv-borda-rgb) / .35); }
  #jv-calibra button:hover, #jv-calibra button:focus-visible { background:rgb(var(--jv-borda-rgb) / .18); outline:none; }
  #hint.hud .jv.brilho.ligado { border-color:rgb(var(--jv-borda-rgb) / .6); background:rgb(var(--jv-borda-rgb) / .12); }
  #hint.hud .jv.maos.quente { color:#efbe7c; border-color:rgba(239,190,124,.45); }
  @media (prefers-reduced-motion:reduce) { #jv-calibra * { transition:none !important; } }`;
  document.head.appendChild(estilo);
  document.body.appendChild(ui);
  const $ = s => ui.querySelector(s);
  ui.addEventListener("click", ev => {
    const a = ev.target.closest("button")?.dataset.a;
    if (a === "fechar") encerrar(calib?.fase === "fim" ? null : "Calibração cancelada. Mantive a anterior.");
    else if (a === "padrao") padrao();
  });
  addEventListener("keydown", ev => {
    if (ev.target.closest?.("input, textarea")) return;
    if (ev.key === "Escape" && calib) { ev.preventDefault(); encerrar(calib.fase === "fim" ? null : "Calibração cancelada. Mantive a anterior."); }
    else if (ev.key === "k" && !ev.ctrlKey && !ev.metaKey) calibrar();
    else if (ev.key === "K" && !ev.ctrlKey && !ev.metaKey) padrao();
    else if ((ev.key === "b" || ev.key === "B") && !ev.ctrlKey && !ev.metaKey) mudarBrilho(ev.key === "B" ? brilho - 1 : (brilho + 1) % BRILHOS.length);
    else if ((ev.key === "t" || ev.key === "T") && !ev.ctrlKey && !ev.metaKey) window.jarvisTema?.alternar();
  });

  let calib = null;
  const FASES = {
    luz: { n: 1, titulo: "Preparando a câmera e a luz", texto: "Fique de frente para a câmera. Leva dois segundos.", ms: 2200 },
    parada: { n: 2, titulo: "Mão aberta, parada", texto: "Mostre a mão aberta apontando para o círculo e segure parada.", ms: 2500 },
    toques: { n: 3, titulo: "Cinco toques", texto: "Encoste a ponta do indicador na ponta do polegar e solte, no círculo. Cinco vezes, do seu jeito.", ms: 14000 },
    quase: { n: 4, titulo: "Quase encostando", texto: "Aproxime as pontas até quase encostar, SEM encostar, e segure.", ms: 1500 },
    afasta: { n: 4, titulo: "Agora afaste", texto: "Abra os dedos.", ms: 800 },
    punho: { n: 5, titulo: "Feche a mão", texto: "Feche a mão inteira, como um punho.", ms: 1300 },
    abrir: { n: 5, titulo: "Agora abra", texto: "Abra a mão de novo.", ms: 900 },
  };
  function mostrar() {
    if (!calib) return;
    const f = FASES[calib.fase];
    ui.classList.toggle("punho", calib.fase === "punho" || calib.fase === "quase");
    if (f) {
      $(".passo").textContent = `CALIBRAR AS MÃOS · PASSO ${f.n} DE 5`;
      $("h2").textContent = calib.fase === "punho" ? `Feche a mão (${calib.punhos + 1} de 3)`
        : calib.fase === "quase" ? `Quase encostando (${calib.quases + 1} de 3)` : f.titulo;
      $(".texto").textContent = calib.semMao > 600 ? "Não estou vendo sua mão. Mostre-a para a câmera." : f.texto;
      $(".pontos").innerHTML = calib.fase === "toques" ? Array.from({ length: 5 }, (_, i) => `<b class="${i < calib.eps.length ? "ok" : ""}"></b>`).join("") : "";
      $(".barra i").style.width = calib.fase === "toques" ? (calib.eps.length * 20) + "%" : clamp(calib.tempo / f.ms * 100, 0, 100) + "%";
      $(".leitura").innerHTML = `<dt>Câmera</dt><dd>${esc(modoMedido)} · ${Math.round(qps)} quadros/s</dd>` +
        `<dt>Luz na mão</dt><dd class="${["fraca", "baixa"].includes(estadoLuz()) ? "quente" : ""}">${esc(estadoLuz())}${reforco > 1 ? " · reforço " + reforco.toFixed(1) + "×" : ""}</dd>`;
    }
  }
  function calibrar() {
    if (calib || !trilha()) return;
    luzLigada = true; guardar("jv-luz", "1"); luzMudou();
    window.jarvisBrainGestures?.finishFrame([]);
    calib = { fase: "luz", tempo: 0, inicio: performance.now(), ultimo: performance.now(), semMao: 0,
      amostras: [], parada: [], eps: [], aberto: [], fechado: [], punhos: 0, perto: [], quases: 0, atual: null, mao: null };
    $("button[data-a=fechar]").textContent = "Cancelar";
    ui.hidden = false; mostrar();
  }
  function encerrar(msg) {
    calib = null; ui.hidden = true; ui.classList.remove("toque", "punho");
    if (msg) aviso(msg);
  }
  // Called by the timer (time only runs while the hand is seen, except "luz").
  function avancar(agora) {
    const c = calib;
    if (!c || c.fase === "fim") return;
    const dt = Math.min(agora - c.ultimo, 100); c.ultimo = agora;
    const vista = agora - maoEm < 250;
    c.semMao = vista ? 0 : c.semMao + dt;
    if (c.fase === "luz" || vista) c.tempo += dt;
    if (agora - c.inicio > 90000) { encerrar("Não consegui ver a mão por tempo suficiente. Mantive a calibração anterior."); return; }
    const f = FASES[c.fase];
    if (c.fase === "toques" ? c.eps.length >= 5 || c.tempo > f.ms : c.tempo >= f.ms) {
      if (c.fase === "toques" && c.eps.length < 3) { encerrar("Vi poucas pinças. Mantive a calibração anterior."); return; }
      let proxima = { luz: "parada", parada: "toques", toques: "quase", quase: "afasta", afasta: "quase", punho: "abrir", abrir: "punho" }[c.fase];
      if (c.fase === "punho") c.punhos++;
      if (c.fase === "quase") c.quases++;
      if (c.fase === "afasta" && c.quases >= 3) proxima = "punho";
      c.tempo = 0;
      if (c.fase === "abrir" && c.punhos >= 3) { concluir(); return; }
      c.fase = proxima;
    }
    mostrar();
  }
  // Every frame of the chosen hand during calibration.
  function coletar(f) {
    const c = calib, t = f.now;
    if (c.fase === "parada" && c.tempo > 500) c.parada.push({ x: f.x, y: f.y });
    if (c.fase === "punho" && c.tempo > 350) (c.fechado[c.punhos] ||= []).push(f);
    if (c.fase === "quase" && c.tempo > 450) (c.perto[c.quases] ||= []).push(f);
    if (c.fase === "parada" || c.fase === "abrir" || c.fase === "afasta") c.aberto.push(f.ratio);
    if (c.fase !== "toques") return;
    // Segment quick pinches by the thumb-index gap: closed below the midpoint
    // between this hand's open gap and the narrowest gap it reaches.
    const abertoMed = quantil(c.aberto, 0.5) || 0.8;
    const fecha = Math.min(0.45, (abertoMed + 0.15) / 2), abre = fecha + 0.06;
    const e = c.atual;
    if (!e && f.ratio < fecha) c.atual = { ini: t, fr: [f], x0: f.x, y0: f.y, depois: [] };
    else if (e && !e.fim) {
      e.fr.push(f);
      if (f.ratio > abre) e.fim = t;
    } else if (e && e.fim) {
      e.depois.push(f);
      if (e.depois.length >= 6 || t - e.fim > 300) {
        if (e.fr.length >= 2 && e.fim - e.ini < 1500) {
          e.dur = e.fim - e.ini;
          const pos = [...e.fr, ...e.depois.slice(0, 3)];
          e.viagem = Math.max(...pos.map(p => Math.hypot(p.x - e.x0, p.y - e.y0)));
          e.pico = Math.max(...e.depois.map(p => p.ratio));
          c.eps.push(e);
          ui.classList.add("toque"); setTimeout(() => ui.classList.remove("toque"), 160);
        }
        c.atual = null;
      }
    }
  }
  // Would this profile have recognised the pinch? Same rule as stage.html:
  // gap under the ceiling and the OK-sign signature on two frames in a row.
  function reconhece(p, frames) {
    let antes = false;
    for (const f of frames) {
      const ok = (f.backMean - f.f8v > p.contraste && f.backMean > p.arco) || (f.aspect < 2.0 && f.tRel > 0.95);
      const fechado = f.ratio < (f.aspect < 2.0 ? p.pincaPerfil : p.pincaFrontal) &&
        !(p.toque3 > 0 && Number.isFinite(f.ratio3) && f.ratio3 >= p.toque3);
      if (fechado && ok && antes) return true;
      antes = fechado && ok;
    }
    return false;
  }
  function propor(c) {
    const toque = c.eps.flatMap(e => { const m = Math.min(...e.fr.map(f => f.ratio)); return e.fr.filter(f => f.ratio <= m + 0.06); });
    const punho = c.fechado.flat();
    const p = { ...PADRAO };
    const frontal = toque.filter(f => f.aspect >= 2.0).map(f => f.ratio), perfilR = toque.filter(f => f.aspect < 2.0).map(f => f.ratio);
    // Calibration only RELAXES the original: never stricter on the gap or the
    // OK-sign. It tightens only later, if a fist would pass (see concluir).
    if (frontal.length >= 4) p.pincaFrontal = limitar("pincaFrontal", Math.max(PADRAO.pincaFrontal, quantil(frontal, 0.9) * 1.2 + 0.02));
    if (perfilR.length >= 4) p.pincaPerfil = limitar("pincaPerfil", Math.max(PADRAO.pincaPerfil, quantil(perfilR, 0.9) * 1.2 + 0.02));
    const cP = quantil(toque.map(f => f.backMean - f.f8v), 0.1), cK = quantil(punho.map(f => f.backMean - f.f8v), 0.9);
    if (Number.isFinite(cP)) p.contraste = limitar("contraste", Math.min(PADRAO.contraste, Number.isFinite(cK) && cP > cK + 0.02 ? (cP + cK) / 2 : cP - 0.03));
    const bP = quantil(toque.map(f => f.backMean), 0.1), bK = quantil(punho.map(f => f.backMean), 0.9);
    if (Number.isFinite(bP) && Number.isFinite(bK) && bP > bK + 0.02) p.arco = limitar("arco", Math.min(PADRAO.arco, (bP + bK) / 2, bP - 0.02));
    const picos = c.eps.map(e => e.pico).filter(Number.isFinite);
    if (picos.length) p.soltar = limitar("soltar", Math.min(PADRAO.soltar, quantil(picos, 0.2) * 0.8));
    p.soltar = Math.max(p.soltar, Math.max(p.pincaFrontal, p.pincaPerfil) + 0.08);
    if (p.soltar > LIMITES.soltar[1]) { p.pincaFrontal = Math.min(p.pincaFrontal, LIMITES.soltar[1] - 0.08); p.pincaPerfil = Math.min(p.pincaPerfil, LIMITES.soltar[1] - 0.08); p.soltar = LIMITES.soltar[1]; }
    p.soltarRapido = limitar("soltarRapido", p.soltar + 0.15);
    const centro = c.parada.length ? { x: quantil(c.parada.map(q => q.x), 0.5), y: quantil(c.parada.map(q => q.y), 0.5) } : null;
    const tremor = centro ? quantil(c.parada.map(q => Math.hypot(q.x - centro.x, q.y - centro.y)), 0.75) : 0;
    p.tremor = Math.round(limitar("tremor", Math.max(tremor * 2.5, quantil(c.eps.map(e => e.viagem), 0.8) * 1.25) + 4));
    p.toqueMs = Math.round(limitar("toqueMs", quantil(c.eps.map(e => e.dur), 0.8) * 1.3 + 80));
    // Touch, literally: the 3D gap of a real touch vs "almost touching". The
    // line sits closer to the touch, so approaching never counts as a click.
    const t3 = quantil(toque.map(f => f.ratio3).filter(Number.isFinite), 0.9);
    const n3 = quantil(c.perto.flat().map(f => f.ratio3).filter(Number.isFinite), 0.1);
    if (Number.isFinite(t3)) p.toque3 = +clamp(Number.isFinite(n3) && n3 > t3 + 0.02 ? t3 + (n3 - t3) * 0.4 : t3 + 0.01, 0.05, 0.40).toFixed(3);
    return { p, tremor, toque, punho, t3 };
  }
  async function concluir() {
    const c = calib;
    c.fase = "fim";
    let { p, tremor, toque, t3 } = propor(c);
    const pinchas = p2 => c.eps.filter(e => reconhece(p2, e.fr)).length;
    const punhos = p2 => c.fechado.filter(fr => fr && reconhece(p2, fr)).length;
    // A fist must never pass. Tighten the signature until it doesn't, or give up.
    // First narrow the gap down to what this pinch really needs, then the OK-sign.
    const precisa = limitar("pincaFrontal", quantil(toque.filter(f => f.aspect >= 2.0).map(f => f.ratio), 0.95) + 0.02 || LIMITES.pincaFrontal[1]);
    for (let i = 0; i < 12 && punhos(p) > 0; i++) {
      if (p.pincaFrontal - 0.02 >= precisa) p = { ...p, pincaFrontal: +(p.pincaFrontal - 0.02).toFixed(3) };
      else p = { ...p, contraste: limitar("contraste", p.contraste + 0.02), arco: limitar("arco", p.arco + 0.02) };
    }
    // "Almost touching" must not click: pull the 3D line toward the real touch.
    const quases = p2 => c.perto.filter(fr => fr && reconhece(p2, fr)).length;
    for (let i = 0; i < 20 && p.toque3 > 0 && quases(p) > 0 && p.toque3 - 0.005 > t3; i++) p = { ...p, toque3: +(p.toque3 - 0.005).toFixed(3) };
    const antes = pinchas(perfil), antesPadrao = pinchas(PADRAO), depois = pinchas(p), n = c.eps.length;
    const aceito = valido(p) && punhos(p) === 0 && depois >= Math.max(antes, antesPadrao) && depois >= Math.ceil(n * 0.8);
    const res = { toques: n, reconhecidosAntes: antes, reconhecidosPadrao: antesPadrao, reconhecidos: depois,
      punhos: c.fechado.filter(Boolean).length, punhosAceitos: punhos(p),
      quases: c.perto.filter(Boolean).length, quasesAceitos: quases(p), quasesPadrao: quases(PADRAO), tremorPx: Math.round(tremor),
      qps: Math.round(qps), luz: estadoLuz(), em: Date.now() };
    const ok = aceito && await salvar(p, "calibrado", res);
    $(".passo").textContent = "CALIBRAR AS MÃOS · RESULTADO";
    $("h2").textContent = ok ? "Calibração pronta" : "Mantive a calibração anterior";
    $(".texto").textContent = ok
      ? `Reconheci ${depois} de ${n} toques (antes: ${antes}). Nenhum punho virou pinça.` +
        (quases(p) ? ` Quase encostar ainda contou ${quases(p)} de ${res.quases} vezes; repita com mais luz.` : " Quase encostar não conta mais.")
      : depois < Math.ceil(n * 0.8) || punhos(p) > 0
        ? "Não consegui separar bem a sua pinça da mão fechada. Tente com mais luz ou repita."
        : `A calibração atual já reconhece ${antes} de ${n} pinças; não mudei nada.`;
    $(".pontos").innerHTML = ""; $(".barra i").style.width = "100%";
    $(".leitura").innerHTML = `<dt>Encostar (3D)</dt><dd>${perfil.toque3 > 0 ? "abaixo de " + perfil.toque3.toFixed(2) : "desligado"}</dd><dt>Tolerância de movimento</dt><dd>${perfil.tremor} px</dd><dt>Tempo de uma pinça</dt><dd>até ${perfil.toqueMs} ms</dd>` +
      `<dt>Câmera</dt><dd>${esc(modoMedido)} · ${Math.round(qps)} quadros/s</dd><dt>Luz na mão</dt><dd>${esc(estadoLuz())}</dd>`;
    $("button[data-a=fechar]").textContent = "Fechar";
    setTimeout(() => { if (calib?.fase === "fim") encerrar(null); }, 9000);
  }
  async function padrao() {
    try { await api("/maos/perfil", { padrao: true }); } catch (e) {}
    usar(null);
    luzLigada = false; guardar("jv-luz", "0");
    await luzPadrao();
    encerrar("Voltei à calibração e à câmera originais.");
  }

  // ---------- the stage hook --------------------------------------------------
  let escolhida = null, escolhidaEm = 0, pincaEm = 0;
  function amostra(i, f) {
    if (f.pinched) pincaEm = performance.now();   // the person is using the hands right now
    const area = (f.caixa[2] - f.caixa[0]) * (f.caixa[3] - f.caixa[1]);
    // One hand at a time: the closest (largest) one, kept while it is seen.
    if (escolhida === null || escolhida === i || f.now - escolhidaEm > 300 || area > (caixa ? (caixa[2] - caixa[0]) * (caixa[3] - caixa[1]) * 1.6 : 0)) {
      escolhida = i; escolhidaEm = f.now; caixa = f.caixa; maoEm = performance.now();
    }
    // Pinch closed by the gap but refused by the signature, three frames running.
    const teto = f.aspect < 2.0 ? perfil.pincaPerfil : perfil.pincaFrontal;
    const run = f.ratio < teto && !f.pinched ? (assinatura.get(i) || 0) + 1 : 0;
    assinatura.set(i, run);
    if (run === 3) { contagem.assinatura = (contagem.assinatura || 0) + 1; diagMudou = true; }
    if (!calib) return false;
    if (i === escolhida && calib.fase !== "fim") coletar(f);
    return calib.fase !== "fim";
  }

  // ---------- HUD chip ---------------------------------------------------------
  function chip() {
    const h = document.getElementById("hint");
    if (!h || !h.classList.contains("hud")) return;
    let linha = document.getElementById("hud-maos");
    if (!linha) {
      linha = document.createElement("div"); linha.className = "linha"; linha.id = "hud-maos";
      const jv = document.getElementById("hud-jv");
      jv ? h.insertBefore(linha, jv) : h.appendChild(linha);
      linha.addEventListener("click", ev => { const b = ev.target.closest(".btn"); if (b) acionar(b.dataset.acao); });
    }
    if (!trilha()) { linha.innerHTML = ""; return; }
    const luz = estadoLuz(), quente = qps && qps < 45 || ["fraca", "baixa"].includes(luz);
    const rotulo = { padrao: "PADRÃO", calibrado: "CALIBRADA", ajustado: "CALIBRADA" }[origem];
    const dica = `Mãos: calibração ${rotulo.toLowerCase()}\nCâmera ${modoMedido} · ${Math.round(qps)} quadros/s · inferência ${inferencia.toFixed(1)} ms\n` +
      `Luz na mão: ${luz}${reforco > 1 ? " · reforço " + reforco.toFixed(1) + "×" : ""}${hw?.c && luzLigada ? " · ajuste da câmera ligado" : ""}\n\nPince para calibrar · K calibra · Shift+K volta ao padrão`;
    const html = `<span class="jv maos btn${quente ? " quente" : ""}" data-acao="calibrar" title="${esc(dica)}">✋ MÃOS · ${Math.round(qps) || "—"} QPS · LUZ ${esc(luz.toUpperCase())} · ${rotulo}</span>` +
      `<span class="jv brilho btn${brilho ? " ligado" : ""}" data-acao="brilho" title="Brilho da câmera: pince para trocar (B)">☀ BRILHO ${BRILHOS[brilho].nome}</span>` +
      (window.jarvisTema ? `<span class="jv tema btn" data-acao="tema" title="Cores do JARVIS: pince para trocar (T)">◐ ${esc(window.jarvisTema.rotulo)}</span>` : "");
    if (linha.innerHTML !== html) linha.innerHTML = html;
  }

  // ---------- loops ----------------------------------------------------------------
  let ultimoPedido = 0;
  async function pedidos() {
    try {
      const p = await api("/jarvis/maos-pedido");
      if (p.pedido && p.pedido > ultimoPedido) {
        const novo = ultimoPedido !== 0 || Date.now() / 1000 - p.pedido < 10;
        ultimoPedido = p.pedido;
        if (!novo) return;
        const a = String(p.acao || "calibrar");
        if (a === "padrao") padrao();
        else if (a === "brilho:+") mudarBrilho(Math.max(1, brilho + 1));
        else if (a === "brilho:-") mudarBrilho(brilho - 1);
        else if (a === "brilho:liga") mudarBrilho(brilho || 2);
        else if (a === "brilho:desliga") mudarBrilho(0);
        else if (a.startsWith("tema:")) window.jarvisTema?.usar(a.slice(5));
        else if (a === "config") window.jarvisConfig?.abrir();
        else calibrar();
      }
    } catch (e) {}
  }
  let tLuz = 0;
  function tique() {
    const agora = performance.now();
    avancar(agora);
    if (agora - tLuz > 300) {
      tLuz = agora; medir();
      if (hw === null) prepararHw();
      if (hw === false && modoLuz !== "fixo") { modoLuz = "fixo"; lumaSuave = luma; decidirReforco(); }
      passoHw(agora);
    }
  }
  window.jarvisMaos = {
    get p() { return perfil; }, get calibrado() { return origem !== "padrao"; }, get origem() { return origem; },
    get calibrando() { return !!calib && calib.fase !== "fim"; },
    // A pinch in the last 1.5 s: the JARVIS waits instead of moving the screen under it.
    get emUso() { return performance.now() - pincaEm < 1500 || !!window.jarvisBrainGestures?.holding?.(0) || !!window.jarvisBrainGestures?.holding?.(1); },
    PADRAO, amostra, entrada, registrar, calibrar, padrao, valido, acionar, mudarBrilho,
    get brilho() { return BRILHOS[brilho].nome; }, get nivelBrilho() { return brilho; },
    estado: () => ({ fase: calib?.fase || null, modoLuz, qps, luma, lumaMao, luz: estadoLuz(), reforco, modo: modoMedido, inferencia, origem, perfil, contagem }),
  };
  carregar(); aplicarFiltro();
  setInterval(tique, 100);
  setInterval(() => { conferirCamera(); chip(); }, 1000);
  setInterval(pedidos, 1500);
})();
