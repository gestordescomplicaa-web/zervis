// SPDX-License-Identifier: AGPL-3.0-or-later
// The Zé explains anything with an animated scene (ADR 0047): he writes a short script, a JSON
// "cena" made of blocks from the catalogue below (title, big number, charts, steps, network,
// waves, 3D shapes, globe, comparison, list, timeline), and this page draws it, step by step,
// with the same holographic panels, beams and caption as his self-presentation
// (jarvis-apresentacao.js). Every block is a real board item: the hands grab and throw it.
//
// Honesty: a block that shows numbers says where they come from (fonte) or carries the
// ILUSTRATIVO tag; one without either is tagged ILUSTRATIVO. Schemes (steps, network, waves, 3D)
// say ESQUEMA. The scene arrives from the brain (tela_explicar → the "explicar" action), from
// the E key (the examples below, one after the other) or from ?cena=<example>.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const NS = "http://www.w3.org/2000/svg";
  const num = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)");
  const raiz = getComputedStyle(document.documentElement);
  const acento = () => raiz.getPropertyValue("--jv-acento-rgb").trim() || "143 240 228";
  const P = () => window.jarvisApresentacao.palco;
  const suave = k => 1 - Math.pow(1 - Math.max(0, Math.min(1, k)), 3);

  // ---- the scene, cleaned: what the brain sends is never trusted as-is ----
  const texto = (v, n = 120) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, n);
  const numero = v => { const n = typeof v === "number" ? v : Number(String(v ?? "").replace(/\./g, "").replace(",", ".")); return Number.isFinite(n) ? n : null; };
  const lista = (v, n) => (Array.isArray(v) ? v : []).slice(0, n);
  const COM_NUMEROS = new Set(["numero", "barras", "linha", "rosca"]);
  const TIPOS = {
    titulo: b => (b.texto || b.titulo) && { texto: texto(b.texto || b.titulo, 70), subtitulo: texto(b.subtitulo, 110) },
    numero: b => numero(b.valor) != null && { valor: numero(b.valor), unidade: texto(b.unidade, 16), prefixo: texto(b.prefixo, 6),
      rotulo: texto(b.rotulo || b.titulo, 60), detalhe: texto(b.detalhe, 90), de: numero(b.de) },
    barras: b => { const itens = lista(b.itens, 8).map(i => ({ nome: texto(i?.nome, 40), valor: numero(i?.valor) })).filter(i => i.nome && i.valor != null);
      return itens.length && { itens, unidade: texto(b.unidade, 16) }; },
    linha: b => { const pontos = lista(b.pontos, 24).map(i => ({ rotulo: texto(i?.rotulo, 14), valor: numero(i?.valor) })).filter(i => i.valor != null);
      return pontos.length > 1 && { pontos, unidade: texto(b.unidade, 16) }; },
    rosca: b => { const fatias = lista(b.fatias, 6).map(i => ({ nome: texto(i?.nome, 32), valor: numero(i?.valor) })).filter(i => i.nome && i.valor > 0);
      return fatias.length && { fatias, centro: texto(b.centro, 18) }; },
    etapas: b => { const etapas = lista(b.etapas, 6).map(i => ({ nome: texto(i?.nome ?? i, 32), texto: texto(i?.texto, 80) })).filter(i => i.nome);
      return etapas.length > 1 && { etapas }; },
    rede: b => { const nos = lista(b.nos, 10).map(i => ({ nome: texto(i?.nome ?? i, 26), texto: texto(i?.texto, 34) })).filter(i => i.nome);
      return nos.length && { centro: texto(b.centro, 14) || "•", nos }; },
    onda: b => { const ondas = lista(b.ondas, 3).map(i => ({ nome: texto(i?.nome, 26), frequencia: Math.max(.3, Math.min(8, numero(i?.frequencia) ?? 1)),
      amplitude: Math.max(.1, Math.min(1, numero(i?.amplitude) ?? .8)) }));
      return { ondas: ondas.length ? ondas : [{ nome: "", frequencia: 1, amplitude: .8 }], soma: !!b.soma && ondas.length > 1 }; },
    forma3d: b => ({ forma: FORMAS[b.forma] ? b.forma : "esfera", legenda: texto(b.legenda, 90) }),
    globo: b => ({ pontos: lista(b.pontos, 12).map(i => ({ nome: texto(i?.nome, 22), lat: numero(i?.lat), lon: numero(i?.lon) }))
      .filter(i => i.lat != null && i.lon != null && Math.abs(i.lat) <= 90 && Math.abs(i.lon) <= 180), ligar: b.ligar !== false }),
    comparar: b => { const lados = lista(b.lados, 2).map(l => ({ nome: texto(l?.nome, 28), itens: lista(l?.itens, 6).map(i => texto(i, 60)).filter(Boolean) }));
      return lados.length === 2 && lados.every(l => l.nome) && { lados }; },
    lista: b => { const itens = lista(b.itens, 7).map(i => texto(i, 90)).filter(Boolean); return itens.length && { itens }; },
    // a real 3D object (jarvis-holograma.js): the pinch lock turns it, two hands scale it
    holograma: b => window.jarvisHolograma?.limpar(b) || null,
    linha_tempo: b => { const marcos = lista(b.marcos, 8).map(i => ({ quando: texto(i?.quando, 14), nome: texto(i?.nome, 40) })).filter(i => i.nome);
      return marcos.length > 1 && { marcos }; },
  };
  const NOME = { titulo: "TÍTULO", numero: "NÚMERO", barras: "COMPARAÇÃO", linha: "EVOLUÇÃO", rosca: "DIVISÃO", etapas: "ETAPAS", rede: "CONEXÕES",
    onda: "ONDAS", forma3d: "FORMA", holograma: "HOLOGRAMA 3D", globo: "MAPA", comparar: "LADO A LADO", lista: "PONTOS", linha_tempo: "LINHA DO TEMPO" };
  function limpar(cena) {
    if (typeof cena === "string") { try { cena = JSON.parse(cena); } catch (_) { cena = null; } }
    if (!cena || typeof cena !== "object") throw new Error("cena: um objeto com titulo e passos");
    const ignorados = [], passos = [];
    let total = 0;
    for (const p of lista(cena.passos, 10)) {
      const blocos = [];
      for (const b of lista(p?.blocos, 4)) {
        const f = TIPOS[b?.tipo], ok = f && total < 16 && f(b || {});
        if (!ok) { ignorados.push(String(b?.tipo ?? "?")); continue; }
        total++;
        // "exemplo ilustrativo" written as a source is the ILUSTRATIVO tag, not a source
        const fonte = texto(b.fonte, 40), deExemplo = /ilustrativ|exemplo|hipot[eé]tic/i.test(fonte);
        blocos.push({ tipo: b.tipo, titulo: texto(b.titulo, 48), fonte: deExemplo ? "" : fonte, ilustrativo: !!b.ilustrativo || deExemplo, ...ok });
      }
      if (blocos.length || p?.fala) passos.push({ fala: texto(p?.fala, 240), blocos, limpar: !!p?.limpar });
    }
    if (!passos.length) throw new Error("cena sem passos que a tela saiba desenhar");
    // a scene without a title block opens with its own title
    const titulo = texto(cena.titulo, 70);
    if (titulo && !passos.some(p => p.blocos.some(b => b.tipo === "titulo")) && passos[0].blocos.length < 4)
      passos[0].blocos.unshift({ tipo: "titulo", titulo: "", fonte: "", ilustrativo: false, texto: titulo, subtitulo: "" });
    return { titulo, passos, ignorados };
  }

  // ---- layout: a page holds a title and up to four blocks, to the right of the Zé ----
  const AREA = { x0: .30, x1: .975, y0: .07, y1: .79 }, VAO = .014;
  function paginar(passos) {
    let n = 0, titulo = false;
    for (const p of passos) {
      const t = p.blocos.filter(b => b.tipo === "titulo").length, o = p.blocos.length - t;
      if (p.limpar || n + o > 4 || (t && titulo)) { if (n || titulo) p.limpar = true; n = 0; titulo = false; }
      n += o; titulo ||= !!t;
    }
    const paginas = [[]];
    for (const p of passos) { if (p.limpar && paginas.at(-1).length) paginas.push([]); paginas.at(-1).push(...p.blocos); }
    for (const pg of paginas) {
      const tit = pg.find(b => b.tipo === "titulo"), resto = pg.filter(b => b !== tit);
      let y0 = AREA.y0;
      if (tit) { tit.caixa = { x: AREA.x0, y: y0, w: AREA.x1 - AREA.x0, h: resto.length ? .15 : .3 }; y0 += .17; }
      const W = AREA.x1 - AREA.x0, H = AREA.y1 - y0, m = resto.length;
      const c = (x, y, w, h) => ({ x: AREA.x0 + x * W, y: y0 + y * H, w: w * W, h: h * H });
      const g = VAO / W, gy = VAO / H;
      const caixas = m === 1 ? [c(0, 0, 1, 1)]
        : m === 2 ? [c(0, 0, .5 - g / 2, 1), c(.5 + g / 2, 0, .5 - g / 2, 1)]
        : m === 3 ? [c(0, 0, .56 - g / 2, 1), c(.56 + g / 2, 0, .44 - g / 2, .5 - gy / 2), c(.56 + g / 2, .5 + gy / 2, .44 - g / 2, .5 - gy / 2)]
        : [c(0, 0, .5 - g / 2, .5 - gy / 2), c(.5 + g / 2, 0, .5 - g / 2, .5 - gy / 2), c(0, .5 + gy / 2, .5 - g / 2, .5 - gy / 2), c(.5 + g / 2, .5 + gy / 2, .5 - g / 2, .5 - gy / 2)];
      resto.forEach((b, i) => { b.caixa = caixas[i]; });
    }
    return paginas.length;
  }

  // ---- drawing helpers ----
  function tela(caixa) {
    // measured before the canvas goes in, so its default size never stretches the box
    const dpr = Math.min(devicePixelRatio || 1, 2), W = Math.max(1, caixa.clientWidth), H = Math.max(1, caixa.clientHeight);
    const cv = document.createElement("canvas"); cv.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    cv.width = W * dpr; cv.height = H * dpr; caixa.appendChild(cv);
    const ctx = cv.getContext("2d"); ctx.scale(dpr, dpr);
    return { ctx, W, H };
  }
  const CAR = "▓▒░<>/\\|=+*#%01ΞΣΔ";
  function embaralhar(el, alvo, ms = 700) {
    const t0 = performance.now();
    (function passo() {
      const k = Math.min(1, (performance.now() - t0) / ms), n = Math.floor(alvo.length * k);
      el.textContent = alvo.slice(0, n) + [...alvo.slice(n)].map(ch => ch === " " ? " " : CAR[Math.random() * CAR.length | 0]).join("");
      if (k < 1 && el.isConnected) requestAnimationFrame(passo);
    })();
  }
  function contar(el, ate, ms, casas) {
    const t0 = performance.now(), f = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
    (function passo() {
      const k = Math.min(1, (performance.now() - t0) / ms); el.textContent = f.format(ate * suave(k));
      if (k < 1 && el.isConnected) requestAnimationFrame(passo);
    })();
  }
  const casasDe = v => Math.min(2, (String(v).split(".")[1] || "").length);
  // the short form for big numbers: 3,1 bi, 12 mil
  function curto(v) {
    const a = Math.abs(v);
    return a >= 1e9 ? [v / 1e9, " bi"] : a >= 1e6 ? [v / 1e6, " mi"] : a >= 1e4 ? [v / 1e3, " mil"] : [v, ""];
  }

  // ---- the blocks ----
  const BLOCOS = {
    titulo(reg, caixa, b) {
      caixa.innerHTML = `<div class="jv-c-titulo"><span class="kicker">EXPLICAÇÃO</span><h1></h1>${b.subtitulo ? `<p>${esc(b.subtitulo)}</p>` : ""}<i class="traco"></i></div>`;
      embaralhar(caixa.querySelector("h1"), b.texto, 900);
    },
    numero(reg, caixa, b) {
      const [v, sufixo] = curto(b.valor), casas = sufixo ? (Math.abs(v) < 10 ? 1 : 0) : casasDe(b.valor);
      caixa.innerHTML = `<div class="jv-c-numero"><div class="anel"></div><div class="valor"><small>${esc(b.prefixo)}</small><b>0</b><span>${esc(sufixo + (b.unidade ? " " + b.unidade : ""))}</span></div>
        ${b.rotulo ? `<em>${esc(b.rotulo)}</em>` : ""}${b.detalhe ? `<p>${esc(b.detalhe)}</p>` : ""}</div>`;
      contar(caixa.querySelector("b"), v, 1600, casas);
      const { ctx, W, H } = tela(caixa.querySelector(".anel")), t0 = performance.now();
      const parte = b.de > 0 ? Math.max(0, Math.min(1, b.valor / b.de)) : null;
      reg.quadro = t => {
        const rgb = acento(), e = (performance.now() - t0) / 1000, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 6;
        ctx.clearRect(0, 0, W, H); ctx.lineCap = "round";
        ctx.strokeStyle = `rgb(${rgb} / .1)`; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();
        const fim = (parte ?? .72) * suave(e / 1.6), giro = parte == null ? t * .6 : 0;
        ctx.strokeStyle = `rgb(${rgb})`; ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 14;
        ctx.beginPath(); ctx.arc(cx, cy, R, -Math.PI / 2 + giro, -Math.PI / 2 + giro + fim * Math.PI * 2); ctx.stroke(); ctx.shadowBlur = 0;
        ctx.strokeStyle = `rgb(${rgb} / .35)`; ctx.lineWidth = 1; ctx.setLineDash([2, 6]);
        ctx.beginPath(); ctx.arc(cx, cy, R - 13, -t * .3, -t * .3 + Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
        for (let i = 0; i < 60; i++) {   // the tick ring
          const a = i / 60 * Math.PI * 2, r1 = R + 3, r2 = R + (i % 5 ? 5 : 8);
          ctx.strokeStyle = `rgb(${rgb} / ${i / 60 <= fim ? .55 : .12})`;
          ctx.beginPath(); ctx.moveTo(cx + Math.cos(a - Math.PI / 2) * r1, cy + Math.sin(a - Math.PI / 2) * r1); ctx.lineTo(cx + Math.cos(a - Math.PI / 2) * r2, cy + Math.sin(a - Math.PI / 2) * r2); ctx.stroke();
        }
      };
    },
    barras(reg, caixa, b) {
      caixa.innerHTML = "<div></div>";
      P().barras(caixa.firstChild, b.itens);
      if (b.unidade) caixa.insertAdjacentHTML("beforeend", `<span class="jv-h-legenda">EM ${esc(b.unidade.toUpperCase())}</span>`);
    },
    linha(reg, caixa, b) {
      caixa.innerHTML = '<div class="jv-grafico"></div>';
      const alvo = caixa.firstChild, s = document.createElementNS(NS, "svg"); alvo.appendChild(s);
      const W = alvo.clientWidth, H = alvo.clientHeight, pe = 18, topo = 18, esq = 4;
      const vals = b.pontos.map(p => p.valor), min = Math.min(0, ...vals), max = Math.max(...vals), amp = max - min || 1;
      const X = i => esq + i / (b.pontos.length - 1) * (W - esq * 2), Y = v => topo + (1 - (v - min) / amp) * (H - pe - topo);
      const d = b.pontos.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.valor).toFixed(1)}`).join(" ");
      const iMax = vals.indexOf(max), passoRot = Math.ceil(b.pontos.length / 8);
      s.innerHTML = `<defs><linearGradient id="jv-g-area-${reg.id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--jv-acento, #8ff0e4)" stop-opacity=".32"/>
          <stop offset="1" stop-color="var(--jv-acento, #8ff0e4)" stop-opacity="0"/></linearGradient></defs>`
        + [0, .5, 1].map(f => `<line class="jv-grade" x1="0" x2="${W}" y1="${topo + (H - pe - topo) * f}" y2="${topo + (H - pe - topo) * f}"/>`).join("")
        + `<path class="jv-c-area" d="${d} L${X(b.pontos.length - 1)},${H - pe} L${X(0)},${H - pe} Z" fill="url(#jv-g-area-${reg.id})"/>`
        + `<path class="jv-c-traco" d="${d}"/>`
        + b.pontos.map((p, i) => i % passoRot ? "" : `<text class="jv-eixo" x="${X(i)}" y="${H - 4}" text-anchor="middle">${esc(p.rotulo)}</text>`).join("")
        + `<text class="jv-rotulo" x="${X(iMax)}" y="${Y(max) - 8}" text-anchor="middle">${esc(num.format(max) + (b.unidade ? " " + b.unidade : ""))}</text>`
        + `<circle class="jv-c-cabeca" r="3.5"/>`;
      const traco = s.querySelector(".jv-c-traco"), area = s.querySelector(".jv-c-area"), cabeca = s.querySelector(".jv-c-cabeca"), L = traco.getTotalLength();
      traco.style.strokeDasharray = L; traco.style.strokeDashoffset = L;
      const t0 = performance.now();
      b.pontos.forEach((p, i) => {   // hover: a target per point, wider than the mark
        const r = document.createElementNS(NS, "rect"), w = (W - esq * 2) / (b.pontos.length - 1);
        for (const [k, v] of Object.entries({ x: X(i) - w / 2, y: 0, width: w, height: H, fill: "transparent" })) r.setAttribute(k, v);
        r.addEventListener("pointerenter", () => { const q = r.getBoundingClientRect(); P().mostrarDica(q.left + q.width / 2, q.top + Y(p.valor) * (q.height / H), `${esc(p.rotulo)}<small>${esc(num.format(p.valor) + (b.unidade ? " " + b.unidade : ""))}</small>`); });
        r.addEventListener("pointerleave", () => P().esconderDica());
        s.appendChild(r);
      });
      reg.quadro = t => {
        const k = suave((performance.now() - t0) / 1600);
        traco.style.strokeDashoffset = L * (1 - k); area.style.opacity = k;
        const q = traco.getPointAtLength(k < 1 ? L * k : ((t * .25) % 1) * L);
        cabeca.setAttribute("cx", q.x); cabeca.setAttribute("cy", q.y);
      };
    },
    rosca(reg, caixa, b) {
      const soma = b.fatias.reduce((a, f) => a + f.valor, 0), alfa = [1, .66, .44, .3, .2, .13];
      caixa.innerHTML = `<div class="jv-c-rosca"><div class="disco"><b>${esc(b.centro)}</b></div><ul>${b.fatias.map((f, i) =>
        `<li style="--a:${alfa[i]};animation-delay:${.5 + i * .12}s"><i></i><span>${esc(f.nome)}</span><b>${Math.round(f.valor / soma * 100)}%</b></li>`).join("")}</ul></div>`;
      const { ctx, W, H } = tela(caixa.querySelector(".disco")), t0 = performance.now();
      reg.quadro = t => {
        const rgb = acento(), k = suave((performance.now() - t0) / 1500), cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 8;
        ctx.clearRect(0, 0, W, H);
        let a = -Math.PI / 2;
        b.fatias.forEach((f, i) => {
          const fim = a + f.valor / soma * Math.PI * 2 * k;
          ctx.strokeStyle = `rgb(${rgb} / ${alfa[i]})`; ctx.lineWidth = i ? 14 : 18;
          if (!i) { ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 16; }
          ctx.beginPath(); ctx.arc(cx, cy, R - 4, a + .025, Math.max(a + .03, fim - .025)); ctx.stroke(); ctx.shadowBlur = 0;
          a = fim;
        });
        ctx.strokeStyle = `rgb(${rgb} / .25)`; ctx.lineWidth = 1; ctx.setLineDash([1, 5]);
        ctx.beginPath(); ctx.arc(cx, cy, R - 22, t * .4, t * .4 + Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
      };
    },
    etapas(reg, caixa, b) {
      const vertical = caixa.clientHeight > caixa.clientWidth * .9;
      caixa.innerHTML = `<div class="jv-c-etapas${vertical ? " vertical" : ""}">${b.etapas.map((e, i) =>
        `<div class="etapa" style="animation-delay:${.3 + i * .18}s"><span class="n">${String(i + 1).padStart(2, "0")}</span><b>${esc(e.nome)}</b>${e.texto ? `<small>${esc(e.texto)}</small>` : ""}</div>`).join("")}</div>`;
      const nos = [...caixa.querySelectorAll(".etapa")];
      const { ctx, W, H } = tela(caixa); ctx.canvas.classList.add("fios");
      // layout coordinates (offset*), not the screen: the card may be tilted or scaled by a hand
      const centros = nos.map(n => ({ x: n.offsetLeft + n.offsetWidth / 2, y: n.offsetTop + (vertical ? n.offsetHeight / 2 : 15) }));
      const t0 = performance.now();
      reg.quadro = t => {
        const rgb = acento(), e = (performance.now() - t0) / 1000, n = centros.length;
        ctx.clearRect(0, 0, W, H);
        const ativa = Math.floor(e / 1.1) % n;
        nos.forEach((no, i) => no.classList.toggle("ativa", e > .3 + n * .18 && i === ativa));
        for (let i = 0; i < n - 1; i++) {
          const a = centros[i], z = centros[i + 1], k = suave((e - .5 - i * .18) / .5); if (k <= 0) continue;
          ctx.strokeStyle = `rgb(${rgb} / .35)`; ctx.lineWidth = 1; ctx.setLineDash([3, 5]); ctx.lineDashOffset = -t * 20;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(a.x + (z.x - a.x) * k, a.y + (z.y - a.y) * k); ctx.stroke(); ctx.setLineDash([]);
          if (k >= 1 && !reduzir.matches) {
            const f = (t * .9 + i * .3) % 1;
            ctx.fillStyle = "#eafffb"; ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 10;
            ctx.beginPath(); ctx.arc(a.x + (z.x - a.x) * f, a.y + (z.y - a.y) * f, 2, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
          }
        }
      };
    },
    rede(reg, caixa, b) {
      const { ctx, W, H } = tela(caixa), t0 = performance.now(), n = b.nos.length;
      const cx = W / 2, cy = H / 2, R = Math.min(W * .34, H * .36);
      const pos = b.nos.map((no, i) => { const a = -Math.PI / 2 + i / n * Math.PI * 2, f = n > 5 && i % 2 ? .78 : 1; return { ...no, a, x: cx + Math.cos(a) * R * f * 1.15, y: cy + Math.sin(a) * R * f }; });
      reg.quadro = t => {
        const rgb = acento(), e = (performance.now() - t0) / 1000;
        ctx.clearRect(0, 0, W, H);
        ctx.strokeStyle = `rgb(${rgb} / .07)`; ctx.lineWidth = 1;
        for (const f of [.4, .8, 1.2]) { ctx.beginPath(); ctx.ellipse(cx, cy, R * f * 1.15, R * f, 0, 0, Math.PI * 2); ctx.stroke(); }
        pos.forEach((p, i) => {
          const k = suave((e - .3 - i * .16) / .6); if (k <= 0) return;
          const ex = cx + (p.x - cx) * k, ey = cy + (p.y - cy) * k;
          ctx.strokeStyle = `rgb(${rgb} / .4)`; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(ex, ey); ctx.stroke();
          if (k < 1) return;
          if (!reduzir.matches) for (let j = 0; j < 2; j++) {
            const f = (t * (.32 + i * .03) + j * .5 + i * .11) % 1, q = j ? 1 - f : f;
            ctx.fillStyle = "#eafffb"; ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 8;
            ctx.beginPath(); ctx.arc(cx + (p.x - cx) * q, cy + (p.y - cy) * q, 1.6, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
          }
          const pul = .5 + .5 * Math.sin(t * 2 + i);
          ctx.strokeStyle = `rgb(${rgb})`; ctx.fillStyle = `rgb(${rgb} / ${(.15 + pul * .2).toFixed(2)})`; ctx.lineWidth = 1.2;
          ctx.beginPath(); ctx.arc(p.x, p.y, 6, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
          const dir = Math.cos(p.a) >= -.05 ? 1 : -1, tx = p.x + dir * 12;
          ctx.textAlign = dir > 0 ? "left" : "right"; ctx.textBaseline = "middle";
          ctx.fillStyle = "#ecfffa"; ctx.font = "600 12px 'Chakra Petch', sans-serif"; ctx.fillText(p.nome, tx, p.y - (p.texto ? 6 : 0));
          if (p.texto) { ctx.fillStyle = "#a8d8cf"; ctx.font = "400 9.5px 'JetBrains Mono', monospace"; ctx.fillText(p.texto, tx, p.y + 7); }
        });
        const hp = .5 + .5 * Math.sin(t * 3), rc = Math.max(17, Math.min(30, b.centro.length * 4.2));
        ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 20; ctx.fillStyle = `rgb(${rgb} / ${(.25 + hp * .25).toFixed(2)})`;
        ctx.beginPath(); ctx.arc(cx, cy, rc, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
        ctx.strokeStyle = `rgb(${rgb})`; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.arc(cx, cy, rc, 0, Math.PI * 2); ctx.stroke();
        ctx.strokeStyle = `rgb(${rgb} / .5)`; ctx.beginPath(); ctx.arc(cx, cy, rc + 6, t % (Math.PI * 2), t % (Math.PI * 2) + 1.6); ctx.stroke();
        ctx.fillStyle = "#00140f"; ctx.font = "700 11px 'Chakra Petch', sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(b.centro.toUpperCase(), cx, cy + .5);
      };
    },
    onda(reg, caixa, b) {
      const legenda = b.ondas.some(o => o.nome) || b.soma;
      caixa.innerHTML = `<div class="jv-c-onda"></div>${legenda ? `<div class="jv-c-legenda">${b.ondas.map((o, i) => `<span style="--a:${[1, .6, .4][i]}"><i></i>${esc(o.nome || "Onda " + (i + 1))}</span>`).join("")}${b.soma ? '<span class="soma"><i></i>Soma</span>' : ""}</div>` : ""}`;
      const { ctx, W, H } = tela(caixa.firstChild), t0 = performance.now();
      reg.quadro = t => {
        const rgb = acento(), k = suave((performance.now() - t0) / 1400), meio = H / 2, A = H * .36;
        ctx.clearRect(0, 0, W, H);
        ctx.strokeStyle = `rgb(${rgb} / .07)`; ctx.lineWidth = 1;   // the oscilloscope grid
        for (let x = (t * 12) % 24; x < W; x += 24) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
        for (let y = meio % 24; y < H; y += 24) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
        ctx.strokeStyle = `rgb(${rgb} / .25)`; ctx.beginPath(); ctx.moveTo(0, meio); ctx.lineTo(W, meio); ctx.stroke();
        const y = (o, x) => Math.sin(x / W * Math.PI * 2 * o.frequencia * 2 - t * 2.2 * (o.frequencia > 2 ? 1.6 : 1)) * o.amplitude;
        const ate = W * k, linhas = b.ondas.map((o, i) => ({ f: x => y(o, x) / (b.soma ? b.ondas.length : 1), a: [1, .6, .4][i], larg: 1.4 }));
        if (b.soma) linhas.push({ f: x => b.ondas.reduce((s, o) => s + y(o, x), 0) / b.ondas.length, a: 1, larg: 2.4, quente: true });
        for (const l of linhas) {
          ctx.strokeStyle = l.quente ? "#eafffb" : `rgb(${rgb} / ${l.a})`; ctx.lineWidth = l.larg;
          ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = l.quente || l.a === 1 ? 12 : 0;
          ctx.beginPath(); for (let x = 0; x <= ate; x += 3) ctx[x ? "lineTo" : "moveTo"](x, meio - l.f(x) * A); ctx.stroke(); ctx.shadowBlur = 0;
        }
      };
    },
    forma3d(reg, caixa, b) {
      caixa.innerHTML = `<div class="jv-c-forma"></div>${b.legenda ? `<p class="jv-c-nota">${esc(b.legenda)}</p>` : ""}`;
      const { ctx, W, H } = tela(caixa.firstChild), forma = FORMAS[b.forma](), t0 = performance.now();
      const n = forma.pontos.length / 3, de = new Float32Array(n * 3).map(() => (Math.random() * 2 - 1) * 2.4), p = new Float32Array(3), proj = new Float32Array(n * 3);
      reg.quadro = t => {
        const rgb = acento(), e = (performance.now() - t0) / 1000, k = suave(e / 1.8), escala = Math.min(W, H) * (forma.escala ?? .36);
        // a shape read from the front (layers left to right) sways instead of spinning
        const ry = forma.balanco ? Math.sin(t * .4) * .5 : t * .35, rx = forma.balanco ? -.12 : -.38, cy = Math.cos(ry), sy = Math.sin(ry), cx = Math.cos(rx), sx = Math.sin(rx);
        const varre = ((t * .35) % 1.6) - .8, vivo = forma.vivo?.(t);
        ctx.clearRect(0, 0, W, H); ctx.globalCompositeOperation = "lighter";
        for (let i = 0; i < n; i++) {
          let x = forma.pontos[i * 3], y = forma.pontos[i * 3 + 1], z = forma.pontos[i * 3 + 2];
          if (vivo) { vivo(i, x, y, z, p); x = p[0]; y = p[1]; z = p[2]; }
          x = de[i * 3] + (x - de[i * 3]) * k; y = de[i * 3 + 1] + (y - de[i * 3 + 1]) * k; z = de[i * 3 + 2] + (z - de[i * 3 + 2]) * k;
          const x1 = x * cy + z * sy, z1 = -x * sy + z * cy, y1 = y * cx - z1 * sx, z2 = y * sx + z1 * cx;
          const f = 3.2 / (3.2 + z2), px = W / 2 + x1 * escala * f, py = H / 2 - y1 * escala * f;
          proj[i * 3] = px; proj[i * 3 + 1] = py; proj[i * 3 + 2] = f;
          const luz = Math.max(0, 1 - Math.abs(y - varre) * 6), al = Math.min(1, (.18 + (f - .75) * 1.2 + luz * .7) * (forma.alfa?.[i] ?? 1));
          const tam = (1.1 + f * 1.1) * (forma.tamanho?.[i] ?? 1);
          if ((forma.tamanho?.[i] ?? 1) >= 3) {   // a node: a lit bead with a halo, not a square
            ctx.fillStyle = `rgb(${rgb} / ${(al * .25).toFixed(3)})`; ctx.beginPath(); ctx.arc(px, py, tam * .9, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = `rgb(234 255 251 / ${Math.min(1, al + .2).toFixed(3)})`; ctx.beginPath(); ctx.arc(px, py, tam * .38, 0, Math.PI * 2); ctx.fill();
            continue;
          }
          ctx.fillStyle = luz > .5 || forma.alfa?.[i] > 1 ? `rgb(234 255 251 / ${al})` : `rgb(${rgb} / ${al})`;
          ctx.fillRect(px - tam / 2, py - tam / 2, tam, tam);
        }
        if (forma.ligacoes) {
          ctx.strokeStyle = `rgb(${rgb} / ${.16 * k})`; ctx.lineWidth = 1; ctx.beginPath();
          for (let j = 0; j < forma.ligacoes.length; j += 2) { const a = forma.ligacoes[j] * 3, z = forma.ligacoes[j + 1] * 3; ctx.moveTo(proj[a], proj[a + 1]); ctx.lineTo(proj[z], proj[z + 1]); }
          ctx.stroke();
          if (forma.pulsos && !reduzir.matches) {   // light running along some links
            ctx.fillStyle = "#eafffb";
            for (let j = 0; j < forma.ligacoes.length; j += 14) {
              const a = forma.ligacoes[j] * 3, z = forma.ligacoes[j + 1] * 3, f = (t * .8 + j * .013) % 1;
              ctx.fillRect(proj[a] + (proj[z] - proj[a]) * f - 1.2, proj[a + 1] + (proj[z + 1] - proj[a + 1]) * f - 1.2, 2.4, 2.4);
            }
          }
        }
        ctx.globalCompositeOperation = "source-over";
      };
    },
    globo(reg, caixa, b) {
      caixa.innerHTML = '<div class="jv-c-forma"></div>';
      const { ctx, W, H } = tela(caixa.firstChild), t0 = performance.now(), N = 1100, esfera = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) { const y = 1 - i / (N - 1) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963; esfera.set([Math.cos(th) * r, y, Math.sin(th) * r], i * 3); }
      const geo = (lat, lon) => { const la = lat * Math.PI / 180, lo = lon * Math.PI / 180; return [Math.cos(la) * Math.cos(lo), Math.sin(la), -Math.cos(la) * Math.sin(lo)]; };
      const marcas = b.pontos.map(p => ({ ...p, v: geo(p.lat, p.lon) }));
      const giro0 = marcas[0] ? Math.PI / 2 - marcas[0].lon * Math.PI / 180 : 0;   // the first point faces the viewer
      const arcos = b.ligar && marcas.length > 1 ? marcas.slice(1).map((m, i) => {
        const a = marcas[0].v, z = m.v, pts = [];
        const d = Math.hypot(a[0] - z[0], a[1] - z[1], a[2] - z[2]);
        for (let j = 0; j <= 40; j++) { const f = j / 40, v = [a[0] + (z[0] - a[0]) * f, a[1] + (z[1] - a[1]) * f, a[2] + (z[2] - a[2]) * f], l = Math.hypot(...v), h = 1 + Math.sin(f * Math.PI) * d * .12;
          pts.push(v.map(c => c / l * h)); }
        return { pts, atraso: 1 + i * .15 };
      }) : [];
      reg.quadro = t => {
        const rgb = acento(), e = (performance.now() - t0) / 1000, k = suave(e / 1.4), R = Math.min(W, H) * .42 * (.3 + .7 * k);
        const ry = giro0 + Math.sin(t * .15) * .5, cy = Math.cos(ry), sy = Math.sin(ry), rx = -.3, cx = Math.cos(rx), sx = Math.sin(rx);
        const P3 = v => { const x1 = v[0] * cy + v[2] * sy, z1 = -v[0] * sy + v[2] * cy, y1 = v[1] * cx - z1 * sx, z2 = v[1] * sx + z1 * cx; return [W / 2 + x1 * R, H / 2 - y1 * R, z2]; };
        ctx.clearRect(0, 0, W, H);
        const halo = ctx.createRadialGradient(W / 2, H / 2, R * .2, W / 2, H / 2, R * 1.15);
        halo.addColorStop(0, `rgb(${rgb} / .06)`); halo.addColorStop(1, `rgb(${rgb} / 0)`); ctx.fillStyle = halo; ctx.fillRect(0, 0, W, H);
        for (let i = 0; i < N; i++) {
          const [px, py, z] = P3(esfera.subarray(i * 3, i * 3 + 3)), frente = -z;
          ctx.fillStyle = `rgb(${rgb} / ${(Math.max(.05, .1 + frente * .55) * k).toFixed(3)})`;
          const tam = frente > 0 ? 1.8 : 1.1; ctx.fillRect(px - tam / 2, py - tam / 2, tam, tam);
        }
        ctx.strokeStyle = `rgb(${rgb} / .25)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(W / 2, H / 2, R, 0, Math.PI * 2); ctx.stroke();
        for (const a of arcos) {
          const f = suave((e - a.atraso) / 1); if (f <= 0) continue;
          const pts = a.pts.map(P3), ate = Math.round(f * (pts.length - 1));
          // the part of an arc behind the globe is not drawn
          const atras = q => q[2] > .02 && Math.hypot(q[0] - W / 2, q[1] - H / 2) < R;
          ctx.strokeStyle = `rgb(${rgb} / .7)`; ctx.lineWidth = 1.3; ctx.beginPath();
          for (let j = 0, solto = true; j <= ate; j++) { if (atras(pts[j])) { solto = true; continue; } ctx[solto ? "moveTo" : "lineTo"](pts[j][0], pts[j][1]); solto = false; }
          ctx.stroke();
          const q = pts[Math.floor(((t * .5 + a.atraso) % 1) * (pts.length - 1))];
          if (f >= 1 && !reduzir.matches && !atras(q)) {
            ctx.fillStyle = "#eafffb"; ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 10; ctx.beginPath(); ctx.arc(q[0], q[1], 2.2, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0; }
        }
        marcas.forEach((m, i) => {
          const [px, py, z] = P3(m.v.map(c => c * 1.01)); if (z > .15 || k < 1) return;
          const pul = .5 + .5 * Math.sin(t * 3 + i);
          ctx.fillStyle = i ? "#eafffb" : `rgb(${rgb})`; ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 12;
          ctx.beginPath(); ctx.arc(px, py, i ? 2.6 : 3.6, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
          ctx.strokeStyle = `rgb(${rgb} / ${(.6 - pul * .5).toFixed(2)})`; ctx.beginPath(); ctx.arc(px, py, 5 + pul * 7, 0, Math.PI * 2); ctx.stroke();
          if (m.nome) { ctx.fillStyle = "#ecfffa"; ctx.font = "600 11px 'Chakra Petch', sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle"; ctx.fillText(m.nome, px + 9, py); }
        });
      };
    },
    comparar(reg, caixa, b) {
      caixa.innerHTML = `<div class="jv-c-comparar">${b.lados.map((l, j) => `<div class="lado"><h3>${esc(l.nome)}</h3><ul>${l.itens.map((i, n) =>
        `<li style="animation-delay:${.4 + j * .25 + n * .14}s">${esc(i)}</li>`).join("")}</ul></div>`).join('<div class="vs"><i></i><b>VS</b><i></i></div>')}</div>`;
    },
    lista(reg, caixa, b) {
      caixa.innerHTML = `<ol class="jv-c-lista">${b.itens.map((i, n) => `<li style="animation-delay:${.35 + n * .2}s"><span>${String(n + 1).padStart(2, "0")}</span><p>${esc(i)}</p></li>`).join("")}</ol>`;
    },
    linha_tempo(reg, caixa, b) {
      caixa.innerHTML = `<div class="jv-c-tempo"><i class="trilho"><i class="luz"></i></i>${b.marcos.map((m, i) =>
        `<div class="marco${i % 2 ? " baixo" : ""}" style="--x:${(i / (b.marcos.length - 1) * 100).toFixed(2)}%;animation-delay:${.4 + i * .2}s"><span class="ponto"></span><time>${esc(m.quando)}</time><b>${esc(m.nome)}</b></div>`).join("")}</div>`;
    },
  };

  // ---- the 3D shapes: points in a unit box (vivo moves them every frame) ----
  const FORMAS = {
    esfera() { const n = 900, p = new Float32Array(n * 3); for (let i = 0; i < n; i++) { const y = 1 - i / (n - 1) * 2, r = Math.sqrt(1 - y * y), a = i * 2.399963; p.set([Math.cos(a) * r, y, Math.sin(a) * r], i * 3); } return { pontos: p }; },
    toro() { const A = 64, B = 18, p = new Float32Array(A * B * 3); let k = 0;
      for (let i = 0; i < A; i++) for (let j = 0; j < B; j++) { const u = i / A * Math.PI * 2, v = j / B * Math.PI * 2, r = .72 + .28 * Math.cos(v); p.set([Math.cos(u) * r, .28 * Math.sin(v), Math.sin(u) * r], k++ * 3); }
      return { pontos: p }; },
    helice() { const n = 170, p = [], lig = [];
      for (let i = 0; i < n; i++) { const t = i / (n - 1), a = t * Math.PI * 6, y = t * 2.2 - 1.1;
        p.push(Math.cos(a) * .5, y, Math.sin(a) * .5, Math.cos(a + Math.PI) * .5, y, Math.sin(a + Math.PI) * .5);
        if (i % 6 === 0) { const s = p.length / 3 - 2; for (let j = 1; j < 6; j++) { const f = j / 6; p.push(Math.cos(a) * .5 * (1 - 2 * f), y, Math.sin(a) * .5 * (1 - 2 * f)); } lig.push(s, s + 1); }
      }
      const pontos = new Float32Array(p); return { pontos, ligacoes: lig, pulsos: true }; },
    cubo() { const p = [], m = 9; for (let x = 0; x < m; x++) for (let y = 0; y < m; y++) for (let z = 0; z < m; z++) {
        const borda = [x, y, z].filter(c => c === 0 || c === m - 1).length; if (borda < 2 && Math.random() > .08) continue;
        p.push(x / (m - 1) * 1.3 - .65, y / (m - 1) * 1.3 - .65, z / (m - 1) * 1.3 - .65); }
      return { pontos: new Float32Array(p) }; },
    atomo() { const nucleo = 70, orb = 3, por = 140, n = nucleo + orb * por + orb, p = new Float32Array(n * 3), alfa = new Float32Array(n).fill(1), tamanho = new Float32Array(n).fill(1);
      for (let i = 0; i < nucleo; i++) { const r = .16 * Math.cbrt(Math.random()), a = Math.random() * 6.28, b = Math.acos(Math.random() * 2 - 1); p.set([r * Math.sin(b) * Math.cos(a), r * Math.cos(b), r * Math.sin(b) * Math.sin(a)], i * 3); alfa[i] = 1.4; tamanho[i] = 1.6; }
      const eixo = (o, a) => { const rx = [0, 1.05, -1.05][o], c = Math.cos(rx), s = Math.sin(rx), x = Math.cos(a) * .95, z = Math.sin(a) * .42; return [x, z * s, z * c]; };
      for (let o = 0; o < orb; o++) for (let i = 0; i < por; i++) { const ang = i / por * Math.PI * 2, [x, y, z] = eixo(o, ang), r = o * Math.PI / 3; p.set([x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r), z], (nucleo + o * por + i) * 3); alfa[nucleo + o * por + i] = .55; }
      const e0 = nucleo + orb * por; for (let o = 0; o < orb; o++) { alfa[e0 + o] = 2; tamanho[e0 + o] = 3.2; }
      return { pontos: p, alfa, tamanho, vivo: t => (i, x, y, z, out) => {
        if (i < e0) { out[0] = x; out[1] = y; out[2] = z; return; }
        const o = i - e0, [ex, ey, ez] = eixo(o, t * (1.4 + o * .4) + o * 2), r = o * Math.PI / 3;
        out[0] = ex * Math.cos(r) - ey * Math.sin(r); out[1] = ex * Math.sin(r) + ey * Math.cos(r); out[2] = ez; } }; },
    galaxia() { const n = 1300, p = new Float32Array(n * 3); for (let i = 0; i < n; i++) { const braco = i % 3, r = Math.pow(Math.random(), .7), a = braco * 2.094 + r * 4.2 + (Math.random() - .5) * .5 / (r + .2);
        p.set([Math.cos(a) * r, (Math.random() - .5) * .12 * (1 - r), Math.sin(a) * r], i * 3); } return { pontos: p }; },
    terreno() { const m = 38, p = new Float32Array(m * m * 3); for (let i = 0; i < m; i++) for (let j = 0; j < m; j++) p.set([i / (m - 1) * 2 - 1, 0, j / (m - 1) * 2 - 1], (i * m + j) * 3);
      return { pontos: p, escala: .5, vivo: t => (i, x, y, z, out) => { out[0] = x * 1.1; out[2] = z * 1.1;
        out[1] = (Math.sin(x * 3.2 + t * 1.6) * .16 + Math.cos(z * 2.6 - t * 1.1) * .12 + Math.sin(Math.hypot(x, z) * 6 - t * 2.4) * .06) - .1; } }; },
    neural() { const camadas = [4, 7, 7, 3], p = [], lig = [], idx = [];
      camadas.forEach((q, c) => { const linha = []; for (let i = 0; i < q; i++) { const y = q > 1 ? i / (q - 1) * 1.5 - .75 : 0; p.push(c / (camadas.length - 1) * 2 - 1, y * .9, Math.sin(i * 1.7 + c) * .25); linha.push(p.length / 3 - 1); } idx.push(linha); });
      for (let c = 0; c < idx.length - 1; c++) for (const a of idx[c]) for (const z of idx[c + 1]) lig.push(a, z);
      const n = p.length / 3, tamanho = new Float32Array(n).fill(4.2), alfa = new Float32Array(n).fill(1.5);
      return { pontos: new Float32Array(p), ligacoes: lig, pulsos: true, tamanho, alfa, balanco: true }; },
    plexo() { const n = 140, p = new Float32Array(n * 3), lig = [];
      for (let i = 0; i < n; i++) { const r = .55 + Math.random() * .45, a = Math.random() * 6.28, b = Math.acos(Math.random() * 2 - 1); p.set([r * Math.sin(b) * Math.cos(a), r * Math.cos(b), r * Math.sin(b) * Math.sin(a)], i * 3); }
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) if (Math.hypot(p[i * 3] - p[j * 3], p[i * 3 + 1] - p[j * 3 + 1], p[i * 3 + 2] - p[j * 3 + 2]) < .36) lig.push(i, j);
      return { pontos: p, ligacoes: lig, pulsos: true, tamanho: new Float32Array(n).fill(1.8) }; },
  };

  // ---- the scene runner ----
  let atual = null;
  function explicar(cena) {
    if (!window.jarvisApresentacao?.palco || !window.jarvisStage?.adicionar) throw new Error("a tela ainda não carregou");
    const c = limpar(cena), paginas = paginar(c.passos), palco = P();
    const id = palco.comecar();
    let n = 0;
    const passos = c.passos.map(p => ({
      limpar: p.limpar, fala: p.fala, foco: p.blocos[0] ? `cena-${n + (p.blocos[0].tipo === "titulo" && p.blocos[1] ? 1 : 0)}` : null,
      mostrar: p.blocos.map(b => {
        const nome = `cena-${n++}`, ordem = String(n).padStart(2, "0");
        if (b.tipo === "holograma") return () => {   // a model card, not a panel
          const { x, y, w, h } = b.caixa, W = innerWidth, H = innerHeight;
          // without a title of its own, the hologram is named after the scene ("fecha o foguete")
          const it = window.jarvisStage.holograma({ ...b, titulo: b.titulo || c.titulo }, { x: (x + w / 2) * W, y: (y + h / 2) * H, tam: Math.min(w * W, h * H) * 1.05 });
          return palco.anexar(nome, it);
        };
        return () => {
          const { x, y, w, h } = b.caixa, esquema = !COM_NUMEROS.has(b.tipo);
          const reg = palco.painel(nome, { cod: `${ordem} · ${NOME[b.tipo]}`, titulo: b.titulo || (b.tipo === "titulo" ? b.texto : NOME[b.tipo][0] + NOME[b.tipo].slice(1).toLowerCase()),
            x, y, w, h, classe: `jv-cena jv-cena-${b.tipo}`, fonte: esquema ? "ESQUEMA" : b.fonte ? "FONTE · " + b.fonte.toUpperCase() : "",
            ilustrativo: !esquema && (b.ilustrativo || !b.fonte) });
          const caixa = reg.el.querySelector(".jv-h-corpo");
          setTimeout(() => { if (reg.el.isConnected && !caixa.childElementCount) try { BLOCOS[b.tipo](reg, caixa, b); } catch (e) { caixa.textContent = "—"; console.error(e); } }, 320);
          return reg;
        };
      }),
    }));
    atual = c.titulo || "cena";
    palco.roteiro(id, passos);
    return { explicando: true, cena: atual, blocos: n, paginas, ...(c.ignorados.length ? { ignorados: c.ignorados } : {}) };
  }

  // ---- examples (the E key, one after the other) ----
  const EXEMPLOS = {
    mcp: { titulo: "Como funciona o MCP", passos: [
      { fala: "MCP é o jeito de um assistente usar ferramentas de fora, sempre do mesmo modo.",
        blocos: [{ tipo: "titulo", texto: "Model Context Protocol", subtitulo: "Um padrão para a IA usar ferramentas e dados de outros sistemas" }] },
      { fala: "No centro está o assistente. Cada sistema vira um servidor MCP ligado a ele.",
        blocos: [{ tipo: "rede", titulo: "Um assistente, vários servidores", centro: "Zé", nos: [{ nome: "n8n", texto: "fluxos" }, { nome: "GitHub", texto: "código" },
          { nome: "Gmail", texto: "e-mails" }, { nome: "Planilhas", texto: "dados" }, { nome: "Banco", texto: "SQL" }, { nome: "Navegador", texto: "páginas" }] }] },
      { fala: "Um pedido passa por cinco etapas: você pede, o cliente escolhe a ferramenta, o servidor executa e a resposta volta.",
        blocos: [{ tipo: "etapas", titulo: "O caminho de um pedido", etapas: [{ nome: "Pedido", texto: "você fala" }, { nome: "Cliente MCP", texto: "escolhe a ferramenta" },
          { nome: "Servidor MCP", texto: "traduz o pedido" }, { nome: "Ferramenta", texto: "executa de verdade" }, { nome: "Resposta", texto: "volta para a IA" }] }] },
      { fala: "A vantagem: liga uma vez e qualquer assistente compatível usa.",
        blocos: [{ tipo: "lista", titulo: "Por que isso importa", itens: ["Uma integração serve para vários assistentes", "As permissões ficam no servidor", "Ferramentas novas sem mexer no assistente"] }] },
    ] },
    som: { titulo: "Como o som viaja", passos: [
      { fala: "Som é vibração: o ar é empurrado e puxado, e essa onda chega no seu ouvido.",
        blocos: [{ tipo: "titulo", texto: "Como o som viaja", subtitulo: "Ondas de pressão passando de molécula em molécula" }] },
      { fala: "Cada som é uma onda. Quando duas se encontram, elas se somam.",
        blocos: [{ tipo: "onda", titulo: "Duas notas e a soma", ondas: [{ nome: "Grave", frequencia: 1, amplitude: .9 }, { nome: "Aguda", frequencia: 3, amplitude: .5 }], soma: true }] },
      { fala: "No ar, a onda se espalha como ondulações numa superfície.",
        blocos: [{ tipo: "forma3d", titulo: "A onda se espalhando", forma: "terreno", legenda: "Cada ponto sobe e desce; a forma é que viaja" }] },
      { fala: "No ar a vinte graus ele anda a 343 metros por segundo. Na água, mais de quatro vezes mais rápido.",
        blocos: [{ tipo: "numero", titulo: "Velocidade no ar", valor: 343, unidade: "m/s", rotulo: "ar a 20 °C", fonte: "valor de referência da física" },
          { tipo: "barras", titulo: "Velocidade por meio", unidade: "m/s", fonte: "valores de referência", itens: [{ nome: "Ar (20 °C)", valor: 343 }, { nome: "Água (25 °C)", valor: 1497 }, { nome: "Aço", valor: 5960 }] }] },
    ] },
    dna: { titulo: "O que é o DNA", passos: [
      { fala: "O DNA é a receita do corpo, escrita numa escada torcida.",
        blocos: [{ tipo: "titulo", texto: "DNA", subtitulo: "A dupla hélice que guarda as instruções da vida" }, { tipo: "forma3d", titulo: "A dupla hélice", forma: "helice", legenda: "Duas fitas ligadas por pares de bases" }] },
      { fala: "A informação sai do DNA, vira RNA e o RNA vira proteína.",
        blocos: [{ tipo: "etapas", titulo: "Do gene à proteína", etapas: [{ nome: "DNA", texto: "o gene guardado" }, { nome: "Transcrição", texto: "cópia em RNA" }, { nome: "Tradução", texto: "no ribossomo" }, { nome: "Proteína", texto: "faz o trabalho" }] }] },
      { fala: "O genoma humano tem cerca de três bilhões de pares de bases.",
        blocos: [{ tipo: "numero", titulo: "Tamanho do genoma", valor: 3100000000, unidade: "pares", rotulo: "pares de bases no genoma humano", fonte: "Projeto Genoma Humano" }] },
    ] },
    ia: { titulo: "Como uma rede neural aprende", passos: [
      { fala: "Uma rede neural são camadas de números ligados entre si.",
        blocos: [{ tipo: "titulo", texto: "Redes neurais", subtitulo: "Camadas que transformam entrada em resposta" }, { tipo: "forma3d", titulo: "Entrada, camadas e saída", forma: "neural", legenda: "Cada ligação tem um peso que o treino ajusta" }] },
      { fala: "Treinar é repetir: ela erra, mede o erro e ajusta os pesos. O erro vai caindo.",
        blocos: [{ tipo: "linha", titulo: "Erro durante o treino", ilustrativo: true, pontos: [9.1, 6.4, 4.9, 3.7, 3, 2.4, 2.05, 1.8, 1.62, 1.5, 1.43, 1.4].map((v, i) => ({ rotulo: `ép ${i + 1}`, valor: v })) },
          { tipo: "comparar", titulo: "Antes e depois do treino", lados: [{ nome: "Antes", itens: ["Pesos aleatórios", "Respostas ao acaso"] }, { nome: "Depois", itens: ["Pesos ajustados", "Acerta o padrão"] }] }] },
      { fala: "E onde o modelo roda: perto de quem usa, para responder mais rápido.",
        blocos: [{ tipo: "globo", titulo: "Onde as respostas saem", pontos: [{ nome: "São Paulo", lat: -23.55, lon: -46.63 }, { nome: "Virgínia", lat: 38.9, lon: -77.4 },
          { nome: "Dublin", lat: 53.35, lon: -6.26 }, { nome: "Tóquio", lat: 35.68, lon: 139.7 }] },
          { tipo: "rosca", titulo: "Onde vai o tempo de uma resposta", ilustrativo: true, centro: "1,4 s", fatias: [{ nome: "Pensar", valor: 62 }, { nome: "Rede", valor: 23 }, { nome: "Voz", valor: 15 }] },
          { tipo: "linha_tempo", titulo: "Marcos", marcos: [{ quando: "1958", nome: "Perceptron" }, { quando: "1986", nome: "Retropropagação" }, { quando: "2012", nome: "AlexNet" }, { quando: "2017", nome: "Transformer" }] }] },
    ] },
  };
  EXEMPLOS.solar = { titulo: "O sistema solar em 3D", passos: [
    { fala: "Este é o sistema solar em holograma. Pegue com a pinça e gire para ver de todos os lados.",
      blocos: [{ tipo: "titulo", texto: "Sistema solar", subtitulo: "Holograma 3D: pinça para girar, duas mãos para ampliar" },
        { tipo: "holograma", titulo: "Sistema solar", pecas: [
          { forma: "esfera", nome: "Sol", rotulo: "Sol", cor: "#ffc955", tam: 1.6, anim: "pulsar", velocidade: .6 },
          { forma: "esfera", nome: "Mercúrio", cor: "#cfd8df", tam: .18, orbita: { raio: 1.5, velocidade: 2.4 } },
          { forma: "esfera", nome: "Vênus", cor: "#ffd38a", tam: .3, orbita: { raio: 2.1, velocidade: 1.6 } },
          { forma: "esfera", nome: "Terra", rotulo: "Terra", cor: "#4aa3ff", tam: .34, orbita: { raio: 2.9, velocidade: 1.1 }, anim: "girar",
            filhos: [{ forma: "esfera", nome: "Lua", cor: "#e6eef2", tam: .1, orbita: { raio: .38, velocidade: 4, trilha: false } }] },
          { forma: "esfera", nome: "Marte", cor: "#ff5a4f", tam: .24, orbita: { raio: 3.6, velocidade: .8 } },
          { forma: "esfera", nome: "Saturno", rotulo: "Saturno", cor: "#e8c88a", tam: .62, orbita: { raio: 5, velocidade: .4, inclinacao: 6 },
            filhos: [{ forma: "anel", cor: "#f1dcae", tam: 1.35, rot: [22, 0, 0], espessura: .2 }] },
          { forma: "particulas", nome: "Estrelas", cor: "#bffff2", tam: 13, quantidade: 900 },
        ] }] },
  ] };
  EXEMPLOS.agua = { titulo: "A molécula de água", passos: [
    { fala: "A molécula de água tem um oxigênio no meio e dois hidrogênios, num ângulo de cerca de cento e quatro graus.",
      blocos: [{ tipo: "holograma", titulo: "H₂O", pecas: [
        { forma: "esfera", nome: "Oxigênio", rotulo: "O", cor: "#ff5a4f", tam: 1, anim: "pulsar", velocidade: .5 },
        { forma: "ligacao", cor: "#cfd8df", de: [0, 0, 0], ate: [-.95, -.75, 0], espessura: .3 },
        { forma: "ligacao", cor: "#cfd8df", de: [0, 0, 0], ate: [.95, -.75, 0], espessura: .3 },
        { forma: "esfera", nome: "Hidrogênio", rotulo: "H", cor: "#f4fbff", tam: .6, pos: [-.95, -.75, 0] },
        { forma: "esfera", nome: "Hidrogênio", rotulo: "H", cor: "#f4fbff", tam: .6, pos: [.95, -.75, 0] },
        { forma: "particulas", cor: "#5ff2e6", tam: 3.4, quantidade: 500 },
      ] }, { tipo: "numero", titulo: "Ângulo entre as ligações", valor: 104.5, unidade: "°", rotulo: "H-O-H", fonte: "valor de referência da química" }] },
  ] };
  let proximo = 0;
  const exemplo = nome => explicar(EXEMPLOS[nome] || EXEMPLOS[Object.keys(EXEMPLOS)[proximo++ % Object.keys(EXEMPLOS).length]]);

  addEventListener("keydown", e => {
    if ((e.key !== "e" && e.key !== "E") || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest?.("input, textarea, [contenteditable], #jv-teclado")) return;
    try { exemplo(); } catch (_) {}
  });
  const pedido = new URLSearchParams(location.search).get("cena");
  if (pedido) (function quandoPronto(n = 0) {
    if (window.jarvisStage?.anel?.() && window.jarvisApresentacao) { try { exemplo(pedido); } catch (e) { console.error(e); } }
    else if (n < 100) setTimeout(() => quandoPronto(n + 1), 200);
  })();
  window.jarvisCenas = { explicar, exemplo, limpar, get exemplos() { return Object.keys(EXEMPLOS); }, tipos: Object.keys(TIPOS), formas: Object.keys(FORMAS),
    get atual() { return window.jarvisApresentacao?.apresentando ? atual : null; } };
})();
