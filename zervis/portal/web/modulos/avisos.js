// A central de avisos (ADR 0133): o sino no topo conta o que precisa de você; o painel ao lado
// lista esses itens e os avisos de hoje; o aviso do Zé entra na tela com o anel e Fechar.
// Carregado logo depois da abertura (modulos/principal.js), fora do orçamento dela.
import { $, api, esc, toast } from "../painel.js";
import { ICONES, icone } from "./casca.js";

/** @typedef {{ id: string, secao: string, area: string, titulo: string, detalhe: string, quando: number, nivel: string, acao: string, link: string, aprovacao: string }} ItemPrecisa */
/** @type {{ itens: ItemPrecisa[], recentes: { quando: string, texto: string }[] }} */
let ultimo = { itens: [], recentes: [] };
let prazo = 0;

/** Há quanto tempo: "agora", "5 min", "2 h", "3 d". @param {number} s epoch, em segundos */
export function ha(s) {
  const m = Math.max(0, Math.round((Date.now() / 1000 - s) / 60));
  return m < 1 ? "agora" : m < 60 ? `${m} min` : m < 1440 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} d`;
}

/** Uma linha do "Precisa de você", no Início e no sino. @param {ItemPrecisa} i */
export function linhaPrecisa(i) {
  const fora = /^https?:/.test(i.link), id = esc(i.aprovacao);
  const botoes = i.aprovacao
    ? `<button type="button" class="acao" data-acao="aprovacao-decidir" data-id="${id}" data-aprovar="0">Negar</button><button type="button" class="acao principal" data-acao="aprovacao-decidir" data-id="${id}" data-aprovar="1">Aprovar</button>`
    : `<a class="acao" href="${esc(i.link)}"${fora ? ' target="_blank" rel="noopener"' : ' data-acao="avisos-fechar"'}>${esc(i.acao)}</a>`;
  return `<div class="linha-item precisa" data-nivel="${esc(i.nivel)}"><span class="icone-area">${icone(ICONES[i.secao] || "bell")}</span><div class="texto"><strong>${esc(i.titulo)}</strong><small>${esc(i.area)}${i.detalhe ? ` · ${esc(i.detalhe)}` : ""}</small></div>${i.quando ? `<span class="hora">${ha(i.quando)}</span>` : ""}<div class="botoes">${botoes}</div></div>`;
}

/** @param {string} iso */
const hora = (iso) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

function desenhar() {
  const corpo = $("avisos-corpo");
  if (!corpo) return;
  const { itens, recentes } = ultimo;
  corpo.innerHTML = `<h3 class="subtitulo">Precisa de você</h3>
    ${itens.length ? `<div class="itens">${itens.map(linhaPrecisa).join("")}</div>` : `<p class="vazio">Nada pendente.</p>`}
    <h3 class="subtitulo">Avisos de hoje</h3>
    ${recentes.length ? `<ol class="recentes">${recentes.map((a) => `<li><time>${hora(a.quando)}</time><p>${esc(a.texto)}</p></li>`).join("")}</ol>` : `<p class="vazio">Nenhum aviso hoje.</p>`}`;
}

/** Lê a lista de novo: o contador do sino e, se aberto, o painel. */
export async function atualizarAvisos() {
  try { ultimo = await api("precisa"); } catch { return; }
  const n = ultimo.itens.length, contador = $("contador-avisos");
  if (contador) { contador.hidden = !n; contador.textContent = n > 9 ? "9+" : String(n); }
  $("sino")?.setAttribute("title", n ? `Avisos · ${n} ${n === 1 ? "pendente" : "pendentes"}` : "Avisos");
  desenhar();
}

export function alternarAvisos() {
  let painel = $("avisos");
  if (!painel) {
    painel = Object.assign(document.createElement("aside"), { id: "avisos", className: "avisos" });
    painel.setAttribute("aria-label", "Avisos");
    painel.innerHTML = `<header><h2>Avisos</h2><button type="button" class="x" data-acao="avisos-fechar" aria-label="Fechar">×</button></header><div class="avisos-corpo" id="avisos-corpo"></div>`;
    document.body.append(painel);
    desenhar();
    painel.getBoundingClientRect(); // entra deslizando já na primeira vez
  }
  const abrir = !painel.classList.contains("aberto");
  painel.classList.toggle("aberto", abrir);
  $("sino")?.setAttribute("aria-expanded", String(abrir));
  if (abrir) atualizarAvisos();
}

export function fecharAvisos() {
  $("avisos")?.classList.remove("aberto");
  $("sino")?.setAttribute("aria-expanded", "false");
}

/** Aprovar ou negar, ali mesmo, uma ação pedida pelo WhatsApp (o mesmo pedido da Conversa). @param {HTMLButtonElement} b */
export async function decidirAprovacao(b) {
  const id = b.dataset.id || "";
  for (const x of b.parentElement?.querySelectorAll("button") || []) /** @type {HTMLButtonElement} */ (x).disabled = true;
  try { toast((await api("conversa/aprovacao", { id, aprovar: b.dataset.aprovar === "1" })).aviso); }
  finally {
    for (const x of document.querySelectorAll(`.precisa [data-id="${CSS.escape(id)}"]`)) x.closest(".linha-item")?.remove();
    atualizarAvisos();
  }
}

/** Um aviso do Zé na tela (o que ele não falou): o anel, o texto e Fechar; fica também no sino. @param {string} texto @param {number} ms */
export function avisoDoZe(texto, ms) {
  let t = /** @type {HTMLElement | null} */ (document.querySelector(".aviso-ze"));
  if (!t) { t = Object.assign(document.createElement("div"), { className: "toast aviso-ze" }); t.setAttribute("role", "status"); document.body.append(t); }
  const aviso = t;
  aviso.innerHTML = `<img src="/ze.webp" alt="" width="32" height="32"><div><strong>Aviso</strong><p>${esc(texto)}</p></div><button type="button" class="x" data-acao="aviso-fechar" aria-label="Fechar">×</button>`;
  requestAnimationFrame(() => aviso.classList.add("on"));
  clearTimeout(prazo);
  prazo = window.setTimeout(() => aviso.classList.remove("on"), ms);
  atualizarAvisos();
}

export const fecharAviso = () => document.querySelector(".aviso-ze")?.classList.remove("on");

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.avisos { position: fixed; z-index: 45; top: 64px; right: 0; bottom: 0; width: min(400px, 100vw); display: flex; flex-direction: column;
  background: #0a0f13; border-left: 1px solid var(--borda); box-shadow: -18px 0 50px rgb(0 0 0 / .45);
  transform: translateX(102%); visibility: hidden; transition: transform .35s var(--saida), visibility 0s .35s; }
.avisos.aberto { transform: none; visibility: visible; transition: transform .35s var(--saida); }
.avisos header { display: flex; align-items: center; padding: 14px 16px 10px 20px; }
.avisos header h2 { margin: 0 auto 0 0; }
.avisos-corpo { flex: 1; overflow-y: auto; padding: 0 16px 24px; display: grid; gap: 10px; align-content: start; }
.avisos .subtitulo { margin: 10px 4px 0; font-size: 12px; font-weight: 500; letter-spacing: .06em; text-transform: uppercase; color: var(--apagado); }
.recentes { list-style: none; margin: 0; padding: 0; display: grid; }
.recentes li { display: grid; grid-template-columns: 44px 1fr; gap: 8px; padding: 9px 4px; border-top: 1px solid var(--borda); font-size: 13.5px; }
.recentes li:first-child { border-top: 0; }
.recentes time { color: var(--apagado); font: 12px/1.7 var(--mono); }
.recentes p { margin: 0; color: var(--suave); }
.linha-item.precisa, .linha-item.agora { flex-wrap: nowrap; gap: 12px; }
.icone-area { width: 32px; height: 32px; flex: none; border-radius: 9px; display: grid; place-items: center; color: var(--suave); background: var(--realce); }
.icone-area svg { width: 16px; height: 16px; }
.precisa[data-nivel="alerta"] .icone-area { color: var(--alerta); background: rgb(239 190 124 / .1); }
.precisa[data-nivel="critico"] .icone-area { color: var(--erro); background: rgb(240 135 126 / .1); }
.icone-area.vivo { color: var(--acento); background: var(--acento-suave); animation: piscar 2.4s ease-in-out infinite; }
.linha-item .hora { flex: none; color: var(--apagado); font: 12px var(--mono); white-space: nowrap; }
.linha-item.precisa .texto small { overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.avisos .linha-item.precisa { flex-wrap: wrap; }
.avisos .linha-item.precisa .texto { flex-basis: calc(100% - 100px); }
.avisos .linha-item.precisa .botoes { margin-left: 44px; }
@media (max-width: 720px) {
  .linha-item.precisa { flex-wrap: wrap; }
  .linha-item.precisa .texto { flex-basis: calc(100% - 100px); }
  .linha-item.precisa .botoes { margin-left: 44px; }
}
a.linha-item.agora { color: inherit; text-decoration: none !important; }
/* O aviso do Zé: o anel, o texto e Fechar (os outros avisos da tela são só o texto). */
.toast.aviso-ze { display: flex; align-items: flex-start; gap: 12px; padding: 12px 10px 12px 12px; pointer-events: auto; border-color: rgb(70 217 222 / .35); }
.aviso-ze img { width: 32px; height: 32px; border-radius: 50%; flex: none; }
.aviso-ze div { flex: 1; min-width: 0; }
.aviso-ze strong { display: block; font-size: 12px; font-weight: 500; letter-spacing: .06em; text-transform: uppercase; color: var(--acento); }
.aviso-ze p { margin: 2px 0 0; }
.aviso-ze .x { margin: -4px 0 0; }
@media (max-width: 720px) { .avisos { top: 58px; } }
` }));
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") fecharAvisos(); });
window.addEventListener("hashchange", fecharAvisos); // outra página (a Imersão também) não fica coberta
setInterval(() => { if (!document.hidden) atualizarAvisos(); }, 30000);
atualizarAvisos();
