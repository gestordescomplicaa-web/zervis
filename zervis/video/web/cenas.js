// As cenas embutidas dos vídeos do Zé (ADR 0106, 0107 e 0110). Cada uma recebe a cena do plano de
// direção e desenha com a marca; o visual fino é do estilo (CSS). Um estilo pode trocar qualquer
// uma ou acrescentar outras no próprio `cenas.js`, com `Ze.cena(tipo, {montar, render})`.
//
// O tempo vem da voz: `c.palavras` traz cada palavra da fala com o instante em que é dita, e os
// `tempos_*` dizem quando cada elemento entra (a palavra do "quando", em segundos desde o começo
// da cena). `ctx.cena` é a cena. `montar` devolve `foco`: o elemento de onde a íris abre e para
// onde o zoom atravessa na transição para a cena seguinte.
//
// A edição (ADR 0110): cada cena entra de um jeito (desfoque, tinta, queda, lado, máscara, giro em
// perspectiva), o que assenta fica parado, e o 3D aparece onde é conteúdo gerado (cartões, o logo),
// nunca numa tela de produto.
(() => {
  const { h, revela, mola, prog, curvas, contar, cl } = window.Ze;

  /** O brilho atrás do que importa: cresce na entrada e fica (nada de respirar). */
  function brilho(el, t, a) {
    const p = curvas.chega(prog(t, a, 0.9));
    el.style.opacity = String(0.85 * p);
    el.style.transform = `translate(-50%, -50%) scale(${0.6 + 0.4 * p})`;
  }

  /** Quando cada um dos `n` elementos entra: o tempo da palavra ou, sem ela, espalhado. */
  function tempos(lista, n, d, inicio = 0.4) {
    const passo = cl((d - inicio - 1.0) / n, 0.35, 1.2);
    const saida = [];
    for (let i = 0; i < n; i++) {
      const dado = lista && lista[i];
      const t = typeof dado === "number" ? dado : inicio + i * passo;
      // o tempo da voz vale, mas nunca antes do anterior: a ordem da tela é a da lista
      saida.push(Math.max(t, i ? saida[i - 1] + 0.22 : 0.15));
    }
    return saida;
  }

  /** O marca-texto do destaque: a faixa corre por baixo da palavra depois que ela é dita. */
  function marcaTexto(spans, c, t) {
    spans.forEach((x, k) => {
      if (!x.classList.contains("destaque")) return;
      const w = c.palavras[k];
      const p = curvas.chega(prog(t, (w ? w.f - c.inicio : 0) - 0.05, 0.45));
      x.style.setProperty("--marca", p.toFixed(3));
    });
  }

  // --- gancho e frase: a fala é a tipografia ----------------------------------------------------
  function falaGrande(classe) {
    return {
      montar(c, el) {
        const b = h("div", "brilho");
        const r = c.rotulo ? h("div", "rotulo", c.rotulo) : null;
        const aspas = classe === "frase" && c.composicao !== "cheia" ? h("div", "aspas", "“") : null;
        const t = h("h1", `fala-grande ${classe}`);
        const spans = Ze.falaCinetica(t, c);
        const gigante = c.composicao === "gigante";
        if (gigante) {
          // uma palavra por linha: o tamanho que a maior couber na largura e todas na altura;
          // palavras de até 2 letras grudam na seguinte ("o dia", "a sua"), sem linha sozinha
          const maior = Math.max(...c.palavras.map((w) => w.p.length));
          const linhas = c.palavras.filter((w, k) => !(w.p.length <= 2 && k < c.palavras.length - 1)).length;
          t.style.fontSize = `${Math.round(Math.min(220, 900 / (maior * 0.56), 1120 / (linhas * 0.93)))}px`;
          spans.forEach((x, k) => { if (x.textContent.length <= 2 && k < spans.length - 1) x.classList.add("cola"); });
        } else {
          const n = c.fala.length;
          const [max, min] = classe === "gancho" ? [118, 72] : [94, 62];
          t.style.fontSize = `${Math.round(max - (max - min) * cl((n - 20) / 90))}px`;
        }
        el.append(b);
        if (r) el.append(r);
        if (aspas) el.append(aspas);
        el.append(t);
        const foco = spans.find((s) => s.classList.contains("destaque")) || t;
        return { b, r, aspas, spans, foco };
      },
      render(t, d, s, ctx) {
        const c = ctx.cena;
        brilho(s.b, t, 0);
        if (s.r) revela(s.r, t, 0.02, "mascara");
        if (s.aspas) mola(s.aspas, t, 0.0, { de: 0.2 });
        // cada composição entra de um jeito: gigante cai com peso, à esquerda chega de lado,
        // a frase em fundo cheio acende do cinza, e o centro nasce do desfoque
        const jeito = c.composicao === "gigante" ? "queda"
          : c.composicao === "esquerda" ? "lado"
          : c.composicao === "cheia" || classe === "frase" ? "tinta"
          : "desfoque";
        Ze.animarFala(s.spans, c, t, jeito);
        marcaTexto(s.spans, c, t);
      },
    };
  }
  Ze.cena("gancho", falaGrande("gancho"));
  Ze.cena("frase", falaGrande("frase"));

  // --- passos: cartões que giram em perspectiva até ficar de frente, na palavra deles ---------
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
      return { titulo, itens, linha, foco: lista };
    },
    render(t, d, s, ctx) {
      if (s.titulo) revela(s.titulo, t, 0.02, "mascara");
      const n = s.itens.length;
      const quando = tempos(ctx.cena.tempos_passos, n, d);
      let ativo = 0;
      s.itens.forEach(({ item, num }, i) => {
        revela(item, t, quando[i], "giro");
        mola(num, t, quando[i] + 0.12, { de: 0.3 });
        if (t >= quando[i]) ativo = i;
      });
      s.itens.forEach(({ item }, i) => item.classList.toggle("ativo", t >= quando[i] && i === ativo));
      s.foco = s.itens[ativo].item;
      // a linha chega a cada número junto com ele
      const alvo = quando.findLastIndex((q) => t >= q);
      const ate = alvo <= 0 ? 0 : (alvo - 1 + curvas.chega(prog(t, quando[alvo], 0.4))) / Math.max(1, n - 1);
      s.linha.style.transform = `scaleY(${cl(ate)})`;
    },
  });

  // --- antes e depois: empilhado (o depois cai por cima) ou dividido (uma cortina) -------------
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
        return { titulo, antes, depois, icone, fio, foco: depois };
      }
      el.append(antes, depois);
      return { titulo, antes, depois, icone, fio: null, foco: depois };
    },
    render(t, d, s, ctx) {
      const c = ctx.cena;
      if (s.titulo) revela(s.titulo, t, 0.02, "mascara");
      const virada = typeof c.tempo === "number" ? Math.max(0.9, c.tempo) : Math.min(d * 0.42, 2.2);
      if (s.fio) {
        revela(s.antes, t, 0.1, "desfoque", { d: 0.2 });
        const p = curvas.vaivem(prog(t, virada, 0.6));
        s.depois.style.clipPath = `inset(0 ${(1 - p) * 100}% 0 0 round 34px)`;
        s.antes.style.opacity = String(1 - p);  // some por baixo da cortina, sem vazar
        s.fio.style.opacity = String(p > 0 && p < 1 ? 1 : 0);
        s.fio.style.transform = `translateX(${p * 900}px)`;
        mola(s.icone, t, virada + 0.45, { de: 0.2 });
        return;
      }
      revela(s.antes, t, 0.15, "lado");
      revela(s.depois, t, virada, "queda");
      mola(s.icone, t, virada + 0.2, { de: 0.2 });
      // o antes recua quando o depois chega (sem sumir: a comparação continua na tela)
      if (t >= virada) {
        const r = curvas.chega(prog(t, virada, 0.5));
        s.antes.style.opacity = String(1 - 0.5 * r);
        s.antes.style.transform = `scale(${1 - 0.06 * r})`;
        s.antes.style.filter = r > 0.05 ? `saturate(${1 - 0.8 * r})` : "none";
      }
    },
  });

  // --- conversa: balões que estalam do canto deles, com o "digitando" antes da resposta ---------
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
        balao.style.transformOrigin = empresa ? "0% 100%" : "100% 100%";
        linha.append(balao);
        corpo.append(linha);
        return { linha, balao, digitando };
      });
      el.append(janela);
      return { janela, msgs, foco: janela };
    },
    render(t, d, s, ctx) {
      revela(s.janela, t, 0, "giro");
      const quando = tempos(ctx.cena.tempos_mensagens, s.msgs.length, d, 0.5);
      s.msgs.forEach(({ linha, balao, digitando }, i) => {
        const chega = quando[i];
        if (digitando) {
          const de = Math.max(i ? quando[i - 1] + 0.3 : 0.3, chega - 0.6);
          digitando.style.display = t >= de && t < chega ? "" : "none";
          [...digitando.children].forEach((b, k) => {
            b.style.transform = `translateY(${-6 * Math.max(0, Math.sin((t - de) * 9 - k * 0.9))}px)`;
          });
        }
        linha.style.display = t >= chega ? "" : "none";
        mola(balao, t, chega, { de: 0.55, d: 0.4 });
      });
    },
  });

  // --- lista: cartões que giram em perspectiva, ou um item por vez, enorme ----------------------
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
      return { titulo, itens, umPorVez, pontos, foco: lista };
    },
    render(t, d, s, ctx) {
      if (s.titulo) revela(s.titulo, t, 0.02, "mascara");
      const n = s.itens.length;
      const quando = tempos(ctx.cena.tempos_itens, n, d);
      const atual = Math.max(0, quando.findLastIndex((q) => t >= q));
      s.foco = s.itens[atual].item;
      if (s.umPorVez) {
        // um de cada vez: o da vez cai enorme, o anterior sai rápido para cima, borrado
        s.itens.forEach(({ item, marca }, i) => {
          if (i < atual) {
            const p = curvas.acelera(prog(t, quando[i + 1] - 0.05, 0.22));
            item.style.opacity = String(1 - p);
            item.style.transform = `translateY(${-140 * p}px)`;
            item.style.filter = p > 0.05 && p < 1 ? `blur(${(10 * p).toFixed(1)}px)` : "none";
          } else {
            revela(item, t, quando[i], "queda");
            revela(marca, t, quando[i] + 0.08, "mascara");
          }
        });
        [...s.pontos.children].forEach((p, i) => p.classList.toggle("aceso", i <= atual && t >= quando[0]));
        return;
      }
      s.itens.forEach(({ item, marca }, i) => {
        revela(item, t, quando[i], "giro");
        mola(marca, t, quando[i] + 0.15, { de: 0.1 });
        item.classList.toggle("ativo", t >= quando[i] && i === atual);
      });
    },
  });

  // --- número: conta crescendo junto (quanto maior, maior na tela) e assenta --------------------
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
      return { b, anel, arco, valor, traco, r, fonte, pct, texto: String(c.valor), foco: valor };
    },
    render(t, d, s) {
      brilho(s.b, t, 0);
      // a contagem dura 1,4 s e assenta; o número cresce com ela e dá um estalo ao chegar
      const p = prog(t, 0.15, 1.4);
      contar(s.valor, s.texto, p);
      const estalo = Math.sin(Math.PI * prog(t, 1.55, 0.22)) * 0.05;
      s.valor.style.opacity = String(cl(p * 5));
      s.valor.style.transform = `scale(${0.72 + 0.28 * curvas.saiForte(p) + estalo})`;
      s.valor.style.filter = p < 0.2 ? `blur(${((0.2 - p) * 40).toFixed(1)}px)` : "none";
      if (s.anel) {
        revela(s.anel, t, 0.0, "desfoque", { d: 0.25 });
        s.arco.style.strokeDashoffset = String(553 * (1 - s.pct * curvas.saiForte(p)));
      } else {
        s.traco.style.transform = `scaleX(${curvas.chega(prog(t, 1.5, 0.5))})`;
      }
      revela(s.r, t, 1.55, "mascara");
      if (s.fonte) revela(s.fonte, t, 1.9, "tinta");
    },
  });

  // --- fecho: o logo extrudado em 3D vira com a luz correndo, o nome letra a letra -------------
  const CAMADAS = 12;
  Ze.cena("fecho", {
    montar(c, el, ctx) {
      const b = h("div", "brilho");
      const palco = h("div", "logo3d");
      const giro = h("div", "logo3d-giro");
      for (let i = CAMADAS - 1; i >= 0; i--) {
        const camada = h("div", `logo3d-camada${i === 0 ? " frente" : ""}`);
        if (ctx.marca.logo) { const img = h("img"); img.src = ctx.marca.logo; camada.append(img); }
        else camada.append(h("span", "logo3d-letra", (ctx.marca.nome || "?").slice(0, 1)));
        // a extrusão: camadas para trás, cada uma mais escura (o lado do bloco)
        camada.style.transform = `translateZ(${-i * 4}px)`;
        if (i > 0) camada.style.filter = `brightness(${(0.62 - i * 0.025).toFixed(3)})`;
        if (i === 0) camada.append(h("div", "logo3d-luz"));
        giro.append(camada);
      }
      palco.append(giro);
      const nome = h("div", "fecho-nome");
      const letras = Ze.letras(nome, ctx.marca.nome || "");
      const arroba = ctx.marca.instagram ? h("div", "fecho-arroba", `@${ctx.marca.instagram}`) : null;
      const botao = h("div", "fecho-chamada", c.chamada || "");
      const detalhe = c.detalhe ? h("div", "fecho-detalhe", c.detalhe) : null;
      el.append(b, palco, nome);
      if (arroba) el.append(arroba);
      el.append(botao);
      if (detalhe) el.append(detalhe);
      const luz = giro.querySelector(".logo3d-luz");
      return { b, palco, giro, luz, letras, arroba, botao, detalhe, foco: botao };
    },
    render(t, d, s) {
      brilho(s.b, t, 0);
      // o logo: chega de lado, girando em Y e inclinado em X, e assenta de frente com peso
      // (começa depois da transição e gira devagar o bastante para o 3D ser visto)
      const k = prog(t, 0.3, 1.3), p = curvas.vaivem(k);
      s.palco.style.opacity = String(cl(prog(t, 0.2, 0.25)));
      s.giro.style.transform = `rotateX(${(16 * (1 - p)).toFixed(2)}deg) rotateY(${(-118 * (1 - p)).toFixed(2)}deg) scale(${0.7 + 0.3 * p})`;
      // a luz corre pela face quando ele assenta
      const l = curvas.vaivem(prog(t, 1.5, 0.9));
      s.luz.style.transform = `translateX(${(-130 + 260 * l).toFixed(1)}%) skewX(-18deg)`;
      s.luz.style.opacity = String(l > 0 && l < 1 ? 1 : 0);
      s.letras.forEach((x, i) => revela(x, t, 1.1 + i * 0.035, "desfoque", { d: 0.16 }));
      if (s.arroba) revela(s.arroba, t, 1.5, "desfoque", { d: 0.2 });
      revela(s.botao, t, 1.6, "mascara");
      // o botão: aperta e volta com mola (sem anel de clique: é cara de vídeo gerado)
      const clique = Math.min(2.6, d * 0.6);
      if (t >= clique) {
        const aperto = prog(t, clique, 0.1), solta = prog(t, clique + 0.1, 0.4);
        s.botao.style.transform = `scale(${1 - 0.07 * aperto + 0.07 * curvas.mola(solta)})`;
      }
      if (s.detalhe) revela(s.detalhe, t, 1.9, "desfoque", { d: 0.2 });
    },
  });
})();
