// As cenas de arte dos vídeos do Zé (ADR 0110): metáforas animadas em vez de texto e cartões.
// A fala fica na legenda; a tela mostra a ideia com ícones que se desenham, conexões por onde
// correm dados, uma constelação em volta de um centro, o caos que vira ordem.
//
// Os ícones são os da Lucide que o Zé já traz (`zervis/marca_icones.json`, ISC): o modelo só
// escolhe o nome, e o desenho vem do arquivo (nunca do modelo). Tudo é função do tempo; o que
// parece aleatório (a posição do caos, a poeira) vem de um gerador com semente.
(() => {
  const { h, revela, mola, prog, curvas, cl } = window.Ze;
  const NS = "http://www.w3.org/2000/svg";

  /** Um gerador com semente (mulberry32): o mesmo vídeo, os mesmos "acasos". */
  Ze.semente = (n) => {
    let a = n >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };

  /** Um ícone da Lucide como SVG de traço, pronto para ser desenhado (`Ze.desenhar`). */
  Ze.icone = (nome, classe = "icone") => {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", classe);
    const icones = (window.VIDEO && window.VIDEO.icones) || {};
    svg.innerHTML = icones[nome] || icones.sparkles || "";
    svg.querySelectorAll("path, circle, rect, line, polyline, polygon, ellipse").forEach((p) => p.setAttribute("pathLength", "1"));
    return svg;
  };

  /** Desenha o ícone traço por traço a partir de `a` (cada traço um pouco depois do anterior). */
  Ze.desenhar = (svg, t, a, d = 0.8) => {
    const tracos = svg.querySelectorAll("path, circle, rect, line, polyline, polygon, ellipse");
    tracos.forEach((p, i) => {
      const k = curvas.chega(prog(t, a + i * 0.07, d));
      p.style.strokeDashoffset = String(1 - k);
    });
    svg.style.opacity = t >= a ? "1" : "0";
  };

  /** Ondas que se abrem de um ponto (uma vez, não em laço). */
  function ondas(aneis, t, a) {
    aneis.forEach((anel, i) => {
      const k = prog(t, a + i * 0.22, 1.1);
      anel.style.opacity = String(k > 0 && k < 1 ? 0.6 * (1 - k) : 0);
      anel.style.transform = `translate(-50%, -50%) scale(${0.5 + 1.9 * curvas.chega(k)})`;
    });
  }

  /** Partículas que estouram de um centro e se apagam (o "pousou"). */
  function particulas(el, n, semente) {
    const r = Ze.semente(semente);
    return Array.from({ length: n }, () => {
      const p = h("i", "faisca");
      el.append(p);
      return { p, ang: r() * Math.PI * 2, dist: 160 + r() * 260, tam: 0.5 + r() * 1.2 };
    });
  }
  function estourar(fs, t, a) {
    fs.forEach(({ p, ang, dist, tam }) => {
      const k = prog(t, a, 0.9), e = curvas.chega(k);
      p.style.opacity = String(k > 0 && k < 1 ? 1 - k : 0);
      p.style.transform = `translate(${Math.cos(ang) * dist * e}px, ${Math.sin(ang) * dist * e}px) scale(${tam * (1 - 0.6 * k)})`;
    });
  }

  /** Um nó: o círculo aceso com o ícone dentro e o rótulo embaixo. */
  function no(icone, rotulo, grande = false) {
    const caixa = h("div", `no${grande ? " grande" : ""}`);
    const disco = h("div", "no-disco");
    const svg = Ze.icone(icone, "icone no-icone");
    disco.append(svg);
    caixa.append(disco);
    const r = rotulo ? h("div", "no-rotulo", rotulo) : null;
    if (r) caixa.append(r);
    return { caixa, disco, svg, r };
  }

  /** Quando cada elemento entra: o tempo da palavra ou, sem ela, espalhado. */
  function tempos(lista, n, d, inicio = 0.35) {
    const passo = cl((d - inicio - 1.0) / n, 0.3, 1.2);
    const saida = [];
    for (let i = 0; i < n; i++) {
      const dado = lista && lista[i];
      const t = typeof dado === "number" ? dado : inicio + i * passo;
      saida.push(Math.max(t, i ? saida[i - 1] + 0.22 : 0.12));
    }
    return saida;
  }

  // --- ícone: o conceito desenhado grande --------------------------------------------------------
  Ze.cena("icone", {
    montar(c, el) {
      const palco = h("div", "arte-icone");
      const disco = h("div", "arte-disco");
      const aneis = [h("div", "anel"), h("div", "anel"), h("div", "anel")];
      const svg = Ze.icone(c.icone, "icone arte-heroi");
      const fx = h("div", "faiscas");
      const fs = particulas(fx, 18, c.icone.length * 97 + 7);
      palco.append(...aneis, disco, svg, fx);
      el.append(palco);
      const r = c.rotulo ? h("div", "arte-rotulo", c.rotulo) : null;
      if (r) el.append(r);
      return { disco, aneis, svg, fs, r, foco: svg };
    },
    render(t, d, s, ctx) {
      const a = typeof ctx.cena.tempo === "number" ? ctx.cena.tempo : 0.15;
      // o disco já está na carta quando ela chega; o ícone se desenha na palavra
      mola(s.disco, t, Math.min(a - 0.05, 0.1), { de: 0.2, d: 0.6 });
      Ze.desenhar(s.svg, t, a, 0.85);
      const pousou = a + 0.75;
      // o ícone dá um estalo quando termina de ser desenhado; as ondas e as faíscas saem dele
      const estalo = Math.sin(Math.PI * prog(t, pousou, 0.25)) * 0.08;
      s.svg.style.transform = `scale(${1 + estalo})`;
      s.svg.classList.toggle("aceso", t >= pousou);
      ondas(s.aneis, t, pousou);
      estourar(s.fs, t, pousou);
      if (s.r) revela(s.r, t, pousou + 0.1, "mascara");
    },
  });

  // --- conexão: nós ligados por linhas, com dados correndo por elas ------------------------------
  const LARGURA = 900, ALTURA = 860;
  Ze.cena("conexao", {
    montar(c, el) {
      const rede = h("div", "rede");
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("viewBox", `0 0 ${LARGURA} ${ALTURA}`);
      svg.setAttribute("class", "rede-linhas");
      rede.append(svg);
      const n = c.nos.length;
      // zigue-zague de cima para baixo (ou na diagonal, com dois)
      const pos = c.nos.map((_, i) => {
        const y = n === 1 ? ALTURA / 2 : 120 + i * ((ALTURA - 280) / (n - 1));
        const x = n === 2 ? (i ? 660 : 240) : i % 2 ? 660 : 240;
        return [x, y];
      });
      const nos = c.nos.map((x, i) => {
        const nn = no(x.icone, x.rotulo);
        nn.caixa.style.left = `${pos[i][0]}px`;
        nn.caixa.style.top = `${pos[i][1]}px`;
        rede.append(nn.caixa);
        return nn;
      });
      const ligacoes = pos.slice(1).map((p, i) => {
        const [x1, y1] = pos[i], [x2, y2] = p;
        const caminho = document.createElementNS(NS, "path");
        caminho.setAttribute("d", `M ${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`);
        caminho.setAttribute("pathLength", "1");
        caminho.setAttribute("class", "ligacao");
        svg.append(caminho);
        const pacotes = [0, 1, 2].map(() => {
          const p2 = document.createElementNS(NS, "circle");
          p2.setAttribute("r", "9");
          p2.setAttribute("class", "pacote");
          svg.append(p2);
          return p2;
        });
        return { caminho, pacotes };
      });
      el.append(rede);
      return { nos, ligacoes, foco: nos[0].disco };
    },
    render(t, d, s, ctx) {
      const quando = tempos(ctx.cena.tempos_nos, s.nos.length, d);
      // o primeiro nó já está na carta quando ela chega (a cena nunca entra vazia)
      quando[0] = Math.min(quando[0], 0.15);
      let ativo = 0;
      s.nos.forEach((nn, i) => {
        mola(nn.disco, t, quando[i], { de: 0.3, d: 0.5 });
        Ze.desenhar(nn.svg, t, quando[i] + 0.1, 0.6);
        if (nn.r) revela(nn.r, t, quando[i] + 0.3, "desfoque");
        if (t >= quando[i]) ativo = i;
      });
      s.nos.forEach((nn, i) => nn.caixa.classList.toggle("ativo", i === ativo && t >= quando[i]));
      s.foco = s.nos[ativo].disco;
      s.ligacoes.forEach(({ caminho, pacotes }, i) => {
        // a linha se desenha até o próximo nó um pouco antes de ele chegar
        const a = Math.max(quando[i] + 0.2, quando[i + 1] - 0.45);
        const k = curvas.vaivem(prog(t, a, 0.45));
        caminho.style.strokeDashoffset = String(1 - k);
        const total = caminho.getTotalLength();
        pacotes.forEach((p, j) => {
          const vivo = t >= a + 0.45;
          p.style.opacity = vivo ? "1" : "0";
          if (!vivo) return;
          const fase = ((t - a) * 0.55 + j / pacotes.length) % 1;
          const pt = caminho.getPointAtLength(fase * total);
          p.setAttribute("cx", pt.x.toFixed(1));
          p.setAttribute("cy", pt.y.toFixed(1));
        });
      });
    },
  });

  // --- hub: o centro e a constelação em volta, ligada a ele --------------------------------------
  Ze.cena("hub", {
    montar(c, el, ctx) {
      const rede = h("div", "rede");
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("viewBox", `0 0 ${LARGURA} ${ALTURA}`);
      svg.setAttribute("class", "rede-linhas");
      rede.append(svg);
      const centro = c.centro.icone === "marca" && ctx.marca.logo
        ? (() => { const caixa = h("div", "no grande marca"); const disco = h("div", "no-disco"); const img = h("img"); img.src = ctx.marca.logo; disco.append(img); caixa.append(disco); return { caixa, disco, svg: null, r: null }; })()
        : no(c.centro.icone, c.centro.rotulo, true);
      centro.caixa.style.left = `${LARGURA / 2}px`;
      centro.caixa.style.top = `${ALTURA / 2}px`;
      const aneis = [h("div", "anel"), h("div", "anel")];
      aneis.forEach((a) => { a.style.left = `${LARGURA / 2}px`; a.style.top = `${ALTURA / 2}px`; rede.append(a); });
      rede.append(centro.caixa);
      const sats = c.ao_redor.map((x) => {
        const nn = no(x.icone, x.rotulo);
        const linha = document.createElementNS(NS, "line");
        linha.setAttribute("pathLength", "1");
        linha.setAttribute("class", "ligacao");
        const pacote = document.createElementNS(NS, "circle");
        pacote.setAttribute("r", "8");
        pacote.setAttribute("class", "pacote");
        svg.append(linha, pacote);
        rede.append(nn.caixa);
        return { ...nn, linha, pacote };
      });
      el.append(rede);
      return { centro, aneis, sats, foco: centro.disco };
    },
    render(t, d, s, ctx) {
      mola(s.centro.disco, t, 0.05, { de: 0.2, d: 0.6 });
      if (s.centro.svg) Ze.desenhar(s.centro.svg, t, 0.15, 0.7);
      ondas(s.aneis, t, 0.55);
      const quando = tempos(ctx.cena.tempos_ao_redor, s.sats.length, d, 0.6);
      // a constelação gira devagar (4 graus por segundo) depois que o centro chega
      const giro = (Math.max(0, t - 0.6) * 4 * Math.PI) / 180;
      const raio = 390, cx = LARGURA / 2, cy = ALTURA / 2;
      s.sats.forEach((x, i) => {
        const ang = -Math.PI / 2 + (i * 2 * Math.PI) / s.sats.length + giro;
        const px = cx + raio * Math.cos(ang), py = cy + raio * Math.sin(ang) * 0.92;
        x.caixa.style.left = `${px.toFixed(1)}px`;
        x.caixa.style.top = `${py.toFixed(1)}px`;
        x.linha.setAttribute("x1", String(cx)); x.linha.setAttribute("y1", String(cy));
        x.linha.setAttribute("x2", px.toFixed(1)); x.linha.setAttribute("y2", py.toFixed(1));
        const k = curvas.vaivem(prog(t, quando[i] - 0.2, 0.35));
        x.linha.style.strokeDashoffset = String(1 - k);
        mola(x.disco, t, quando[i], { de: 0.2, d: 0.5 });
        Ze.desenhar(x.svg, t, quando[i] + 0.08, 0.55);
        if (x.r) revela(x.r, t, quando[i] + 0.25, "desfoque");
        // os dados correm do satélite para o centro
        const vivo = t >= quando[i] + 0.3;
        x.pacote.style.opacity = vivo ? "1" : "0";
        if (vivo) {
          const f = ((t - quando[i]) * 0.7 + i * 0.13) % 1;
          x.pacote.setAttribute("cx", (px + (cx - px) * f).toFixed(1));
          x.pacote.setAttribute("cy", (py + (cy - py) * f).toFixed(1));
        }
      });
    },
  });

  // --- caos e ordem: ícones espalhados, tortos e tremendo, que se organizam na palavra ----------
  Ze.cena("caos", {
    montar(c, el) {
      const palco = h("div", "caos");
      const r = Ze.semente(c.icones.join("").length * 131 + 3);
      const n = c.icones.length, colunas = n > 4 ? 3 : 2;
      const itens = c.icones.map((nome, i) => {
        const caixa = h("div", "caos-item");
        const svg = Ze.icone(nome, "icone caos-icone");
        caixa.append(svg);
        palco.append(caixa);
        const linha = Math.floor(i / colunas), col = i % colunas;
        const linhas = Math.ceil(n / colunas);
        return {
          caixa, svg,
          de: [90 + r() * 720, 70 + r() * 680, (r() - 0.5) * 80, 0.75 + r() * 0.5],
          para: [450 + (col - (colunas - 1) / 2) * 280, 390 + (linha - (linhas - 1) / 2) * 280],
          fase: r() * 6.28,
        };
      });
      el.append(palco);
      const rot = c.rotulo ? h("div", "arte-rotulo", c.rotulo) : null;
      if (rot) el.append(rot);
      return { itens, rot, foco: palco };
    },
    render(t, d, s, ctx) {
      const ordem = typeof ctx.cena.tempo === "number" ? Math.max(1.0, ctx.cena.tempo) : Math.min(d * 0.5, 2.6);
      s.itens.forEach((x, i) => {
        const chega = 0.05 + i * 0.06;
        const k = prog(t, ordem + i * 0.04, 0.7), p = curvas.mola(k);
        // antes da ordem: espalhados, tortos, tremendo; depois: na grade, retos, acesos
        const tremor = (1 - cl(k * 2)) * 7;
        const [dx, dy, dr, ds] = x.de, [px, py] = x.para;
        const xx = dx + (px - dx) * p + Math.sin(t * 13 + x.fase) * tremor;
        const yy = dy + (py - dy) * p + Math.cos(t * 11 + x.fase) * tremor;
        x.caixa.style.left = `${xx.toFixed(1)}px`;
        x.caixa.style.top = `${yy.toFixed(1)}px`;
        x.caixa.style.transform = `translate(-50%, -50%) rotate(${(dr * (1 - p)).toFixed(2)}deg) scale(${(ds + (1 - ds) * p).toFixed(3)})`;
        x.caixa.style.opacity = String(cl(prog(t, chega, 0.25)));
        x.caixa.classList.toggle("ordem", k >= 0.5);
        Ze.desenhar(x.svg, t, chega, 0.5);
      });
      if (s.rot) revela(s.rot, t, ordem + 0.6, "mascara");
    },
  });
})();
