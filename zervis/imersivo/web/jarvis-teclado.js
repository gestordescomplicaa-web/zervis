// SPDX-License-Identifier: AGPL-3.0-or-later
// gdautomacao.ia: the Teclado. A small keyboard icon beside CPU · RAM · GPU · VRAM opens
// a plain (non-holographic) text bar: what is typed goes to the Zé exactly like a
// spoken request (local commands first, then the brain), with no "Ei Zé" needed.
// POST /teclado writes state/teclado.json; the Zé answers in teclado-resposta.json
// (what it says, as it says it), shown under the bar. Also typed: "sim" / "não" to a
// question the Zé is waiting on. Enter sends, ↑/↓ recall, Esc closes, "/" opens.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const hint = document.getElementById("hint"), linha = document.getElementById("hud-m");
  if (!hint || !linha) return;

  const css = document.createElement("style");
  css.textContent = `
  /* The HUD look of the presentation panels (29/10/2026, the person's review note "mude o teclado"):
     corner brackets, scan lines and a glow when pointed at. Same 56 px target for the pinch. */
  #jv-teclado-btn { --c:var(--jv-acento, #8ff0e4); position:relative; display:inline-flex; align-items:center; justify-content:center;
    width:56px; height:56px; border-radius:2px; cursor:pointer; color:var(--jv-claro, #bffff2);
    border:1px solid rgb(var(--jv-borda-rgb, 140 240 225) / .2);
    background:
      linear-gradient(var(--c), var(--c)) top left / 10px 1px no-repeat, linear-gradient(var(--c), var(--c)) top left / 1px 10px no-repeat,
      linear-gradient(var(--c), var(--c)) top right / 10px 1px no-repeat, linear-gradient(var(--c), var(--c)) top right / 1px 10px no-repeat,
      linear-gradient(var(--c), var(--c)) bottom left / 10px 1px no-repeat, linear-gradient(var(--c), var(--c)) bottom left / 1px 10px no-repeat,
      linear-gradient(var(--c), var(--c)) bottom right / 10px 1px no-repeat, linear-gradient(var(--c), var(--c)) bottom right / 1px 10px no-repeat,
      repeating-linear-gradient(0deg, rgb(200 255 248 / .04) 0 1px, transparent 1px 3px),
      linear-gradient(160deg, rgb(12 58 54 / .55), rgb(2 16 15 / .7));
    box-shadow:inset 0 0 18px rgb(var(--jv-acento-rgb, 143 240 228) / .08), 0 0 18px rgb(var(--jv-acento-rgb, 143 240 228) / .08);
    transition:box-shadow .2s, border-color .2s, color .2s; }
  #jv-teclado-btn svg { width:20px; height:14px; filter:drop-shadow(0 0 4px rgb(var(--jv-acento-rgb, 143 240 228) / .7)); }
  #jv-teclado-btn:hover, #jv-teclado-btn.ativo, #jv-teclado-btn.apontado { border-color:rgb(var(--jv-acento-rgb, 143 240 228) / .7); color:#fff;
    box-shadow:inset 0 0 22px rgb(var(--jv-acento-rgb, 143 240 228) / .18), 0 0 26px rgb(var(--jv-acento-rgb, 143 240 228) / .35); }
  #jv-teclado-btn.ativo::after { content:""; position:absolute; inset:-5px; border:1px solid rgb(var(--jv-acento-rgb, 143 240 228) / .5);
    animation:jv-tecla-pulso 1.6s ease-out infinite; pointer-events:none; }
  @keyframes jv-tecla-pulso { from { opacity:.9; transform:scale(.92); } to { opacity:0; transform:scale(1.18); } }
  @media (prefers-reduced-motion: reduce) { #jv-teclado-btn.ativo::after { animation:none; opacity:.6; } }
  #jv-teclado { position:absolute; left:50%; bottom:calc(100% + 12px); transform:translateX(-50%);
    width:min(640px, calc(100vw - 32px)); box-sizing:border-box; padding:10px 12px 12px; border-radius:14px; text-align:left;
    background:var(--jv-painel, rgba(10,38,31,.94)); border:1px solid rgb(var(--jv-borda-rgb, 140 240 225) / .45);
    box-shadow:0 14px 50px rgba(0,0,0,.5); color:var(--jv-texto, #ecfffa); text-shadow:none;
    font:500 13.5px -apple-system, 'Segoe UI', sans-serif; letter-spacing:0; }
  #jv-teclado header { display:flex; align-items:center; gap:8px; margin-bottom:8px;
    font:600 11px 'SF Mono', Menlo, monospace; letter-spacing:.16em; color:var(--jv-acento, #8ff0e4); }
  #jv-teclado header small { margin-left:auto; color:var(--jv-suave, #a8d8cf); letter-spacing:.04em; font-weight:500; }
  #jv-teclado form { display:flex; gap:8px; }
  #jv-teclado input { flex:1; min-width:0; height:56px; padding:0 12px; border-radius:10px; outline:none;
    color:inherit; font:inherit; font-size:15px; background:rgba(0,0,0,.28);
    border:1px solid rgb(var(--jv-borda-rgb, 140 240 225) / .3); }
  #jv-teclado input:focus { border-color:var(--jv-acento, #8ff0e4); }
  #jv-teclado button { height:56px; min-width:56px; padding:0 14px; border-radius:10px; cursor:pointer; color:inherit;
    font:600 13px -apple-system, 'Segoe UI', sans-serif; background:rgb(var(--jv-borda-rgb, 140 240 225) / .1);
    border:1px solid rgb(var(--jv-borda-rgb, 140 240 225) / .35); }
  #jv-teclado button:hover, #jv-teclado button.apontado { background:rgb(var(--jv-borda-rgb, 140 240 225) / .22);
    border-color:var(--jv-acento, #8ff0e4); }
  #jv-teclado .resposta { margin-top:9px; max-height:30vh; overflow:auto; line-height:1.45; white-space:pre-wrap; }
  #jv-teclado .resposta:empty { display:none; }
  #jv-teclado .resposta .voce { color:var(--jv-suave, #a8d8cf); }
  #jv-teclado .resposta .esperando { color:var(--jv-suave, #a8d8cf); font-style:italic; }`;
  document.head.appendChild(css);

  const botao = document.createElement("span");
  botao.id = "jv-teclado-btn"; botao.setAttribute("role", "button"); botao.tabIndex = 0;
  botao.title = "Teclado: escrever um comando para o Zé (/)";
  botao.setAttribute("aria-label", "Teclado");
  botao.innerHTML = '<svg viewBox="0 0 18 12" fill="none" stroke="currentColor" stroke-width="1.2" aria-hidden="true">' +
    '<rect x=".6" y=".6" width="16.8" height="10.8" rx="2"/>' +
    '<path d="M3.5 3.6h1M6.5 3.6h1M9.5 3.6h1M12.5 3.6h2M3.5 6h2M7 6h1M9.5 6h1M12 6h2.5M5 8.6h8" stroke-linecap="round"/></svg>';
  linha.appendChild(botao);

  const painel = document.createElement("div");
  painel.id = "jv-teclado"; painel.hidden = true;
  painel.innerHTML = `<header>TECLADO<small>Enter envia · ↑ anteriores · Esc fecha</small></header>
    <form><input type="text" maxlength="2000" autocomplete="off" spellcheck="true"
      placeholder="Escreva um comando para o Zé…" aria-label="Comando para o Zé">
      <button type="submit" title="Enviar">Enviar</button><button type="button" data-a="fechar" title="Fechar">✕</button></form>
    <div class="resposta" aria-live="polite"></div>`;
  hint.appendChild(painel);
  const campo = painel.querySelector("input"), saida = painel.querySelector(".resposta");

  const esc = t => String(t).replace(/[&<>"]/g, x => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[x]);
  let historico = [];
  try { historico = JSON.parse(localStorage.getItem("jv-teclado") || "[]").slice(-20); } catch (e) {}
  let pos = historico.length, esperando = null, ultimoTexto = "";

  function abrir() {
    painel.hidden = false; botao.classList.add("ativo");
    setTimeout(() => campo.focus(), 0);
  }
  function fechar() { painel.hidden = true; botao.classList.remove("ativo"); campo.blur(); }
  const alternar = () => (painel.hidden ? abrir() : fechar());

  function mostrar(pedido, resposta, fim) {
    saida.innerHTML = `<div class="voce">› ${esc(pedido)}</div>` +
      (resposta ? `<div>${esc(resposta)}</div>` : "") +
      (fim ? "" : '<div class="esperando">pensando…</div>');
    saida.scrollTop = saida.scrollHeight;
  }

  async function enviar(texto) {
    texto = String(texto || "").trim();
    if (!texto) return null;
    historico = [...historico.filter(h => h !== texto), texto].slice(-20); pos = historico.length;
    try { localStorage.setItem("jv-teclado", JSON.stringify(historico)); } catch (e) {}
    ultimoTexto = texto; mostrar(texto, "", false);
    try {
      const r = await fetch("/teclado", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }) });
      if (!r.ok) throw new Error(r.status);
      esperando = (await r.json()).id;
      return esperando;
    } catch (e) {
      saida.innerHTML = `<div class="voce">› ${esc(texto)}</div><div>Não consegui enviar ao Zé.</div>`;
      return null;
    }
  }

  // The answer arrives as the Zé speaks it; a request with no answer in 20 s is
  // reported (the Zé stopped, or inactive with the screen locked).
  let desde = 0;
  async function ouvir() {
    if (!esperando) return;
    desde ||= Date.now();
    try {
      const d = await (await fetch("/jarvis/teclado-resposta", { cache: "no-store" })).json();
      if (d.pedido === esperando) {
        mostrar(ultimoTexto, d.texto || "", !!d.fim);
        if (d.fim) { esperando = null; desde = 0; }
        return;
      }
    } catch (e) {}
    if (Date.now() - desde > 20000) {
      mostrar(ultimoTexto, "O Zé não respondeu. Ele está rodando?", true);
      esperando = null; desde = 0;
    }
  }
  setInterval(ouvir, 300);

  painel.querySelector("form").addEventListener("submit", ev => {
    ev.preventDefault(); const t = campo.value; campo.value = ""; enviar(t);
  });
  painel.addEventListener("click", ev => { if (ev.target.closest("[data-a=fechar]")) fechar(); });
  botao.addEventListener("click", alternar);
  botao.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); alternar(); } });
  campo.addEventListener("keydown", ev => {
    if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); fechar(); }
    else if (ev.key === "ArrowUp" && historico.length) { ev.preventDefault(); pos = Math.max(0, pos - 1); campo.value = historico[pos]; }
    else if (ev.key === "ArrowDown") { ev.preventDefault(); pos = Math.min(historico.length, pos + 1); campo.value = historico[pos] || ""; }
  });
  addEventListener("keydown", ev => {
    if (ev.key === "/" && !ev.ctrlKey && !ev.metaKey && !ev.target.closest?.("input, textarea")) { ev.preventDefault(); abrir(); }
  });

  const contem = (x, y) => {
    if (painel.hidden) return false;
    const r = painel.getBoundingClientRect();
    return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
  };
  window.jarvisTeclado = { abrir, fechar, alternar, enviar, contem, get aberto() { return !painel.hidden; } };
})();
