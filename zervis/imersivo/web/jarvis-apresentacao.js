// SPDX-License-Identifier: AGPL-3.0-or-later
// The Zé presents himself (ADR 0045, approved in the hologram lab on 29/10/2026): he moves to the
// side, turns towards the board, and holographic panels materialize one by one, linked to him by
// beams, while a caption says what each one shows. Every number comes from his self-knowledge
// (GET /autoconhecimento, written by the Zé once a minute): the screen only shows what he knows of
// himself. The panels are real board items (jarvisStage.adicionar): the hands grab, move, scale
// and throw them away like any card. Start: the A key, Configurações → Apresentação, or the Zé's
// "apresentar" action (jarvis-controle.js).
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const NS = "http://www.w3.org/2000/svg";
  const num = new Intl.NumberFormat("pt-BR");
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  let ritmo = 1;  // the browser tests run the script faster (jarvisApresentacao.ritmo)
  const espera = ms => new Promise(r => setTimeout(r, ms * ritmo));
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)");

  // Beams live behind the cards, in the board layer.
  const feixes = document.createElementNS(NS, "svg");
  feixes.id = "jv-feixes"; feixes.setAttribute("aria-hidden", "true");
  feixes.innerHTML = `<defs><linearGradient id="jv-g-feixe" x1="0" x2="1"><stop offset="0" stop-color="#eafffb" stop-opacity=".9"/>
    <stop offset="1" stop-color="var(--jv-acento, #8ff0e4)" stop-opacity=".25"/></linearGradient></defs>`;
  const quadro = () => document.getElementById("behind");
  const legenda = Object.assign(document.createElement("div"), { id: "jv-legenda-ze" });
  legenda.setAttribute("aria-live", "polite");
  const dica = Object.assign(document.createElement("div"), { id: "jv-dica-ze" });
  document.body.append(legenda, dica);

  // ---- sound: small synthesized cues (the board's own foley stays in stage.html) ----
  let ac = null;
  const som = () => { try { ac ||= new AudioContext(); return ac.state === "running" ? ac : (ac.resume(), ac); } catch (_) { return null; } };
  function tom(f, dur, ganho = .03, tipo = "sine", ate = 0, atraso = 0) {
    const c = som(); if (!c) return;
    const t = c.currentTime + atraso, o = c.createOscillator(), g = c.createGain();
    o.type = tipo; o.frequency.setValueAtTime(f, t); if (ate) o.frequency.exponentialRampToValueAtTime(ate, t + dur);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(ganho, t + .01); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
    o.connect(g).connect(c.destination); o.start(t); o.stop(t + dur + .02);
  }

  // ---- panels ----
  const paineis = new Map();  // id -> {it, el, feixe, pacote, fase, quadro?}
  const vw = () => innerWidth, vh = () => innerHeight;
  function painel(id, { cod, titulo, x, y, w, h, corpo = "" }) {
    if (paineis.has(id)) return paineis.get(id);
    const el = document.createElement("div");
    el.className = "card jv-holo"; el.dataset.titulo = titulo;
    el.style.width = Math.round(w * vw()) + "px"; el.style.height = Math.round(h * vh()) + "px";
    el.setAttribute("role", "region"); el.setAttribute("aria-label", titulo);
    el.innerHTML = `<div class="jv-h-conteudo"><div class="jv-h-varre"></div>
      <header><span class="jv-h-cod">${esc(cod)}</span><h2>${esc(titulo)}</h2><span class="jv-h-fonte"><i></i>AO VIVO</span></header>
      <div class="jv-h-regua"></div><div class="jv-h-corpo">${corpo}</div></div>`;
    const it = window.jarvisStage.adicionar(el, { x: (x + w / 2) * vw(), y: (y + h / 2) * vh() });
    it.ry = -.12;  // turned a little towards the Zé on the left
    const f = document.createElementNS(NS, "path"); f.setAttribute("class", "feixe");
    const p = document.createElementNS(NS, "circle"); p.setAttribute("r", "2.4"); p.setAttribute("class", "pacote");
    feixes.append(f, p);
    const reg = { id, it, el, feixe: f, pacote: p, fase: Math.random() };
    paineis.set(id, reg);
    tom(1760, .12, .02, "sine", 0, .18); tom(420, .3, .015, "triangle", 1200);
    return reg;
  }
  function tirar(reg) {
    paineis.delete(reg.id); reg.feixe.remove(); reg.pacote.remove();
    if (reg.el.isConnected) window.jarvisStage.remover(reg.it);
  }
  function focar(id) {
    for (const r of paineis.values()) {
      r.el.classList.toggle("foco", r.id === id); r.el.classList.toggle("recuado", !!id && r.id !== id);
      r.feixe.classList.toggle("foco", r.id === id);
    }
  }

  // ---- the Zé's place: to the side while presenting, then back where he was ----
  let pose = null, alvo = null;
  function paraOCanto() {
    const anel = window.jarvisStage?.anel(); if (!anel) return;
    if (window.jarvisStage.nucleo?.().aberto) window.jarvisStage.fecharNucleo?.();
    pose ||= { x: anel.x, y: anel.y, scale: anel.scale };
    alvo = { x: vw() * .16, y: vh() * .48, scale: Math.min(.85, vh() / 1000), ry: .38 };
  }
  function paraOLugar() {
    if (!pose) { alvo = null; return; }
    alvo = { ...pose, ry: 0, fim: true }; pose = null;
  }

  // ---- building blocks ----
  function contar(el, ate, ms = 1300) {
    const t0 = performance.now();
    (function passo() {
      const k = Math.min(1, (performance.now() - t0) / ms), e = 1 - Math.pow(1 - k, 3);
      el.textContent = num.format(Math.round(ate * e)); if (k < 1 && el.isConnected) requestAnimationFrame(passo);
    })();
  }
  function mostrarDica(x, y, html) { dica.innerHTML = html; dica.style.left = x + "px"; dica.style.top = y + "px"; dica.classList.add("on"); }
  const esconderDica = () => dica.classList.remove("on");
  const quandoRel = s => { const m = Math.round((Date.now() / 1000 - s) / 60); return m < 1 ? "agora" : m < 60 ? `${m} min` : m < 1440 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} d`; };
  const TIPO = { execucao: ["bom", "✓", "EXECUTOU"], falha: ["critico", "✕", "FALHOU"], negada: ["alerta", "⊘", "NEGADA"],
    pedido: ["", "›", "PEDIDO"], nao_entendi: ["alerta", "?", "NÃO ENTENDI"], correcao: ["alerta", "↺", "CORREÇÃO"] };

  // Columns: one series (the title names it), hover shows each day.
  function colunas(caixa, dados) {
    const s = document.createElementNS(NS, "svg"); caixa.appendChild(s);
    const W = caixa.clientWidth, H = caixa.clientHeight, pe = 18, topo = 14, max = Math.max(1, ...dados.map(d => d.valor));
    const passo = W / dados.length, larg = Math.min(26, passo * .56), base = H - pe, alto = H - pe - topo;
    s.innerHTML = `<defs><linearGradient id="jv-g-coluna" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--jv-acento, #8ff0e4)"/>
      <stop offset="1" stop-color="var(--jv-acento, #8ff0e4)" stop-opacity=".18"/></linearGradient></defs>`
      + [.5, 1].map(f => `<line class="jv-grade" x1="0" x2="${W}" y1="${topo + alto * (1 - f)}" y2="${topo + alto * (1 - f)}"/>`).join("")
      + `<line class="jv-grade" x1="0" x2="${W}" y1="${base}" y2="${base}" style="stroke-opacity:.35"/>`;
    const iMax = dados.findIndex(d => d.valor === max);
    dados.forEach((d, i) => {
      const h = alto * d.valor / max, x = passo * i + (passo - larg) / 2;
      const r = document.createElementNS(NS, "path"); r.setAttribute("class", "jv-coluna");
      const forma = hh => { const y = base - hh, rr = Math.min(4, hh); return `M${x},${base} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + larg - rr} Q${x + larg},${y} ${x + larg},${y + rr} V${base} Z`; };
      r.setAttribute("d", forma(0)); s.appendChild(r);
      const t0 = performance.now() + i * 70;
      (function cresce() { const k = Math.max(0, Math.min(1, (performance.now() - t0) / 900)); r.setAttribute("d", forma(h * (1 - Math.pow(1 - k, 3)))); if (k < 1 && r.isConnected) requestAnimationFrame(cresce); })();
      const lb = document.createElementNS(NS, "text"); lb.setAttribute("class", "jv-eixo"); lb.setAttribute("x", x + larg / 2); lb.setAttribute("y", H - 4);
      lb.setAttribute("text-anchor", "middle"); lb.textContent = d.rotulo; s.appendChild(lb);
      if (i === iMax && d.valor > 0) { const v = document.createElementNS(NS, "text"); v.setAttribute("class", "jv-rotulo"); v.setAttribute("x", x + larg / 2); v.setAttribute("y", base - h - 5); v.setAttribute("text-anchor", "middle"); v.textContent = num.format(d.valor); s.appendChild(v); }
      const alvoH = document.createElementNS(NS, "rect");
      for (const [k, v] of Object.entries({ x: passo * i, y: 0, width: passo, height: H, fill: "transparent" })) alvoH.setAttribute(k, v);
      alvoH.addEventListener("pointerenter", () => { r.classList.add("ativa"); const b = alvoH.getBoundingClientRect(); mostrarDica(b.left + b.width / 2, b.top + (base - h) * (b.height / H), d.dica); });
      alvoH.addEventListener("pointerleave", () => { r.classList.remove("ativa"); esconderDica(); });
      s.appendChild(alvoH);
    });
  }
  function barras(caixa, itens) {
    const max = Math.max(1, ...itens.map(i => i.valor));
    caixa.innerHTML = `<div class="jv-barras">${itens.map(i => `<div class="jv-barra"><span class="nome">${esc(i.nome)}</span>
      <span class="trilho"><i data-w="${(i.valor / max * 100).toFixed(1)}"></i></span><span class="valor">${num.format(i.valor)}</span></div>`).join("")}</div>`;
    caixa.querySelectorAll(".jv-barra").forEach((b, n) => setTimeout(() => { const i = b.querySelector("i"); if (i) i.style.width = i.dataset.w + "%"; }, 250 + n * 110));
  }
  // The Zé's connections as a living graph: points joining the hub, packets flowing both ways.
  function grafo(reg, caixa, nos) {
    const cv = document.createElement("canvas"); caixa.appendChild(cv);
    const ctx = cv.getContext("2d"), dpr = Math.min(devicePixelRatio || 1, 2);
    const W = caixa.clientWidth, H = caixa.clientHeight; cv.width = W * dpr; cv.height = H * dpr; ctx.scale(dpr, dpr);
    const cx = W / 2, cy = H / 2, R = Math.min(W * .36, H * .38), t0 = performance.now();
    const pos = nos.map((n, i) => { const a = -Math.PI / 2 + i / nos.length * Math.PI * 2, f = i % 2 ? 1 : .86; return { ...n, a, x: cx + Math.cos(a) * R * f, y: cy + Math.sin(a) * R * f }; });
    const raiz = getComputedStyle(document.documentElement);
    reg.quadro = t => {
      const rgb = raiz.getPropertyValue("--jv-acento-rgb").trim() || "143 240 228", cor = `rgb(${rgb})`, e = (performance.now() - t0) / 1000;
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = `rgb(${rgb} / .08)`; ctx.lineWidth = 1;
      for (const f of [.45, .86, 1.12]) { ctx.beginPath(); ctx.arc(cx, cy, R * f, 0, Math.PI * 2); ctx.stroke(); }
      pos.forEach((n, i) => {
        const k = Math.max(0, Math.min(1, (e - .3 - i * .22) / .6)); if (k <= 0) return;
        const ex = cx + (n.x - cx) * k, ey = cy + (n.y - cy) * k;
        ctx.setLineDash(n.vivo ? [] : [3, 4]); ctx.strokeStyle = n.vivo ? `rgb(${rgb} / .45)` : "rgb(255 122 102 / .45)";
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(ex, ey); ctx.stroke(); ctx.setLineDash([]);
        if (k >= 1 && n.vivo && !reduzir.matches) for (let j = 0; j < 2; j++) {
          const f = (t * (.35 + i * .03) + j * .5 + i * .13) % 1, q = j ? 1 - f : f;
          ctx.fillStyle = "#eafffb"; ctx.shadowColor = cor; ctx.shadowBlur = 8;
          ctx.beginPath(); ctx.arc(cx + (n.x - cx) * q, cy + (n.y - cy) * q, 1.6, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
        }
        if (k < 1) return;
        const pul = .5 + .5 * Math.sin(t * 2 + i);
        ctx.strokeStyle = n.vivo ? cor : "#ff7a66"; ctx.fillStyle = n.vivo ? `rgb(${rgb} / ${(.15 + pul * .2).toFixed(2)})` : "rgb(255 122 102 / .18)";
        ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(n.x, n.y, 5.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        const dir = Math.cos(n.a) >= -.05 ? 1 : -1, tx = n.x + dir * 11;
        ctx.textAlign = dir > 0 ? "left" : "right"; ctx.textBaseline = "middle";
        ctx.fillStyle = "#ecfffa"; ctx.font = "600 12px 'Chakra Petch', sans-serif"; ctx.fillText(n.nome, tx, n.y - 6);
        ctx.fillStyle = n.vivo ? "#a8d8cf" : "#ff7a66"; ctx.font = "400 9.5px 'JetBrains Mono', monospace"; ctx.fillText((n.vivo ? "" : "✕ ") + n.sub, tx, n.y + 7);
      });
      const hp = .5 + .5 * Math.sin(t * 3);
      ctx.shadowColor = cor; ctx.shadowBlur = 18; ctx.fillStyle = `rgb(${rgb} / ${(.25 + hp * .25).toFixed(2)})`;
      ctx.beginPath(); ctx.arc(cx, cy, 15, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
      ctx.strokeStyle = cor; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.arc(cx, cy, 15, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = `rgb(${rgb} / .5)`; ctx.beginPath(); ctx.arc(cx, cy, 21, t % (Math.PI * 2), t % (Math.PI * 2) + 1.6); ctx.stroke();
      ctx.fillStyle = "#00140f"; ctx.font = "700 11px 'Chakra Petch', sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("ZÉ", cx, cy + .5);
    };
  }
  let digitar = 0;
  function dizer(texto) {
    clearInterval(digitar); legenda.textContent = ""; legenda.classList.toggle("digitando", !!texto); if (!texto) return;
    let i = 0;
    digitar = setInterval(() => { legenda.textContent = texto.slice(0, ++i); if (i >= texto.length) { clearInterval(digitar); setTimeout(() => legenda.classList.remove("digitando"), 900); } }, 30);
  }

  // ---- "quem": the Zé by himself ----
  const nomeFerramenta = n => String(n).replace(/_/g, " ");
  function quem(d) {
    const a = d.agora || {}, c = d.capacidades || {}, h = d.historico || {}, q = h.contagem || {};
    const conectores = c.conectores || [], sessoes = c.sessoes || [], skills = c.skills || [], grupos = c.grupos || [];
    const usadas = (h.mais_usadas || []).slice(0, 4), recentes = (h.recentes || []).slice(0, 3);
    const dias = (h.por_dia || []).map(x => { const dia = new Date(x.dia + "T12:00:00");
      return { rotulo: dia.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", ""), valor: x.registros,
        dica: `${esc(dia.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "short" }))}<small>${num.format(x.registros)} REGISTROS · ${num.format(x.falhas)} FALHAS</small>` }; });
    const modelo = a.modelo || a.cerebro || "—";
    const nos = [
      { nome: "Cérebro", sub: modelo, vivo: true },
      { nome: "Respostas rápidas", sub: a.modelo_das_rapidas || "desligadas", vivo: !!a.modelo_das_rapidas },
      ...conectores.slice(0, 2).map(x => ({ nome: x.nome, sub: `${num.format(x.livres)} ferramentas`, vivo: true })),
      { nome: "WhatsApp", sub: c.whatsapp || "—", vivo: c.whatsapp === "conectado" },
      { nome: "Sessões", sub: `${sessoes.length} de código`, vivo: sessoes.length > 0 },
      { nome: "Memória", sub: c.paginas != null ? `${num.format(c.paginas)} páginas` : `${num.format(c.lembrancas || 0)} lembranças`, vivo: true },
      { nome: "Skills", sub: `${skills.length} instaladas`, vivo: skills.length > 0 },
    ];
    const P = {
      identidade: () => painel("identidade", { cod: "01 · IDENTIDADE", titulo: "Identidade", x: .33, y: .1, w: .29, h: .28,
        corpo: `<dl class="jv-linhas">
          <dt>Cérebro</dt><dd>${esc(modelo)}<small>${esc(a.provedor || "")}</small></dd>
          <dt>Rápidas</dt><dd>${esc(a.modelo_das_rapidas || "Desligadas")}</dd>
          <dt>Voz</dt><dd>${esc(a.voz || "—")}</dd>
          <dt>Escuta</dt><dd>${esc(a.escuta || "—")}</dd>
          <dt>Modo</dt><dd>${esc(a.modo || "—")}<small>versão ${esc(a.versao || "")}</small></dd>
        </dl>` }),
      atividade: () => {
        const r = painel("atividade", { cod: `02 · ATIVIDADE · ${h.dias || 7} DIAS`, titulo: "Atividade", x: .64, y: .1, w: .32, h: .37,
          corpo: `<div class="jv-herois">
            <div class="jv-heroi"><span>PEDIDOS</span><b data-n="${q.pedido || 0}">0</b><small>atendidos</small></div>
            <div class="jv-heroi"><span>AÇÕES</span><b data-n="${q.execucao || 0}">0</b><small>executadas</small></div>
            <div class="jv-heroi"><span>FALHAS</span><b data-n="${q.falha || 0}">0</b><small class="jv-st critico" data-ico="✕">${num.format(q.negada || 0)} negadas</small></div>
          </div><span class="jv-h-legenda">REGISTROS POR DIA</span><div class="jv-grafico"></div>` });
        r.el.querySelectorAll("[data-n]").forEach((b, i) => setTimeout(() => contar(b, +b.dataset.n), 300 + i * 150));
        setTimeout(() => { const g = r.el.querySelector(".jv-grafico"); if (g) colunas(g, dias); }, 420);
        return r;
      },
      conexoes: () => { const r = painel("conexoes", { cod: "03 · CONEXÕES", titulo: "Conexões", x: .33, y: .42, w: .29, h: .44, corpo: '<div class="jv-grafo"></div>' });
        setTimeout(() => { const g = r.el.querySelector(".jv-grafo"); if (g) grafo(r, g, nos); }, 380); return r; },
      execucao: () => { const r = painel("execucao", { cod: `04 · EXECUÇÃO · ${h.dias || 7} DIAS`, titulo: "Mais executadas", x: .64, y: .51, w: .32, h: .2, corpo: "<div></div>" });
        barras(r.el.querySelector(".jv-h-corpo > div"), usadas.map(u => ({ nome: nomeFerramenta(u.ferramenta), valor: u.vezes }))); return r; },
      registro: () => painel("registro", { cod: "05 · REGISTRO", titulo: "Recentes", x: .64, y: .745, w: .32, h: .155,
        corpo: `<ul class="jv-registro">${recentes.map((x, i) => { const [cls, ico, rot] = TIPO[x.tipo] || ["", "·", String(x.tipo || "").toUpperCase()];
          return `<li style="animation-delay:${.4 + i * .15}s"><time>${quandoRel(x.quando)}</time><span class="jv-st ${cls}" data-ico="${ico}">${rot}</span><span class="txt">${esc(x.titulo)}</span></li>`; }).join("")}</ul>` }),
    };
    const pct = (q.execucao || 0) + (q.falha || 0) ? Math.round((q.falha || 0) / ((q.execucao || 0) + (q.falha || 0)) * 100) : 0;
    return [
      { fala: "Eu sou o Zé." },
      { mostrar: [P.identidade], foco: "identidade", fala: `Quem pensa agora é o ${modelo}${a.provedor ? `, pelo ${a.provedor}` : ""}.` + (a.modelo_das_rapidas ? ` As respostas rápidas vão pelo ${a.modelo_das_rapidas}.` : "") },
      { mostrar: [P.atividade], foco: "atividade", fala: `Nos últimos ${h.dias || 7} dias atendi ${num.format(q.pedido || 0)} pedidos e executei ${num.format(q.execucao || 0)} ações; ${num.format(q.falha || 0)} falharam, uns ${pct}%.` },
      { mostrar: [P.conexoes], foco: "conexoes", fala: `Tenho ${num.format(c.ferramentas || 0)} ferramentas em ${grupos.length} áreas e ${skills.length} skills` + (conectores[0] ? `, e estou ligado ao ${conectores[0].nome} com ${num.format(conectores[0].livres)} ferramentas.` : ".") },
      ...(usadas.length ? [{ mostrar: [P.execucao], foco: "execucao", fala: `O que eu mais executo é ${nomeFerramenta(usadas[0].ferramenta)}: ${num.format(usadas[0].vezes)} vezes.` }] : []),
      ...(recentes.length ? [{ mostrar: [P.registro], foco: "registro", fala: "E isto foi o que aconteceu agora há pouco." }] : []),
    ];
  }

  // ---- the script runner ----
  let rodada = 0, apresentando = false;
  async function apresentar(tema = "quem") {
    if (tema !== "quem") throw new Error("apresentar: quem ou encerrar");
    const id = ++rodada;
    for (const r of [...paineis.values()]) tirar(r);
    let d = {};
    try { const resp = await fetch("/autoconhecimento"); d = resp.ok ? await resp.json() : {}; } catch (_) { d = {}; }
    if (id !== rodada) return { apresentando: false };
    if (!d.agora) { dizer("Autoconhecimento indisponível."); setTimeout(() => id === rodada && dizer(""), 4000); return { apresentando: false, erro: "sem autoconhecimento" }; }
    const q = quadro(); if (q && feixes.parentNode !== q) q.insertBefore(feixes, q.firstChild);
    apresentando = true; paraOCanto(); tom(110, 1.2, .03, "sawtooth", 440); tom(880, .4, .025, "sine", 0, 1);
    (async () => {
      await espera(700);
      for (const passo of quem(d)) {
        if (id !== rodada) return;
        (passo.mostrar || []).forEach((f, i) => setTimeout(() => id === rodada && f(), i * 260));
        if (passo.mostrar) await espera(450);
        focar(passo.foco || null);
        dizer(passo.fala);
        await espera(Math.max(2600, passo.fala.length * 62));
      }
      if (id === rodada) { focar(null); setTimeout(() => id === rodada && dizer(""), 2500); }
    })();
    return { apresentando: true };
  }
  function encerrar() {
    rodada++; apresentando = false;
    for (const r of [...paineis.values()]) tirar(r);
    paraOLugar(); dizer(""); esconderDica(); tom(900, .25, .02, "sine", 300);
    return { apresentando: false };
  }

  // ---- every frame: the Zé easing to his place, beams, live panels ----
  const v = { x: 0, y: 0 };
  let ultimo = performance.now();
  (function laco(agora) {
    requestAnimationFrame(laco);
    const t = agora / 1000, anel = window.jarvisStage?.anel?.();
    const dt = Math.min(.25, Math.max(0, (agora - ultimo) / 1000)); ultimo = agora;
    if (anel && alvo && !anel.grabbedBy.length) {
      const k = 1 - Math.exp(-dt * 4);  // time based: the same glide on any frame rate
      anel.vx = anel.vy = 0;
      anel.x += (alvo.x - anel.x) * k; anel.y += (alvo.y - anel.y) * k; anel.scale += (alvo.scale - anel.scale) * k;
      if (window.jarvisAvatar?.montados && !anel.girando) anel.ry = (anel.ry || 0) + ((alvo.ry || 0) - (anel.ry || 0)) * k;
      if (alvo.fim && Math.hypot(alvo.x - anel.x, alvo.y - anel.y) < 1) alvo = null;
    }
    if (!paineis.size) return;
    const ra = anel?.el.getBoundingClientRect();
    v.x = ra ? ra.left + ra.width / 2 : vw() * .16; v.y = ra ? ra.top + ra.height * .45 : vh() * .45;
    for (const r of [...paineis.values()]) {
      if (!r.el.isConnected || r.it.anim?.k === "out") { if (!r.el.isConnected) { paineis.delete(r.id); r.feixe.remove(); r.pacote.remove(); } continue; }
      const b = r.el.getBoundingClientRect(), ax = b.left, ay = b.top + b.height / 2, mx = (v.x + ax) / 2;
      r.feixe.setAttribute("d", `M${v.x.toFixed(1)},${v.y.toFixed(1)} C${mx.toFixed(1)},${v.y.toFixed(1)} ${mx.toFixed(1)},${ay.toFixed(1)} ${ax.toFixed(1)},${ay.toFixed(1)}`);
      const L = r.feixe.getTotalLength();
      if (L > 0 && !reduzir.matches) { const p = r.feixe.getPointAtLength(((t * .45 + r.fase) % 1) * L); r.pacote.setAttribute("cx", p.x); r.pacote.setAttribute("cy", p.y); }
      r.quadro?.(t);
    }
    if (apresentando && !paineis.size && !alvo) apresentando = false;
  })(performance.now());

  addEventListener("keydown", e => {
    if ((e.key !== "a" && e.key !== "A") || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest?.("input, textarea, [contenteditable], #jv-teclado")) return;
    apresentando ? encerrar() : apresentar("quem").catch(() => {});
  });
  window.jarvisApresentacao = {
    get apresentando() { return apresentando; },
    get paineis() { return [...paineis.keys()]; },
    get ritmo() { return ritmo; }, set ritmo(v) { ritmo = Math.max(.01, Number(v) || 1); },
    apresentar, encerrar,
  };
})();
