// SPDX-License-Identifier: AGPL-3.0-or-later
// Modified by gdautomacao.ia, 2026-10-07.
// The settings menu (key D): hands calibration, camera brightness, colours,
// the brain batteries and the token meter. The front keeps only the ring and
// the CPU · RAM · GPU · VRAM row; everything else lives here.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const BRILHOS = ["Desligado", "Suave", "Médio", "Forte"];
  // The keys of the page (stage.html, jarvis-maos.js, jarvis-teclado.js); the Guia has the same list.
  const ATALHOS = [
    ["D", "Configurações"], ["K", "Calibrar as mãos"], ["Shift + K", "Mãos no padrão"],
    ["B", "Brilho da câmera (Shift + B diminui)"], ["T", "Trocar as cores"], ["/", "Escrever para o Zé"],
    ["R", "Recarregar a tela"], ["C", "Trocar a câmera"], ["Esc", "Fechar"],
  ];
  const menu = document.createElement("div");
  menu.id = "jv-config"; menu.hidden = true;
  menu.setAttribute("role", "dialog"); menu.setAttribute("aria-label", "Configurações do Zé");
  menu.innerHTML = `
    <header><div><b>CONFIGURAÇÕES</b><small>Zé · modo imersivo</small></div>
      <button data-config="fechar" aria-label="Fechar configurações">×</button></header>
    <section><h3>Mãos</h3><div class="slot" data-slot="maos"></div>
      <div class="linha-cfg"><button data-config="calibrar">Calibrar as mãos</button>
      <button data-config="maos-padrao">Voltar ao padrão</button></div></section>
    <section><h3>Brilho da câmera</h3><div class="seg" data-grupo="brilho" style="--n:4">
      ${BRILHOS.map((n, i) => `<button data-config="brilho:${i}">${n}</button>`).join("")}</div></section>
    <section><h3>Cores</h3><div class="seg" data-grupo="tema" style="--n:3">
      ${(window.jarvisTema?.lista || [{ id: "original", nome: "Original" }]).map(t => `<button data-config="tema:${t.id}">${t.nome}</button>`).join("")}</div></section>
    <section><h3>Visual</h3><div class="seg" data-grupo="visual" style="--n:2">
      <button data-config="visual:avatar">Avatar</button><button data-config="visual:anel">Anel</button></div></section>
    <section><h3>Cérebro</h3><div class="slot" data-slot="cerebros"></div></section>
    <section><h3>Consumo</h3><div class="slot" data-slot="consumo"></div></section>
    <section><h3>Atalhos</h3><dl class="atalhos">
      ${ATALHOS.map(([tecla, faz]) => `<dt>${tecla.split(" + ").map(t => `<kbd>${t}</kbd>`).join("+")}</dt><dd>${faz}</dd>`).join("")}</dl></section>`;
  const css = document.createElement("style");
  css.textContent = `
  /* A side menu where the D readout used to sit (top-left), on the same glass as
     the board. It lives inside #hint so the brain batteries and the token meter
     keep their own HUD styles. */
  #jv-config { position:fixed; left:14px; top:14px; bottom:62px; z-index:2; width:min(360px, calc(100vw - 28px)); box-sizing:border-box;
    overflow-y:auto; overscroll-behavior:contain; padding:4px 18px 14px; text-align:left;
    background:linear-gradient(172deg, var(--jv-vidro-a), var(--jv-vidro-b)); backdrop-filter:blur(8px);
    border:1.5px solid rgb(var(--jv-borda-rgb) / .55); border-radius:18px;
    box-shadow:0 16px 70px rgba(0,0,0,.33), 0 0 35px rgb(var(--jv-borda-rgb) / .13), inset 0 1px 0 rgb(var(--jv-claro-rgb) / .4);
    color:var(--jv-texto); font:14px/1.5 -apple-system, 'Segoe UI', sans-serif; letter-spacing:0;
    text-shadow:0 1px 3px var(--jv-sombra), 0 0 10px var(--jv-sombra); animation:jvcfg .22s ease-out; }
  @keyframes jvcfg { from { opacity:0; transform:translateX(-18px); } }
  #jv-config[hidden] { display:none; }
  #jv-config header { position:sticky; top:0; z-index:1; background:var(--jv-painel); display:flex; align-items:center; justify-content:space-between; padding:12px 0 10px;
    border-bottom:1px solid rgb(var(--jv-borda-rgb) / .25); }
  #jv-config header b { display:block; font:600 13px 'SF Mono', Menlo, monospace; letter-spacing:.14em; color:var(--jv-acento); }
  #jv-config header small { color:var(--jv-suave); font:500 11px 'SF Mono', Menlo, monospace; letter-spacing:.06em; }
  #jv-config section { padding:12px 0 2px; }
  #jv-config h3 { margin:0 0 8px; color:var(--jv-suave); font:600 10.5px 'SF Mono', Menlo, monospace; letter-spacing:.16em; text-transform:uppercase; }
  #jv-config button { min-height:56px; padding:0 12px; border-radius:11px; cursor:pointer; color:var(--jv-texto);
    font:600 12.5px -apple-system, 'Segoe UI', sans-serif; text-shadow:inherit; background:rgb(var(--jv-borda-rgb) / .06);
    border:1px solid rgb(var(--jv-borda-rgb) / .3); transition:background .15s, border-color .15s; }
  #jv-config button:hover, #jv-config button.apontado, #jv-config button:focus-visible { background:rgb(var(--jv-borda-rgb) / .16);
    border-color:var(--jv-acento); outline:none; }
  #jv-config header button { width:56px; min-height:56px; padding:0; border-radius:50%; font-size:16px; }
  #jv-config .linha-cfg { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:8px; }
  #jv-config .seg { display:grid; grid-template-columns:repeat(auto-fit,minmax(88px,1fr)); gap:10px; }
  #jv-config .atalhos { display:grid; grid-template-columns:auto 1fr; gap:8px 12px; margin:0; align-items:center; }
  #jv-config .atalhos dt { white-space:nowrap; color:var(--jv-suave); font:600 11px 'SF Mono', Menlo, monospace; }
  #jv-config .atalhos dd { margin:0; font-size:13px; }
  #jv-config kbd { display:inline-block; min-width:22px; padding:2px 6px; text-align:center; border-radius:6px; color:var(--jv-texto);
    font:600 11.5px 'SF Mono', Menlo, monospace; background:rgb(var(--jv-borda-rgb) / .10); border:1px solid rgb(var(--jv-borda-rgb) / .35); }
  #jv-config .seg button.ativo { background:rgb(var(--jv-borda-rgb) / .24); border-color:var(--jv-acento); }
  /* The hosted HUD rows: stacked, left-aligned, same chips as the bar. */
  #jv-config .slot .linha { justify-content:flex-start; flex-wrap:wrap; gap:6px; font:600 12px 'SF Mono', Menlo, monospace; letter-spacing:.04em; }
  #jv-config #hud-c { flex-direction:column; align-items:stretch; }
  #jv-config #hud-c .cer { justify-content:space-between; min-height:56px; padding:4px 10px; border-color:rgb(var(--jv-borda-rgb) / .14); }
  #jv-config #hud-c .cer .nm { margin-right:auto; }
  #jv-config #hud-jv { flex-direction:column; align-items:flex-start; }
  #jv-config #hud-jv .jv, #jv-config #hud-maos .jv { min-height:56px; flex-wrap:wrap; }
  #jv-config #hud-maos [data-acao=brilho], #jv-config #hud-maos [data-acao=tema] { display:none; }
  #jv-config .slot:empty::after, #jv-config .slot:has(> .linha:empty)::after { content:"Sem dados no momento."; color:var(--jv-suave); font-size:12px; }
    color:var(--jv-suave); font-size:11px; line-height:1.6; }`;
  document.head.appendChild(css);
  const casa = () => document.getElementById("hint") || document.body;
  casa().appendChild(menu);

  // The HUD rows other than CPU/RAM/GPU/VRAM move in here (their own scripts keep
  // updating them wherever they are).
  const lugares = { "hud-maos": "maos", "hud-c": "cerebros", "hud-jv": "consumo" };
  function recolher() {
    if (menu.parentElement !== casa()) casa().appendChild(menu);
    for (const [id, slot] of Object.entries(lugares)) {
      const el = document.getElementById(id), alvo = menu.querySelector(`[data-slot=${slot}]`);
      if (el && el.parentElement !== alvo) alvo.appendChild(el);
    }
  }
  function marcar() {
    const nivel = window.jarvisMaos?.nivelBrilho ?? 0, tema = window.jarvisTema?.nome || "original";
    menu.querySelectorAll("[data-grupo=brilho] button").forEach((b, i) => b.classList.toggle("ativo", i === nivel));
    menu.querySelectorAll("[data-grupo=tema] button").forEach(b => b.classList.toggle("ativo", b.dataset.config === "tema:" + tema));
    const visual = window.jarvisAvatar?.ativo === false ? "anel" : "avatar";
    menu.querySelectorAll("[data-grupo=visual] button").forEach(b => b.classList.toggle("ativo", b.dataset.config === "visual:" + visual));
  }
  let antes = null;
  function abrir() {
    recolher(); marcar(); antes = document.activeElement;
    menu.hidden = false; menu.querySelector("button[data-config=calibrar]")?.focus({ preventScroll: true });
  }
  function fechar() { menu.hidden = true; antes?.focus?.({ preventScroll: true }); }
  function acionar(acao) {
    const M = window.jarvisMaos;
    if (acao === "fechar") fechar();
    else if (acao === "calibrar") { fechar(); M?.calibrar(); }
    else if (acao === "maos-padrao") M?.padrao();
    else if (acao.startsWith("brilho:")) M?.mudarBrilho(Number(acao.slice(7)));
    else if (acao.startsWith("tema:")) window.jarvisTema?.usar(acao.slice(5));
    else if (acao.startsWith("visual:")) window.jarvisAvatar?.usar(acao.slice(7) === "avatar");
    marcar();
  }
  menu.addEventListener("click", ev => { const b = ev.target.closest("[data-config]"); if (b) acionar(b.dataset.config); });
  addEventListener("keydown", ev => { if (ev.key === "Escape" && !menu.hidden && !ev.target.closest?.("#jv-teclado")) { ev.preventDefault(); fechar(); } });
  addEventListener("jv-tema", marcar);
  addEventListener("jv-visual", marcar);
  window.jarvisConfig = {
    get aberto() { return !menu.hidden; }, abrir, fechar, acionar,
    alternar() { menu.hidden ? abrir() : fechar(); },
    contem(x, y) {
      if (menu.hidden) return false;
      const r = menu.getBoundingClientRect();
      return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
    },
  };
  recolher();
  setInterval(() => { recolher(); if (!menu.hidden) marcar(); }, 1000);
})();
