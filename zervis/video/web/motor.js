// O motor dos vídeos do Zé (ADR 0106, 0107 e 0110). Uma página desenha qualquer instante do vídeo:
// `window.render(t)` depende só de `t`, então o Chromium pode fotografar os quadros em qualquer
// ordem, em paralelo, e o resultado é sempre o mesmo.
//
// O roteiro chega pronto em `window.VIDEO` (o `dados.js` de `?dados=`): as cenas com o início, o
// fim e as palavras ditas (com o tempo de cada uma), o volume da voz por quadro, a marca e o
// estilo. O texto do roteiro entra sempre como texto (`textContent`), nunca como HTML.
//
// As cenas moram em `cenas.js` (e no `cenas.js` de um estilo): `Ze.cena(tipo, {montar, render})`.
// `montar(cena, el, ctx)` cria o que a cena mostra e devolve o estado dela (com `foco`, o elemento
// de onde nascem as transições); `render(t, d, estado, ctx)` posiciona tudo no instante `t`.
//
// A edição (ADR 0110) segue o que separa um vídeo editado de um vídeo gerado: entradas variadas
// (nada de tudo subir com fade), o que assenta fica parado, chegadas com cauda longa e saídas
// curtas, câmera só com intenção (um soco na palavra de destaque, não um zoom lento eterno) e
// transições com causa (o chicote, o zoom através do foco, a íris do ponto, a cor que inunda).
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
    // chegada: cauda longa (expo.out), o que "assenta" devagar
    chega: (p) => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
    // acelera (power3.in): o zoom através e a saída
    acelera: (p) => p * p * p,
    vaivem: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    // mola com amortecimento ~0,75: passa um pouco do ponto e assenta (premium, não desenho)
    mola: (p) => { const c1 = 1.25, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
  };
  Object.assign(Ze, { cl, prog, curvas });

  /** Cria um elemento; o texto entra como texto. */
  Ze.h = (tag, classe = "", texto = "") => {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto) el.textContent = texto;
    return el;
  };

  function aplicar(el, opacidade, transform, desfoque) {
    el.style.opacity = String(cl(opacidade));
    el.style.transform = transform;
    el.style.filter = desfoque > 0.05 ? `blur(${desfoque.toFixed(2)}px)` : "none";
  }

  /** Entrada clássica: sobe, nítida e opaca (use pouco: tudo subindo é cara de vídeo gerado). */
  Ze.entra = (el, t, a, o = {}) => {
    const { d = 0.55, y = 46, x = 0, blur = 12, escala = 1, curva = "chega" } = o;
    const q = prog(t, a, d), p = curvas[curva](q);
    aplicar(el, q * 1.6, `translate(${(1 - p) * x}px, ${(1 - p) * y}px) scale(${escala + (1 - escala) * p})`, q < 1 ? (1 - q) * blur : 0);
    return p;
  };

  /** As entradas da edição (ADR 0110). Cada uma tem um papel; variar é o que dá vida.
   * - desfoque: nasce do desfoque, parada no lugar (palavra a palavra, 0,13 s)
   * - tinta: do cinza para a cor, sem mexer (uma frase sendo dita)
   * - queda: cai do tamanho grande e assenta com peso (a palavra que importa)
   * - lado: chega de lado com rastro (algo que entra na conversa)
   * - mascara: revelada por uma cortina da esquerda para a direita
   * - giro: um cartão que gira em perspectiva até ficar de frente (conteúdo gerado, nunca tela)
   * - sobe: a entrada clássica, para o que é secundário */
  Ze.revela = (el, t, a, tipo = "desfoque", o = {}) => {
    const q = (d) => prog(t, a, o.d ?? d);
    if (tipo === "tinta") {
      const p = q(0.1);
      el.style.opacity = String(0.22 + 0.78 * p);
      el.style.transform = "none";
      el.style.filter = "none";
      return p;
    }
    if (tipo === "queda") {
      const k = q(0.38), p = curvas.chega(k);
      aplicar(el, k * 4, `scale(${1 + 0.55 * (1 - p)})`, (1 - k) * 10);
      return p;
    }
    if (tipo === "lado") {
      const k = q(0.42), p = curvas.chega(k);
      aplicar(el, k * 3, `translateX(${(o.de ?? -90) * (1 - p)}px)`, (1 - k) * 9);
      return p;
    }
    if (tipo === "mascara") {
      const k = q(0.5), p = curvas.chega(k);
      el.style.opacity = k > 0 ? "1" : "0";
      el.style.clipPath = `inset(-10% ${(1 - p) * 100}% -10% 0)`;
      el.style.transform = `translateX(${12 * (1 - p)}px)`;
      el.style.filter = "none";
      return p;
    }
    if (tipo === "giro") {
      const k = q(0.6), p = curvas.chega(k);
      aplicar(el, k * 2.5, `perspective(1400px) rotateX(${-72 * (1 - p)}deg) translateZ(${-120 * (1 - p)}px)`, (1 - k) * 6);
      return p;
    }
    if (tipo === "sobe") return Ze.entra(el, t, a, o);
    const k = q(0.14); // desfoque
    aplicar(el, k, "none", (1 - k) * 8);
    return k;
  };

  /** Saída curta (40% da entrada): desfoca e some. */
  Ze.sai = (el, t, a, d = 0.18) => {
    const k = prog(t, a, d);
    if (k <= 0) return 0;
    el.style.opacity = String(1 - k);
    el.style.filter = `blur(${(k * 8).toFixed(2)}px)`;
    return k;
  };

  /** Pop com mola: de `de` a 1 de escala, passando um pouco do ponto. */
  Ze.mola = (el, t, a, o = {}) => {
    const { d = 0.55, de = 0.4 } = o;
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
  /** Quebra em letras (para o nome da marca, letra a letra). */
  Ze.letras = (el, texto) => [...String(texto)].map((ch) => {
    const s = Ze.h("span", "letra", ch === " " ? " " : ch);
    el.append(s);
    return s;
  });
  const normalizar = (s) => String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\p{L}\p{N} ]/gu, "");
  Ze.normalizar = normalizar;

  /** Cascata: cada palavra entra um pouco depois da anterior (palavras a 60–120 ms). */
  Ze.cascata = (spans, t, a, o = {}) => {
    const passo = o.passo ?? Math.min(0.09, 0.6 / Math.max(1, spans.length));
    spans.forEach((s, i) => Ze.revela(s, t, a + i * passo, o.tipo || "desfoque", o));
    return a + spans.length * passo + 0.3;
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
  let V, palco, mundo, cenas = [], legenda, onda, preto, inunda;

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
    legenda = document.getElementById("legenda");
    onda = document.getElementById("onda");
    preto = document.getElementById("preto");
    inunda = Ze.h("div", "inunda");
    palco.append(inunda);
    const ctx = { marca: V.marca, estilo: V.estilo, video: V };
    cenas = V.cenas.map((c, i) => {
      const def = Ze.cenas[c.tipo] || Ze.cenas.frase;
      const fundo = ["escuro", "claro", "cor"].includes(c.fundo) ? c.fundo : "escuro";
      const el = Ze.h("section", `cena cena-${c.tipo} composicao-${c.composicao || "padrao"} fundo-${fundo}`);
      el.dataset.fundo = fundo;
      // cada cena tem o próprio fundo (as mesmas manchas, no mesmo tempo): na íris e no chicote,
      // a que entra cobre a que sai, sem dupla exposição
      const fundoCena = Ze.h("div", "fundo-cena");
      fundoCena.append(Ze.h("div", "mancha um"), Ze.h("div", "mancha dois"), Ze.h("div", "malha"));
      const camera = Ze.h("div", "camera");
      el.append(fundoCena, camera);
      el.style.display = "none";
      mundo.append(el);
      c.palavras = c.palavras && c.palavras.length ? c.palavras : estimadas(c, i);
      const ctxCena = { ...ctx, cena: c };
      const estado = def.montar(c, camera, ctxCena) || {};
      return { c, el, camera, def, i, estado, ctx: ctxCena, blocos: blocos(c), soco: soco(c) };
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

  /** A legenda em grupos de 3 a 5 palavras, quebrando na pontuação: um grupo por vez. */
  function blocos(c) {
    const saida = [];
    let atual = [];
    const fecha = () => { if (atual.length) saida.push(atual); atual = []; };
    c.palavras.forEach((w) => {
      const letras = atual.reduce((n, x) => n + x.p.length + 1, 0) + w.p.length;
      if (atual.length >= 5 || letras > 28) fecha();
      atual.push(w);
      if (/[.,!?;:…]$/.test(w.p)) fecha();
    });
    fecha();
    return saida;
  }

  /** O soco de câmera: o instante da primeira palavra do destaque (segundos na cena), ou null. */
  function soco(c) {
    if ((c.camera || "empurra") !== "empurra") return null;
    const marcadas = new Set(normalizar(c.destaque || "").split(" ").filter(Boolean));
    const w = c.palavras.find((x) => marcadas.has(normalizar(x.p)));
    return w ? Math.max(0.3, w.i - c.inicio) : null;
  }

  /** A fala da cena como tipografia: cada palavra entra quando é dita. */
  Ze.falaCinetica = (el, c) => Ze.palavras(el, c.palavras.map((w) => w.p).join(" "), c.destaque || "");
  Ze.animarFala = (spans, c, t, tipo = "desfoque", o = {}) => {
    spans.forEach((s, k) => {
      const w = c.palavras[k];
      Ze.revela(s, t, (w ? w.i - c.inicio : 0) - 0.06, tipo, o);
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
    // a legenda da cena nova só aparece depois da transição (nada por cima da cena que sai)
    const livre = x ? x.c.inicio + (x.i ? TRANSICAO[x.c.transicao || "zoom"] ?? 0.4 : 0) : 0;
    const bloco = x && x.c.legenda !== "cinetica" && t >= livre
      ? x.blocos.find((b, k) => t >= b[0].i - 0.1 && t < (x.blocos[k + 1]?.[0].i ?? x.c.fim) - 0.05)
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
    // a palavra da vez ganha a pílula; as ditas ficam acesas; as que vêm, apagadas
    [...legenda.querySelectorAll("span")].forEach((s, k) => {
      const w = bloco[k];
      const dita = t >= w.i - 0.02;
      const daVez = dita && (k === bloco.length - 1 ? t < w.f + 0.25 : t < bloco[k + 1].i - 0.02);
      s.classList.toggle("dita", dita);
      s.classList.toggle("ativa", daVez);
    });
    Ze.revela(legenda, t, Math.max(bloco[0].i - 0.1, livre), "desfoque", { d: 0.12 });
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
  const TRANSICAO = {
    mascara: 0.38, deslize: 0.3, zoom: 0.42, cor: 0.5, corte: 0,
    carta: 0.8, baralho: 0.6, cubo: 0.62, fatias: 0.6,
  };
  const CARTA = new Set(["carta", "baralho", "cubo"]);

  /** A câmera da cena (no miolo, para não brigar com a transição). Nada de zoom lento eterno:
   * empurra = um soco na palavra de destaque (rápido, e fica); afasta e desliza = um movimento
   * só na chegada, que assenta; parado = parado. */
  function camera(x, local) {
    const tipo = x.c.camera || "empurra";
    let esc = 1, tx = 0, ty = 0;
    if (tipo === "empurra" && x.soco !== null) {
      const p = curvas.chega(prog(local, x.soco, 0.16));
      esc = 1 + 0.075 * p;
      ty = -14 * p;
    } else if (tipo === "afasta") {
      const p = curvas.chega(prog(local, 0, 0.9));
      esc = 1.12 - 0.12 * p;
    } else if (tipo === "desliza") {
      const p = curvas.chega(prog(local, 0, 0.8));
      tx = 70 * (1 - p);
      esc = 1.03;
    }
    x.camera.style.transform = `translate(${tx}px, ${ty}px) scale(${esc})`;
  }

  /** O centro do foco de uma cena (de onde a íris abre e para onde o zoom atravessa). */
  function foco(x) {
    const alvo = x && x.estado && x.estado.foco;
    if (!alvo || !alvo.isConnected) return [V.largura / 2, V.altura * 0.42];
    const r = alvo.getBoundingClientRect();
    if (!r.width) return [V.largura / 2, V.altura * 0.42];
    return [r.left + r.width / 2, r.top + r.height / 2];
  }

  /** A cena que entra (`x`) e a que sai (`antes`), durante a transição de `x`. */
  function transicao(x, antes, local) {
    const tipo = x.c.transicao || "zoom";
    const d = TRANSICAO[tipo] ?? 0.4;
    const el = x.el;
    el.style.clipPath = "none";
    el.style.filter = "none";
    el.style.opacity = "1";
    el.style.transform = "none";
    el.style.transformOrigin = "";
    inunda.style.transform = "translateY(100%)";
    palco.classList.toggle("mesa", false);
    if (tipo === "corte" || !antes) {
      // corte seco na batida: a cena chega um pouco grande e assenta (o soco do corte)
      if (antes) el.style.transform = `scale(${1.05 - 0.05 * curvas.chega(prog(local, 0, 0.3))})`;
      return;
    }
    const q = prog(local, 0, d);
    if (q >= 1) return;
    const sai = antes.el;
    sai.style.display = "";
    sai.style.zIndex = "1";
    el.style.zIndex = "2";
    if (CARTA.has(tipo)) palco.classList.add("mesa");
    // o lado de cada transição varia por vídeo e por cena (a mesma carta não vira sempre igual)
    const lado = (((V.semente || 7) * 31 + x.i * 17) >> 1) % 2 ? 1 : -1;
    if (tipo === "carta") {
      // a tela vira carta: encolhe, gira no eixo vertical mostrando o verso (a cena nova) e volta
      const s = 1 - 0.16 * Math.sin(Math.PI * curvas.vaivem(q));
      const f = curvas.vaivem(prog(q, 0.18, 0.64));
      const borda = `${Math.round(64 * cl(Math.sin(Math.PI * q) * 3))}px`;
      [[sai, -180 * f * lado], [el, 180 * (1 - f) * lado]].forEach(([c, ang]) => {
        c.style.transform = `perspective(2400px) scale(${s.toFixed(4)}) rotateY(${ang.toFixed(2)}deg)`;
        c.style.borderRadius = borda;
        c.classList.add("carta");
      });
      el.style.zIndex = f >= 0.5 ? "2" : "1";
      sai.style.zIndex = f >= 0.5 ? "1" : "2";
    } else if (tipo === "baralho") {
      // a carta de cima é jogada para o lado, girando; a de baixo cresce e acende
      const a = curvas.acelera(q), b = curvas.chega(prog(q, 0.15, 0.85));
      const borda = `${Math.round(64 * cl(Math.sin(Math.PI * q) * 3))}px`;
      sai.style.zIndex = "2";
      el.style.zIndex = "1";
      sai.style.transformOrigin = "50% 110%";
      sai.style.transform = `translate(${(-125 * a * lado).toFixed(2)}%, ${(-6 * a).toFixed(2)}%) rotate(${(-24 * a * lado).toFixed(2)}deg) scale(${(1 - 0.08 * Math.min(1, q * 4)).toFixed(4)})`;
      sai.style.borderRadius = `${Math.round(64 * Math.min(1, q * 4))}px`;
      el.style.transform = `scale(${(0.88 + 0.12 * b).toFixed(4)})`;
      el.style.borderRadius = borda;
      el.style.filter = b < 1 ? `brightness(${(0.55 + 0.45 * b).toFixed(3)})` : "none";
      sai.classList.add("carta");
      el.classList.add("carta");
    } else if (tipo === "cubo") {
      // a tela é a face de um cubo que gira: a nova face vem da direita, presa pela aresta
      const p = curvas.vaivem(q), s = 1 - 0.12 * Math.sin(Math.PI * p);
      sai.style.transformOrigin = lado > 0 ? "100% 50%" : "0% 50%";
      el.style.transformOrigin = lado > 0 ? "0% 50%" : "100% 50%";
      sai.style.transform = `perspective(2000px) scale(${s.toFixed(4)}) translateX(${(-100 * p * lado).toFixed(3)}%) rotateY(${(-90 * p * lado).toFixed(2)}deg)`;
      el.style.transform = `perspective(2000px) scale(${s.toFixed(4)}) translateX(${(100 * (1 - p) * lado).toFixed(3)}%) rotateY(${(90 * (1 - p) * lado).toFixed(2)}deg)`;
      sai.style.filter = `brightness(${(1 - 0.5 * p).toFixed(3)})`;
      el.style.filter = p < 1 ? `brightness(${(0.5 + 0.5 * p).toFixed(3)})` : "none";
    } else if (tipo === "fatias") {
      // a cena nova desce em tiras, uma logo depois da outra; a que sai recua e escurece
      const n = 6, w = V.largura / n, h = V.altura, pts = ["0px 0px"];
      for (let i = 0; i < n; i++) {
        const ordem = lado > 0 ? i : n - 1 - i; // da esquerda ou da direita
        const y = (curvas.chega(prog(q, ordem * 0.07, 0.6)) * h * 1.02).toFixed(1);
        pts.push(`${(i * w).toFixed(1)}px ${y}px`, `${((i + 1) * w).toFixed(1)}px ${y}px`, `${((i + 1) * w).toFixed(1)}px 0px`);
      }
      el.style.clipPath = `polygon(${pts.join(", ")})`;
      sai.style.transform = `scale(${(1 - 0.06 * curvas.chega(q)).toFixed(4)})`;
      sai.style.filter = `brightness(${(1 - 0.45 * q).toFixed(3)})`;
    } else if (tipo === "mascara") {
      // íris: abre do ponto de foco da cena que sai
      const [fx, fy] = foco(antes);
      el.style.clipPath = `circle(${curvas.chega(q) * 160}% at ${fx}px ${fy}px)`;
    } else if (tipo === "deslize") {
      // chicote: as duas passam rápido para o lado, borradas na velocidade, e a nova assenta
      const p = curvas.vaivem(q), v = Math.sin(q * Math.PI);
      el.style.transform = `translateX(${(1 - p) * 100 * lado}%)`;
      sai.style.transform = `translateX(${-p * 100 * lado}%)`;
      const borrao = v > 0.05 ? `blur(${(18 * v).toFixed(1)}px)` : "none";
      el.style.filter = borrao;
      sai.style.filter = borrao;
    } else if (tipo === "cor") {
      // inundação: a cor da marca sobe e cobre; por trás dela, a cena troca; ela sai por cima
      const sobe = curvas.vaivem(prog(local, 0, d / 2)), sai2 = curvas.vaivem(prog(local, d / 2, d / 2));
      inunda.style.transform = `translateY(${(1 - sobe) * 100 - sai2 * 100}%)`;
      if (local < d / 2) { el.style.opacity = "0"; } else { sai.style.display = "none"; }
    } else {
      // zoom através: a que sai acelera para dentro do foco e some no desfoque; a nova chega
      const [fx, fy] = foco(antes);
      const a = curvas.acelera(q);
      sai.style.transformOrigin = `${fx}px ${fy}px`;
      sai.style.transform = `scale(${1 + 2.2 * a})`;
      sai.style.opacity = String(1 - curvas.acelera(prog(local, d * 0.45, d * 0.55)));
      sai.style.filter = a > 0.05 ? `blur(${(14 * a).toFixed(1)}px)` : "none";
      const k = prog(local, d * 0.45, d * 0.55), p = curvas.chega(k);
      el.style.opacity = String(k);
      el.style.transform = `scale(${1.12 - 0.12 * p})`;
      el.style.filter = k < 1 ? `blur(${((1 - k) * 10).toFixed(1)}px)` : "none";
    }
  }

  window.render = (t) => {
    document.documentElement.style.setProperty("--t", String(t));
    // o piso em perspectiva anda devagar para a frente (o palco vivo, não um título se mexendo)
    document.documentElement.style.setProperty("--desloca", `${((t * 45) % 90).toFixed(2)}px`);
    const v = volume(t);
    let atual = null;
    for (const x of cenas) {
      const dentro = t >= x.c.inicio && t < x.c.fim;
      x.el.style.display = dentro ? "" : "none";
      x.el.style.zIndex = "";
      x.el.style.transform = "none";
      x.el.style.filter = "none";
      x.el.style.opacity = "1";
      x.el.style.clipPath = "none";
      x.el.style.borderRadius = "";
      x.el.style.transformOrigin = "";
      x.el.classList.remove("carta");
      if (dentro) atual = x;
    }
    if (atual) {
      const antes = cenas[atual.i - 1];
      const local = t - atual.c.inicio, d = atual.c.fim - atual.c.inicio;
      const dur = TRANSICAO[atual.c.transicao || "zoom"] ?? 0.4;
      // a cena que sai continua desenhando (um pouco além do fim dela) por baixo da que entra
      if (antes && local < dur) {
        const la = t - antes.c.inicio, da = antes.c.fim - antes.c.inicio;
        antes.def.render(la, da, antes.estado, { ...antes.ctx, volume: v });
        camera(antes, la);
      }
      // o corte com escurecida: a cena que sai escurece nos 3 últimos quadros antes do corte
      const seguinte = cenas[atual.i + 1];
      atual.def.render(local, d, atual.estado, { ...atual.ctx, volume: v });
      camera(atual, local);
      transicao(atual, antes, local);
      if (seguinte && (seguinte.c.transicao || "zoom") === "corte" && d - local < 0.1) {
        atual.el.style.filter = "brightness(0.6)";
      }
    }
    if (atual) palco.dataset.fundo = atual.el.dataset.fundo;
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
