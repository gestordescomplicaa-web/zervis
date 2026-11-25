// A casca do painel (docs/plano-design.md): ícones do menu (icones/lucide.svg), recolher o menu,
// o título da página no topo e o estado do Zé por escrito ao lado do anel.
import { ESTADOS } from "../painel.js";

const SPRITE = "/icones/lucide.svg";
/** @type {Record<string, string>} */
const ICONES = {
  inicio: "house", conversa: "message-square", imersao: "scan-face", sessoes: "terminal", foco: "target",
  automacoes: "repeat", pesquisas: "search", projetos3d: "box", prospeccao: "trending-up", empresas: "building-2",
  atendimento: "message-circle", marketing: "megaphone", dispositivos: "monitor-smartphone", memoria: "brain",
  skills: "puzzle", conectores: "plug", atividade: "activity", melhorias: "wrench", perfil: "user",
  modelos: "cpu", voz: "audio-lines", atualizacoes: "download",
};
// Páginas abertas por dentro de outra (o aparelho em Dispositivos) e as que não estão no menu.
/** @type {Record<string, [string, string]>} */
const DENTRO = { camera: ["dispositivos", "Câmera"], impressora: ["dispositivos", "Impressora"], tv: ["dispositivos", "TV"] };
/** @type {Record<string, string>} */
const FORA_DO_MENU = { configurar: "Configuração inicial" };
const RECOLHIDO = "ze.menu-recolhido";

/** @param {string} nome */
export const icone = (nome) => `<svg class="i" aria-hidden="true"><use href="${SPRITE}#${nome}"/></svg>`;

/** O rótulo de um item do menu (sem o ponto de novidade). @param {string} secao */
function rotulo(secao) {
  return document.querySelector(`nav a[data-secao="${secao}"] .rotulo`)?.textContent?.trim() || "";
}

function prepararMenu() {
  /** @type {NodeListOf<HTMLAnchorElement>} */ (document.querySelectorAll("nav a[data-secao]")).forEach((a) => {
    const simbolo = a.querySelector(":scope > i");
    if (simbolo) simbolo.outerHTML = icone(ICONES[a.dataset.secao || ""] || "chevron-right");
    const texto = [...a.childNodes].find((n) => n.nodeType === Node.TEXT_NODE && n.textContent?.trim());
    if (texto) {
      const span = document.createElement("span");
      span.className = "rotulo";
      span.textContent = texto.textContent?.trim() || "";
      texto.replaceWith(span);
      a.title = span.textContent;
    }
  });
}

/** @param {boolean} recolher */
function aplicarRecolhido(recolher) {
  document.body.classList.toggle("menu-recolhido", recolher);
  const botao = document.querySelector(".recolher");
  botao?.setAttribute("aria-expanded", String(!recolher));
  botao?.setAttribute("aria-label", recolher ? "Abrir o menu" : "Recolher o menu");
  botao?.querySelector("use")?.setAttribute("href", `${SPRITE}#${recolher ? "panel-left-open" : "panel-left-close"}`);
}

export function alternarRecolhido() {
  const recolher = !document.body.classList.contains("menu-recolhido");
  aplicarRecolhido(recolher);
  try { localStorage.setItem(RECOLHIDO, recolher ? "1" : ""); } catch { /* sem armazenamento: vale só agora */ }
}

/** O título da página na barra do topo, com o caminho quando ela abre dentro de outra. */
function mostrarTrilha() {
  const trilha = document.getElementById("trilha");
  if (!trilha) return;
  const nome = (location.hash || "#inicio").slice(1);
  const [pai, filho] = DENTRO[nome] || [nome, ""];
  const titulo = rotulo(pai) || FORA_DO_MENU[nome] || "";
  trilha.innerHTML = filho
    ? `<a href="#${pai}">${titulo}</a>${icone("chevron-right")}<strong>${filho}</strong>`
    : `<strong>${titulo}</strong>`;
}

/** "Pronto", "Ouvindo"…: o estado que o batimento escreve no anel, por escrito ao lado dele. */
function seguirEstado() {
  const anel = /** @type {HTMLElement | null} */ (document.querySelector(".topo .icone-ze"));
  const texto = document.getElementById("estado-ze");
  if (!anel || !texto) return;
  const escrever = () => {
    const estado = ESTADOS[/** @type {keyof typeof ESTADOS} */ (anel.dataset.estado || "inativo")] || "inativo";
    texto.textContent = estado.charAt(0).toUpperCase() + estado.slice(1);
  };
  new MutationObserver(escrever).observe(anel, { attributes: true, attributeFilter: ["data-estado"] });
  escrever();
}

prepararMenu();
try { aplicarRecolhido(localStorage.getItem(RECOLHIDO) === "1"); } catch { /* sem armazenamento */ }
window.addEventListener("hashchange", mostrarTrilha);
mostrarTrilha();
seguirEstado();
