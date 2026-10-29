// SPDX-License-Identifier: AGPL-3.0-or-later
// Modified by gdautomacao.ia, 2026-10-07.
// The settings menu: the gear at the top-left (or the D key). Shortcuts first, then hands,
// camera brightness, colours and the visual; the brain batteries and the token meter only
// when they have data.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const BRILHOS = ["Desligado", "Suave", "Médio", "Forte"];
  // The keys of the page (stage.html, jarvis-maos.js, jarvis-teclado.js); the Guia has the same list.
  const ATALHOS = [
    ["D", "Configurações"], ["K", "Calibrar as mãos"], ["Shift + K", "Mãos no padrão"],
    ["B", "Mais brilho na câmera"], ["Shift + B", "Menos brilho na câmera"], ["T", "Trocar as cores"],
    ["F", "Fundo: câmera ou escuro"], ["/", "Escrever para o Zé"], ["R", "Recarregar a tela"], ["C", "Trocar a câmera"], ["Esc", "Fechar"],
  ];
  const ENGRENAGEM = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg>';
  // The gear (top-left, always there): the menu by hand, mouse or touch, not only by the D key.
  const engrenagem = document.createElement("button");
  engrenagem.id = "jv-engrenagem"; engrenagem.type = "button";
  engrenagem.setAttribute("aria-label", "Configurações"); engrenagem.setAttribute("aria-expanded", "false");
  engrenagem.title = "Configurações (D)"; engrenagem.innerHTML = ENGRENAGEM;
  document.body.appendChild(engrenagem);
  const seg = (grupo, n, botoes) => `<div class="seg" data-grupo="${grupo}" style="--n:${n}">${botoes}</div>`;
  const menu = document.createElement("div");
  menu.id = "jv-config"; menu.hidden = true;
  menu.setAttribute("role", "dialog"); menu.setAttribute("aria-label", "Configurações do Zé");
  menu.innerHTML = `
    <header><b>Configurações</b><button data-config="fechar" aria-label="Fechar configurações">×</button></header>
    <div class="corpo">
      <section><h3>Atalhos</h3><dl class="atalhos">
        ${ATALHOS.map(([tecla, faz]) => `<dt>${tecla.split(" + ").map(t => `<kbd>${t}</kbd>`).join("")}</dt><dd>${faz}</dd>`).join("")}</dl></section>
      <section><h3>Mãos</h3><div class="slot" data-slot="maos"></div>
        <div class="seg" style="--n:2"><button data-config="calibrar">Calibrar as mãos</button>
        <button data-config="maos-padrao">Voltar ao padrão</button></div></section>
      <section><h3>Brilho da câmera</h3>
        ${seg("brilho", 4, BRILHOS.map((n, i) => `<button data-config="brilho:${i}">${n}</button>`).join(""))}</section>
      <section><h3>Cores</h3>
        ${seg("tema", 3, (window.jarvisTema?.lista || [{ id: "original", nome: "Original" }]).map(t => `<button data-config="tema:${t.id}">${t.nome}</button>`).join(""))}</section>
      <section><h3>Visual</h3>
        ${seg("visual", 2, '<button data-config="visual:avatar">Avatar</button><button data-config="visual:anel">Anel</button>')}</section>
      <section><h3>Fundo</h3>
        ${seg("fundo", 2, '<button data-config="fundo:camera">Câmera</button><button data-config="fundo:escuro">Escuro</button>')}</section>
      <section class="opcional"><h3>Cérebro</h3><div class="slot" data-slot="cerebros"></div></section>
      <section class="opcional"><h3>Consumo</h3><div class="slot" data-slot="consumo"></div></section>
    </div>`;
  const css = document.createElement("style");
  css.textContent = `
  /* The gear: same glass as the board, top-left, 56 px (a comfortable pinch). */
  #jv-engrenagem { position:fixed; left:14px; top:14px; z-index:1000; width:56px; height:56px; padding:0; border-radius:50%; cursor:pointer;
    display:grid; place-items:center; color:var(--jv-acento); background:linear-gradient(172deg, var(--jv-vidro-a), var(--jv-vidro-b));
    backdrop-filter:blur(8px); border:1.5px solid rgb(var(--jv-borda-rgb) / .45); box-shadow:0 8px 30px rgba(0,0,0,.3); transition:background .15s, border-color .15s; }
  #jv-engrenagem svg { width:24px; height:24px; fill:none; stroke:currentColor; stroke-width:1.6; stroke-linecap:round; stroke-linejoin:round; transition:transform .3s; }
  #jv-engrenagem:hover, #jv-engrenagem.apontado, #jv-engrenagem:focus-visible, #jv-engrenagem[aria-expanded="true"] {
    background:rgb(var(--jv-borda-rgb) / .18); border-color:var(--jv-acento); outline:none; }
  #jv-engrenagem[aria-expanded="true"] svg { transform:rotate(45deg); }
  body.overlay #jv-engrenagem, body.greenkey #jv-engrenagem { display:none; }
  /* The menu opens under the gear: a fixed header and a body that scrolls (nothing slides under the title). */
  #jv-config { position:fixed; left:14px; top:82px; bottom:14px; z-index:999; width:min(340px, calc(100vw - 28px)); box-sizing:border-box;
    display:flex; flex-direction:column; text-align:left; letter-spacing:0; white-space:normal;
    background:var(--jv-painel); backdrop-filter:blur(10px); border:1.5px solid rgb(var(--jv-borda-rgb) / .45); border-radius:18px;
    box-shadow:0 16px 70px rgba(0,0,0,.4), 0 0 35px rgb(var(--jv-borda-rgb) / .1);
    color:var(--jv-texto); font:14px/1.45 -apple-system, 'Segoe UI', sans-serif; text-shadow:none; animation:jvcfg .2s ease-out; }
  @keyframes jvcfg { from { opacity:0; transform:translateY(-8px); } }
  #jv-config[hidden] { display:none; }
  #jv-config header { flex:none; display:flex; align-items:center; justify-content:space-between; padding:10px 10px 10px 18px;
    border-bottom:1px solid rgb(var(--jv-borda-rgb) / .2); }
  #jv-config header b { font:600 12px 'SF Mono', Menlo, monospace; letter-spacing:.16em; text-transform:uppercase; color:var(--jv-acento); }
  #jv-config .corpo { flex:1; min-height:0; overflow-y:auto; overscroll-behavior:contain; padding:4px 18px 16px;
    scrollbar-width:thin; scrollbar-color:rgb(var(--jv-borda-rgb) / .35) transparent; }
  #jv-config section { padding:14px 0 4px; }
  #jv-config section + section { border-top:1px solid rgb(var(--jv-borda-rgb) / .1); }
  #jv-config h3 { margin:0 0 10px; color:var(--jv-suave); font:600 10.5px 'SF Mono', Menlo, monospace; letter-spacing:.16em; text-transform:uppercase; }
  #jv-config button { min-height:56px; padding:0 10px; border-radius:12px; cursor:pointer; color:var(--jv-texto);
    font:600 13px -apple-system, 'Segoe UI', sans-serif; background:rgb(var(--jv-borda-rgb) / .06);
    border:1px solid rgb(var(--jv-borda-rgb) / .28); transition:background .15s, border-color .15s; }
  #jv-config button:hover, #jv-config button.apontado, #jv-config button:focus-visible { background:rgb(var(--jv-borda-rgb) / .16);
    border-color:var(--jv-acento); outline:none; }
  #jv-config header button { width:56px; height:56px; padding:0; border-radius:50%; font-size:20px; font-weight:400; }
  #jv-config .seg { display:grid; grid-template-columns:repeat(var(--n, 3), minmax(0, 1fr)); gap:8px; }
  #jv-config .seg button { padding:0 6px; }
  #jv-config .seg[data-grupo=brilho] button { font-size:12px; padding:0 2px; }
  #jv-config .seg button.ativo { background:rgb(var(--jv-borda-rgb) / .24); border-color:var(--jv-acento); }
  #jv-config .atalhos { display:grid; grid-template-columns:96px 1fr; gap:9px 10px; margin:0; align-items:center; }
  #jv-config .atalhos dt { display:flex; gap:4px; }
  #jv-config .atalhos dd { margin:0; font-size:13px; color:var(--jv-texto); }
  #jv-config kbd { min-width:26px; padding:3px 7px; box-sizing:border-box; text-align:center; border-radius:7px; color:var(--jv-texto);
    font:600 11.5px 'SF Mono', Menlo, monospace; background:rgb(var(--jv-borda-rgb) / .10); border:1px solid rgb(var(--jv-borda-rgb) / .35);
    border-bottom-width:2px; }
  /* The hosted HUD rows: stacked, left-aligned, same chips as the bar. */
  #jv-config .slot .linha { display:flex; justify-content:flex-start; flex-wrap:wrap; gap:8px; margin-bottom:8px;
    font:600 12px 'SF Mono', Menlo, monospace; letter-spacing:.04em; }
  #jv-config .slot:empty, #jv-config .slot .linha:empty { display:none; }
  #jv-config #hud-c { flex-direction:column; align-items:stretch; }
  #jv-config #hud-c .cer { justify-content:space-between; min-height:56px; padding:4px 10px; border-color:rgb(var(--jv-borda-rgb) / .14); }
  #jv-config #hud-c .cer .nm { margin-right:auto; }
  #jv-config #hud-jv { flex-direction:column; align-items:flex-start; }
  #jv-config #hud-jv .jv, #jv-config #hud-maos .jv { min-height:56px; flex-wrap:wrap; }
  #jv-config #hud-maos [data-acao=brilho], #jv-config #hud-maos [data-acao=tema] { display:none; }
  /* Brain and usage only show when there is something to show (no "no data" filler). */
  #jv-config section.opcional:not(:has(.slot .linha:not(:empty))) { display:none; }`;
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
    const fundo = window.jarvisFundo?.modo || "camera";
    menu.querySelectorAll("[data-grupo=fundo] button").forEach(b => b.classList.toggle("ativo", b.dataset.config === "fundo:" + fundo));
  }
  let antes = null;
  function abrir() {
    recolher(); marcar(); antes = document.activeElement;
    menu.hidden = false; engrenagem.setAttribute("aria-expanded", "true");
    menu.querySelector("button[data-config=fechar]")?.focus({ preventScroll: true });
  }
  function fechar() { menu.hidden = true; engrenagem.setAttribute("aria-expanded", "false"); antes?.focus?.({ preventScroll: true }); }
  engrenagem.addEventListener("click", () => (menu.hidden ? abrir() : fechar()));
  function acionar(acao) {
    const M = window.jarvisMaos;
    if (acao === "fechar") fechar();
    else if (acao === "calibrar") { fechar(); M?.calibrar(); }
    else if (acao === "maos-padrao") M?.padrao();
    else if (acao.startsWith("brilho:")) M?.mudarBrilho(Number(acao.slice(7)));
    else if (acao.startsWith("tema:")) window.jarvisTema?.usar(acao.slice(5));
    else if (acao.startsWith("visual:")) window.jarvisAvatar?.usar(acao.slice(7) === "avatar");
    else if (acao.startsWith("fundo:")) window.jarvisFundo?.usar(acao.slice(6));
    marcar();
  }
  menu.addEventListener("click", ev => { const b = ev.target.closest("[data-config]"); if (b) acionar(b.dataset.config); });
  addEventListener("keydown", ev => { if (ev.key === "Escape" && !menu.hidden && !ev.target.closest?.("#jv-teclado")) { ev.preventDefault(); fechar(); } });
  addEventListener("jv-tema", marcar);
  addEventListener("jv-visual", marcar); addEventListener("jv-fundo", marcar);
  window.jarvisConfig = {
    get aberto() { return !menu.hidden; }, abrir, fechar, acionar,
    alternar() { menu.hidden ? abrir() : fechar(); },
    contem(x, y) {
      const dentro = el => { const r = el.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; };
      return dentro(engrenagem) || (!menu.hidden && dentro(menu));
    },
  };
  recolher();
  setInterval(() => { recolher(); if (!menu.hidden) marcar(); }, 1000);
})();
