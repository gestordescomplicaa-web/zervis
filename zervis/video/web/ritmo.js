// O ritmo dos vídeos do Zé (ADR 0113): ganchos que param o dedo e um fecho que não é sempre o
// mesmo. Envolve as cenas de texto e o fecho de `cenas.js`: as composições novas desenham aqui;
// as outras seguem para a original.
//
// - "cortes": cada palavra sozinha na tela inteira, num corte seco no tempo dela, alternando fundo,
//   tamanho e inclinação (o texto que bate na batida dos Reels de edição rápida).
// - "carimbo": a fala entra normal e o destaque bate na tela como um carimbo: chega enorme, para
//   num quadro, a tela treme e dá um clarão.
// - fecho "chamada": o convite enorme na cor da marca, o logo pequeno em cima e uma seta que
//   aponta para o link.
(() => {
  const { h, revela, mola, prog, curvas, cl } = window.Ze;

  /** Os pedaços de "cortes": uma palavra por tela; as de até 2 letras grudam na seguinte. */
  function pedacos(c) {
    const saida = [];
    let junto = [];
    c.palavras.forEach((w, k) => {
      junto.push(w);
      if (w.p.replace(/\W/g, "").length > 2 || k === c.palavras.length - 1) {
        saida.push(junto);
        junto = [];
      }
    });
    return saida;
  }

  function cortes() {
    return {
      montar(c, el) {
        const marcadas = new Set(Ze.normalizar(c.destaque || "").split(" ").filter(Boolean));
        const telas = pedacos(c).map((grupo, i) => {
          const texto = grupo.map((w) => w.p).join(" ");
          const destaque = grupo.some((w) => marcadas.has(Ze.normalizar(w.p)));
          // fundo e inclinação alternam; o destaque sempre na cor da marca
          const tela = h("div", `corte-tela corte-${destaque ? "marca" : ["escuro", "claro", "escuro"][i % 3]}`);
          const palavra = h("div", "corte-palavra", texto);
          const maior = Math.max(...texto.split(" ").map((p) => p.length));
          palavra.style.fontSize = `${Math.round(Math.min(330, 940 / (maior * 0.58)))}px`;
          palavra.style.setProperty("--inclina", `${[-3, 2.5, -1.5, 3][i % 4]}deg`);
          tela.append(palavra);
          el.append(tela);
          return { tela, palavra, inicio: grupo[0].i - c.inicio };
        });
        return { telas, foco: telas[0].palavra };
      },
      render(t, d, s) {
        let atual = 0;
        s.telas.forEach((x, i) => { if (t >= x.inicio - 0.04) atual = i; });
        s.telas.forEach((x, i) => {
          x.tela.style.display = i === atual ? "" : "none";
          if (i !== atual) return;
          // o soco do corte: chega um pouco grande e assenta em 120 ms
          const p = curvas.chega(prog(t, x.inicio - 0.04, 0.12));
          x.palavra.style.transform = `rotate(var(--inclina)) scale(${(1.18 - 0.18 * p).toFixed(4)})`;
        });
        s.foco = s.telas[atual].palavra;
      },
    };
  }

  /** "carimbo": a cena de texto normal, com o destaque batendo na tela. */
  function carimbo(base) {
    return {
      montar(c, el, ctx) {
        const s = base.montar({ ...c, composicao: "centro" }, el, ctx);
        if (s.aspas) { s.aspas.remove(); s.aspas = null; }
        const texto = s.spans[0].parentElement;
        texto.style.fontSize = `${Math.round(parseFloat(texto.style.fontSize || "96") * 1.25)}px`;
        const clarao = h("div", "clarao");
        el.append(clarao);
        const destaques = s.spans.filter((x) => x.classList.contains("destaque"));
        const alvo = destaques.length ? destaques : s.spans.slice(-1);
        const k = s.spans.indexOf(alvo[0]);
        const w = c.palavras[k];
        return { ...s, clarao, alvo, bate: w ? w.i - c.inicio : 0.6, texto };
      },
      render(t, d, s, ctx) {
        base.render(t, d, s, { ...ctx, cena: { ...ctx.cena, composicao: "centro" } });
        // o destaque: escondido até bater; chega 2,6x maior e para num quadro, um pouco torto
        const p = prog(t, s.bate - 0.02, 0.1);
        s.alvo.forEach((x) => {
          x.style.opacity = t >= s.bate - 0.02 ? "1" : "0";
          x.style.filter = "none";
          x.style.transform = `scale(${(2.6 - 1.6 * curvas.saiForte(p)).toFixed(3)}) rotate(${(-6 + 3 * p).toFixed(2)}deg)`;
          x.style.display = "inline-block";
        });
        // a tela treme 250 ms depois do impacto, cada vez menos, e dá um clarão
        const tr = prog(t, s.bate + 0.08, 0.25);
        const forca = tr > 0 && tr < 1 ? 16 * (1 - tr) : 0;
        s.texto.style.transform = forca ? `translate(${(Math.sin(t * 90) * forca).toFixed(1)}px, ${(Math.cos(t * 77) * forca).toFixed(1)}px)` : "";
        const f = prog(t, s.bate + 0.06, 0.18);
        s.clarao.style.opacity = String(f > 0 && f < 1 ? 0.55 * (1 - f) : 0);
      },
    };
  }

  /** Embrulha o gancho e a frase: "cortes" e "carimbo" aqui, o resto na original. */
  ["gancho", "frase"].forEach((tipo) => {
    const base = Ze.cenas[tipo];
    const variantes = { cortes: cortes(), carimbo: carimbo(base) };
    Ze.cena(tipo, {
      montar(c, el, ctx) {
        const v = variantes[c.composicao] || base;
        return { ...v.montar(c, el, ctx), _v: v };
      },
      render(t, d, s, ctx) { s._v.render(t, d, s, ctx); },
    });
  });

  // --- fecho "chamada": o convite enorme, o logo pequeno e a seta para o link -------------------
  const fechoBase = Ze.cenas.fecho;
  const chamada = {
    montar(c, el, ctx) {
      const logo = h("div", "chamada-logo");
      if (ctx.marca.logo) { const img = h("img"); img.src = ctx.marca.logo; logo.append(img); }
      const nome = h("div", "chamada-nome", ctx.marca.instagram ? `@${ctx.marca.instagram}` : ctx.marca.nome || "");
      const texto = h("div", "chamada-texto");
      const spans = Ze.palavras(texto, c.chamada || "");
      const seta = Ze.icone("arrow-down", "icone chamada-seta");
      const detalhe = c.detalhe ? h("div", "chamada-detalhe", c.detalhe) : null;
      el.append(logo, nome, texto, seta);
      if (detalhe) el.append(detalhe);
      return { logo, nome, spans, seta, detalhe, foco: texto };
    },
    render(t, d, s) {
      mola(s.logo, t, 0.15, { de: 0.3, d: 0.5 });
      revela(s.nome, t, 0.35, "desfoque", { d: 0.2 });
      // o convite: palavra por palavra, cada uma caindo com peso
      s.spans.forEach((x, i) => revela(x, t, 0.45 + i * 0.12, "queda"));
      const fim = 0.45 + s.spans.length * 0.12;
      Ze.desenhar(s.seta, t, fim + 0.1, 0.5);
      // a seta quica para baixo (aponta o link), três vezes, e para
      const q = prog(t, fim + 0.6, 1.5);
      s.seta.style.transform = `translateY(${(Math.abs(Math.sin(q * Math.PI * 3)) * 26 * (1 - q)).toFixed(1)}px)`;
      if (s.detalhe) revela(s.detalhe, t, fim + 0.3, "mascara");
    },
  };
  Ze.cena("fecho", {
    montar(c, el, ctx) {
      const v = c.composicao === "chamada" ? chamada : fechoBase;
      return { ...v.montar(c, el, ctx), _v: v };
    },
    render(t, d, s, ctx) { s._v.render(t, d, s, ctx); },
  });
})();
