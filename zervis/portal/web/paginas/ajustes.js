import { ACOES } from "../modulos/acoes.js";
import { ICONES, icone } from "../modulos/casca.js";
import { PAGINAS, cabeca, esc, sub } from "../painel.js";

// A página Ajustes (ADR 0135): tudo o que se configura no Zé, por assunto, com busca. Cada ajuste
// leva à página dele, já no cartão certo; as páginas continuam as mesmas.

/** [página, título, descrição, [ajuste, alvo][]]; alvo: o título do cartão, ou "#id" do lugar. */
/** @type {[string, string, string, [string, string][]][]} */
const ASSUNTOS = [
  ["voz", "Voz", "A voz do Zé, o modo de fala, a escuta, a ativação, os avisos e o acesso pelo celular.",
    [["Voz do Zé", "Voz do Zé"], ["Modo de fala", "Modo de fala"], ["Escuta", "Escuta"], ["Ativação", "Ativação"], ["Espera", "Espera"], ["Avisos pelo WhatsApp", "WhatsApp"], ["Acesso pelo celular", "Acesso pelo celular"], ["App de voz", "App de voz"]]],
  ["modelos", "Modelos", "O cérebro, as respostas rápidas, as contas dos agentes e o reconhecimento de fala.",
    [["Cérebro", "#cartao-acesso"], ["Respostas rápidas", "Respostas rápidas"], ["Contas", "#cartao-contas"], ["Sessões de código", "Sessões de código"], ["Reconhecimento de fala", "#cartao-escuta"]]],
  ["perfil", "Perfil", "O seu nome, o seu jeito, o fuso e a abertura do dia.",
    [["Nome e fuso", ""], ["Abertura do dia", "#cartao-abertura"]]],
  ["conectores", "Conectores", "As integrações com outros sistemas: n8n, o navegador e outros.", []],
  ["atendimento", "Redes sociais", "O WhatsApp e o Instagram ligados ao Zé, o atendimento e o agente.",
    [["WhatsApp", "WhatsApp"], ["Instagram", "Instagram"], ["Atendimento", "Atendimento"], ["Agente", "Agente"], ["Avisos", "Avisos"]]],
  ["marketing", "Marketing", "O site e o blog, os vídeos, o Instagram, a marca e as chaves.",
    [["Site e blog", "#mk-ajuste-site"], ["Vídeos", "#mk-ajuste-videos"], ["Instagram", "#mk-ajuste-instagram"], ["Marca", "#mk-ajuste-marca"], ["Chaves e contas", "#mk-ajuste-chaves"]]],
  ["prospeccao", "Prospecção", "A cidade, os ramos, a oferta, a mensagem e as fontes.",
    [["Configuração", "Configuração"], ["Mensagem", "Mensagem"], ["Fontes", "Fontes"]]],
  ["atualizacoes", "Atualizações", "As versões novas do Zé e de onde vêm.", [["Canal", "Canal"], ["Versão", "Versão"]]],
];

/** Sem acento e em minúsculas, para a busca. @param {string} t */
const simples = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** @param {string} pagina @param {string} nome @param {string} alvo */
const ajuste = (pagina, nome, alvo) => `<button type="button" class="ajuste" data-acao="ajustes-ir" data-pagina="${pagina}" data-alvo="${esc(alvo)}" data-busca="${esc(simples(nome))}">${esc(nome)}</button>`;

PAGINAS.ajustes = async () => `${cabeca("Ajustes")}${sub("Tudo o que se configura no Zé, por assunto.")}
  <div class="ajustes-hub">
    <label class="busca-ajustes">${icone("search")}<input type="search" id="ajustes-busca" placeholder="Buscar ajuste" autocomplete="off" aria-label="Buscar ajuste"></label>
    <p class="pela-voz">${icone("mic")}Pela voz: “Zé, como eu ligo o Live?”</p>
    <div class="assuntos">${ASSUNTOS.map(([pagina, titulo, descricao, ajustes]) => `<section class="cartao assunto" data-busca="${esc(simples(`${titulo} ${descricao}`))}">
      <button type="button" class="titulo-assunto" data-acao="ajustes-ir" data-pagina="${pagina}" data-alvo="">${icone(ICONES[pagina] || "settings")}<span><strong>${esc(titulo)}</strong><small>${esc(descricao)}</small></span>${icone("chevron-right")}</button>
      ${ajustes.length ? `<div class="ajustes">${ajustes.map(([nome, alvo]) => ajuste(pagina, nome, alvo)).join("")}</div>` : ""}
    </section>`).join("")}</div>
    <p class="vazio" id="ajustes-nada" hidden>Nenhum ajuste com esse nome.</p>
  </div>`;

