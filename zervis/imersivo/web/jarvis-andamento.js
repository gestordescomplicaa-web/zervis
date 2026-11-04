// SPDX-License-Identifier: AGPL-3.0-or-later
// Modified by gdautomacao.ia, 2026-11-04.
// The loading bar at the top (ADR 0064): while the Zé thinks, what he is doing ("Pesquisando na
// internet") and a bar that moves like a game's: fast at first, slower near the end, and full only
// when the answer starts. The Zé writes each step and how long it usually takes (the real average
// of that tool); GET /orb brings it with the state. The bar never claims 100% before the answer.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const TETO = 0.95; // o que a barra alcança sozinha: o resto é a resposta chegando
  const VOLTA_S = 1.5; // a frase de espera ("um instante") fala no meio: a barra espera voltar
  const css = document.createElement("style");
  css.textContent = `
  #jv-andamento { position:fixed; top:0; left:0; right:0; z-index:60; pointer-events:none;
    opacity:0; transition:opacity .45s ease; }
  #jv-andamento.ativo { opacity:1; }
  #jv-andamento .trilho { height:4px; background:rgba(var(--jv-borda-rgb, 70, 217, 222), .12); }
  #jv-andamento .cheio { height:100%; width:0; background:var(--jv-acento, #46d9de);
    box-shadow:0 0 12px var(--jv-acento, #46d9de), 0 0 2px #fff; transition:width .25s linear; }
  #jv-andamento .rotulo { margin:8px auto 0; width:max-content; max-width:70vw; padding:4px 12px;
    font:600 13px/1.3 system-ui, sans-serif; letter-spacing:.04em; color:var(--jv-texto, #e6fbff);
    background:rgba(0,0,0,.35); border:1px solid rgba(var(--jv-borda-rgb, 70, 217, 222), .35);
    border-radius:999px; backdrop-filter:blur(6px); white-space:nowrap; overflow:hidden;
    text-overflow:ellipsis; }
  @media (prefers-reduced-motion: reduce) { #jv-andamento .cheio { transition:none; } }`;
  document.head.appendChild(css);
  const raiz = document.createElement("div");
  raiz.id = "jv-andamento";
  raiz.setAttribute("role", "progressbar");
  raiz.setAttribute("aria-label", "O que o Zé está fazendo");
  raiz.innerHTML = '<div class="trilho"><div class="cheio"></div></div><div class="rotulo"></div>';
  document.body.appendChild(raiz);
  const cheio = raiz.querySelector(".cheio"), rotulo = raiz.querySelector(".rotulo");

  let ativo = false, inicio = 0, base = 0, desde = 0, tau = 3, texto = "Pensando", visto = 0;
  let saiu = 0, fim = 0;
  const agora = () => performance.now() / 1000;
  const progresso = (t) => base + (TETO - base) * (1 - Math.exp(-(t - desde) / tau));

  function etapa(novo, esperado) {
    const t = agora();
    base = Math.min(TETO, ativo ? progresso(t) : 0);
    desde = t; tau = Math.max(0.6, esperado); texto = novo;
  }

  function ler(d) {
    const t = agora(), pensando = d.state === "thinking";
    if (pensando) {
      saiu = 0;
      if (!ativo) { ativo = true; inicio = t; etapa("Pensando", 3); raiz.classList.add("ativo"); }
      const a = d.andamento;
      // Só um passo deste pedido: mais novo que o início (relógio do servidor em segundos).
      if (a && a.ts !== visto && a.ts * 1000 > Date.now() - (t - inicio) * 1000 - 1500) {
        visto = a.ts;
        etapa(a.rotulo || "Pensando", Number(a.esperado_s) || 3);
      }
    } else if (ativo) {
      saiu = saiu || t;
      if (t - saiu > VOLTA_S || d.state === "idle") { ativo = false; fim = t; }
    }
  }

  function desenhar() {
    const t = agora();
    if (ativo) {
      const p = progresso(t);
      cheio.style.width = (p * 100).toFixed(1) + "%";
      raiz.setAttribute("aria-valuenow", String(Math.round(p * 100)));
      rotulo.textContent = `${texto}… ${Math.round(t - inicio)} s`;
    } else if (fim) {
      cheio.style.width = "100%";
      if (t - fim > 0.6) { raiz.classList.remove("ativo"); fim = 0; }
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
  window.jarvisAndamento = { get ativo() { return ativo; }, get texto() { return texto; }, ler };
})();
