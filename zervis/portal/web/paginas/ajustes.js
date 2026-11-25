import { ACOES } from "../modulos/acoes.js";
import { ICONES, icone } from "../modulos/casca.js";
import { PAGINAS, cabeca, esc, sub } from "../painel.js";

// A página Ajustes (ADR 0135): tudo o que se configura no Zé, por assunto, com busca. Cada ajuste
// leva à página dele, já no cartão certo; as páginas continuam as mesmas.

/** [página, título, descrição, palavras da busca, [ajuste, alvo][]]; alvo: o título do cartão, ou "#id". */
/** @type {[string, string, string, string, [string, string][]][]} */
const ASSUNTOS = [
  ["voz", "Voz", "Como o Zé fala, ouve e avisa.", "fala ouvir microfone ei ze live silencioso celular",
    [["Voz do Zé", "Voz do Zé"], ["Modo de fala", "Modo de fala"], ["Escuta", "Escuta"], ["Ativação", "Ativação"], ["Espera", "Espera"], ["Avisos pelo WhatsApp", "WhatsApp"], ["Acesso pelo celular", "Acesso pelo celular"], ["App de voz", "App de voz"]]],
  ["modelos", "Modelos", "Os modelos de IA e as contas.", "llm cerebro claude codex openai anthropic assinatura api chave whisper deepgram",
    [["Cérebro", "#cartao-acesso"], ["Respostas rápidas", "Respostas rápidas"], ["Contas", "#cartao-contas"], ["Sessões de código", "Sessões de código"], ["Reconhecimento de fala", "#cartao-escuta"]]],
  ["perfil", "Perfil", "Quem você é e como o dia começa.", "nome jeito sobre horario dia",
    [["Nome e fuso", ""], ["Abertura do dia", "#cartao-abertura"]]],
  ["atendimento", "Redes sociais", "WhatsApp, Instagram e o atendimento.", "zap direct comentarios leads agente clientes",
    [["WhatsApp", "WhatsApp"], ["Instagram", "Instagram"], ["Atendimento", "Atendimento"], ["Agente", "Agente"], ["Avisos", "Avisos"]]],
  ["marketing", "Marketing", "Site, vídeos, marca e chaves.", "blog reels carrossel pixabay publicar",
    [["Site e blog", "#mk-ajuste-site"], ["Vídeos", "#mk-ajuste-videos"], ["Instagram", "#mk-ajuste-instagram"], ["Marca", "#mk-ajuste-marca"], ["Chaves e contas", "#mk-ajuste-chaves"]]],
  ["prospeccao", "Prospecção", "Onde procurar clientes e o que dizer.", "cidade ramos oferta disparo",
    [["Configuração", "Configuração"], ["Mensagem", "Mensagem"], ["Fontes", "Fontes"]]],
  ["conectores", "Conectores", "Integrações com outros sistemas.", "mcp n8n navegador integracao", []],
  ["atualizacoes", "Atualizações", "Versões novas do Zé.", "versao canal atualizar",
    [["Canal", "Canal"], ["Versão", "Versão"]]],
];

/** Sem acento e em minúsculas, para a busca. @param {string} t */
const simples = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** @param {string} pagina @param {string} nome @param {string} alvo */
const ajuste = (pagina, nome, alvo) => `<li><button type="button" class="ajuste" data-acao="ajustes-ir" data-pagina="${pagina}" data-alvo="${esc(alvo)}" data-busca="${esc(simples(nome))}">${esc(nome)}${icone("chevron-right")}</button></li>`;

