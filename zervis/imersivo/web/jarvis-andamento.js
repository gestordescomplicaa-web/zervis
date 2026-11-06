// SPDX-License-Identifier: AGPL-3.0-or-later
// Modified by gdautomacao.ia, 2026-11-05.
// The loading bar at the top (ADR 0064): while the Zé thinks, a small hologram panel in the same
// language as his presentations (corner brackets, scanlines, sweep, it materializes from a line)
// with what he is doing ("Pesquisando na internet"), the steps already done and a segmented bar
// that fills like a game's: fast at first, slower near the end, and full only when the answer
// starts. The Zé writes each step and how long it usually takes (the real median of that tool);
// GET /orb brings it with the state. The bar never claims 100% before the answer.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const TETO = 0.95; // o que a barra alcança sozinha: o resto é a resposta chegando
  const VOLTA_S = 1.5; // a frase de espera ("um instante") fala no meio: a barra espera voltar
  const CELULAS = 36;
  const RASTRO = 3; // passos já feitos que ficam à vista
  const A = "rgb(var(--jv-acento-rgb, 143 240 228) /";
  const css = document.createElement("style");
  css.textContent = `
  #jv-andamento { --display:"Chakra Petch", ui-sans-serif, system-ui, sans-serif; --codigo:"JetBrains Mono", ui-monospace, monospace;
    position:fixed; top:18px; left:50%; z-index:60; width:min(540px, calc(100vw - 32px)); transform:translateX(-50%);
    pointer-events:none; visibility:hidden; color:var(--jv-texto, #ecfffa); }
  #jv-andamento.ativo { visibility:visible; animation:jv-a-surgir .7s cubic-bezier(.2,.8,.2,1) both; }
  #jv-andamento.saindo { animation:jv-a-sumir .5s cubic-bezier(.6,0,.8,.2) both; }
  #jv-andamento .vidro { position:relative; overflow:hidden; display:grid; gap:9px; padding:11px 16px 12px;
    background:linear-gradient(160deg, rgb(12 58 54 / .62), rgb(2 16 15 / .78)); border:1px solid ${A} .24);
    box-shadow:inset 0 0 30px ${A} .06), 0 0 calc(26px + var(--p, 0) * 30px) ${A} calc(.08 + var(--p, 0) * .16)); }
  #jv-andamento .vidro::before { content:""; position:absolute; inset:0; pointer-events:none;
    background:repeating-linear-gradient(0deg, rgb(200 255 248 / .03) 0 1px, transparent 1px 3px); }
  #jv-andamento .vidro::after { content:""; position:absolute; inset:0; pointer-events:none; --c:var(--jv-acento, #8ff0e4);
    background:
      linear-gradient(var(--c), var(--c)) top left / 14px 2px no-repeat, linear-gradient(var(--c), var(--c)) top left / 2px 14px no-repeat,
      linear-gradient(var(--c), var(--c)) top right / 14px 2px no-repeat, linear-gradient(var(--c), var(--c)) top right / 2px 14px no-repeat,
      linear-gradient(var(--c), var(--c)) bottom left / 14px 2px no-repeat, linear-gradient(var(--c), var(--c)) bottom left / 2px 14px no-repeat,
      linear-gradient(var(--c), var(--c)) bottom right / 14px 2px no-repeat, linear-gradient(var(--c), var(--c)) bottom right / 2px 14px no-repeat; }
  #jv-andamento .varre { position:absolute; top:0; bottom:0; left:0; width:28%; pointer-events:none;
    background:linear-gradient(90deg, transparent, ${A} .08), transparent); animation:jv-a-varrer 3.6s linear infinite; }
  #jv-andamento .cab { display:flex; align-items:center; gap:8px; font:500 9px var(--codigo); letter-spacing:.28em;
    color:var(--jv-suave, #a8d8cf); text-transform:uppercase; }
  #jv-andamento .cab i { width:6px; height:6px; border-radius:50%; background:var(--jv-acento, #8ff0e4);
    box-shadow:0 0 8px var(--jv-acento, #8ff0e4); animation:jv-a-pulsar 1.2s ease-in-out infinite; }
  #jv-andamento .cab .relogio { margin-left:auto; letter-spacing:.14em; font-variant-numeric:tabular-nums; color:var(--jv-claro, #bffff2); }
  #jv-andamento .linha { display:flex; align-items:baseline; gap:12px; }
  #jv-andamento .rotulo { flex:1; min-width:0; font:600 17px/1.2 var(--display); letter-spacing:.04em; color:var(--jv-claro, #bffff2);
    text-shadow:0 0 12px ${A} .5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  #jv-andamento .rotulo.novo { animation:jv-a-chegar .55s both; }
  #jv-andamento .pct { font:600 17px/1 var(--display); font-variant-numeric:tabular-nums; color:var(--jv-acento, #8ff0e4);
    text-shadow:0 0 12px ${A} .6); }
  #jv-andamento .trilho { position:relative; height:12px; }
  #jv-andamento .celulas { position:absolute; inset:0; display:grid; grid-template-columns:repeat(${CELULAS}, 1fr); gap:3px; padding:0 3px; }
  #jv-andamento .celulas i { transform:skewX(-24deg); }
  #jv-andamento .apagadas i { background:${A} .06); box-shadow:inset 0 0 0 1px ${A} .16); }
  #jv-andamento .acesas { clip-path:inset(0 calc(100% - var(--p, 0) * 100%) 0 0); }
  #jv-andamento .acesas i { background:linear-gradient(180deg, var(--jv-claro, #bffff2), var(--jv-acento, #8ff0e4) 55%, ${A} .55));
    box-shadow:0 0 8px ${A} .55); }
  #jv-andamento .luz { position:absolute; top:-3px; bottom:-3px; left:0; width:calc(var(--p, 0) * 100%); overflow:hidden; pointer-events:none; }
  #jv-andamento .luz::after { content:""; position:absolute; top:0; bottom:0; width:60px; left:-60px;
    background:linear-gradient(90deg, transparent, rgb(255 255 255 / .55), transparent); mix-blend-mode:screen;
    animation:jv-a-luz 1.8s linear infinite; }
  #jv-andamento .cabeca { position:absolute; top:-4px; bottom:-4px; left:calc(var(--p, 0) * 100%); width:2px; margin-left:-1px;
    background:#fff; box-shadow:0 0 6px #fff, 0 0 16px var(--jv-acento, #8ff0e4); animation:jv-a-tremer .9s steps(3) infinite; }
  #jv-andamento .regua { display:flex; justify-content:space-between; padding:0 2px; font:400 8px var(--codigo);
    letter-spacing:.1em; color:${A} .4); font-variant-numeric:tabular-nums; }
  #jv-andamento .rastro { display:flex; align-items:center; gap:6px 14px; flex-wrap:wrap; min-height:14px;
    font:400 10px var(--codigo); letter-spacing:.06em; color:var(--jv-suave, #a8d8cf); }
  #jv-andamento .rastro span { white-space:nowrap; animation:jv-a-chegar .5s both; }
  #jv-andamento .rastro .feito::before { content:"✓ "; color:var(--jv-acento, #8ff0e4); }
  #jv-andamento .rastro .agora { color:var(--jv-texto, #ecfffa); }
  #jv-andamento .rastro .agora::before { content:"▸ "; color:var(--jv-acento, #8ff0e4); }
  #jv-andamento .rastro .espera { margin-left:auto; color:${A} .7); }
  #jv-andamento .feixe { display:block; width:1px; height:30px; margin:0 auto;
    background:repeating-linear-gradient(180deg, ${A} .8) 0 2px, transparent 2px 7px);
    -webkit-mask:linear-gradient(#000, transparent); mask:linear-gradient(#000, transparent); animation:jv-a-fluxo .8s linear infinite; }
  #jv-andamento.pronto .acesas i { background:#fff; box-shadow:0 0 12px var(--jv-acento, #8ff0e4), 0 0 3px #fff; }
  #jv-andamento.pronto .vidro { border-color:${A} .7); }
  #jv-andamento.pronto .cabeca, #jv-andamento.pronto .luz { display:none; }
  @keyframes jv-a-surgir { 0% { clip-path:inset(49% 0 49% 0); filter:brightness(4); opacity:0; }
    20% { clip-path:inset(49% 0 49% 0); opacity:1; } 65% { clip-path:inset(0 0 0 0); filter:brightness(1.6); }
    100% { clip-path:inset(0 0 0 0); filter:none; } }
  @keyframes jv-a-sumir { 0% { clip-path:inset(0 0 0 0); filter:brightness(1.4); }
    55% { clip-path:inset(49% 0 49% 0); filter:brightness(3); opacity:1; } 100% { clip-path:inset(49% 50% 49% 50%); opacity:0; } }
  @keyframes jv-a-varrer { from { transform:translateX(-100%); } to { transform:translateX(460%); } }
  @keyframes jv-a-luz { to { left:100%; } }
  @keyframes jv-a-pulsar { 50% { opacity:.3; } }
  @keyframes jv-a-tremer { 33% { opacity:.55; } 66% { opacity:1; transform:scaleY(1.2); } }
  @keyframes jv-a-chegar { from { opacity:0; transform:translateX(-8px); filter:brightness(3); } }
  @keyframes jv-a-fluxo { to { background-position:0 7px; } }
  @media (prefers-reduced-motion: reduce) {
    #jv-andamento.ativo, #jv-andamento.saindo, #jv-andamento .rotulo.novo, #jv-andamento .rastro span { animation-duration:.01s; }
    #jv-andamento .varre, #jv-andamento .luz, #jv-andamento .cabeca, #jv-andamento .feixe, #jv-andamento .cab i { animation:none; } }`;
  document.head.appendChild(css);
  const celulas = '<i></i>'.repeat(CELULAS);
  const raiz = document.createElement("div");
  raiz.id = "jv-andamento";
  raiz.setAttribute("role", "progressbar");
  raiz.setAttribute("aria-label", "O que o Zé está fazendo");
  raiz.setAttribute("aria-valuemin", "0");
  raiz.setAttribute("aria-valuemax", "100");
  raiz.innerHTML = `<div class="vidro"><span class="varre"></span>
    <div class="cab"><i></i><span class="estado">Zé · processando</span><span class="relogio">T+00:00</span></div>
    <div class="linha"><div class="rotulo"></div><div class="pct">0%</div></div>
    <div class="trilho"><div class="celulas apagadas">${celulas}</div><div class="celulas acesas">${celulas}</div>
      <span class="luz"></span><span class="cabeca"></span></div>
    <div class="regua"><span>00</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
    <div class="rastro"></div></div><span class="feixe"></span>`;
  document.body.appendChild(raiz);
  const $ = (s) => raiz.querySelector(s);
  const rotulo = $(".rotulo"), pct = $(".pct"), relogio = $(".relogio"), estado = $(".estado"), rastro = $(".rastro");

  let ativo = false, inicio = 0, base = 0, desde = 0, tau = 3, esperado = 3, texto = "Pensando", visto = 0;
  let saiu = 0, fim = 0, mostrado = 0;
  let feitos = [];
  const agora = () => performance.now() / 1000;
  const progresso = (t) => base + (TETO - base) * (1 - Math.exp(-(t - desde) / tau));
  const relogioDe = (s) => `T+${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  function escrever() {
    rotulo.textContent = `${texto}…`;
    rotulo.classList.remove("novo"); void rotulo.offsetWidth; rotulo.classList.add("novo");
    rastro.replaceChildren(
      ...feitos.slice(-RASTRO).map((f) => Object.assign(document.createElement("span"), { className: "feito", textContent: f })),
      Object.assign(document.createElement("span"), { className: "agora", textContent: texto }),
      Object.assign(document.createElement("span"), { className: "espera", textContent: `≈ ${Math.max(1, Math.round(esperado))} s` }),
    );
  }

  function etapa(novo, segundos) {
    const t = agora();
    base = Math.min(TETO, ativo ? progresso(t) : 0);
    desde = t; tau = Math.max(0.6, segundos); esperado = segundos;
    if (texto && novo !== texto) feitos.push(texto);
    texto = novo;
    escrever();
  }

  function abrir(t) {
    ativo = true; inicio = t; fim = 0; feitos = []; texto = ""; mostrado = 0;
    base = 0; desde = t; // um pedido novo começa do zero, não de onde o anterior parou
    raiz.classList.remove("saindo", "pronto");
    estado.textContent = "Zé · processando";
    etapa("Pensando", 3);
    raiz.classList.add("ativo");
  }

  function ler(d) {
    const t = agora(), pensando = d.state === "thinking";
    if (pensando) {
      saiu = 0;
      if (!ativo) abrir(t);
      const a = d.andamento;
      // Só um passo deste pedido: mais novo que o início (relógio do servidor em segundos).
      if (a && a.ts !== visto && a.ts * 1000 > Date.now() - (t - inicio) * 1000 - 1500) {
        visto = a.ts;
        etapa(a.rotulo || "Pensando", Number(a.esperado_s) || 3);
      }
    } else if (ativo) {
      saiu = saiu || t;
      if (t - saiu > VOLTA_S || d.state === "idle") {
        ativo = false; fim = t;
        raiz.classList.add("pronto");
        estado.textContent = "Zé · pronto";
        rotulo.textContent = "Resposta pronta";
      }
    }
  }

  function mostrar(p) {
    mostrado = p;
    raiz.style.setProperty("--p", p.toFixed(4));
    const n = Math.round(p * 100);
    pct.textContent = `${n}%`;
    raiz.setAttribute("aria-valuenow", String(n));
  }

  function desenhar() {
    const t = agora();
    if (ativo) {
      mostrar(progresso(t));
      relogio.textContent = relogioDe(t - inicio);
    } else if (fim) {
      // Completa em ~0,3 s (não salta), brilha e se desfaz como os painéis do Zé.
      if (mostrado < 1) mostrar(Math.min(1, mostrado + (1 - mostrado) * 0.25 + 0.01));
      if (t - fim > 0.9 && !raiz.classList.contains("saindo")) raiz.classList.add("saindo");
      if (t - fim > 1.45) { raiz.classList.remove("ativo", "saindo", "pronto"); fim = 0; }
    }
    requestAnimationFrame(desenhar);
  }
  requestAnimationFrame(desenhar);

  setInterval(async () => {
    try {
      const r = await fetch("/orb", { cache: "no-store" });
      if (r.ok) ler(await r.json());
    } catch (_) { /* o Zé parado: a barra some sozinha */ }
  }, 250);
  window.jarvisAndamento = {
    get ativo() { return ativo; }, get texto() { return texto; }, get progresso() { return mostrado; }, ler,
  };
})();
