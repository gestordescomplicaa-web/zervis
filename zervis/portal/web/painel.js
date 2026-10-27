// O painel do Zé (docs/plano-painel.md). Uma página, sem framework e sem nada de fora.
// Regras de tela (09/10/2026): tudo em português; cada página tem título, no máximo uma linha
// e a ação principal; o que aparece dá para mexer; detalhe técnico fica em "Detalhes".
// Todo botão diz o que faz em data-acao; um despachante só executa. A regra mora no jarvisd.
"use strict";

const TOKEN = /** @type {HTMLMetaElement} */ (document.querySelector('meta[name="ze-token"]')).content;
const NO_PC = ["127.0.0.1", "localhost"].includes(location.hostname); // o próprio PC, não outro aparelho
// Ajustes do Zé (autodesenvolvimento): no próprio PC ou, num servidor, de um aparelho que entrou
// com o código do autenticador. Quem decide é o servidor do painel; isto só esconde a página.
const AJUSTES = /** @type {HTMLMetaElement} */ (document.querySelector('meta[name="ze-ajustes"]'))?.content === "1";
const conteudo = document.getElementById("conteudo");

const ESTADOS = { inativo: "inativo", ativo: "pronto", ouvindo: "ouvindo", pensando: "pensando", falando: "falando", confirmando: "esperando o seu sim" };
const ESTADO_SESSAO = { parada: "pronta", trabalhando: "trabalhando", erro: "erro" };
const estadoSessao = (s) => (s.limite ? "sem créditos" : ESTADO_SESSAO[s.estado] || s.estado);
const TIPO_AUTOMACAO = { lembrete: "Lembrete", pergunta: "Pergunta ao Zé" };
const NOME_MOTOR = { contas: "Automático", codex: "Codex", plano: "Claude", openai: "OpenAI API", anthropic: "Anthropic", openrouter: "OpenRouter", ponte: "Ponte", omniroute: "OmniRoute" };