PAGINAS.ajustes = async () => `${cabeca("Ajustes")}${sub("Tudo o que se configura no Zé, por assunto.")}
  <div class="ajustes-hub">
    <label class="busca-ajustes">${icone("search")}<input type="search" id="ajustes-busca" placeholder="Buscar ajuste" autocomplete="off" aria-label="Buscar ajuste"></label>
    <p class="pela-voz">${icone("mic")}Pela voz: “Zé, como eu ligo o Live?”</p>
    <div class="assuntos">${ASSUNTOS.map(([pagina, titulo, descricao, palavras, ajustes]) => `<section class="cartao assunto" data-busca="${esc(simples(`${titulo} ${descricao} ${palavras}`))}">
      <button type="button" class="titulo-assunto" data-acao="ajustes-ir" data-pagina="${pagina}" data-alvo=""><span class="icone-assunto">${icone(ICONES[pagina] || "settings")}</span><span class="nome"><strong>${esc(titulo)}</strong><small>${esc(descricao)}</small></span>${icone("chevron-right")}</button>
      ${ajustes.length ? `<ul class="ajustes">${ajustes.map(([nome, alvo]) => ajuste(pagina, nome, alvo)).join("")}</ul>` : ""}
    </section>`).join("")}</div>
    <p class="vazio" id="ajustes-nada" hidden>Nenhum ajuste com esse nome.</p>
  </div>`;

/** Mostra só os assuntos e os ajustes que batem com a busca: os ajustes com o nome buscado; sem
 * nenhum, o assunto inteiro, se a busca bate nele (título, descrição ou palavras). @param {string} texto */
function filtrar(texto) {
  const q = simples(texto.trim());
  let algum = false;
  for (const a of /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll(".assunto"))) {
    const noAssunto = !q || (a.dataset.busca || "").includes(q);
    const itens = [.../** @type {NodeListOf<HTMLElement>} */ (a.querySelectorAll(".ajuste"))];
    const batem = itens.filter((b) => (b.dataset.busca || "").includes(q));
    const mostrar = !q ? itens : batem.length ? batem : noAssunto ? itens : [];
    for (const b of itens) /** @type {HTMLElement} */ (b.parentElement).hidden = !mostrar.includes(b);
    a.hidden = !noAssunto && !mostrar.length;
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
.assuntos { columns: 3 280px; column-gap: 14px; }
.assunto { display: block; break-inside: avoid; margin: 0 0 14px; padding: 0; overflow: hidden; }
.titulo-assunto { display: flex; align-items: center; gap: 12px; width: 100%; padding: 14px 14px 14px 16px; border: 0; background: none; color: inherit; text-align: left; cursor: pointer; font: inherit; transition: background .15s; }
.titulo-assunto:hover { background: rgb(255 255 255 / .025); }
.icone-assunto { display: grid; place-items: center; width: 34px; height: 34px; flex: none; border-radius: 9px; background: var(--acento-suave); color: var(--acento); }
.icone-assunto svg { width: 17px; height: 17px; }
.titulo-assunto .nome { display: grid; gap: 1px; min-width: 0; flex: 1; }
.titulo-assunto strong { font-weight: 600; font-size: 14.5px; }
.titulo-assunto small { color: var(--suave); font-size: 13px; line-height: 1.35; }
.titulo-assunto > svg { width: 16px; height: 16px; color: var(--apagado); transition: transform .2s var(--saida), color .15s; }
.titulo-assunto:hover > svg { transform: translateX(2px); color: var(--texto); }
.ajustes { list-style: none; margin: 0; padding: 6px; border-top: 1px solid var(--borda); display: grid; }
.ajuste { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; height: 34px; padding: 0 10px; border: 0; border-radius: 8px; background: none; cursor: pointer;
  font: 13.5px var(--sans); color: var(--suave); text-align: left; transition: background .15s, color .15s; }
.ajuste svg { width: 15px; height: 15px; color: var(--apagado); opacity: 0; transition: opacity .15s; }
.ajuste:hover { background: var(--realce); color: var(--texto); }
.ajuste:hover svg, .ajuste:focus-visible svg { opacity: 1; }
.destacado { animation: destacar 1.8s var(--saida); }
@keyframes destacar { 0%, 40% { box-shadow: 0 0 0 2px var(--acento); } 100% { box-shadow: 0 0 0 2px transparent; } }
` }));
