// A copy manda na tela (ADR 0115): cada coisa dita vira imagem real na palavra em que é dita.
//
// A cena "visual" tem batidas: {quando, imagem (foto ou logo), rotulo}. O layout é sempre o
// mesmo: a imagem na área de cima, a legenda embaixo.
// - "sequencia": um cartão grande que troca o conteúdo a cada batida, num corte seco com soco.
// - "colagem": as imagens chegam uma a uma no grid e a da vez pulsa quando é dita.
// O item da lista também ganha a imagem (o logo no lugar do ícone, a foto em cima do cartão).
(() => {
  const { h, revela, mola, prog, curvas, cl } = window.Ze;

  /** O conteúdo de uma batida: foto (cobre), logo (no centro, na cor da marca dele) ou ícone. */
  function midia(b, classe) {
    const caixa = h("div", `vis-midia ${classe} vis-${b.imagem ? b.imagem_tipo || "foto" : "icone"}`);
    if (b.imagem && b.imagem_tipo === "site") {
      // o print do site numa janela de navegador: a barra com o endereço em cima
      const barra = h("div", "vis-barra");
      barra.append(h("i"), h("i"), h("i"), h("span", "vis-endereco", b.site || ""));
      const img = h("img");
      img.src = b.imagem;
      img.alt = "";
      caixa.append(barra, img);
    } else if (b.imagem) {
      const img = h("img");
      img.src = b.imagem;
      img.alt = "";
      caixa.append(img);
    } else {
      caixa.append(Ze.icone(b.icone || "sparkles", "icone vis-icone"));
    }
    return caixa;
  }

  /** Quando cada batida entra: o tempo da palavra ou, sem ele, espalhado na cena. */
  function tempos(c, n, d) {
    const lista = c.tempos_batidas || [];
    const saida = [];
    for (let i = 0; i < n; i++) {
      const t = typeof lista[i] === "number" ? lista[i] - 0.04 : 0.15 + (i * (d - 0.8)) / n;
      saida.push(Math.max(t, i ? saida[i - 1] + 0.25 : 0.05));
    }
    return saida;
  }

  // posições da colagem na área de imagem (900 x 900), por quantidade
  const GRADE = {
    1: [[470, 430, 1, 0]],
    2: [[270, 300, 0.64, -4], [670, 610, 0.64, 3.5]],
    3: [[245, 250, 0.54, -4], [695, 300, 0.54, 3], [470, 700, 0.54, -2]],
    4: [[245, 245, 0.5, -3.5], [695, 260, 0.5, 3], [245, 690, 0.5, 2.5], [695, 700, 0.5, -3]],
  };

  Ze.cena("visual", {
    montar(c, el) {
      const comp = c.composicao === "colagem" ? "colagem" : "sequencia";
      const area = h("div", `vis-area vis-${comp}`);
      const n = c.batidas.length;
      const pecas = c.batidas.map((b, i) => {
        const peca = h("div", "vis-peca");
        const m = midia(b, "");
        peca.append(m);
        const desenho = m.querySelector("svg.vis-icone"); // o ícone de reserva se desenha na palavra
        const r = b.rotulo ? h("div", "vis-rotulo", b.rotulo) : null;
        if (r) peca.append(r);
        if (comp === "colagem") {
          const [x, y, s, rot] = GRADE[n][i];
          peca.style.left = `${x}px`;
          peca.style.top = `${y}px`;
          peca.style.setProperty("--escala", String(s));
          peca.style.setProperty("--rot", `${rot}deg`);
        }
        area.append(peca);
        return { peca, m, r, desenho };
      });
      el.append(area);
      return { comp, pecas, foco: area };
    },
    render(t, d, s, ctx) {
      const quando = tempos(ctx.cena, s.pecas.length, d);
      if (s.comp === "sequencia") {
        // um cartão só, que troca na palavra: corte seco e um soco de 150 ms
        let atual = 0;
        quando.forEach((q, i) => { if (t >= q) atual = i; });
        s.pecas.forEach((x, i) => {
          x.peca.style.display = i === atual ? "" : "none";
          if (i !== atual) return;
          const p = curvas.chega(prog(t, quando[i], 0.16));
          const primeira = i === 0 ? cl(prog(t, quando[0], 0.12)) : 1;
          x.peca.style.opacity = String(primeira);
          x.peca.style.transform = `scale(${(1.1 - 0.1 * p).toFixed(4)})`;
          if (x.desenho) Ze.desenhar(x.desenho, t, quando[i], 0.5);
          if (x.r) revela(x.r, t, quando[i] + 0.08, "desfoque", { d: 0.14 });
        });
        s.foco = s.pecas[atual].peca;
      } else {
        // a colagem: cada peça chega na palavra dela com mola; a da vez dá um pulso
        let atual = -1;
        quando.forEach((q, i) => { if (t >= q) atual = i; });
        s.pecas.forEach((x, i) => {
          const q = quando[i];
          const p = curvas.mola(prog(t, q, 0.5));
          const visivel = t >= q;
          const pulso = i === atual ? 1 + 0.05 * Math.sin(Math.PI * prog(t, q + 0.35, 0.3)) : 1;
          x.peca.style.opacity = visivel ? String(cl(prog(t, q, 0.12))) : "0";
          x.peca.style.transform = `translate(-50%, -50%) rotate(calc(var(--rot) * ${p.toFixed(3)})) scale(calc(var(--escala) * ${((0.4 + 0.6 * p) * pulso).toFixed(4)}))`;
          x.peca.classList.toggle("atual", i === atual);
          if (x.desenho) Ze.desenhar(x.desenho, t, q + 0.05, 0.5);
          if (x.r) revela(x.r, t, q + 0.15, "desfoque", { d: 0.16 });
        });
        if (atual >= 0) s.foco = s.pecas[atual].peca;
      }
    },
  });

  // --- o item ganha a imagem: o logo no lugar do ícone; a foto em cima do cartão -------------
  const item = Ze.cenas.item;
  Ze.cena("item", {
    montar(c, el, ctx) {
      const s = item.montar(c, el, ctx);
      if (c.imagem && c.imagem_tipo === "logo") {
        const logo = h("img", "item-logo");
        logo.src = c.imagem;
        s.icone.replaceWith(logo);
        s.logo = logo;
      } else if (c.imagem) {
        const foto = h("div", "item-foto");
        const img = h("img");
        img.src = c.imagem;
        foto.append(img);
        s.cartao.prepend(foto);
      }
      return s;
    },
    render(t, d, s, ctx) {
      item.render(t, d, s, ctx);
      if (s.logo) mola(s.logo, t, s.continua ? 0 : 0.3, { de: 0.3, d: 0.45 });
    },
  });
})();