/** @param {unknown} t @returns {string} */
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const seg = (ms) => (ms == null ? "—" : (ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " s");
const quando = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
/** @param {string} id @returns {HTMLElement} */
const $ = (id) => document.getElementById(id);
/** @param {string} id @returns {HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement} */
const valorCampo = (id) => /** @type {HTMLInputElement} */ ($(id));
/** @param {string} id @returns {HTMLInputElement} */
const entradaCampo = (id) => /** @type {HTMLInputElement} */ ($(id));

/** @param {string} caminho @param {Record<string, unknown>} [corpo] @param {AbortSignal} [sinal]
 * @returns {Promise<any>} */
async function api(caminho, corpo, sinal) {
  /** @type {RequestInit & {headers: Record<string, string>}} */
  const opcoes = { headers: { "X-Ze-Token": TOKEN }, signal: sinal };
  if (corpo !== undefined) {
    opcoes.method = "POST";
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  if (corpo !== undefined) { gravacoes++; cachePaginas.clear(); } // as páginas guardadas ficam velhas
  const r = await fetch("/api/" + caminho, opcoes);
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || "falha " + r.status);
  return dados;
}

let prazoToast = 0;
function toast(texto, ms = 2600) {
  let t = /** @type {HTMLElement} */ (document.querySelector(".toast"));
  if (!t) { t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status"); document.body.append(t); }
  t.textContent = texto;
  t.classList.add("on");
  clearTimeout(prazoToast);
  prazoToast = setTimeout(() => t.classList.remove("on"), ms);
}

/** @template T @param {HTMLButtonElement | null} botao @param {() => Promise<T>} trabalho @returns {Promise<T>} */
async function ocupado(botao, trabalho) {
  if (botao) botao.disabled = true;
  try { return await trabalho(); } finally { if (botao) botao.disabled = false; }
}

// --- pedaços de tela ---

const cabeca = (titulo, acoes = "") => `<div class="cabeca"><h1>${titulo}</h1>${acoes}</div>`;
const sub = (texto) => `<p class="sub">${texto}</p>`;
const cartao = (titulo, corpo, extra = "") => `<section class="cartao ${extra}">${titulo ? `<h2>${titulo}</h2>` : ""}${corpo}</section>`;
const vazio = (texto) => `<p class="vazio">${texto}</p>`;
const liga = (ligado, mudar, dados = "", rotulo = "Ligar ou desligar") =>
  `<label class="liga" title="${rotulo}"><input type="checkbox" data-mudar="${mudar}" ${dados} ${ligado ? "checked" : ""} aria-label="${rotulo}"><span></span></label>`;
const botao = (texto, acao, dados = "", classe = "") => `<button type="button" class="acao ${classe}" data-acao="${acao}" ${dados}>${texto}</button>`;
const xis = (acao, dados, rotulo) => `<button type="button" class="x" data-acao="${acao}" ${dados} aria-label="${rotulo}" title="${rotulo}">×</button>`;
const item = (titulo, detalhe, direita = "", apagado = false) =>
  `<div class="linha-item ${apagado ? "apagado" : ""}"><div class="texto">${titulo ? `<strong>${titulo}</strong>` : ""}${detalhe ? (titulo ? `<small>${detalhe}</small>` : `<span>${detalhe}</span>`) : ""}</div>${direita ? `<div class="botoes">${direita}</div>` : ""}</div>`;

// Confirmação dentro da própria tela (o navegador do painel não usa confirm()).
const pendentes = new Map();
function confirmar(el, pergunta, fazer) {
  const id = Math.random().toString(36).slice(2);
  pendentes.set(id, fazer);
  const lugar = /** @type {HTMLElement} */ (el.closest(".botoes")) || el.parentElement;
  lugar.dataset.antes = lugar.innerHTML;
  lugar.innerHTML = `<span class="confirmar">${pergunta} ${botao("Sim", "confirmar-sim", `data-id="${id}"`, "perigo")} ${botao("Não", "confirmar-nao", `data-id="${id}"`, "discreta")}</span>`;
}

// --- as páginas ---

/** @type {Record<string, () => Promise<string>>} */
const PAGINAS = {};
// O desenho da última vez de cada página: a troca de aba mostra isto na hora e se atualiza quando
// o Zé responde. Longe do servidor (VPS), cada resposta custa uma ida e volta de rede.
/** @type {Map<string, string>} */
const cachePaginas = new Map();
let gravacoes = 0; // quantas gravações já foram; uma página lida antes de uma gravação não é guardada

const ESPERAS = [["rapida", "Rápida", "Para pedidos curtos."], ["normal", "Normal", "Para a maioria das conversas."], ["longa", "Longa", "Para pensar enquanto fala."]];


function mostrar(id, ok, texto) {
  const r = $(id);
  if (!r) return;
  r.className = "resultado " + (ok === null ? "" : ok ? "ok" : "erro");
  r.textContent = texto;
}

let sessaoAberta = null;

let relogioSessoes = null;
// Cada troca de página ganha um número. Clicando rápido, a página anterior ainda espera o Zé
// quando a nova abre: ao voltar, ela não desenha, não mostra erro e não liga relógio.
let navegacao = 0;

/** O relógio da página aberta (1,5 s); de uma navegação já trocada, não liga.
 * @param {number} vez @param {() => unknown} volta */
function relogio(vez, volta) {
  if (vez !== navegacao) return;
  clearInterval(relogioSessoes);
  relogioSessoes = setInterval(volta, 1500);
}

let buscaPendente = null;

const encher = () => /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll("[data-cheio]")).forEach((b) => b.style.setProperty("--cheio", b.dataset.cheio + "%"));

function escolha(nome, rotulo, grupos, atual, titulo) {
  const itens = grupos.map((g) => (g.titulo ? `<div class="escolha-grupo">${esc(g.titulo)}</div>` : "") + g.itens.map((i) =>
    `<button type="button" role="option" class="escolha-item" data-acao="escolha-item" data-valor="${esc(i.valor)}" aria-selected="${i.valor === atual}">
      <span class="marca-escolha">${i.valor === atual ? "✓" : ""}</span><span class="texto-escolha"><strong>${esc(i.nome)}</strong>${i.detalhe ? `<small>${esc(i.detalhe)}</small>` : ""}</span></button>`).join("")).join("");
  return `<div class="escolha" data-escolha="${esc(nome)}">
    <button type="button" class="escolha-botao" data-acao="escolha-abrir" aria-haspopup="listbox" aria-expanded="false" title="${esc(titulo)}">${esc(rotulo)}<span class="seta" aria-hidden="true">▾</span></button>
    <div class="escolha-menu" role="listbox" aria-label="${esc(titulo)}" hidden>${itens}</div></div>`;
}

function fecharEscolhas(exceto) {
  /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll(".escolha-menu:not([hidden])")).forEach((m) => {
    if (m === exceto) return;
    m.hidden = true;
    m.previousElementSibling.setAttribute("aria-expanded", "false");
  });
}

let term = null, termId = null, termPos = 0, termObservador = null, filaEscrita = Promise.resolve();
let termWs = null, termWsPronto = false, filaTerminalWs = [], prazoTerminalWs = null;
// Cancela a leitura do terminal aberto. A leitura espera novidade por até 20 s; sem cancelar, cada
// troca de aba deixava uma presa, e seis presas esgotam as conexões do navegador com o painel.
/** @type {AbortController | null} */
let termParar = null;

function fecharTerminalTela() {
  termParar?.abort();
  termParar = null;
  termId = null;
  clearTimeout(prazoTerminalWs);
  prazoTerminalWs = null;
  const ws = termWs;
  termWs = null;
  termWsPronto = false;
  filaTerminalWs = [];
  ws?.close();
  termObservador?.disconnect();
  termObservador = null;
  term?.dispose();
  term = null;
}