/** Mostra só os assuntos e os ajustes que batem com a busca. @param {string} texto */
function filtrar(texto) {
  const q = simples(texto.trim());
  let algum = false;
  for (const a of /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll(".assunto"))) {
    const noAssunto = !q || (a.dataset.busca || "").includes(q);
    let nos = 0;
    for (const b of /** @type {NodeListOf<HTMLElement>} */ (a.querySelectorAll(".ajuste"))) {
      const bate = noAssunto || (b.dataset.busca || "").includes(q);
      b.hidden = !bate;
      if (bate) nos++;
    }
    a.hidden = !noAssunto && !nos;
    algum ||= !a.hidden;
  }
  const nada = document.getElementById("ajustes-nada");
  if (nada) nada.hidden = algum;
}

document.addEventListener("input", (ev) => { if (/** @type {HTMLElement} */ (ev.target).id === "ajustes-busca") filtrar(/** @type {HTMLInputElement} */ (ev.target).value); });

/** O lugar do ajuste na página dele: um "#id", ou o cartão cujo título começa pelo nome. @param {string} alvo */
function lugar(alvo) {
  if (alvo.startsWith("#")) return document.querySelector(`#conteudo ${alvo}`);
  const titulo = [.../** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll("#conteudo h2"))]
    .find((h) => h.offsetParent !== null && (h.textContent || "").trim().startsWith(alvo));
  return titulo?.closest(".cartao") || titulo || null;
}

Object.assign(ACOES, {
  /** Abre a página do ajuste e leva ao cartão dele, com um destaque breve. @param {HTMLButtonElement} b */
  "ajustes-ir": async (b) => {
    const pagina = b.dataset.pagina || "", alvo = b.dataset.alvo || "";
    if (pagina === "marketing") try { localStorage.setItem("ze.marketing-aba", "ajustes"); } catch { /* abre na aba de antes */ }
    location.hash = `#${pagina}`;
    if (!alvo) return;
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 100));
      if (location.hash !== `#${pagina}` || document.querySelector("#conteudo .ajustes-hub")) continue;
      const achado = /** @type {HTMLElement | null} */ (lugar(alvo));
      if (!achado) continue;
      achado.scrollIntoView({ behavior: "smooth", block: "start" });
      achado.classList.add("destacado");
      setTimeout(() => achado.classList.remove("destacado"), 1800);
      return;
    }
  },
});

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.ajustes-hub { display: grid; gap: 16px; }
.busca-ajustes { position: relative; display: block; max-width: 520px; }
.busca-ajustes svg { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--apagado); width: 16px; height: 16px; }
.busca-ajustes input { width: 100%; height: 42px; padding-left: 38px; font-size: 15px; }
.assuntos { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; align-items: start; }
.assunto { gap: 12px; padding: 0; overflow: hidden; }
.titulo-assunto { display: flex; align-items: center; gap: 12px; width: 100%; padding: 16px 18px 4px; border: 0; background: none; color: inherit; text-align: left; cursor: pointer; font: inherit; }
.titulo-assunto > svg:first-child { width: 20px; height: 20px; color: var(--acento); flex: none; }
.titulo-assunto > svg:last-child { margin-left: auto; color: var(--apagado); transition: transform .2s var(--saida), color .15s; }
.titulo-assunto:hover > svg:last-child { transform: translateX(3px); color: var(--texto); }
.titulo-assunto span { display: grid; gap: 2px; min-width: 0; }
.titulo-assunto strong { font-weight: 600; font-size: 15px; }
.titulo-assunto small { color: var(--suave); font-size: 13px; line-height: 1.4; }
.assunto:not(:has(.ajustes)) .titulo-assunto { padding-bottom: 16px; }
.ajustes { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 18px 16px 50px; }
.ajuste { height: 28px; padding: 0 11px; border-radius: 14px; cursor: pointer; font: 500 12.5px var(--sans); color: var(--suave); background: var(--fundo-2); border: 1px solid var(--borda-forte); transition: color .15s, border-color .15s, background .15s; }
.ajuste:hover { color: var(--texto); border-color: #33454f; background: var(--realce); }
.destacado { animation: destacar 1.8s var(--saida); }
@keyframes destacar { 0%, 40% { box-shadow: 0 0 0 2px var(--acento); } 100% { box-shadow: 0 0 0 2px transparent; } }
` }));
