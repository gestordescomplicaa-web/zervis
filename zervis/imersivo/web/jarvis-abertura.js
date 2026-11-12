// SPDX-License-Identifier: AGPL-3.0-or-later
// The opening (ADR 0078): opening the Zérvis program lands here with ?abertura=1. The music
// plays, the name lights up, and the Zé presents the day: one holographic panel per block of the
// panorama he writes (GET /abertura), grouped by his menu: now (the hour and the weather), today
// (agenda, automations and the Focus), social networks (WhatsApp and Instagram), activity (what he
// did, what is running) and what is pending, plus the headlines on a strip. Each scene comes in
// large at the centre while he speaks of it in his own voice (POST /abertura/falar asks for that
// block's line; the text is always the one the Zé wrote), then docks into the mosaic.
// The music ducks while he speaks. Esc skips it.
// Also: the Zé's "apresentar dia" action (jarvis-controle.js), without the music.
(() => {
  const busca = new URLSearchParams(location.search);
  if (busca.get("role") === "render") return;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  let ritmo = 1;  // the browser tests run it faster (jarvisAbertura.ritmo)
  const espera = ms => new Promise(r => setTimeout(r, ms * ritmo));
  const P = () => window.jarvisApresentacao.palco;
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)");
  let musica = null, rodada = 0, rodando = false, relogio = 0, feitos = 0;
  const falados = [];  // the steps whose line was asked for (the tests read it)

  // ---- the music: the file of whoever uses the Zé, or a short synthesized swell ----
  // Web Audio, not an <audio>: a media element shows up as a player (MPRIS), and the Zé pauses
  // every player while he speaks ("pausar mídia"), so the music stalled under his voice.
  let ac = null, ganho = null;
  async function tocar() {
    try {
      const r = await fetch("/abertura/musica", { cache: "no-store" });
      if (r.ok) {
        ac ||= new AudioContext();
        if (ac.state !== "running") await ac.resume();
        const sinal = await ac.decodeAudioData(await r.arrayBuffer());
        ganho = ac.createGain(); ganho.gain.value = .9; ganho.connect(ac.destination);
        const fonte = ac.createBufferSource(); fonte.buffer = sinal; fonte.connect(ganho); fonte.start();
        musica = fonte;
        return "arquivo";
      }
    } catch (_) { musica = null; }
    const tom = P().tom;
    [110, 165, 220, 330].forEach((f, i) => tom(f, 2.6, .03, "sine", f * 2, i * .4));
    tom(880, .9, .025, "triangle", 1760, 1.8);
    return "sintetizada";
  }
  function volume(alvo, ms = 500) {
    if (!musica || !ganho || !ac) return;
    const g = ganho.gain, agora = ac.currentTime;
    g.cancelScheduledValues(agora); g.setValueAtTime(g.value, agora); g.linearRampToValueAtTime(alvo, agora + ms / 1000);
    if (alvo === 0) { const m = musica; setTimeout(() => { try { m.stop(); } catch (_) { /* already over */ } }, ms + 50); }
  }
  function calar() {
    try { musica?.stop(); } catch (_) { /* already over */ }
    musica = null;
  }

  // ---- the opening tells the Zé it began (-1) or was skipped (-2): no step, no line ----
  let montado = "";
  function sinal(passo) {
    if (!montado) return;
    fetch("/abertura/falar", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ montado, passo }) }).catch(() => {});
  }

  // ---- the Zé's voice: ask for the line, then follow /orb while he speaks ----
  async function estado() {
    try { const r = await fetch("/orb", { cache: "no-store" }); return r.ok ? (await r.json()).state : ""; } catch (_) { return ""; }
  }
  // One subject at a time: the line is asked for first; its panel comes with the
  // voice (or after a short head start, if it is slow), and the next one waits for the end.
  async function falar(montado, passo, texto, id, mostrar) {
    falados.push(passo);
    try {
      await fetch("/abertura/falar", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ montado, passo }) });
    } catch (_) { /* no voice: the panel still shows */ }
    let comecou = false, mostrado = false;
    for (const t0 = performance.now(); id === rodada && performance.now() - t0 < 12000 * ritmo;) {
      if (await estado() === "speaking") { comecou = true; break; }
      if (!mostrado && performance.now() - t0 > 2500 * ritmo) { mostrado = true; mostrar(); }
      await espera(150);
    }
    if (!mostrado) mostrar();
    if (!comecou) { await espera(Math.max(3000, texto.length * 70)); return; }
    volume(.18);
    // Done after 600 ms in a row without speaking: the voice pauses between sentences.
    for (let calado = 0, t0 = performance.now(); id === rodada && calado < 4 && performance.now() - t0 < 60000;) {
      calado = await estado() === "speaking" ? 0 : calado + 1;
      await espera(150);
    }
    volume(.45);
    await espera(400);
  }

  // ---- the opening title, over the music; the day's scenes light up when the Zé has them ----
  const NOMES = { agora: "AGORA", hoje: "HOJE", redes: "REDES SOCIAIS", atividade: "ATIVIDADE", pendencias: "PENDÊNCIAS", noticias: "BRASIL" };
  function vinheta(dia) {
    const v = document.createElement("div");
    v.id = "jv-abertura-vinheta"; v.setAttribute("aria-hidden", "true");
    const oi = (dia.blocos || [])[0] || {};
    v.innerHTML = `<div class="anel"></div><h1>ZÉRVIS</h1><p>${esc(oi.data || new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" }))}</p><div class="cenas"></div>`;
    document.body.appendChild(v);
    return v;
  }
  function anunciar(v, dia) {
    const nomes = (dia.blocos || []).map(b => NOMES[b.tipo]).filter(Boolean);
    v.querySelector(".cenas").innerHTML = nomes.map((n, i) => `<span style="animation-delay:${i * .13}s">${esc(n)}</span>`).join("");
    return nomes.length;
  }

  // ---- the mosaic: each scene has its place, in one or two rows to the right of the Zé ----
  // The panels are drawn for a 1600x900 screen and scaled as a whole (the board's own scale),
  // so they look the same on any screen.
  const AREA = { x0: .215, x1: .988, y0: .045, y1: .88 }, FAIXA = .056, VAO = { x: .012, y: .02 };
  const PESO = { agora: 1.3, hoje: 1, redes: 1, atividade: 1.3, pendencias: 2 };
  const escala = () => Math.min(innerWidth / 1600, innerHeight / 900);
  function mosaico(tipos, comFaixa) {
    const n = tipos.length, corte = n <= 3 ? n : Math.ceil(n / 2), linhas = [tipos.slice(0, corte), tipos.slice(corte)].filter(l => l.length);
    const fundo = AREA.y1 - (comFaixa ? FAIXA + VAO.y : 0), alto = fundo - AREA.y0, largo = AREA.x1 - AREA.x0, lugares = {};
    const alturas = linhas.length === 2 ? [(alto - VAO.y) * .61, (alto - VAO.y) * .39] : [Math.min(alto, .5)];
    let y = AREA.y0 + (linhas.length === 1 ? (alto - alturas[0]) * .3 : 0);
    linhas.forEach((linha, l) => {
      const pesos = linha.map(t => PESO[t] || 1), soma = pesos.reduce((a, b) => a + b, 0), util = largo - VAO.x * (linha.length - 1);
      let x = AREA.x0;
      linha.forEach((t, i) => { const w = util * pesos[i] / soma; lugares[t] = { x, y, w, h: alturas[l] }; x += w + VAO.x; });
      y += alturas[l] + VAO.y;
    });
    if (comFaixa) lugares.noticias = { x: AREA.x0, y: AREA.y1 - FAIXA, w: largo, h: FAIXA };
    return lugares;
  }
  // A scene comes in large, at the centre, while the Zé speaks of it; then it docks.
  const centro = onde => {
    const k = escala(), largo = (AREA.x1 - AREA.x0) * innerWidth, alto = (AREA.y1 - AREA.y0) * innerHeight;
    const w = onde.w * innerWidth, h = onde.h * innerHeight;
    return { x: (AREA.x0 + AREA.x1) / 2 * innerWidth, y: (AREA.y0 + AREA.y1) / 2 * innerHeight, s: k * Math.min(1.5, largo * .94 / w, alto * .94 / h), ry: 0 };
  };
  const encaixe = onde => ({ x: (onde.x + onde.w / 2) * innerWidth, y: (onde.y + onde.h / 2) * innerHeight, s: escala(), ry: 0 });
  const movimentos = new Map();  // the board item -> {de, para, t0, ms}
  function mover(it, para, ms = 720) {
    if (reduzir.matches || ms <= 0) { Object.assign(it, { x: para.x, y: para.y, scale: para.s, ry: para.ry }); movimentos.delete(it); return; }
    movimentos.set(it, { de: { x: it.x, y: it.y, s: it.scale, ry: it.ry || 0 }, para, t0: performance.now(), ms: ms * ritmo });
  }
  (function quadro() {
    requestAnimationFrame(quadro);
    for (const [it, m] of movimentos) {
      // a hand that grabs it takes over; an item leaving the board is no longer ours
      if (it.grabbedBy.length || !it.el.isConnected || it.anim?.k === "out") { movimentos.delete(it); continue; }
      const k = Math.min(1, (performance.now() - m.t0) / m.ms), e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      it.vx = it.vy = 0;
      it.x = m.de.x + (m.para.x - m.de.x) * e; it.y = m.de.y + (m.para.y - m.de.y) * e;
      it.scale = m.de.s + (m.para.s - m.de.s) * e; it.ry = m.de.ry + (m.para.ry - m.de.ry) * e;
      if (k >= 1) movimentos.delete(it);
    }
  })();

  // ---- the charts ----
  const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
  const lista = itens => `<ul class="jv-ab-lista">${itens.join("")}</ul>`;
  const minutos = hhmm => { const [h, m] = String(hhmm).split(":").map(Number); return h * 60 + (m || 0); };
  // The sky, in line art (the theme's colour), moving a little.
  const NUVEM = '<path class="nuvem" d="M15 36a8 8 0 0 1 .6-16 11.5 11.5 0 0 1 22-2.4A9.2 9.2 0 0 1 36 36z"/>';
  const ALTA = `<g transform="translate(0 -8)">${NUVEM}</g>`;
  const CEUS = {
    sol: '<g class="raios"><path d="M24 5v6M24 37v6M5 24h6M37 24h6M10.6 10.6l4.2 4.2M33.2 33.2l4.2 4.2M10.6 37.4l4.2-4.2M33.2 14.8l4.2-4.2"/></g><circle cx="24" cy="24" r="8"/>',
    lua: '<path d="M33 30.5A14 14 0 0 1 18.2 10 14.5 14.5 0 1 0 33 30.5z"/><path class="pisca" d="M36 10v4M34 12h4"/>',
    nuvens: '<g class="raios pequeno"><path d="M33 4v4M44 15h-4M40.8 7.2l-2.8 2.8"/></g><circle cx="33" cy="15" r="6"/>' + NUVEM,
    nublado: '<path class="nuvem longe" d="M22 22a6 6 0 0 1 .5-12 8.6 8.6 0 0 1 16.4-1.8A6.9 6.9 0 0 1 38 22z"/>' + NUVEM,
    neblina: '<path class="nevoa" d="M8 16h32M12 24h28M8 32h26M14 40h24"/>',
    chuva: ALTA + '<path class="gotas" d="M17 33l-2 6M25 33l-2 6M33 33l-2 6"/>',
    neve: ALTA + '<path class="gotas neve" d="M17 34v.1M25 38v.1M33 34v.1M21 42v.1M29 42v.1"/>',
    trovoada: ALTA + '<path class="raio" d="M26 30l-5 8h5l-2 7"/>',
  };
  const ceu = icone => `<svg class="jv-ab-ceu" viewBox="0 0 48 48" aria-hidden="true">${CEUS[icone] || CEUS.nublado}</svg>`;
  // A smooth line through the points (Catmull-Rom as Béziers).
  function suave(pts) {
    let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
      d += ` C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)},${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)},${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
    }
    return d;
  }
  // The day's temperature as an area, the chance of rain as bars under it, and a mark on now.
  function tempo(c) {
    const horas = c.horas || [], chuva = c.chuva_horas || [];
    if (horas.length < 2) return "";
    const min = Math.min(...horas), max = Math.max(...horas), x = i => i / (horas.length - 1) * 240;
    const y = t => 62 - (t - min) / Math.max(1, max - min) * 50, pts = horas.map((t, i) => [x(i), y(t)]);
    const linha = suave(pts), agora = Math.min(horas.length - 1, new Date().getHours()), passo = 240 / horas.length;
    const barras = chuva.map((p, i) => p > 0 ? `<rect x="${(i * passo + 1).toFixed(1)}" y="${(80 - p / 100 * 26).toFixed(1)}" width="${(passo - 2).toFixed(1)}" height="${(p / 100 * 26).toFixed(1)}"/>` : "").join("");
    const iMax = horas.indexOf(max);
    return `<div class="jv-ab-tempo"><div class="traco"><svg viewBox="0 0 240 80" preserveAspectRatio="none">
      <defs><linearGradient id="jv-ab-g-tempo" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--jv-acento, #8ff0e4)" stop-opacity=".42"/><stop offset="1" stop-color="var(--jv-acento, #8ff0e4)" stop-opacity="0"/></linearGradient></defs>
      <g class="chuva">${barras}</g><path class="area" d="${linha} L240,80 L0,80 Z"/><path class="linha" d="${linha}"/></svg>
      <i class="agora" style="left:${(x(agora) / 240 * 100).toFixed(1)}%"><b style="top:${(y(horas[agora]) / 80 * 100).toFixed(1)}%"></b></i>
      <em style="left:${(x(iMax) / 240 * 100).toFixed(1)}%;top:${(y(max) / 80 * 100).toFixed(1)}%">${esc(max)}°</em></div>
      <div class="eixo"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div></div>`;
  }
  // The day as a 24-hour dial: what is past, each item at its hour, and a hand on now.
  function mostrador(itens) {
    const agora = new Date(), feito = (agora.getHours() * 60 + agora.getMinutes()) / 1440, C = 2 * Math.PI * 44;
    const em = (f, r) => { const a = f * 2 * Math.PI - Math.PI / 2; return [60 + Math.cos(a) * r, 60 + Math.sin(a) * r]; };
    const marcas = (itens || []).map((i, n) => {
      const f = minutos(i.hora) / 1440, [mx, my] = em(f, 44), passou = f < feito ? " passou" : "";
      return i.tipo === "automacao"
        ? `<circle class="marca auto${passou}" style="animation-delay:${.5 + n * .12}s" cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="3.2"/>`
        : `<rect class="marca${passou}" style="animation-delay:${.5 + n * .12}s" x="${(mx - 3.4).toFixed(1)}" y="${(my - 3.4).toFixed(1)}" width="6.8" height="6.8" transform="rotate(45 ${mx.toFixed(1)} ${my.toFixed(1)})"/>`;
    }).join("");
    const horas = [0, 6, 12, 18].map(h => { const [tx, ty] = em(h / 24, 31); return `<text x="${tx.toFixed(1)}" y="${(ty + 2.6).toFixed(1)}">${h}</text>`; }).join("");
    const [px, py] = em(feito, 52), [qx, qy] = em(feito, 36);
    return `<svg class="jv-ab-mostrador" viewBox="0 0 120 120" aria-hidden="true">
      <circle class="horas" cx="60" cy="60" r="53" pathLength="240" stroke-dasharray="1 9"/>
      <circle class="quartos" cx="60" cy="60" r="53" pathLength="240" stroke-dasharray="2 58" stroke-dashoffset="1"/>
      <circle class="trilho" cx="60" cy="60" r="44"/>
      <circle class="feito" cx="60" cy="60" r="44" transform="rotate(-90 60 60)" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${C.toFixed(1)}" data-ate="${(C * (1 - feito)).toFixed(1)}"/>
      <g class="varre"><path d="M60 60 L60 16 A44 44 0 0 1 91.1 28.9 Z"/></g>
      ${horas}${marcas}<line class="ponteiro" x1="${qx.toFixed(1)}" y1="${qy.toFixed(1)}" x2="${px.toFixed(1)}" y2="${py.toFixed(1)}"/>
      <circle class="ponta" cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="2.6"/></svg>`;
  }
  // How long until an hour of today ("em 2 h 10"), or "" when it is past.
  function falta(hhmm) {
    const agora = new Date(), m = minutos(hhmm) - agora.getHours() * 60 - agora.getMinutes();
    return m < 0 ? "" : m < 1 ? "agora" : m < 60 ? `em ${m} min` : `em ${Math.floor(m / 60)} h${m % 60 ? " " + String(m % 60).padStart(2, "0") : ""}`;
  }
  // The pending items by section of the menu, as a ring in segments.
  function anelDeAreas(areas, total) {
    const C = 2 * Math.PI * 46, vao = areas.length > 1 ? 5 : 0;
    let ini = 0;
    const arcos = areas.map((a, i) => {
      const comp = Math.max(2, a.n / Math.max(1, total) * C - vao), arco = `<circle class="arco a${i % 5}" cx="60" cy="60" r="46" transform="rotate(${(-90 + ini / C * 360).toFixed(1)} 60 60)"
        stroke-dasharray="${comp.toFixed(1)} ${C.toFixed(1)}" stroke-dashoffset="${comp.toFixed(1)}" style="transition-delay:${.25 + i * .14}s"/>`;
      ini += a.n / Math.max(1, total) * C;
      return arco;
    }).join("");
    return `<div class="jv-ab-anel"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="trilho" cx="60" cy="60" r="46"/>
      <circle class="giro" cx="60" cy="60" r="54" pathLength="100" stroke-dasharray="14 86"/>${arcos}</svg>
      <div><b data-n="${Number(total) || 0}">0</b><span>${total === 1 ? "ITEM" : "ITENS"}</span></div></div>`;
  }
  const NIVEL = { critico: ["critico", "✕"], alerta: ["alerta", "!"], info: ["bom", "●"] };
  // After a panel is on the board: the numbers count up and the drawn charts start.
  const animar = (reg, fazer) => setTimeout(() => {
    if (!reg.el.isConnected) return;
    reg.el.querySelectorAll("[data-n]").forEach((b, i) => setTimeout(() => P().contar(b, +b.dataset.n, 1100), i * 140));
    reg.el.querySelectorAll("[data-ate]").forEach(c => { c.style.strokeDashoffset = c.dataset.ate; });
    reg.el.querySelectorAll(".jv-ab-anel .arco").forEach(c => { c.style.strokeDashoffset = "0"; });
    reg.el.querySelectorAll("[data-w]").forEach((b, i) => setTimeout(() => { b.style.width = b.dataset.w + "%"; }, i * 110));
    fazer?.(reg);
  }, 420);

  // ---- the scenes: one panel for each, by the Zé's menu ----
  const PAINEIS = {
    // the hour with its seconds, the greeting, and the weather with the day's curve
    agora: b => {
      const c = b.clima;
      return { nome: "AGORA", titulo: "Agora", fonte: c ? "OPEN-METEO" : "AO VIVO", classe: c ? "" : "sem-clima", corpo: `<div class="jv-ab-relogio">
        <div><b class="jv-ab-hora" data-relogio>--:--</b><p class="jv-ab-data">${esc(b.data)}</p><p class="jv-ab-oi">${esc(b.saudacao)}</p></div>
        <svg class="jv-ab-segundos" viewBox="0 0 100 100" aria-hidden="true"><circle class="marcas" cx="50" cy="50" r="44" pathLength="240" stroke-dasharray="1 3"/>
          <circle class="trilho" cx="50" cy="50" r="36"/><circle class="volta" cx="50" cy="50" r="36" pathLength="60" stroke-dasharray="60" stroke-dashoffset="60" transform="rotate(-90 50 50)" data-segundos/>
          <text x="50" y="57" data-segundo>00</text></svg></div>`
        + (c ? `<div class="jv-ab-clima">${ceu(c.icone)}<b>${esc(c.temperatura)}°</b><p><span>${esc(c.ceu || "—")}</span><small>${esc(c.cidade)}</small></p>
        <dl><dt>MÁX</dt><dd>${esc(c.maxima)}°</dd><dt>MÍN</dt><dd>${esc(c.minima)}°</dd><dt>CHUVA</dt><dd>${esc(c.chuva)}%</dd></dl></div>` + tempo(c) : ""),
        depois: reg => animar(reg) };
    },
    // the agenda and today's automations on the day's dial, and the Focus
    hoje: b => {
      const itens = b.itens || [], f = b.foco, proximo = itens.find(i => falta(i.hora));
      const frentes = f ? [["Ativas", f.ativas, ""], ["Travadas", f.travadas, "alerta"], ["Pausadas", f.pausadas, "pausa"], ["Feitas na semana", f.feitas_semana, "bom"]].filter(([, v]) => v > 0) : [];
      const soma = frentes.reduce((a, [, v]) => a + v, 0);
      return { nome: "HOJE", titulo: "Hoje", corpo: `<div class="jv-ab-dia">${mostrador(itens)}<div class="jv-ab-proximo">${proximo
        ? `<span>PRÓXIMO</span><b>${esc(proximo.hora)}</b><p>${esc(proximo.titulo)}</p><small>${esc(falta(proximo.hora))}</small>`
        : `<span>AGENDA</span><p>${itens.length ? "Concluída" : "Livre"}</p>`}</div></div>`
        + (itens.length ? lista(itens.slice(0, f ? 2 : 5).map((i, n) => `<li style="animation-delay:${.4 + n * .12}s"><time>${esc(i.hora)}</time>
          <span class="jv-st ${i.tipo === "automacao" ? "" : "bom"}" data-ico="${i.tipo === "automacao" ? "⟳" : "◆"}"></span><span class="txt">${esc(i.titulo)}</span>${i.chuva ? '<span class="jv-ab-chuva" title="Chuva prevista">CHUVA</span>' : ""}</li>`))
          + (b.total > Math.min(itens.length, f ? 2 : 5) ? `<p class="jv-ab-mais">+${b.total - Math.min(itens.length, f ? 2 : 5)}</p>` : "") : "")
        + (f ? `<div class="jv-ab-foco"><span class="jv-h-legenda">FOCO</span><p class="jv-ab-frente">${esc(f.atual || "Nenhuma frente ativa")}</p>
          ${f.proximo_passo ? `<p class="jv-ab-passo"><span>PRÓXIMO PASSO</span>${esc(f.proximo_passo)}</p>` : ""}
          ${soma ? `<div class="jv-ab-frentes">${frentes.map(([nome, v, cls]) => `<i class="${cls}" style="flex-grow:${v}" title="${esc(nome)}"></i>`).join("")}</div>
          <div class="jv-ab-legenda">${frentes.map(([nome, v, cls]) => `<span class="${cls}"><b>${esc(v)}</b>${esc(nome)}</span>`).join("")}</div>` : ""}</div>` : ""),
        depois: reg => animar(reg) };
    },
    // the menu's "Redes sociais": WhatsApp waiting for an answer and the Instagram numbers
    redes: b => {
      const w = b.whatsapp, ig = b.instagram, maior = Math.max(60, ...(w ? w.itens.map(i => i.min || 0) : [0]));
      return { nome: "REDES SOCIAIS", titulo: "Redes sociais", fonte: ig ? "META" : "AO VIVO", corpo:
        (w ? `<section class="jv-ab-whats"><span class="jv-h-legenda">WHATSAPP · SEM RESPOSTA</span><div class="linha"><b class="num" data-n="${Number(w.total) || 0}">0</b>
          <ul>${w.itens.slice(0, ig ? 3 : 5).map((i, n) => `<li style="animation-delay:${.4 + n * .12}s"><span class="txt">${esc(i.nome)}</span><time>${esc(i.ha)}</time>
          <span class="trilho"><i data-w="${(Math.max(.06, (i.min || 0) / maior) * 100).toFixed(1)}"></i></span></li>`).join("")}</ul></div></section>` : "")
        + (ig ? `<section class="jv-ab-insta"><span class="jv-h-legenda">INSTAGRAM · @${esc(ig.usuario)}</span><div class="jv-herois">
          <div class="jv-heroi"><span>SEGUIDORES</span><b>${esc(compacto.format(ig.seguidores || 0))}</b></div>
          <div class="jv-heroi"><span>NA SEMANA</span><b>${esc(ig.semana || 0)}</b><small>${ig.semana === 1 ? "publicação" : "publicações"}</small></div>
          ${ig.destaque ? `<div class="jv-heroi"><span>DESTAQUE</span><b>${esc(ig.destaque.valor)}</b><small>visualizações</small></div>` : ""}</div>
          ${(ig.grafico || []).length ? '<div class="jv-grafico"></div>' : ""}</section>` : ""),
        depois: reg => animar(reg, () => { const g = reg.el.querySelector(".jv-grafico");
          if (g && (ig?.grafico || []).length) P().colunas(g, ig.grafico.map(d => ({ ...d, dica: `${esc(d.rotulo)}<small>${esc(compacto.format(d.valor))} VISUALIZAÇÕES</small>` }))); }) };
    },
    // the menu's "Atividade": what the Zé did, day by day, and what is running now
    atividade: b => {
      const dias = (b.por_dia || []).map(x => { const dia = new Date(x.dia + "T12:00:00");
        return { rotulo: dia.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", ""), valor: x.registros,
          dica: `${esc(dia.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "short" }))}<small>${esc(x.registros)} REGISTROS · ${esc(x.falhas)} FALHAS</small>` }; });
      const rodando = [...(b.sessoes || []).map(n => `<span class="viva">${esc(n)}</span>`),
        ...(b.automacoes ? [`<span>${esc(b.automacoes)} ${b.automacoes === 1 ? "automação hoje" : "automações hoje"}</span>`] : [])];
      return { nome: `ATIVIDADE · ${esc(b.dias || 7)} DIAS`, titulo: "Atividade", corpo: `<div class="jv-herois">
        <div class="jv-heroi"><span>PEDIDOS</span><b data-n="${Number(b.pedidos) || 0}">0</b></div>
        <div class="jv-heroi"><span>AÇÕES</span><b data-n="${Number(b.acoes) || 0}">0</b></div>
        <div class="jv-heroi"><span>FALHAS</span><b data-n="${Number(b.falhas) || 0}">0</b></div></div>
        ${dias.length ? '<div class="jv-grafico"></div>' : ""}${rodando.length ? `<div class="jv-ab-rodando">${rodando.join("")}</div>` : ""}`,
        depois: reg => animar(reg, () => { const g = reg.el.querySelector(".jv-grafico"); if (g) P().colunas(g, dias); }) };
    },
    // what waits for whoever uses the Zé, each item with the section of the menu that solves it
    pendencias: b => ({ nome: "PENDÊNCIAS", titulo: "Pendências", corpo: `<div class="jv-ab-pendencias">${anelDeAreas(b.areas || [], b.total || 0)}
      <ul>${(b.itens || []).map((i, n) => { const [cls, ico] = NIVEL[i.nivel] || NIVEL.info;
        return `<li style="animation-delay:${.45 + n * .13}s"><span class="jv-st ${cls}" data-ico="${ico}"></span><small>${esc(String(i.area).toUpperCase())}</small>
          <span class="txt">${esc(i.titulo)}</span><em>${esc(i.detalhe)}</em></li>`; }).join("")}
      ${b.total > (b.itens || []).length ? `<li class="jv-ab-mais">+${b.total - b.itens.length}</li>` : ""}</ul></div>`,
      depois: reg => animar(reg) }),
    // the headlines pass on a strip under the mosaic
    noticias: b => { const fita = (b.itens || []).map(i => `<span>${esc(i.titulo)}<small>${esc(i.fonte)}</small></span>`).join("");
      return { nome: "BRASIL", titulo: "Manchetes", fonte: "RSS", classe: "jv-ab-faixa", corpo: `<b>BRASIL</b><div class="jv-ab-fita"><div style="animation-duration:${Math.max(30, fita.length / 9)}s">${fita}${fita}</div></div>` }; },
  };
  function marcarHora() {
    const d = new Date(), agora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }), s = d.getSeconds();
    document.querySelectorAll("[data-relogio]").forEach(el => { el.textContent = agora; });
    document.querySelectorAll("[data-segundos]").forEach(el => { el.style.transition = s ? "" : "none"; el.style.strokeDashoffset = String(60 - s); });
    document.querySelectorAll("[data-segundo]").forEach(el => { el.textContent = String(s).padStart(2, "0"); });
  }

  function passos(dia, id) {
    const blocos = Array.isArray(dia.blocos) ? dia.blocos : [];
    const cenas = blocos.filter(b => PAINEIS[b.tipo] && b.tipo !== "noticias").map(b => b.tipo);
    const lugares = mosaico(cenas, blocos.some(b => b.tipo === "noticias"));
    let i = 0;
    return blocos.map((b, passo) => {
      const fazer = PAINEIS[b.tipo], fala = String(b.fala || "");
      const id_ = "abertura-" + b.tipo, ordem = fazer ? ++i : 0, onde = lugares[b.tipo], faixa = b.tipo === "noticias";
      let reg = null;
      const mostrar = () => {
        if (id !== rodada || !fazer || reg) return;
        const { nome, depois, classe = "", ...painel } = fazer(b), k = escala();
        reg = P().painel(id_, { ...onde, w: onde.w / k, h: onde.h / k, fonte: "AO VIVO", ...painel, cod: `${String(ordem).padStart(2, "0")} · ${nome}`, classe: `jv-ab jv-ab-${b.tipo} ${classe}` });
        // the strip is born in its place; a scene, large at the centre, until its line is over
        const pose = faixa ? encaixe(onde) : centro(onde);
        Object.assign(reg.it, { x: pose.x, y: pose.y, scale: pose.s });
        reg.el.classList.toggle("heroi", !faixa);
        depois?.(reg); P().focar(id_); marcarHora();
      };
      const encaixar = () => {
        if (!reg || faixa || !reg.el.isConnected) return;
        reg.el.classList.remove("heroi"); reg.el.classList.add("encaixado");
        mover(reg.it, encaixe(onde)); P().tom(660, .16, .018, "sine", 990); P().tom(180, .35, .02, "triangle", 90, .05);
      };
      // The script runner only waits: the panel comes with the voice, and docks when it is over.
      return { fala: "", aguardar: async () => {
        await (dia.montado ? falar(dia.montado, passo, fala, id, mostrar) : (mostrar(), espera(Math.max(3000, fala.length * 70))));
        if (id === rodada && reg && !faixa) { encaixar(); await espera(560); }
        if (id === rodada) feitos++;
      } };
    });
  }

  async function panorama() {
    for (let n = 0; n < 30; n++) {
      try {
        const r = await fetch("/abertura", { cache: "no-store" });
        const d = r.ok ? await r.json() : {};
        if (Array.isArray(d.blocos) && d.blocos.length) return d;
      } catch (_) { /* the Zé is still starting */ }
      await espera(200);
    }
    // Without the Zé: the clock and the greeting from this machine, no voice.
    const agora = new Date(), h = agora.getHours();
    return { blocos: [{ tipo: "agora", clima: null, saudacao: h >= 5 && h < 12 ? "Bom dia" : h >= 12 && h < 18 ? "Boa tarde" : "Boa noite",
      data: agora.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" }), fala: "" }] };
  }

  // Opening the program starts the Zé: his first panorama comes before the weather, the
  // Instagram and the headlines (completo: false). The name stays up over the music until the
  // full one arrives, or a while passes (no network: the day goes without them).
  async function completar(dia, id) {
    for (const t0 = performance.now(); dia.completo === false && id === rodada && performance.now() - t0 < 12000 * ritmo;) {
      await espera(300);
      try {
        const r = await fetch("/abertura", { cache: "no-store" });
        const d = r.ok ? await r.json() : {};
        if (Array.isArray(d.blocos) && d.blocos.length) dia = d;
      } catch (_) { /* keep the one in hand */ }
    }
    return dia;
  }

  async function iniciar({ musica: comMusica = true, automatica = false } = {}) {
    for (let n = 0; n < 100 && !(window.jarvisStage && window.jarvisApresentacao); n++) await new Promise(r => setTimeout(r, 100));
    if (!window.jarvisApresentacao) return { abertura: false, erro: "apresentação indisponível" };
    encerrar();
    const id = ++rodada; rodando = true; falados.length = 0; feitos = 0;
    let dia = await panorama();
    if (id !== rodada) return { abertura: false };
    if (automatica && dia.ligada === false) { rodando = false; return { abertura: false, desligada: true }; }
    montado = dia.montado || "";
    sinal(-1);  // the Zé holds his notices until the opening is over
    const som = comMusica ? await tocar() : "sem";
    const v = vinheta(dia);
    // the name stays up while the full day comes; then its scenes light up under it
    const [, completo] = await Promise.all([espera(1700), completar(dia, id)]);
    if (id !== rodada) return { abertura: false };  // skipped: encerrar() took the title away
    dia = completo; montado = dia.montado || montado;
    await espera(500 + anunciar(v, dia) * 130);
    if (id !== rodada) return { abertura: false };
    v.classList.add("saindo"); setTimeout(() => v.remove(), 900 * ritmo);
    clearInterval(relogio); marcarHora(); relogio = setInterval(marcarHora, 1000);
    P().comecar();
    const pronto = P().roteiro(P().rodada, passos(dia, id));
    (async () => {  // when the script is over: the music fades and the opening is done
      while (id === rodada && window.jarvisApresentacao.apresentando && feitos < (dia.blocos || []).length) await espera(300);
      await espera(1500);
      if (id === rodada) { volume(0, 2500); rodando = false; }
    })();
    return { abertura: true, musica: som, blocos: (dia.blocos || []).map(b => b.tipo), ...pronto };
  }

  function encerrar() {
    if (rodando) sinal(-2);  // skipped: the notices may come now
    rodada++; clearInterval(relogio);
    calar();
    document.getElementById("jv-abertura-vinheta")?.remove();
    if (rodando && window.jarvisApresentacao?.apresentando) window.jarvisApresentacao.encerrar();
    rodando = false;
    return { abertura: false };
  }

  addEventListener("keydown", e => {
    if (e.key === "Escape" && rodando) encerrar();
  });
  window.jarvisAbertura = {
    iniciar, encerrar,
    get rodando() { return rodando; },
    get falados() { return [...falados]; },
    get ritmo() { return ritmo; }, set ritmo(v) { ritmo = Math.max(.01, Number(v) || 1); },
  };
  // Opening the program: once, then the address forgets it (a reload does not repeat it).
  if (busca.get("abertura") === "1") {
    busca.delete("abertura");
    history.replaceState(null, "", location.pathname + (busca.size ? "?" + busca : "") + location.hash);
    addEventListener("load", () => iniciar({ automatica: true }).catch(() => {}), { once: true });
  }
})();
