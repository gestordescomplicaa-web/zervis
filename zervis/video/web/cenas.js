// As cenas embutidas dos vídeos do Zé (ADR 0106). Cada uma recebe o pedaço do roteiro dela e
// desenha com a marca; o visual fino é do estilo (CSS). Um estilo pode trocar qualquer uma ou
// acrescentar outras no próprio `cenas.js`, com `Ze.cena(tipo, {montar, render})`.
//
// A coreografia segue regras de motion design: a entrada é uma onda (cada parte começa antes de a
// anterior assentar), nada entra de uma vez, o que importa ganha uma mola ou um brilho, e tudo
// assenta cedo para ser lido enquanto a voz fala.
(() => {
  const { h, entra, mola, palavras, cascata, tamanho, prog, curvas, contar, cl } = window.Ze;

  /** O brilho atrás do que importa: cresce na entrada e respira com a voz. */
  function brilho(el, t, a, v = 0) {
    const p = curvas.sai(prog(t, a, 0.9));
    el.style.opacity = String(0.85 * p);
    el.style.transform = `translate(-50%, -50%) scale(${0.6 + 0.4 * p + 0.05 * v})`;
  }

  /** Um rótulo pequeno em cápsula (a categoria, o nome da marca). */
  function rotulo(el, texto) {
    if (!texto) return null;
    const r = h("div", "rotulo", texto);
    el.append(r);
    return r;
  }

  // --- gancho: a frase que faz parar de rolar ---------------------------------------------------
  Ze.cena("gancho", {
    montar(c, el) {
      const b = h("div", "brilho");
      const r = rotulo(el, c.rotulo);
      const t = h("h1", "manchete");
      t.style.fontSize = `${tamanho(c.texto, 132, 84, 16, 64)}px`;
      const spans = palavras(t, c.texto, c.destaque);
      const sub = c.apoio ? h("p", "apoio", c.apoio) : null;
      el.append(b, t);
      if (sub) el.append(sub);
      const traco = h("div", "traco");
      el.append(traco);
      return { b, r, t, spans, sub, traco };
    },
    render(t, d, s, ctx) {
      brilho(s.b, t, 0, ctx.volume);
      if (s.r) entra(s.r, t, 0.05, { y: 20, blur: 0, d: 0.45 });
      const fim = cascata(s.spans, t, 0.12);
      s.traco.style.transform = `scaleX(${curvas.saiForte(prog(t, fim - 0.2, 0.6))})`;
      if (s.sub) entra(s.sub, t, fim - 0.1, { y: 24, blur: 6 });
      // o destaque varre um brilho por dentro das letras depois de assentar
      s.spans.forEach((x) => x.classList.contains("destaque") && x.style.setProperty("--varre", String(prog(t, fim, 1.2))));
    },
  });

  // --- frase: uma afirmação grande, com aspas --------------------------------------------------
  Ze.cena("frase", {
    montar(c, el) {
      const b = h("div", "brilho");
      const aspas = h("div", "aspas", "“");
      const t = h("p", "frase-texto");
      t.style.fontSize = `${tamanho(c.texto, 96, 64, 24, 120)}px`;
      const spans = palavras(t, c.texto, c.destaque);
      el.append(b, aspas, t);
      return { b, aspas, spans };
    },
    render(t, d, s, ctx) {
      brilho(s.b, t, 0, ctx.volume);
      mola(s.aspas, t, 0.05, { de: 0.2 });
      cascata(s.spans, t, 0.25, { y: 40 });
    },
  });

  // --- passos: um fluxo que se monta, ligado por uma linha que se desenha -----------------------
  Ze.cena("passos", {
    montar(c, el) {
      const titulo = h("h2", "titulo-cena", c.titulo || "");
      const lista = h("div", "passos");
      const linha = h("div", "passos-linha");
      lista.append(linha);
      const itens = c.passos.map((texto, i) => {
        const item = h("div", "passo");
        const num = h("div", "passo-num", String(i + 1));
        const txt = h("div", "passo-texto", texto);
        item.append(num, txt);
        lista.append(item);
        return { item, num };
      });
      el.append(titulo, lista);
      return { titulo, itens, linha };
    },
    render(t, d, s) {
      entra(s.titulo, t, 0.05);
      const n = s.itens.length;
      const passo = cl((d - 1.6) / n, 0.45, 1.1);
      s.itens.forEach(({ item, num }, i) => {
        const a = 0.45 + i * passo;
        entra(item, t, a, { x: -40, y: 0, blur: 8, d: 0.5 });
        mola(num, t, a + 0.08, { de: 0.3 });
        const ativo = t >= a && (i === n - 1 || t < a + passo);
        item.classList.toggle("ativo", ativo);
      });
      // a linha liga os números: chega a cada passo junto com ele
      const p = prog(t, 0.45, passo * (n - 1) + 0.3);
      s.linha.style.transform = `scaleY(${curvas.sai(p)})`;
    },
  });

  // --- antes e depois: o depois chega e empurra o antes para trás -------------------------------
  Ze.cena("antes_depois", {
    montar(c, el) {
      const titulo = c.titulo ? h("h2", "titulo-cena", c.titulo) : null;
      const antes = h("div", "lado antes");
      antes.append(h("div", "lado-rotulo", c.rotulo_antes || "Antes"), h("div", "lado-icone", "×"), h("div", "lado-texto", c.antes));
      const depois = h("div", "lado depois");
      const icone = h("div", "lado-icone", "✓");
      depois.append(h("div", "lado-rotulo", c.rotulo_depois || "Depois"), icone, h("div", "lado-texto", c.depois));
      if (titulo) el.append(titulo);
      el.append(antes, depois);
      return { titulo, antes, depois, icone };
    },
    render(t, d, s) {
      if (s.titulo) entra(s.titulo, t, 0.05);
      entra(s.antes, t, 0.25, { y: 60 });
      const virada = Math.min(d * 0.42, 2.2);
      entra(s.depois, t, virada, { y: 90, escala: 0.94 });
      mola(s.icone, t, virada + 0.25, { de: 0.2 });
      // o antes recua quando o depois chega (sem sumir: a comparação continua na tela)
      const r = curvas.sai(prog(t, virada, 0.6));
      if (t >= virada) {
        s.antes.style.opacity = String(1 - 0.45 * r);
        s.antes.style.transform = `scale(${1 - 0.05 * r})`;
      }
    },
  });

  // --- conversa: balões chegando, com o "digitando" antes da resposta ---------------------------
  Ze.cena("conversa", {
    montar(c, el, ctx) {
      const janela = h("div", "conversa");
      const topo = h("div", "conversa-topo");
      const avatar = h("div", "conversa-avatar");
      if (ctx.marca.logo) { const img = h("img"); img.src = ctx.marca.logo; avatar.append(img); }
      else avatar.textContent = (ctx.marca.nome || "?").slice(0, 1);
      const quem = h("div", "conversa-quem");
      quem.append(h("b", "", ctx.marca.nome || "Atendimento"), h("small", "", "online"));
      topo.append(avatar, quem, h("div", "selo", "Ilustração"));
      const corpo = h("div", "conversa-corpo");
      janela.append(topo, corpo);
      const msgs = c.mensagens.map((m) => {
        const empresa = m.de !== "cliente";
        const linha = h("div", `msg ${empresa ? "empresa" : "cliente"}`);
        const digitando = empresa ? h("div", "digitando") : null;
        if (digitando) { digitando.append(h("i"), h("i"), h("i")); corpo.append(digitando); }
        const balao = h("div", "balao", m.texto);
        linha.append(balao);
        corpo.append(linha);
        return { linha, digitando, empresa };
      });
      el.append(janela);
      return { janela, msgs };
    },
    render(t, d, s) {
      entra(s.janela, t, 0, { y: 70, escala: 0.96 });
      const n = s.msgs.length;
      const passo = cl((d - 1.2) / n, 0.6, 1.6);
      s.msgs.forEach(({ linha, digitando, empresa }, i) => {
        const a = 0.5 + i * passo;
        const chega = empresa ? a + 0.55 : a;
        if (digitando) {
          const visivel = t >= a && t < chega;
          digitando.style.display = visivel ? "" : "none";
          [...digitando.children].forEach((b, k) => {
            b.style.transform = `translateY(${-6 * Math.max(0, Math.sin((t - a) * 9 - k * 0.9))}px)`;
          });
        }
        linha.style.display = t >= chega ? "" : "none";
        entra(linha, t, chega, { y: 26, blur: 0, d: 0.4, escala: 0.92 });
      });
    },
  });

  // --- lista: itens que acendem um a um, com a marcação passando ---------------------------------
  Ze.cena("lista", {
    montar(c, el) {
      const titulo = h("h2", "titulo-cena", c.titulo || "");
      const lista = h("div", "lista-itens");
      const itens = c.itens.map((texto) => {
        const item = h("div", "item");
        const check = h("div", "item-check", "✓");
        item.append(check, h("div", "item-texto", texto));
        lista.append(item);
        return { item, check };
      });
      el.append(titulo, lista);
      return { titulo, itens };
    },
    render(t, d, s) {
      entra(s.titulo, t, 0.05);
      const n = s.itens.length;
      const passo = cl((d - 1.4) / n, 0.4, 1.1);
      s.itens.forEach(({ item, check }, i) => {
        const a = 0.4 + i * passo;
        entra(item, t, a, { y: 40, d: 0.5 });
        mola(check, t, a + 0.15, { de: 0.1 });
        item.classList.toggle("ativo", t >= a && (i === n - 1 || t < a + passo));
      });
    },
  });

  // --- número: um dado que conta, com a fonte ---------------------------------------------------
  Ze.cena("numero", {
    montar(c, el) {
      const b = h("div", "brilho");
      const anel = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      anel.setAttribute("viewBox", "0 0 200 200");
      anel.classList.add("anel");
      const fundoAnel = document.createElementNS(anel.namespaceURI, "circle");
      const arco = document.createElementNS(anel.namespaceURI, "circle");
      for (const x of [fundoAnel, arco]) { x.setAttribute("cx", "100"); x.setAttribute("cy", "100"); x.setAttribute("r", "88"); }
      fundoAnel.classList.add("anel-fundo"); arco.classList.add("anel-arco");
      anel.append(fundoAnel, arco);
      const valor = h("div", "numero-valor");
      const r = h("p", "numero-rotulo", c.rotulo || "");
      const fonte = c.fonte ? h("p", "numero-fonte", `Fonte: ${c.fonte}`) : null;
      el.append(b, anel, valor, r);
      if (fonte) el.append(fonte);
      const pct = /%\s*$/.test(c.valor) ? cl(parseFloat(String(c.valor).replace(",", ".")) / 100) : 1;
      return { b, anel, arco, valor, r, fonte, pct, texto: String(c.valor) };
    },
    render(t, d, s, ctx) {
      brilho(s.b, t, 0, ctx.volume);
      mola(s.anel, t, 0.05, { de: 0.7, d: 0.7 });
      const p = prog(t, 0.2, 1.4);
      contar(s.valor, s.texto, p);
      s.arco.style.strokeDashoffset = String(553 * (1 - s.pct * curvas.saiForte(p)));
      entra(s.valor, t, 0.15, { y: 20, blur: 6 });
      entra(s.r, t, 0.6, { y: 24 });
      if (s.fonte) entra(s.fonte, t, 1.0, { y: 10, blur: 0 });
    },
  });

  // --- fecho: a marca, a chamada como botão e o clique ------------------------------------------
  Ze.cena("fecho", {
    montar(c, el, ctx) {
      const b = h("div", "brilho");
      const logo = h("div", "fecho-logo");
      if (ctx.marca.logo) { const img = h("img"); img.src = ctx.marca.logo; logo.append(img); }
      else logo.textContent = (ctx.marca.nome || "?").slice(0, 1);
      const nome = h("div", "fecho-nome", ctx.marca.nome || "");
      const arroba = ctx.marca.instagram ? h("div", "fecho-arroba", `@${ctx.marca.instagram}`) : null;
      const botao = h("div", "fecho-chamada", c.chamada || "");
      const onda = h("div", "fecho-onda");
      botao.append(onda);
      const detalhe = c.detalhe ? h("div", "fecho-detalhe", c.detalhe) : null;
      el.append(b, logo, nome);
      if (arroba) el.append(arroba);
      el.append(botao);
      if (detalhe) el.append(detalhe);
      return { b, logo, nome, arroba, botao, onda, detalhe };
    },
    render(t, d, s, ctx) {
      brilho(s.b, t, 0, ctx.volume);
      mola(s.logo, t, 0.05, { de: 0.3, d: 0.7 });
      entra(s.nome, t, 0.3);
      if (s.arroba) entra(s.arroba, t, 0.45, { y: 20, blur: 0 });
      entra(s.botao, t, 0.7, { y: 40, escala: 0.9 });
      // o clique no botão: aperta, volta com mola e solta uma onda
      const clique = Math.min(1.7, d * 0.5);
      const aperto = prog(t, clique, 0.12), solta = prog(t, clique + 0.12, 0.45);
      if (t >= clique) s.botao.style.transform = `scale(${1 - 0.06 * aperto + 0.06 * curvas.mola(solta)})`;
      const o = prog(t, clique + 0.1, 0.8);
      s.onda.style.opacity = String(o > 0 && o < 1 ? 0.55 * (1 - o) : 0);
      s.onda.style.transform = `scale(${1 + 0.45 * curvas.sai(o)})`;
      if (s.detalhe) entra(s.detalhe, t, 1.0, { y: 16, blur: 0 });
    },
  });
})();
