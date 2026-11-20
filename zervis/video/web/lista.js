// A lista dos vídeos do Zé (ADR 0114): o que fica de uma cena para a outra.
//
// - "item": um cartão que não sai da tela entre itens seguidos; só o conteúdo troca (o nome, o que
//   faz, o número contando). O motor não faz transição entre dois itens: parece o mesmo cartão.
// - o placar (uma camada, por cima das cenas): um selo por item da lista, que acende quando o item
//   chega, e o contador "3/8". Quem assiste sente o progresso, não slides.
// - fecho "comenta": "comenta VÍDEO", com a caixa do perfil e o botão de seguir.
(() => {
  const { h, revela, mola, prog, curvas, cl } = window.Ze;

  const sigla = (nome) => {
    const partes = String(nome || "?").replace(/[^\p{L}\p{N} ]/gu, "").split(/\s+/).filter(Boolean);
    return (partes.length > 1 ? partes[0][0] + partes[1][0] : (partes[0] || "?").slice(0, 2)).toUpperCase();
  };

  // --- item ------------------------------------------------------------------------------------
  Ze.cena("item", {
    montar(c, el, ctx) {
      const cenas = ctx.video.cenas;
      const i = cenas.indexOf(c);
      const continua = i > 0 && cenas[i - 1].tipo === "item";
      const numero = cenas.slice(0, i + 1).filter((x) => x.tipo === "item").length;
      const cartao = h("div", "item-cartao");
      const topo = h("div", "item-topo");
      const icone = Ze.icone(c.icone || "sparkles", "icone item-icone");
      topo.append(icone, h("span", "item-categoria", c.categoria || ""), h("span", "item-num", String(numero).padStart(2, "0")));
      const caixa = h("div", "item-caixa");
      const detalhe = h("div", "item-detalhe", c.detalhe || "");
      caixa.append(h("div", "item-caixa-titulo", "Sobre"), detalhe);
      const nome = h("div", "item-nome", c.nome || "");
      const traco = h("div", "item-traco");
      const valor = c.valor ? h("div", "item-valor") : null;
      let numeroValor = null;
      if (valor) { valor.append(Ze.icone("sparkles", "icone item-valor-icone")); numeroValor = h("span", "item-valor-num", c.valor); valor.append(numeroValor); }
      cartao.append(topo, caixa, nome, traco);
      if (valor) cartao.append(valor);
      el.append(cartao);
      return { continua, cartao, icone, caixa, detalhe, nome, traco, valor, numeroValor, foco: nome };
    },
    render(t, d, s, ctx) {
      if (!s.continua) {
        // o primeiro item: o cartão sobe e assenta; os seguintes já estão lá
        const p = curvas.chega(prog(t, 0.05, 0.5));
        s.cartao.style.opacity = String(cl(prog(t, 0.05, 0.2)));
        s.cartao.style.transform = `translateY(${(140 * (1 - p)).toFixed(1)}px) scale(${(0.94 + 0.06 * p).toFixed(4)})`;
      }
      const a = s.continua ? 0 : 0.3;
      Ze.desenhar(s.icone, t, a, 0.4);
      revela(s.nome, t, a + 0.02, s.continua ? "desfoque" : "queda", { d: s.continua ? 0.16 : undefined });
      revela(s.detalhe, t, a + 0.08, "tinta");
      s.traco.style.transform = `scaleX(${curvas.chega(prog(t, a + 0.15, 0.4)).toFixed(4)})`;
      if (s.valor) {
        revela(s.valor, t, a + 0.2, "desfoque", { d: 0.15 });
        Ze.contar(s.numeroValor, ctx.cena.valor, prog(t, a + 0.2, 0.9));
      }
    },
  });

  // --- o placar: um selo por item, que acende quando o item chega -----------------------------
  let placar = null;
  Ze.camadas.push((t, atual, V, palco) => {
    const itens = V.cenas.map((c, i) => ({ c, i })).filter((x) => x.c.tipo === "item");
    if (itens.length < 3) return;
    if (!placar) {
      const el = h("div", "placar");
      const selos = itens.map((x, k) => {
        const selo = h("div", `placar-selo cor-${k % 8}`);
        if (x.c.imagem && x.c.imagem_tipo === "logo") {
          // o selo de um item com logo é o próprio logo
          const img = h("img", "placar-logo");
          img.src = x.c.imagem;
          selo.append(img);
          selo.classList.add("com-logo");
        } else selo.append(h("span", "placar-sigla", sigla(x.c.nome)));
        el.append(selo);
        return selo;
      });
      const conta = h("div", "placar-conta");
      el.append(conta);
      palco.append(el);
      placar = { el, selos, conta };
    }
    const inicio = itens[0].c.inicio, fim = itens[itens.length - 1].c.fim;
    const vis = cl(prog(t, inicio + 0.15, 0.3)) * (1 - cl(prog(t, fim - 0.05, 0.25)));
    placar.el.style.opacity = String(vis);
    placar.el.style.transform = `translateY(${(40 * (1 - curvas.chega(prog(t, inicio + 0.15, 0.4)))).toFixed(1)}px)`;
    let acesos = 0;
    itens.forEach((x, k) => {
      const chega = x.c.inicio + 0.12;
      const aceso = t >= chega;
      if (aceso) acesos = k + 1;
      const selo = placar.selos[k];
      selo.classList.toggle("aceso", aceso);
      selo.classList.toggle("atual", atual === x.i);
      const p = curvas.mola(prog(t, chega, 0.4));
      selo.style.transform = aceso ? `scale(${(0.6 + 0.4 * p).toFixed(4)})` : "scale(1)";
    });
    placar.conta.textContent = `${acesos}/${itens.length}`;
  });

  // --- fecho "comenta": a palavra para comentar, o perfil e o seguir --------------------------
  const fecho = Ze.cenas.fecho;
  const comenta = {
    montar(c, el, ctx) {
      const pede = h("div", "comenta-pede", "Comenta");
      const palavra = h("div", "comenta-palavra");
      const marca = h("i", "comenta-marca");
      palavra.append(marca, h("span", "", `“${String(c.palavra || c.chamada || "").toUpperCase()}”`));
      const caixa = h("div", "comenta-caixa");
      const avatar = h("div", "comenta-avatar");
      if (ctx.marca.logo) { const img = h("img"); img.src = ctx.marca.logo; avatar.append(img); }
      const quem = h("div", "comenta-quem");
      quem.append(h("strong", "", ctx.marca.instagram ? `@${ctx.marca.instagram}` : ctx.marca.nome || ""), h("small", "", c.chamada || ""));
      const seguir = h("div", "comenta-seguir", "Seguir");
      caixa.append(avatar, quem, seguir);
      const detalhe = c.detalhe ? h("div", "comenta-detalhe", c.detalhe) : null;
      el.append(pede, palavra, caixa);
      if (detalhe) el.append(detalhe);
      return { pede, palavra, marca, caixa, seguir, detalhe, foco: palavra };
    },
    render(t, d, s) {
      revela(s.pede, t, 0.1, "desfoque", { d: 0.2 });
      revela(s.palavra, t, 0.3, "queda");
      s.marca.style.transform = `scaleX(${curvas.chega(prog(t, 0.55, 0.35)).toFixed(4)})`;
      const p = curvas.chega(prog(t, 0.8, 0.5));
      s.caixa.style.opacity = String(cl(prog(t, 0.8, 0.2)));
      s.caixa.style.transform = `translateY(${(80 * (1 - p)).toFixed(1)}px)`;
      // o seguir: aperta e volta com mola
      const clique = Math.min(2.2, d * 0.6);
      const aperto = prog(t, clique, 0.1), solta = prog(t, clique + 0.1, 0.4);
      s.seguir.style.transform = `scale(${(1 - 0.08 * aperto + 0.08 * curvas.mola(solta)).toFixed(4)})`;
      s.seguir.classList.toggle("feito", t >= clique + 0.1);
      if (s.detalhe) revela(s.detalhe, t, 1.2, "desfoque", { d: 0.2 });
    },
  };
  Ze.cena("fecho", {
    montar(c, el, ctx) {
      const v = c.composicao === "comenta" ? comenta : fecho;
      return { ...v.montar(c, el, ctx), _v: v };
    },
    render(t, d, s, ctx) { s._v.render(t, d, s, ctx); },
  });
})();
