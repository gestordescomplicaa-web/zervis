// As cenas embutidas dos vídeos do Zé (ADR 0106 e 0107). Cada uma recebe a cena do plano de
// direção e desenha com a marca; o visual fino é do estilo (CSS). Um estilo pode trocar qualquer
// uma ou acrescentar outras no próprio `cenas.js`, com `Ze.cena(tipo, {montar, render})`.
//
// O tempo vem da voz: `c.palavras` traz cada palavra da fala com o instante em que é dita, e os
// `tempos_*` dizem quando cada elemento entra (a palavra do "quando", em segundos desde o começo
// da cena). Sem eles, os elementos se espalham no tempo da cena. `ctx.cena` é a cena.
//
// A tela não repete a fala: gancho e frase são a própria fala em tipografia, palavra por palavra;
// as outras mostram a ideia em poucas palavras e deixam a fala para a legenda embaixo.
(() => {
  const { h, entra, mola, tamanho, prog, curvas, contar, cl } = window.Ze;

  /** O brilho atrás do que importa: cresce na entrada e respira com a voz. */
  function brilho(el, t, a, v = 0) {
    const p = curvas.sai(prog(t, a, 0.9));
    el.style.opacity = String(0.85 * p);
    el.style.transform = `translate(-50%, -50%) scale(${0.6 + 0.4 * p + 0.05 * v})`;
  }

  /** Quando cada um dos `n` elementos entra: o tempo da palavra ou, sem ela, espalhado. */
  function tempos(lista, n, d, inicio = 0.4) {
    const passo = cl((d - inicio - 1.0) / n, 0.35, 1.2);
    const saida = [];
    for (let i = 0; i < n; i++) {
      const dado = lista && lista[i];
      const t = typeof dado === "number" ? dado : inicio + i * passo;
      // o tempo da voz vale, mas nunca antes do anterior: a ordem da tela é a da lista
      saida.push(Math.max(t, i ? saida[i - 1] + 0.25 : 0.15));
    }
    return saida;
  }

  // --- gancho e frase: a fala é a tipografia ----------------------------------------------------
  function falaGrande(classe, max, min) {
    return {
      montar(c, el) {
        const b = h("div", "brilho");
        const r = c.rotulo ? h("div", "rotulo", c.rotulo) : null;
        const aspas = classe === "frase" ? h("div", "aspas", "“") : null;
        const t = h("h1", `fala-grande ${classe}`);
        t.style.fontSize = `${tamanho(c.fala, max, min, 20, 110)}px`;
        const spans = Ze.falaCinetica(t, c);
        const traco = h("div", "traco");
        el.append(b);
        if (r) el.append(r);
        if (aspas) el.append(aspas);
        el.append(t, traco);
        return { b, r, aspas, spans, traco };
      },
      render(t, d, s, ctx) {
        const c = ctx.cena;
        brilho(s.b, t, 0, ctx.volume);
        if (s.r) entra(s.r, t, 0.02, { y: 20, blur: 0, d: 0.4 });
        if (s.aspas) mola(s.aspas, t, 0.0, { de: 0.2 });
        Ze.animarFala(s.spans, c, t);
        const fim = c.palavras.length ? c.palavras[c.palavras.length - 1].f - c.inicio : 1;
        s.traco.style.transform = `scaleX(${curvas.saiForte(prog(t, fim - 0.1, 0.6))})`;
        // o destaque varre um brilho por dentro das letras depois de dito
        s.spans.forEach((x, k) => {
          if (!x.classList.contains("destaque")) return;
          const w = c.palavras[k];
          x.style.setProperty("--varre", String(prog(t, w ? w.f - c.inicio : 0, 1.1)));
        });
      },
    };
  }
  Ze.cena("gancho", falaGrande("gancho", 118, 74));
  Ze.cena("frase", falaGrande("frase", 92, 62));

  // --- passos: um fluxo que se monta, cada passo na palavra dele --------------------------------
  Ze.cena("passos", {
    montar(c, el) {
      const titulo = c.titulo ? h("h2", "titulo-cena", c.titulo) : null;
      const lista = h("div", "passos");
      const linha = h("div", "passos-linha");
      lista.append(linha);
      const itens = c.passos.map((x, i) => {
        const item = h("div", "passo");
        const num = h("div", "passo-num", String(i + 1));
        item.append(num, h("div", "passo-texto", x.texto));
        lista.append(item);
        return { item, num };
      });
      if (titulo) el.append(titulo);
      el.append(lista);
      return { titulo, itens, linha };
    },
    render(t, d, s, ctx) {
      if (s.titulo) entra(s.titulo, t, 0.05);
      const n = s.itens.length;
      const quando = tempos(ctx.cena.tempos_passos, n, d);
      s.itens.forEach(({ item, num }, i) => {
        entra(item, t, quando[i], { x: -50, y: 0, blur: 8, d: 0.45 });
        mola(num, t, quando[i] + 0.06, { de: 0.3 });
        item.classList.toggle("ativo", t >= quando[i] && (i === n - 1 || t < quando[i + 1]));
      });
      // a linha chega a cada número junto com ele
      const alvo = quando.findLastIndex((q) => t >= q);
      const ate = alvo <= 0 ? 0 : (alvo - 1 + curvas.sai(prog(t, quando[alvo], 0.4))) / Math.max(1, n - 1);
      s.linha.style.transform = `scaleY(${cl(ate)})`;
    },
  });

  // --- antes e depois: empilhado (o depois empurra o antes) ou dividido (uma cortina) ----------
  Ze.cena("antes_depois", {
    montar(c, el) {
      const titulo = c.titulo ? h("h2", "titulo-cena", c.titulo) : null;
      const lado = (classe, rotulo, icone, texto) => {
        const x = h("div", `lado ${classe}`);
        const i = h("div", "lado-icone", icone);
        x.append(h("div", "lado-rotulo", rotulo), i, h("div", "lado-texto", texto));
        return [x, i];
      };
      const [antes] = lado("antes", "Antes", "×", c.antes);
      const [depois, icone] = lado("depois", "Depois", "✓", c.depois);
      if (titulo) el.append(titulo);
      if (c.composicao === "dividido") {
        const palco = h("div", "dividido");
        const fio = h("div", "dividido-fio");
        palco.append(antes, depois, fio);
        el.append(palco);
        return { titulo, antes, depois, icone, fio };
      }
      el.append(antes, depois);
      return { titulo, antes, depois, icone, fio: null };
    },
    render(t, d, s, ctx) {
      const c = ctx.cena;
      if (s.titulo) entra(s.titulo, t, 0.05);
      const virada = typeof c.tempo === "number" ? Math.max(0.9, c.tempo) : Math.min(d * 0.42, 2.2);
      if (s.fio) {
        // dividido: o depois abre por cima do antes como uma cortina, com o fio aceso na borda
        entra(s.antes, t, 0.1, { y: 0, blur: 8, escala: 1.04 });
        const p = curvas.vaivem(prog(t, virada, 0.7));
        s.depois.style.clipPath = `inset(0 ${(1 - p) * 100}% 0 0 round 34px)`;
        s.fio.style.opacity = String(p > 0 && p < 1 ? 1 : 0);
        s.fio.style.transform = `translateX(${p * 900}px)`;
        mola(s.icone, t, virada + 0.5, { de: 0.2 });
        return;
      }
      entra(s.antes, t, 0.2, { y: 60 });
      entra(s.depois, t, virada, { y: 90, escala: 0.94 });
      mola(s.icone, t, virada + 0.25, { de: 0.2 });
      const r = curvas.sai(prog(t, virada, 0.6));
      if (t >= virada) {
        s.antes.style.opacity = String(1 - 0.45 * r);
        s.antes.style.transform = `scale(${1 - 0.05 * r})`;
      }
    },
  });

  // --- conversa: balões chegando na palavra deles, com o "digitando" antes da resposta ----------
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
        linha.append(h("div", "balao", m.texto));
        corpo.append(linha);
        return { linha, digitando };
      });
      el.append(janela);
      return { janela, msgs };
    },
    render(t, d, s, ctx) {
      entra(s.janela, t, 0, { y: 70, escala: 0.96 });
      const quando = tempos(ctx.cena.tempos_mensagens, s.msgs.length, d, 0.5);
      s.msgs.forEach(({ linha, digitando }, i) => {
        const chega = quando[i];
        if (digitando) {
          const de = Math.max(i ? quando[i - 1] + 0.3 : 0.3, chega - 0.6);
          digitando.style.display = t >= de && t < chega ? "" : "none";
          [...digitando.children].forEach((b, k) => {
            b.style.transform = `translateY(${-6 * Math.max(0, Math.sin((t - de) * 9 - k * 0.9))}px)`;
          });
        }
        linha.style.display = t >= chega ? "" : "none";
        entra(linha, t, chega, { y: 26, blur: 0, d: 0.36, escala: 0.92 });
      });
    },
  });

  // --- lista: cartões que acendem, ou um item por vez, grande ----------------------------------
  Ze.cena("lista", {
    montar(c, el) {
      const titulo = c.titulo ? h("h2", "titulo-cena", c.titulo) : null;
      const umPorVez = c.composicao === "um_por_vez";
      const lista = h("div", umPorVez ? "lista-grande" : "lista-itens");
      const itens = c.itens.map((x, i) => {
        const item = h("div", umPorVez ? "item-grande" : "item");
        const marca = umPorVez ? h("div", "item-grande-num", String(i + 1).padStart(2, "0")) : h("div", "item-check", "✓");
        item.append(marca, h("div", umPorVez ? "item-grande-texto" : "item-texto", x.texto));
        lista.append(item);
        return { item, marca };
      });
      const pontos = umPorVez ? h("div", "pontos") : null;
      if (pontos) itens.forEach(() => pontos.append(h("i")));
      if (titulo) el.append(titulo);
      el.append(lista);
      if (pontos) el.append(pontos);
      return { titulo, itens, umPorVez, pontos };
    },
    render(t, d, s, ctx) {
      if (s.titulo) entra(s.titulo, t, 0.05);
      const n = s.itens.length;
      const quando = tempos(ctx.cena.tempos_itens, n, d);
      if (s.umPorVez) {
        // um de cada vez: o da vez entra de baixo, o anterior sobe e some
        const atual = Math.max(0, quando.findLastIndex((q) => t >= q));
        s.itens.forEach(({ item, marca }, i) => {
          if (i < atual) {
            const p = curvas.saiForte(prog(t, quando[i + 1], 0.4));
            item.style.opacity = String(1 - p);
            item.style.transform = `translateY(${-90 * p}px) scale(${1 - 0.08 * p})`;
            item.style.filter = p > 0 && p < 1 ? `blur(${6 * p}px)` : "none";
          } else {
            entra(item, t, quando[i], { y: 110, blur: 12, d: 0.5 });
            mola(marca, t, quando[i] + 0.05, { de: 0.5 });
          }
        });
        [...s.pontos.children].forEach((p, i) => p.classList.toggle("aceso", i <= atual && t >= quando[0]));
        return;
      }
      s.itens.forEach(({ item, marca }, i) => {
        entra(item, t, quando[i], { y: 40, d: 0.45 });
        mola(marca, t, quando[i] + 0.12, { de: 0.1 });
        item.classList.toggle("ativo", t >= quando[i] && (i === n - 1 || t < quando[i + 1]));
      });
    },
  });

  // --- número: anel que enche ou o número gigante, contando -----------------------------------
  Ze.cena("numero", {
    montar(c, el) {
      const b = h("div", "brilho");
      const gigante = c.composicao === "gigante";
      let anel = null, arco = null;
      if (!gigante) {
        anel = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        anel.setAttribute("viewBox", "0 0 200 200");
        anel.classList.add("anel");
        const fundoAnel = document.createElementNS(anel.namespaceURI, "circle");
        arco = document.createElementNS(anel.namespaceURI, "circle");
        for (const x of [fundoAnel, arco]) { x.setAttribute("cx", "100"); x.setAttribute("cy", "100"); x.setAttribute("r", "88"); }
        fundoAnel.classList.add("anel-fundo"); arco.classList.add("anel-arco");
        anel.append(fundoAnel, arco);
      }
      const valor = h("div", gigante ? "numero-gigante" : "numero-valor");
      const traco = gigante ? h("div", "traco") : null;
      const r = h("p", "numero-rotulo", c.rotulo || "");
      const fonte = c.fonte ? h("p", "numero-fonte", `Fonte: ${c.fonte}`) : null;
      el.append(b);
      if (anel) el.append(anel);
      el.append(valor);
      if (traco) el.append(traco);
      el.append(r);
      if (fonte) el.append(fonte);
      const pct = /%\s*$/.test(c.valor) ? cl(parseFloat(String(c.valor).replace(",", ".")) / 100) : 1;
      return { b, anel, arco, valor, traco, r, fonte, pct, texto: String(c.valor) };
    },
    render(t, d, s, ctx) {
      brilho(s.b, t, 0, ctx.volume);
      const p = prog(t, 0.2, 1.4);
      contar(s.valor, s.texto, p);
      if (s.anel) {
        mola(s.anel, t, 0.05, { de: 0.7, d: 0.7 });
        s.arco.style.strokeDashoffset = String(553 * (1 - s.pct * curvas.saiForte(p)));
        entra(s.valor, t, 0.15, { y: 20, blur: 6 });
      } else {
        // gigante: o número chega de perto, nítido, e o traço sublinha quando assenta
        entra(s.valor, t, 0.1, { y: 0, blur: 14, escala: 0.7, d: 0.8 });
        s.traco.style.transform = `scaleX(${curvas.saiForte(prog(t, 1.2, 0.6))})`;
      }
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
