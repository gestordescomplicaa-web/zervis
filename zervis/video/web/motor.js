// O motor dos vídeos do Zé (ADR 0106). Uma página desenha qualquer instante do vídeo:
// `window.render(t)` depende só de `t`, então o Chromium pode fotografar os quadros em qualquer
// ordem, em paralelo, e o resultado é sempre o mesmo.
//
// O roteiro chega pronto em `window.VIDEO` (o `dados.js` de `?dados=`): as cenas com o início e o
// fim de cada uma, as falas (para a legenda), o volume da voz por quadro, a marca e o estilo.
// O texto do roteiro entra sempre como texto (`textContent`), nunca como HTML.
//
// As cenas moram em `cenas.js` (e no `cenas.js` de um estilo): `Ze.cena(tipo, {montar, render})`.
// `montar(cena, el, ctx)` cria o que a cena mostra e devolve o estado dela; `render(t, d, estado,
// ctx)` posiciona tudo no instante `t` (segundos desde o início da cena) de uma cena de `d`.
(() => {
  const Ze = (window.Ze = { cenas: {}, erros: [] });
  window.addEventListener("error", (e) => Ze.erros.push(String(e.message || e)));
  window.addEventListener("unhandledrejection", (e) => Ze.erros.push(String(e.reason)));

  // --- tempo e curvas -------------------------------------------------------------------------
  const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const prog = (t, a, d) => (d <= 0 ? (t >= a ? 1 : 0) : cl((t - a) / d));
  const curvas = {
    linear: (p) => p,
    sai: (p) => 1 - Math.pow(1 - p, 3),
    saiForte: (p) => 1 - Math.pow(1 - p, 5),
    vaivem: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    // mola: passa do ponto e volta (back.out), a entrada que "assenta"
    mola: (p) => { const c1 = 1.6, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
  };
  Object.assign(Ze, { cl, prog, curvas });

  /** Cria um elemento; o texto entra como texto. */
  Ze.h = (tag, classe = "", texto = "") => {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto) el.textContent = texto;
    return el;
  };

  /** Entrada: sobe, nítida e opaca. Com blur só enquanto entra (o desfoque pesa no Chromium). */
  Ze.entra = (el, t, a, o = {}) => {
    const { d = 0.55, y = 46, x = 0, blur = 12, escala = 1, curva = "saiForte" } = o;
    const p = curvas[curva](prog(t, a, d));
    const q = prog(t, a, d);
    el.style.opacity = String(cl(q * 1.6));
    el.style.transform = `translate(${(1 - p) * x}px, ${(1 - p) * y}px) scale(${escala + (1 - escala) * p})`;
    el.style.filter = q < 1 && blur ? `blur(${(1 - q) * blur}px)` : "none";
    return p;
  };

  /** Pop com mola: de `de` a 1 de escala, passando um pouco do ponto. */
  Ze.mola = (el, t, a, o = {}) => {
    const { d = 0.6, de = 0.4 } = o;
    const q = prog(t, a, d);
    const s = de + (1 - de) * curvas.mola(q);
    el.style.opacity = String(cl(q * 3));
    el.style.transform = `scale(${s})`;
    return q;
  };

  /** Quebra o texto em palavras (spans); as do destaque ganham a classe `destaque`. */
  Ze.palavras = (el, texto, destaque = "") => {
    const marcadas = new Set(normalizar(destaque).split(" ").filter(Boolean));
    return String(texto).split(/\s+/).filter(Boolean).map((p, i) => {
      if (i) el.append(" ");
      const s = Ze.h("span", "palavra" + (marcadas.has(normalizar(p)) ? " destaque" : ""), p);
      el.append(s);
      return s;
    });
  };
  const normalizar = (s) => String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\p{L}\p{N} ]/gu, "");

  /** Cascata: cada palavra entra um pouco depois da anterior (a onda inteira cabe em ~0,6 s). */
  Ze.cascata = (spans, t, a, o = {}) => {
    const passo = o.passo ?? Math.min(0.08, 0.6 / Math.max(1, spans.length));
    spans.forEach((s, i) => Ze.entra(s, t, a + i * passo, { d: 0.6, y: 56, blur: 14, ...o }));
    return a + spans.length * passo + 0.6;
  };

  /** O tamanho da letra pelo comprimento do texto, entre `max` e `min`. */
  Ze.tamanho = (texto, max, min, curto = 18, longo = 70) => {
    const n = String(texto).length;
    return Math.round(max - (max - min) * cl((n - curto) / (longo - curto)));
  };

  /** Um número que conta até o valor ("87%", "R$ 1.200", "3x"): o texto em volta fica. */
  Ze.contar = (el, valor, p) => {
    const m = String(valor).match(/^(\D*)(\d+(?:[.,]\d+)*)(.*)$/);
    if (!m) { el.textContent = valor; return; }
    const [, antes, num, depois] = m;
    const decimal = /,\d{1,2}$/.test(num) ? num.split(",")[1].length : 0;
    const alvo = parseFloat(num.replace(/\./g, "").replace(",", "."));
    const v = alvo * curvas.saiForte(p);
    const texto = v.toLocaleString("pt-BR", { minimumFractionDigits: decimal, maximumFractionDigits: decimal });
    el.textContent = `${antes}${texto}${depois}`;
  };

  Ze.cena = (tipo, def) => { Ze.cenas[tipo] = def; };

  // --- o vídeo ----------------------------------------------------------------------------------
  let V, palco, mundo, cenas = [], legenda, onda, preto, fundo;

  function carregar(src, tipo) {
    return new Promise((ok, falha) => {
      const el = document.createElement(tipo === "css" ? "link" : "script");
      if (tipo === "css") { el.rel = "stylesheet"; el.href = src; } else { el.src = src; }
      el.onload = ok;
      el.onerror = () => falha(new Error(`não carregou ${src}`));
      document.head.appendChild(el);
    });
  }

  function aplicarMarca() {
    const r = document.documentElement.style;
    for (const [nome, cor] of Object.entries(V.marca.cores || {})) r.setProperty(`--${nome}`, cor);
    const f = V.estilo.fontes || {};
    if (f.titulo) r.setProperty("--fonte-titulo", `"${f.titulo}", var(--fonte-reserva)`);
    if (f.texto) r.setProperty("--fonte-texto", `"${f.texto}", var(--fonte-reserva)`);
    r.setProperty("--largura", `${V.largura}px`);
    r.setProperty("--altura", `${V.altura}px`);
    document.body.classList.add(`formato-${V.formato}`, `estilo-${V.estilo.id}`);
  }

  function montar() {
    palco = document.getElementById("palco");
    mundo = document.getElementById("mundo");
    fundo = document.getElementById("fundo");
    legenda = document.getElementById("legenda");
    onda = document.getElementById("onda");
    preto = document.getElementById("preto");
    const ctx = { marca: V.marca, estilo: V.estilo, video: V };
    cenas = V.cenas.map((c, i) => {
      const def = Ze.cenas[c.tipo] || Ze.cenas.frase;
      const el = Ze.h("section", `cena cena-${c.tipo} composicao-${c.composicao || "padrao"}`);
      // cada cena tem o próprio fundo (as mesmas manchas, no mesmo tempo): na máscara e no
      // deslize, a que entra cobre a que sai, sem dupla exposição
      const fundoCena = Ze.h("div", "fundo-cena");
      fundoCena.append(Ze.h("div", "mancha um"), Ze.h("div", "mancha dois"));
      const camera = Ze.h("div", "camera");
      el.append(fundoCena, camera);
      el.style.display = "none";
      mundo.append(el);
      c.palavras = c.palavras && c.palavras.length ? c.palavras : estimadas(c, i);
      const ctxCena = { ...ctx, cena: c };
      return { c, el, camera, def, i, estado: def.montar(c, camera, ctxCena) || {}, ctx: ctxCena, blocos: blocos(c) };
    });
    if (V.estilo.onda !== false) for (let i = 0; i < 44; i++) onda.append(Ze.h("i"));
    else onda.remove();
  }

  /** Sem o tempo real (um dados.js antigo), o tempo de cada palavra pelo tamanho dela. */
  function estimadas(c, i) {
    const f = V.falas[i] || { inicio: c.inicio, dur: Math.max(0.5, c.fim - c.inicio - 0.4), texto: c.fala };
    const palavras = String(f.texto || c.fala || "").split(/\s+/).filter(Boolean);
    const total = palavras.reduce((s, p) => s + p.length + 1, 0) || 1;
    let acc = 0;
    return palavras.map((p) => {
      const ini = f.inicio + f.dur * (acc / total);
      acc += p.length + 1;
      return { p, i: ini, f: f.inicio + f.dur * (acc / total) };
    });
  }

  /** A legenda em blocos curtos (até 6 palavras ou 32 letras, quebrando na pontuação): é o que
   * se lê de relance num Reels, sem a frase inteira na tela. */
  function blocos(c) {
    const saida = [];
    let atual = [];
    const fecha = () => { if (atual.length) saida.push(atual); atual = []; };
    c.palavras.forEach((w) => {
      const letras = atual.reduce((n, x) => n + x.p.length + 1, 0) + w.p.length;
      if (atual.length >= 6 || letras > 32) fecha();
      atual.push(w);
      if (/[.,!?;:…]$/.test(w.p)) fecha();
    });
    fecha();
    return saida;
  }

  /** A fala da cena como tipografia: cada palavra entra quando é dita. */
  Ze.falaCinetica = (el, c) => Ze.palavras(el, c.palavras.map((w) => w.p).join(" "), c.destaque || "");
  Ze.animarFala = (spans, c, t, o = {}) => {
    spans.forEach((s, k) => {
      const w = c.palavras[k];
      Ze.entra(s, t, (w ? w.i - c.inicio : 0) - 0.08, { d: 0.42, y: 46, blur: 12, ...o });
    });
  };

  function volume(t) {
    const i = Math.floor(t * V.fps), v = V.volume || [];
    const a = v[i] || 0, b = v[i + 1] || 0;
    return a + (b - a) * (t * V.fps - i);
  }

  let blocoVisto = null;

  function desenharLegenda(t, x) {
    // nas cenas de texto, a própria fala é a tipografia: nada embaixo
    const bloco = x && x.c.legenda !== "cinetica"
      ? x.blocos.find((b, k) => t >= b[0].i - 0.12 && t < (x.blocos[k + 1]?.[0].i ?? x.c.fim) - 0.06)
      : null;
    if (bloco !== blocoVisto) {
      legenda.textContent = "";
      if (bloco) {
        const marcadas = new Set(normalizar(x.c.destaque || "").split(" ").filter(Boolean));
        bloco.forEach((w, k) => {
          if (k) legenda.append(" ");
          legenda.append(Ze.h("span", marcadas.has(normalizar(w.p)) ? "marcada" : "", w.p));
        });
      }
      blocoVisto = bloco;
    }
    if (!bloco) return;
    [...legenda.querySelectorAll("span")].forEach((s, k) => {
      const w = bloco[k];
      const q = prog(t, w.i - 0.03, 0.16);
      s.classList.toggle("dita", q > 0.5);
      const pulso = q > 0 && q < 1 ? Math.sin(q * Math.PI) : 0;
      s.style.transform = pulso ? `translateY(${-6 * pulso}px)` : ""; // só sobe: crescer comeria o espaço
    });
    Ze.entra(legenda, t, bloco[0].i - 0.12, { d: 0.22, y: 14, blur: 0, escala: 0.96 });
  }

  function desenharOnda(t, v) {
    if (!onda.isConnected) return;
    [...onda.children].forEach((barra, i) => {
      const x = i / (onda.children.length - 1), env = Math.sin(Math.PI * x);
      const h = 6 + v * env * (18 + 54 * Math.abs(Math.sin(t * 9.1 + i * 0.67) * Math.cos(t * 3.7 + i * 0.29)));
      barra.style.transform = `scaleY(${h / 6})`;
      barra.style.opacity = String(0.28 + 0.72 * Math.min(1, v * 1.5));
    });
  }

  // --- câmera e transições ------------------------------------------------------------------
  const TRANSICAO = 0.42; // quanto a cena que sai continua na tela por baixo da que entra

  /** O movimento de câmera da cena (no miolo, para não brigar com a transição). */
  function camera(x, local, d) {
    const p = curvas.vaivem(prog(local, 0, d));
    const tipo = x.c.camera || "empurra";
    const [esc, tx, ty] = tipo === "afasta" ? [1.09 - 0.09 * p, 0, 8 * (1 - p)]
      : tipo === "desliza" ? [1.045, 28 - 56 * p, 0]
      : tipo === "parado" ? [1 + 0.012 * p, 0, 0]
      : [1 + 0.07 * p, 0, -12 * p];
    x.camera.style.transform = `translate(${tx}px, ${ty}px) scale(${esc})`;
  }

  /** A cena que entra (`x`) e a que sai (`antes`), durante a transição de `x`. */
  function transicao(x, antes, local) {
    const tipo = x.c.transicao || "zoom";
    const q = prog(local, 0, TRANSICAO), p = curvas.saiForte(q);
    const el = x.el;
    el.style.clipPath = "none";
    el.style.filter = "none";
    el.style.opacity = "1";
    el.style.transform = "none";
    if (tipo === "corte") {
      // corte seco na batida, com um soco de câmera
      el.style.transform = `scale(${1.06 - 0.06 * curvas.saiForte(prog(local, 0, 0.3))})`;
      return;
    }
    if (!antes || q >= 1) return;
    const sai = antes.el;
    sai.style.display = "";
    sai.style.zIndex = "1";
    el.style.zIndex = "2";
    if (tipo === "mascara") {
      el.style.clipPath = `circle(${p * 150}% at 50% 42%)`;
      sai.style.transform = `scale(${1 + 0.05 * p})`;
    } else if (tipo === "deslize") {
      const v = Math.sin(q * Math.PI); // a velocidade: o desfoque segue o movimento
      el.style.transform = `translateX(${(1 - p) * 100}%)`;
      el.style.filter = v > 0.05 ? `blur(${5 * v}px)` : "none";
      sai.style.transform = `translateX(${-35 * p}%)`;
      sai.style.opacity = String(1 - 0.7 * p);
      sai.style.filter = v > 0.05 ? `blur(${5 * v}px)` : "none";
    } else {
      // zoom: a que sai cresce e some; a que entra chega de trás
      el.style.transform = `scale(${0.86 + 0.14 * p})`;
      el.style.opacity = String(p);
      sai.style.transform = `scale(${1 + 0.35 * p})`;
      sai.style.opacity = String(1 - p);
      sai.style.filter = q > 0.05 ? `blur(${8 * q}px)` : "none";
    }
  }

  window.render = (t) => {
    document.documentElement.style.setProperty("--t", String(t));
    const v = volume(t);
    let atual = null;
    for (const x of cenas) {
      const dentro = t >= x.c.inicio && t < x.c.fim;
      x.el.style.display = dentro ? "" : "none";
      x.el.style.zIndex = "";
      if (!dentro) continue;
      atual = x;
    }
    if (atual) {
      const antes = cenas[atual.i - 1];
      const local = t - atual.c.inicio, d = atual.c.fim - atual.c.inicio;
      // a cena que sai continua desenhando (um pouco além do fim dela) por baixo da que entra
      if (antes && local < TRANSICAO && atual.c.transicao !== "corte") {
        const la = t - antes.c.inicio, da = antes.c.fim - antes.c.inicio;
        antes.def.render(la, da, antes.estado, { ...antes.ctx, volume: v });
        camera(antes, la, da);
        antes.el.style.clipPath = "none";
      }
      atual.def.render(local, d, atual.estado, { ...atual.ctx, volume: v });
      camera(atual, local, d);
      transicao(atual, antes, local);
    }
    desenharLegenda(t, atual);
    desenharOnda(t, v);
    preto.style.opacity = String(prog(t, V.duracao - 0.35, 0.35));
  };

  async function iniciar() {
    const dados = new URLSearchParams(location.search).get("dados");
    if (!dados) throw new Error("falta ?dados=");
    await carregar(dados, "js");
    V = window.VIDEO;
    if (V.estilo.fontes_url) await carregar(V.estilo.fontes_url, "css").catch(() => {});
    if (V.estilo.css) await carregar(V.estilo.css, "css");
    if (V.estilo.js) await carregar(V.estilo.js, "js");
    aplicarMarca();
    montar();
    const f = V.estilo.fontes || {};
    await Promise.all(
      [f.titulo && `800 40px "${f.titulo}"`, f.titulo && `700 40px "${f.titulo}"`, f.texto && `400 40px "${f.texto}"`, f.texto && `600 40px "${f.texto}"`]
        .filter(Boolean).map((x) => document.fonts.load(x).catch(() => {})),
    );
    await document.fonts.ready;
    await Promise.all([...document.images].map((i) => i.decode().catch(() => {})));
    window.render(0);
  }

  window.pronto = iniciar().catch((e) => { Ze.erros.push(String(e.message || e)); });
})();
