// SPDX-License-Identifier: AGPL-3.0-or-later
// Real maps for the Zé's scenes (ADR 0050). A language model cannot draw Brazil from memory, so
// it never draws: the "mapa" block names only what to show (the base map, the states or
// countries to light up, their values, cities with lat/lon) and the contours come from
// jarvis-mapas.json (IBGE state mesh; Natural Earth 1:50m countries), made by
// zervis/imersivo/gerar_mapas.py. Two looks: a holographic panel (2D canvas, here) and the same
// map in relief (three.js extrusions, height by value) inside a Barehands model card, so the
// pinch lock turns it and two hands scale it.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const num = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  const suave = k => 1 - Math.pow(1 - Math.max(0, Math.min(1, k)), 3);
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)");
  const acento = () => getComputedStyle(document.documentElement).getPropertyValue("--jv-acento-rgb").trim() || "143 240 228";
  const chave = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/^(o |a |os |as )?(estado|pais|republica) d[aeo]s? /, "").replace(/[^a-z0-9]+/g, " ").trim();
  const curto = v => { const a = Math.abs(v); return a >= 1e9 ? num.format(v / 1e9) + " bi" : a >= 1e6 ? num.format(v / 1e6) + " mi" : a >= 1e4 ? num.format(v / 1e3) + " mil" : num.format(v); };

  // ---- the data: loaded once, early, so a scene can be checked before it is drawn ----
  let dados = null, carregando = null;
  function decodificar(r) {
    const polys = r.p.map(poly => poly.map(anel => {
      const xy = new Float64Array(anel.length); let x = 0, y = 0;
      for (let i = 0; i < anel.length; i += 2) { x += anel[i]; y += anel[i + 1]; xy[i] = x / 100; xy[i + 1] = y / 100; }
      return xy;
    }));
    // the bounding box of each polygon and of the biggest one (framing ignores far islands)
    let maior = null, area = -1;
    const caixas = polys.map(poly => { const a = poly[0], c = [Infinity, Infinity, -Infinity, -Infinity];
      for (let i = 0; i < a.length; i += 2) { c[0] = Math.min(c[0], a[i]); c[1] = Math.min(c[1], a[i + 1]); c[2] = Math.max(c[2], a[i]); c[3] = Math.max(c[3], a[i + 1]); }
      const s = (c[2] - c[0]) * (c[3] - c[1]); if (s > area) { area = s; maior = c; } return c; });
    return { id: r.id, nome: r.nome, grupo: r.grupo, outros: r.outros || [], centro: r.c, polys, caixas, caixa: maior };
  }
  // what people call a country that its official names miss
  const APELIDOS = { eua: "US", usa: "US", "estados unidos da america": "US", america: "US", inglaterra: "GB", "gra bretanha": "GB",
    escocia: "GB", holanda: "NL", tchequia: "CZ", "republica tcheca": "CZ", emirados: "AE", "coreia": "KR", russia: "RU", china: "CN" };
  const GRUPOS = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "america_do_sul", "america_do_norte", "europa", "africa", "asia", "oceania"];
  const GRUPOS_BR = { norte: "Norte", nordeste: "Nordeste", "centro oeste": "Centro-Oeste", sudeste: "Sudeste", sul: "Sul" };
  // continent frames by hand: Natural Earth puts all of Russia in Europe and French Guiana in France
  const QUADROS = { mundo: [-170, -57, 180, 83], america_do_sul: [-82, -56, -34, 13], america_do_norte: [-168, 7, -52, 72],
    america_central: [-118, 6, -59, 33], europa: [-25, 34, 45, 71], africa: [-18, -35, 52, 38], asia: [25, -11, 150, 56],
    oriente_medio: [25, 11, 63, 42], oceania: [110, -48, 180, 0] };
  const CONTINENTE = { "america do sul": "america_do_sul", "america latina": "america_do_sul", "america do norte": "america_do_norte",
    "america central": "america_central", caribe: "america_central", europa: "europa", africa: "africa", asia: "asia",
    "oriente medio": "oriente_medio", oceania: "oceania", mundo: "mundo", planeta: "mundo", world: "mundo" };
  function indexar(regioes, comApelidos) {
    const i = new Map();
    for (const r of regioes) for (const n of [r.id, r.nome, ...r.outros]) if (!i.has(chave(n))) i.set(chave(n), r);
    if (comApelidos) for (const [n, id] of Object.entries(APELIDOS)) { const r = regioes.find(x => x.id === id); if (r && !i.has(n)) i.set(n, r); }
    return i;
  }
  function carregar() {
    return carregando ||= fetch("jarvis-mapas.json").then(r => { if (!r.ok) throw new Error("jarvis-mapas.json: " + r.status); return r.json(); })
      .then(d => {
        const brasil = d.brasil.map(decodificar), mundo = d.mundo.map(decodificar);
        dados = { fontes: d.fontes, brasil: { regioes: brasil, indice: indexar(brasil) }, mundo: { regioes: mundo, indice: indexar(mundo, true) } };
        return dados;
      }).catch(e => { carregando = null; throw e; });
  }
  setTimeout(() => carregar().catch(() => {}), 800);

  // ---- what the block asks for, resolved against the real names ----
  function resolver(b) {
    const reg = chave(b.regiao), grupoBr = GRUPOS_BR[reg];
    const achaBr = n => dados.brasil.indice.get(chave(n)) || (GRUPOS_BR[chave(n)] && dados.brasil.regioes.filter(r => r.grupo === GRUPOS_BR[chave(n)]));
    const achaMundo = n => dados.mundo.indice.get(chave(n)) || (CONTINENTE[chave(n)] && dados.mundo.regioes.filter(r => r.grupo === CONTINENTE[chave(n)]));
    // the base: the states of Brazil, or the countries of the world
    let base = reg === "brasil" || grupoBr ? "brasil" : reg ? "mundo" : null;
    if (!base) base = b.destaques.length && b.destaques.every(d => achaBr(d.nome)) ? "brasil" : b.destaques.length ? "mundo"
      : b.pontos.length && b.pontos.every(p => p.lat < 6 && p.lat > -34 && p.lon > -74 && p.lon < -34) ? "brasil" : "mundo";
    const acha = base === "brasil" ? achaBr : achaMundo, regioes = dados[base].regioes;
    const destaques = new Map(), naoAchei = [];
    for (const d of b.destaques) {
      const r = acha(d.nome);
      if (!r) { naoAchei.push(d.nome); continue; }
      for (const x of Array.isArray(r) ? r : [r]) if (!destaques.has(x.id)) destaques.set(x.id, { ...d, nome: Array.isArray(r) ? x.nome : d.rotulo || x.nome });
    }
    // the frame: a fixed one for continents and the world, else the place itself with some room around
    const juntar = cs => cs.reduce((a, c) => [Math.min(a[0], c[0]), Math.min(a[1], c[1]), Math.max(a[2], c[2]), Math.max(a[3], c[3])], [Infinity, Infinity, -Infinity, -Infinity]);
    const folga = (c, f, min) => { const w = Math.max(min, (c[2] - c[0]) * (1 + f)), h = Math.max(min * .6, (c[3] - c[1]) * (1 + f)), x = (c[0] + c[2]) / 2, y = (c[1] + c[3]) / 2;
      return [x - w / 2, y - h / 2, x + w / 2, y + h / 2]; };
    let quadro;
    if (base === "brasil") quadro = juntar(regioes.filter(r => !grupoBr || r.grupo === grupoBr).map(r => r.caixa));
    else if (QUADROS[CONTINENTE[reg]]) quadro = QUADROS[CONTINENTE[reg]];
    else if (reg && dados.mundo.indice.get(reg)) quadro = folga(dados.mundo.indice.get(reg).caixa, .5, 10);
    else {
      const cs = [...destaques.keys()].map(id => regioes.find(r => r.id === id).caixa).concat(b.pontos.map(p => [p.lon, p.lat, p.lon, p.lat]));
      quadro = cs.length ? folga(juntar(cs), .35, 18) : QUADROS.mundo;
    }
    quadro = [Math.max(-180, quadro[0]), Math.max(-60, quadro[1]), Math.min(180, quadro[2]), Math.min(85, quadro[3])];
    const valores = [...destaques.values()].map(d => d.valor).filter(v => v != null);
    return { base, regioes, destaques, naoAchei, quadro, fonte: dados.fontes[base], valores,
      min: Math.min(...valores), max: Math.max(...valores) };
  }
  // the names the screen could not find, so the Zé hears it in the tool result
  function conferir(b) { if (!dados) return []; try { return resolver(b).naoAchei; } catch (_) { return []; } }
  const fonteDe = b => dados ? (dados.fontes[resolver(b).base] || "").split(",")[0] : "";

  // ---- projection: Equal Earth for the whole world, a local plate carrée for the rest ----
  const A1 = 1.340264, A2 = -.081106, A3 = .000893, A4 = .003796, M = Math.sqrt(3) / 2;
  function terra(lon, lat) {
    const l = lon * Math.PI / 180, th = Math.asin(M * Math.sin(lat * Math.PI / 180)), t2 = th * th, t6 = t2 * t2 * t2;
    return [2 * Math.sqrt(3) * l * Math.cos(th) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1)), A4 * t6 * t2 * th + A3 * t6 * th + A2 * t2 * th + A1 * th];
  }
  // fits the frame in w×h; returns lon/lat -> [x, y] with y down, and the scale
  function projetor(q, w, h, margem) {
    const mundo = q[2] - q[0] > 150, k = Math.cos((q[1] + q[3]) / 2 * Math.PI / 180);
    const base = mundo ? terra : (lon, lat) => [lon * Math.PI / 180 * k, lat * Math.PI / 180];
    const cantos = mundo ? [[q[0], 0], [q[2], 0], [0, q[1]], [0, q[3]], [q[0], q[1]], [q[2], q[3]]].map(([a, b]) => base(a, b)) : [base(q[0], q[1]), base(q[2], q[3])];
    const x0 = Math.min(...cantos.map(c => c[0])), x1 = Math.max(...cantos.map(c => c[0])), y0 = Math.min(...cantos.map(c => c[1])), y1 = Math.max(...cantos.map(c => c[1]));
    const s = Math.min((w - margem * 2) / (x1 - x0), (h - margem * 2) / (y1 - y0)), ox = (w - (x1 - x0) * s) / 2, oy = (h - (y1 - y0) * s) / 2;
    return { p: (lon, lat) => { const [x, y] = base(lon, lat); return [ox + (x - x0) * s, oy + (y1 - y) * s]; }, s };
  }
  const dentro = (c, q, f = .15) => { const w = (q[2] - q[0]) * f, h = (q[3] - q[1]) * f; return c[2] >= q[0] - w && c[0] <= q[2] + w && c[3] >= q[1] - h && c[1] <= q[3] + h; };
  // value -> 0..1, so the strongest is the brightest; a highlight without a value is full. Skewed
  // positive data (São Paulo has 70 times Roraima) goes on a square-root scale, or all but one fade.
  const forca = (r, d) => {
    if (d?.valor == null) return 1;
    if (!(r.max > r.min)) return 1;
    const raiz = r.min >= 0 && r.max > r.min * 8, f = v => raiz ? Math.sqrt(v) : v;
    return (f(d.valor) - f(r.min)) / (f(r.max) - f(r.min));
  };

  // ---- the holographic panel ----
  function desenhar(reg, caixa, b, util) {
    caixa.innerHTML = '<div class="jv-c-mapa"><span class="carregando">CARREGANDO CONTORNOS</span></div>';
    const alvo = caixa.firstChild;
    carregar().then(() => { if (alvo.isConnected) plano(reg, alvo, b, util); })
      .catch(e => { alvo.textContent = "mapa indisponível"; console.error(e); });
  }
  function plano(reg, alvo, b, { dica, semDica }) {
    alvo.textContent = "";
    const r = resolver(b), dpr = Math.min(devicePixelRatio || 1, 2), W = Math.max(1, alvo.clientWidth), H = Math.max(1, alvo.clientHeight);
    const cv = document.createElement("canvas"); cv.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
    cv.width = W * dpr; cv.height = H * dpr; alvo.appendChild(cv);
    const ctx = cv.getContext("2d"); ctx.scale(dpr, dpr);
    const legenda = r.valores.length > 1 ? 30 : 0, { p } = projetor(r.quadro, W, H - legenda, 12);
    const comDestaque = r.destaques.size > 0, terraToda = new Path2D();
    const formas = r.regioes.filter(g => g.caixas.some(c => dentro(c, r.quadro))).map(g => {
      const path = new Path2D();
      g.polys.forEach((poly, i) => { if (!dentro(g.caixas[i], r.quadro, .4)) return;
        for (const a of poly) { for (let j = 0; j < a.length; j += 2) { const [x, y] = p(a[j], a[j + 1]); j ? path.lineTo(x, y) : path.moveTo(x, y); } path.closePath(); } });
      terraToda.addPath(path);
      const [cx, cy] = p(...g.centro), [ax, ay] = p(g.caixa[0], g.caixa[3]), [bx, by] = p(g.caixa[2], g.caixa[1]);
      return { g, path, cx, cy, larg: bx - ax, alt: by - ay, d: r.destaques.get(g.id), atraso: .15 + Math.max(0, Math.min(1, cx / W)) * .9 };
    });
    const pontos = b.pontos.map(q => ({ ...q, xy: p(q.lon, q.lat) }));
    const arcos = b.ligar && pontos.length > 1 ? pontos.slice(1).map((z, i) => {
      const [ax, ay] = pontos[0].xy, [zx, zy] = z.xy, d = Math.hypot(zx - ax, zy - ay);
      return { a: [ax, ay], z: [zx, zy], c: [(ax + zx) / 2, (ay + zy) / 2 - d * .3], atraso: 2.2 + i * .15 };
    }) : [];
    const brasil = r.base === "brasil", poucos = r.destaques.size <= 6;
    const rotulos = formas.filter(f => brasil ? true : f.d ? r.destaques.size <= 14 : !comDestaque && f.larg > 48)
      .map(f => ({ f, txt: f.d ? (brasil && !poucos ? f.g.id : f.d.nome) : brasil ? f.g.id : f.g.nome, val: f.d?.valor != null ? curto(f.d.valor) : "" }));
    // a label that does not fit its place goes to the side of the map, on a leader line
    // (the map's edges on screen: a framed continent runs past the panel on both sides)
    const esq = Math.max(0, Math.min(...formas.map(f => f.cx - f.larg / 2))), dir = Math.min(W, Math.max(...formas.map(f => f.cx + f.larg / 2)));
    const fonte = f => f.d ? "600 11px 'Chakra Petch', sans-serif" : `500 ${brasil ? 8.5 : 9}px 'JetBrains Mono', monospace`;
    const lados = { d: [], e: [] };
    for (const l of rotulos) {
      ctx.font = fonte(l.f); const w = ctx.measureText(l.txt).width, alto = l.val ? 24 : 12;
      if (l.f.larg * .85 > w && l.f.alt * .8 > alto) { l.x = l.f.cx; l.y = l.f.cy; continue; }
      const direita = l.f.cx > (esq + dir) / 2 ? dir + 16 + w < W : esq - 16 - w < 0;
      (direita ? lados.d : lados.e).push(l); l.lado = direita ? 1 : -1; l.y = l.f.cy; l.alto = alto;
      // to the free margin when there is one, else just beside the place
      l.x = direita ? (dir + 16 + w < W ? dir + 16 : Math.min(W - w - 6, l.f.cx + 26)) : (esq - 16 - w > 0 ? esq - 16 : Math.max(w + 6, l.f.cx - 26));
    }
    for (const fila of Object.values(lados)) {
      fila.sort((a, b) => a.y - b.y);
      for (let i = 1; i < fila.length; i++) fila[i].y = Math.max(fila[i].y, fila[i - 1].y + (fila[i - 1].alto + fila[i].alto) / 2 + 2);
      const sobra = fila.length ? fila.at(-1).y + fila.at(-1).alto / 2 - (H - legenda - 4) : 0;
      if (sobra > 0) for (const l of fila) l.y = Math.max(l.alto / 2 + 2, l.y - sobra);
    }
    // a city on top of its state's name (Berlin on Germany) pushes the name down a line
    for (const l of rotulos) if (!l.lado && pontos.some(q => Math.abs(q.xy[0] - l.x) < 40 && Math.abs(q.xy[1] - l.y) < 12)) l.y += 16;
    const t0 = performance.now(), FIM = 2.4;
    let fixo = null;   // the finished map, drawn once to a bitmap: the live layer only adds light
    const fundo = (c, rgb, k) => {
      c.strokeStyle = `rgb(${rgb} / .05)`; c.lineWidth = 1; c.setLineDash([2, 4]);
      const passo = r.quadro[2] - r.quadro[0] > 60 ? 15 : 5;
      for (let lon = Math.ceil(r.quadro[0] / passo) * passo; lon <= r.quadro[2]; lon += passo) { c.beginPath(); for (let lat = r.quadro[1]; lat <= r.quadro[3]; lat += 2) { const [x, y] = p(lon, lat); lat === r.quadro[1] ? c.moveTo(x, y) : c.lineTo(x, y); } c.stroke(); }
      for (let lat = Math.ceil(r.quadro[1] / passo) * passo; lat <= r.quadro[3]; lat += passo) { c.beginPath(); for (let lon = r.quadro[0]; lon <= r.quadro[2]; lon += 2) { const [x, y] = p(lon, lat); lon === r.quadro[0] ? c.moveTo(x, y) : c.lineTo(x, y); } c.stroke(); }
      c.setLineDash([]);
      for (const f of formas) {
        const k1 = k(f), forte = f.d ? forca(r, f.d) : 0; if (k1 <= 0) continue;
        c.fillStyle = f.d ? `rgb(${rgb} / ${((.07 + .78 * forte) * k1).toFixed(3)})` : `rgb(${rgb} / ${((comDestaque ? .035 : .09) * k1).toFixed(3)})`;
        c.fill(f.path, "evenodd");
        c.strokeStyle = f.d ? `rgb(234 255 251 / ${(.85 * k1).toFixed(3)})` : `rgb(${rgb} / ${((comDestaque ? .28 : .6) * k1).toFixed(3)})`;
        c.lineWidth = f.d ? 1.3 : .8; c.stroke(f.path);
      }
    };
    const textos = (c, rgb, k) => {
      c.textBaseline = "middle";
      for (const { f, txt, val, x, y, lado } of rotulos) {
        const a = k; if (a <= 0) continue;
        c.textAlign = lado ? (lado > 0 ? "left" : "right") : "center";
        if (lado) {   // the leader line, from the place to its label
          c.strokeStyle = `rgb(${rgb} / ${(.4 * a).toFixed(3)})`; c.lineWidth = 1; c.beginPath(); c.moveTo(f.cx, f.cy);
          c.lineTo(x - lado * 10, y); c.lineTo(x - lado * 3, y); c.stroke();
          c.fillStyle = `rgb(${rgb} / ${a})`; c.beginPath(); c.arc(f.cx, f.cy, 1.6, 0, Math.PI * 2); c.fill();
        }
        // a dark rim under each text, so it reads on a bright state as well as on a dark one
        c.font = fonte(f); c.lineJoin = "round"; c.lineWidth = 3; c.strokeStyle = `rgb(2 16 15 / ${(.75 * a).toFixed(3)})`;
        c.strokeText(txt, x, y - (val ? 6 : 0));
        c.fillStyle = f.d ? `rgb(236 255 250 / ${a})` : `rgb(${rgb} / ${(.55 * a).toFixed(3)})`;
        c.fillText(txt, x, y - (val ? 6 : 0));
        if (val) { c.font = "700 10px 'JetBrains Mono', monospace"; c.strokeText(val, x, y + 7); c.fillStyle = `rgb(${rgb} / ${a})`; c.fillText(val, x, y + 7); }
      }
      if (legenda) {   // the scale, so the brightness reads as a number
        const x = 12, y = H - legenda + 8, w = Math.min(180, W * .4), g = c.createLinearGradient(x, 0, x + w, 0);
        g.addColorStop(0, `rgb(${rgb} / .07)`); g.addColorStop(1, `rgb(${rgb} / .85)`);
        c.fillStyle = g; c.fillRect(x, y, w, 6);
        c.font = "500 9px 'JetBrains Mono', monospace"; c.fillStyle = `rgb(${rgb} / ${(.8 * k).toFixed(3)})`; c.textBaseline = "top";
        c.textAlign = "left"; c.fillText(curto(r.min), x, y + 10); c.textAlign = "right"; c.fillText(curto(r.max) + (b.unidade ? " " + b.unidade : ""), x + w, y + 10);
      }
      c.textAlign = "right"; c.textBaseline = "bottom"; c.font = "500 8px 'JetBrains Mono', monospace"; c.fillStyle = `rgb(${rgb} / ${(.35 * k).toFixed(3)})`;
      c.fillText("CONTORNOS · " + (r.fonte || "").split(",")[0].toUpperCase(), W - 6, H - 4);
    };
    reg.quadro = t => {
      const rgb = acento(), e = (performance.now() - t0) / 1000;
      ctx.clearRect(0, 0, W, H);
      if (e < FIM || !fixo) {
        fundo(ctx, rgb, f => suave((e - f.atraso) / .6)); textos(ctx, rgb, suave((e - 1.4) / .6));
        if (e < FIM - .3) {   // the scan line that draws the map, left to right
          const x = (e - .15) / .9 * W;
          const g = ctx.createLinearGradient(x - 40, 0, x, 0); g.addColorStop(0, `rgb(${rgb} / 0)`); g.addColorStop(1, `rgb(${rgb} / .35)`);
          ctx.fillStyle = g; ctx.fillRect(x - 40, 0, 40, H); ctx.fillStyle = "rgb(234 255 251 / .7)"; ctx.fillRect(x, 0, 1, H);
        }
        if (e >= FIM) { fixo = document.createElement("canvas"); fixo.width = cv.width; fixo.height = cv.height;
          const c = fixo.getContext("2d"); c.scale(dpr, dpr); fundo(c, rgb, () => 1); textos(c, rgb, 1); }
      } else ctx.drawImage(fixo, 0, 0, W, H);
      if (e < 1) return;
      if (!reduzir.matches) {   // a soft band of light sweeping down the land, every few seconds
        const y = ((t * .12) % 1.4 - .2) * H;
        ctx.save(); ctx.clip(terraToda, "evenodd");
        const g = ctx.createLinearGradient(0, y - 30, 0, y + 30); g.addColorStop(0, `rgb(${rgb} / 0)`); g.addColorStop(.5, `rgb(${rgb} / .16)`); g.addColorStop(1, `rgb(${rgb} / 0)`);
        ctx.fillStyle = g; ctx.fillRect(0, y - 30, W, 60); ctx.restore();
      }
      const pul = .5 + .5 * Math.sin(t * 2.4);
      ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 8 + pul * 8; ctx.strokeStyle = `rgb(234 255 251 / ${(.25 + pul * .35).toFixed(3)})`; ctx.lineWidth = 1.2;
      for (const f of formas) if (f.d) ctx.stroke(f.path);
      ctx.shadowBlur = 0;
      for (const a of arcos) {
        const k = suave((e - a.atraso) / 1); if (k <= 0) continue;
        const ponto = s => [(1 - s) ** 2 * a.a[0] + 2 * (1 - s) * s * a.c[0] + s * s * a.z[0], (1 - s) ** 2 * a.a[1] + 2 * (1 - s) * s * a.c[1] + s * s * a.z[1]];
        ctx.strokeStyle = `rgb(${rgb} / .75)`; ctx.lineWidth = 1.3; ctx.beginPath();
        for (let j = 0; j <= 30 * k; j++) { const [x, y] = ponto(j / 30); j ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
        ctx.stroke();
        if (k >= 1 && !reduzir.matches) { const [x, y] = ponto((t * .45 + a.atraso) % 1); ctx.fillStyle = "#eafffb"; ctx.beginPath(); ctx.arc(x, y, 2.2, 0, Math.PI * 2); ctx.fill(); }
      }
      pontos.forEach((q, i) => {
        const k = suave((e - 1.8 - i * .1) / .4); if (k <= 0) return;
        const [x, y] = q.xy, pu = .5 + .5 * Math.sin(t * 3 + i);
        ctx.fillStyle = i && arcos.length ? "#eafffb" : `rgb(${rgb})`; ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = 12;
        ctx.beginPath(); ctx.arc(x, y, 3.2 * k, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
        ctx.strokeStyle = `rgb(${rgb} / ${(.6 - pu * .5).toFixed(2)})`; ctx.beginPath(); ctx.arc(x, y, 5 + pu * 7, 0, Math.PI * 2); ctx.stroke();
        if (q.nome) { ctx.font = "600 11px 'Chakra Petch', sans-serif"; ctx.textAlign = x > W * .8 ? "right" : "left"; ctx.textBaseline = "middle";
          ctx.fillStyle = "rgb(2 20 18 / .6)"; const w = ctx.measureText(q.nome).width, dx = x > W * .8 ? -9 : 9;
          ctx.fillRect(dx > 0 ? x + dx - 3 : x + dx - w - 3, y - 8, w + 6, 16); ctx.fillStyle = "#ecfffa"; ctx.fillText(q.nome, x + dx, y); }
      });
    };
    // hover: the name and the value of what is under the finger or the mouse
    cv.addEventListener("pointermove", ev => {
      const q = cv.getBoundingClientRect(), x = (ev.clientX - q.left) * (W / q.width) * dpr, y = (ev.clientY - q.top) * (H / q.height) * dpr;
      const f = formas.find(f => ctx.isPointInPath(f.path, x, y, "evenodd"));
      if (!f) { semDica(); return; }
      const v = f.d?.valor != null ? `<small>${curto(f.d.valor)}${b.unidade ? " " + b.unidade : ""}</small>` : "";
      dica(ev.clientX, ev.clientY - 12, `${f.g.nome.replace(/[&<>]/g, "")}${v}`);
    });
    cv.addEventListener("pointerleave", semDica);
  }

  // ---- the same map in relief: a three.js object for a model card ----
  async function construir(T, b) {
    await carregar();
    const r = resolver(b), raiz = new T.Group(), mapa = new T.Group(), subir = [], pulsar = [], viajar = [];
    raiz.add(mapa); mapa.rotation.x = -Math.PI / 2;   // north away from the viewer, heights up
    const LADO = 2.4, { p } = projetor(r.quadro, LADO * 400, LADO * 400 * .75, 0), U = 1 / 400;
    const xy = (lon, lat) => { const [x, y] = p(lon, lat); return [x * U - LADO / 2, LADO * .375 - y * U]; };
    // solid, lit material (the hologram glass blows a whole country into one white glare): deep teal
    // for the least, bright cyan and glowing for the most
    const comDestaque = r.destaques.size > 0, tom = f => new T.Color().setHSL(.49 - .03 * f, .6 + .3 * f, .1 + .55 * f);
    // labels float over the ten biggest at most: in 3D they cannot step aside like on the panel
    const rotular = new Set([...r.destaques].sort((a, z) => (z[1].valor ?? Infinity) - (a[1].valor ?? Infinity)).slice(0, 10).map(([id]) => id));
    for (const g of r.regioes) {
      if (!g.caixas.some(c => dentro(c, r.quadro, 0))) continue;
      const d = r.destaques.get(g.id), f = forca(r, d);
      const altura = d ? (d.valor != null ? .03 + .4 * f : .1) : comDestaque ? .015 : .05;
      g.polys.forEach((poly, i) => {
        if (!dentro(g.caixas[i], r.quadro, .05)) return;
        const pts = a => { const v = []; for (let j = 0; j < a.length; j += 2) v.push(new T.Vector2(...xy(a[j], a[j + 1]))); return v; };
        const forma = new T.Shape(pts(poly[0]));
        for (const furo of poly.slice(1)) forma.holes.push(new T.Path(pts(furo)));
        const geo = new T.ExtrudeGeometry(forma, { depth: altura, bevelEnabled: false });
        // a plain map (nothing lit) tells its regions apart by shade: Brazil's five, or continents
        const c = d ? tom(f) : comDestaque ? new T.Color("#123238") : tom(.35 + .1 * (GRUPOS.indexOf(g.grupo) % 4));
        // Lambert: the card's room reflections would wash every value into the same pale teal
        const m = new T.Mesh(geo, new T.MeshLambertMaterial({ color: c, emissive: c.clone().multiplyScalar(d ? .3 + .5 * f : .25) }));
        m.name = g.nome;
        m.add(new T.LineSegments(new T.EdgesGeometry(geo, 25), new T.LineBasicMaterial({ color: d ? "#eafffb" : "#8ff0e4",
          transparent: true, opacity: d ? .9 : comDestaque ? .3 : .6, blending: T.AdditiveBlending, depthWrite: false })));
        m.scale.z = .02; mapa.add(m);
        subir.push({ m, atraso: .2 + (xy(...g.centro)[0] / LADO + .5) * .9 });
        if (d) pulsar.push(m.children[0]);
      });
      if (d && rotular.has(g.id)) {
        const s = window.jarvisHolograma.rotulo(T, d.valor != null ? `${r.base === "brasil" && r.destaques.size > 6 ? g.id : d.nome} · ${curto(d.valor)}${b.unidade ? " " + b.unidade : ""}` : d.nome);
        const [x, y] = xy(...g.centro), h = .075;
        s.scale.set(h * s.userData.aspecto, h, 1); s.position.set(x, altura + .09, -y); s.visible = false; raiz.add(s);
        subir.push({ s, atraso: 1.6 });
      }
    }
    // the table under the map: a faint grid, as on a holographic desk
    const grade = [], meio = LADO * .62;
    for (let i = -10; i <= 10; i++) { const v = i / 10 * meio; grade.push(-meio, 0, v, meio, 0, v, v, 0, -meio, v, 0, meio); }
    const gg = new T.BufferGeometry(); gg.setAttribute("position", new T.Float32BufferAttribute(grade, 3));
    raiz.add(new T.LineSegments(gg, new T.LineBasicMaterial({ color: "#8ff0e4", transparent: true, opacity: .08, blending: T.AdditiveBlending, depthWrite: false })));
    // cities: a beam of light on each, arcs from the first to the others
    const pts = b.pontos.map(q => { const [x, y] = xy(q.lon, q.lat); return new T.Vector3(x, 0, -y); });
    pts.forEach((v, i) => {
      const feixe = new T.Mesh(new T.CylinderGeometry(.006, .006, .5, 8), new T.MeshBasicMaterial({ color: "#eafffb" }));
      feixe.position.set(v.x, .25, v.z); feixe.userData.cor = "#eafffb"; raiz.add(feixe);
      if (b.pontos[i].nome) { const s = window.jarvisHolograma.rotulo(T, b.pontos[i].nome), h = .06; s.scale.set(h * s.userData.aspecto, h, 1); s.position.set(v.x, .56, v.z); raiz.add(s); }
    });
    if (b.ligar && pts.length > 1) for (const z of pts.slice(1)) {
      const a = pts[0], meioArco = a.clone().add(z).multiplyScalar(.5); meioArco.y = .2 + a.distanceTo(z) * .35;
      const curva = new T.QuadraticBezierCurve3(a.clone().setY(.02), meioArco, z.clone().setY(.02));
      raiz.add(new T.Line(new T.BufferGeometry().setFromPoints(curva.getPoints(48)), new T.LineBasicMaterial({ color: "#8ff0e4", transparent: true, opacity: .8, blending: T.AdditiveBlending, depthWrite: false })));
      const gota = new T.Sprite(new T.SpriteMaterial({ color: "#eafffb", transparent: true, blending: T.AdditiveBlending, depthWrite: false }));
      gota.scale.set(.035, .035, 1); raiz.add(gota); viajar.push({ curva, gota, fase: Math.random() });
    }
    let t0 = null;
    const animar = t => {
      t0 ??= t; const e = t - t0;
      for (const s of subir) { const k = suave((e - s.atraso) / .7); if (s.m) s.m.scale.z = .02 + .98 * k; else s.s.visible = k > 0; }
      for (const l of pulsar) l.material.opacity = .55 + .45 * Math.sin(t * 2.4);
      for (const v of viajar) v.gota.position.copy(v.curva.getPoint((t * .4 + v.fase) % 1));
    };
    // built at full height, so the card frames it whole; the first frame lays it flat to rise
    return { obj: raiz, animar };
  }

  window.jarvisMapas = { carregar, desenhar, construir, conferir, fonteDe, get pronto() { return !!dados; } };
})();
