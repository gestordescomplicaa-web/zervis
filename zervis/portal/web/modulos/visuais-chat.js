import { esc, toast } from "../painel.js";
import { icone } from "./casca.js";

// Os visuais do chat (ADR 0138): apresentações, diagramas, gráficos e painéis que o Zé monta. Cada
// um abre numa moldura isolada (/fluxo/visual: sem rede, numa origem à parte, sem o painel), vai
// para a tela cheia e se baixa em HTML interativo, imagem (PNG) ou PDF.

/** @typedef {{ id: string, titulo: string, especie?: string }} Visual */

/** @type {Record<string, string>} */
const ESPECIES = { apresentacao: "Apresentação", diagrama: "Diagrama", grafico: "Gráfico", painel: "Painel", pagina: "Página" };
/** @type {Map<string, Visual>} */
const vistos = new Map();
const endereco = (/** @type {string} */ id, formato = "") => `/fluxo/visual?id=${encodeURIComponent(id)}${formato ? `&formato=${formato}` : ""}`;

/** @param {string} nome @param {string} rotulo @param {string} acao @param {string} id */
const botao = (nome, rotulo, acao, id) => `<button type="button" class="botao-visual" data-visual-acao="${acao}" data-id="${esc(id)}" aria-label="${rotulo}" title="${rotulo}">${icone(nome)}</button>`;

/** Um visual no fio do chat. @param {Visual} v */
export function visualNaFala(v) {
  vistos.set(v.id, v);
  return `<section class="visual">
    <header><span class="icone-visual">${icone("presentation")}</span><span class="nome-visual"><b>${esc(v.titulo)}</b><small>${ESPECIES[v.especie || ""] || "Visual"} · Interativo</small></span>
      <span class="botoes-visual">${botao("maximize-2", "Tela cheia", "cheio", v.id)}${botao("download", "Baixar", "menu", v.id)}</span></header>
    <iframe sandbox="allow-scripts" src="${endereco(v.id)}" title="${esc(v.titulo)}" loading="lazy" referrerpolicy="no-referrer"></iframe>
  </section>`;
}

/** @param {Visual} v */
function telaCheia(v) {
  fechar();
  document.body.insertAdjacentHTML("beforeend", `<div class="visual-tela" role="dialog" aria-modal="true" aria-label="${esc(v.titulo)}">
    <header><b>${esc(v.titulo)}</b><span class="espaco"></span>${botao("download", "Baixar", "menu", v.id)}${botao("x", "Fechar", "fechar", v.id)}</header>
    <div class="corpo-visual"><iframe sandbox="allow-scripts" src="${endereco(v.id)}" title="${esc(v.titulo)}" referrerpolicy="no-referrer"></iframe></div></div>`);
  /** @type {HTMLElement | null} */ (document.querySelector(".visual-tela [data-visual-acao=fechar]"))?.focus();
}

function fechar() {
  document.querySelector(".visual-tela")?.remove();
  document.querySelector(".menu-baixar")?.remove();
}

/** @param {HTMLElement} b @param {Visual} v */
function menuBaixar(b, v) {
  document.querySelector(".menu-baixar")?.remove();
  const r = b.getBoundingClientRect();
  const item = (/** @type {string} */ formato, /** @type {string} */ nome, /** @type {string} */ rotulo) => `<button type="button" role="menuitem" data-visual-acao="baixar" data-formato="${formato}" data-id="${esc(v.id)}">${icone(nome)}${rotulo}</button>`;
  document.body.insertAdjacentHTML("beforeend", `<div class="menu-baixar" role="menu" style="top:${Math.round(r.bottom + 6)}px;left:${Math.round(Math.max(8, r.right - 200))}px">
    ${item("html", "file-text", "HTML interativo")}${item("png", "image", "Imagem (PNG)")}${item("pdf", "file-text", "PDF")}</div>`);
}

/** Baixa do Zé (o PNG e o PDF levam uns segundos: ele desenha no Chromium). @param {Visual} v @param {string} formato */
async function baixar(v, formato) {
  document.querySelector(".menu-baixar")?.remove();
  const nome = v.titulo.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase() || "visual";
  if (formato !== "html") toast(formato === "pdf" ? "Preparando o PDF." : "Preparando a imagem.");
  try {
    const r = await fetch(endereco(v.id, formato === "html" ? "" : formato));
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).erro || "Não foi possível baixar.");
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(await r.blob()), download: `${nome}.${formato}` });
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
  } catch (erro) { toast(/** @type {Error} */ (erro).message); }
}

document.addEventListener("click", (ev) => {
  const alvo = /** @type {HTMLElement} */ (ev.target);
  const b = /** @type {HTMLElement | null} */ (alvo.closest("[data-visual-acao]"));
  if (!b) { if (!alvo.closest(".menu-baixar")) document.querySelector(".menu-baixar")?.remove(); return; }
  const v = vistos.get(b.dataset.id || "");
  if (!v) return;
  const acao = b.dataset.visualAcao;
  if (acao === "cheio") telaCheia(v);
  else if (acao === "fechar") fechar();
  else if (acao === "menu") menuBaixar(b, v);
  else if (acao === "baixar") baixar(v, b.dataset.formato || "html");
});
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") fechar(); });

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.fala.ze.visual-fala { max-width: 100%; align-self: stretch; }
.visual { display: grid; width: min(760px, 100%); border-radius: 14px; overflow: hidden; border: 1px solid var(--borda-forte); background: var(--vidro); }
.visual > header { display: flex; align-items: center; gap: 10px; padding: 10px 10px 10px 12px; border-bottom: 1px solid var(--borda); }
.icone-visual { display: grid; place-items: center; width: 32px; height: 32px; flex: none; border-radius: 9px; background: var(--acento-suave); color: var(--acento); }
.icone-visual svg { width: 16px; height: 16px; }
.nome-visual { display: grid; min-width: 0; flex: 1; }
.nome-visual b { font-weight: 600; font-size: 13.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nome-visual small { font-size: 12px; color: var(--suave); }
.botoes-visual { display: flex; gap: 4px; }
.botao-visual { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 8px; border: 0; background: none; color: var(--suave); cursor: pointer; transition: background .15s, color .15s; }
.botao-visual:hover { background: var(--realce); color: var(--texto); }
.botao-visual svg { width: 16px; height: 16px; }
.visual iframe { width: 100%; height: 400px; border: 0; background: var(--fundo); display: block; }
.visual-tela { position: fixed; inset: 0; z-index: 60; display: grid; grid-template-rows: auto minmax(0, 1fr); background: var(--fundo); animation: entrar-pagina .2s var(--saida); }
.visual-tela > header { display: flex; align-items: center; gap: 6px; padding: 10px 14px 10px 20px; border-bottom: 1px solid var(--borda); }
.visual-tela .espaco { flex: 1; }
.corpo-visual { min-height: 0; }
.corpo-visual iframe { width: 100%; height: 100%; border: 0; display: block; }
.menu-baixar { position: fixed; z-index: 70; display: grid; width: 200px; padding: 6px; border-radius: 12px; background: var(--vidro-forte); border: 1px solid var(--borda-forte); box-shadow: var(--sombra); }
.menu-baixar button { display: flex; align-items: center; gap: 10px; height: 36px; padding: 0 10px; border: 0; border-radius: 8px; background: none; color: var(--texto); font: 13.5px var(--sans); cursor: pointer; text-align: left; }
.menu-baixar button:hover { background: var(--realce); }
.menu-baixar svg { width: 16px; height: 16px; color: var(--suave); }
@media (max-width: 720px) { .visual iframe { height: 320px; } }
` }));
