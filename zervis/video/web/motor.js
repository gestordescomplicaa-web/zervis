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
  let V, palco, mundo, cenas = [], legenda, onda, preto, fundo, legendaVista = -1, palavrasDaFala = [];

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
      const el = Ze.h("section", `cena cena-${c.tipo}`);
      el.style.display = "none";
      mundo.append(el);
      return { c, el, def, i, estado: def.montar(c, el, ctx) || {}, ctx };
    });
    if (V.estilo.onda !== false) for (let i = 0; i < 44; i++) onda.append(Ze.h("i"));
    else onda.remove();
    palavrasDaFala = V.falas.map((f) => {
      const palavras = f.texto.split(/\s+/).filter(Boolean);
      const total = palavras.reduce((s, p) => s + p.length + 1, 0);
      let acc = 0;
      return palavras.map((p) => { const em = f.inicio + f.dur * (acc / total); acc += p.length + 1; return { p, em }; });
    });
  }

  function volume(t) {
    const i = Math.floor(t * V.fps), v = V.volume || [];
    const a = v[i] || 0, b = v[i + 1] || 0;
    return a + (b - a) * (t * V.fps - i);
  }

  const SAIDA = 0.32;

  function desenharLegenda(t) {
    let atual = -1;
    V.falas.forEach((f, i) => {
      const fim = (V.falas[i + 1]?.inicio ?? V.duracao) - 0.12;
      if (t >= f.inicio - 0.15 && t < fim) atual = i;
    });
    if (atual !== legendaVista) {
      legenda.textContent = "";
      if (atual >= 0) {
        const cena = cenas.find((x) => t >= x.c.inicio && t < x.c.fim);
        const marcadas = new Set(normalizar(cena?.c.destaque || "").split(" ").filter(Boolean));
        palavrasDaFala[atual].forEach(({ p }, k) => {
          if (k) legenda.append(" ");
          legenda.append(Ze.h("span", marcadas.has(normalizar(p)) ? "marcada" : "", p));
        });
      }
      legendaVista = atual;
    }
    if (atual < 0) return;
    [...legenda.querySelectorAll("span")].forEach((s, k) => {
      const { em } = palavrasDaFala[atual][k];
      const q = prog(t, em - 0.04, 0.18);
      s.classList.toggle("dita", q > 0.5);
      // a palavra da vez cresce um pouco e volta (o "brilho" de quem fala)
      const pulso = q > 0 && q < 1 ? Math.sin(q * Math.PI) : 0;
      s.style.transform = pulso ? `translateY(${-6 * pulso}px)` : ""; // só sobe: crescer comeria o espaço
    });
    const inicio = V.falas[atual].inicio - 0.15;
    Ze.entra(legenda, t, inicio, { d: 0.3, y: 16, blur: 0 });
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

  window.render = (t) => {
    fundo.style.setProperty("--t", String(t));
    const v = volume(t);
    for (const x of cenas) {
      const { c, el, def, estado, ctx } = x;
      const dentro = t >= c.inicio && t < c.fim;
      el.style.display = dentro ? "" : "none";
      if (!dentro) continue;
      const local = t - c.inicio, d = c.fim - c.inicio;
      def.render(local, d, estado, { ...ctx, volume: v });
      // a câmera: um empurrão lento por cena; a saída encolhe e desfoca, sem dupla exposição
      const sai = x.i === cenas.length - 1 ? 0 : prog(local, d - SAIDA, SAIDA);
      const empurra = 1 + 0.035 * curvas.vaivem(prog(local, 0, d));
      el.style.opacity = String(1 - sai);
      el.style.transform = `scale(${empurra * (1 - 0.05 * sai)})`;
      el.style.filter = sai > 0 ? `blur(${sai * 10}px)` : "none";
    }
    desenharLegenda(t);
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
