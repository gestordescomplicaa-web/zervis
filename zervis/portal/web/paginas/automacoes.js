import { ACOES } from "../modulos/acoes.js";
import { PAGINAS, $, api, botao, cabeca, esc, item, liga, mostrar, ocupado, quando, sub, toast, vazio, xis } from "../painel.js";

// As Automações (ADR 0141): tudo o que roda sozinho, de lembretes ao marketing, num lugar só. Cada
// uma abre em "Editar": o nome, quando roda e o que ela faz (os temas, a duração, publicar sozinho).
// Criar é pela voz; mudar, por aqui ou pela voz.

/** @type {any[]} */
let lista = [];
/** @type {string | null} */
let editando = null;

const DIAS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const MODOS = [["semana", "Dias da semana"], ["uma_vez", "Uma vez"], ["intervalo", "Intervalo"]];
const UNIDADES = [["m", "minutos"], ["h", "horas"], ["d", "dias"]];

const dois = (/** @type {number} */ n) => String(n).padStart(2, "0");
/** @param {Date} d */
const dataLocal = (d) => `${d.getFullYear()}-${dois(d.getMonth() + 1)}-${dois(d.getDate())}`;

/** @param {string} id @param {string} rotulo @param {boolean} ligado @param {string} dados */
const segmento = (id, rotulo, ligado, dados) => `<button type="button" data-acao="${id}" ${dados} aria-pressed="${ligado}">${rotulo}</button>`;

/** O "quando" do formulário: os dias e a hora, uma data, ou o intervalo. @param {any} j */
function quandoDe(j) {
  const q = j.quando || { modo: "outra" };
  const prox = j.proxima ? new Date(j.proxima) : null;
  const hora = q.hora || (prox ? `${dois(prox.getHours())}:${dois(prox.getMinutes())}` : "09:00");
  const modo = q.modo;
  const dias = q.dias || [];
  return `<div class="largo ae-quando">
    <span class="ae-rotulo">Quando</span>
    <div class="segmentos" role="group" aria-label="Quando">${modo === "outra" ? segmento("ae-modo", "Personalizada", true, 'data-modo="outra"') : ""}${MODOS.map(([m, n]) => segmento("ae-modo", n, m === modo, `data-modo="${m}"`)).join("")}</div>
    <div class="linha" data-modo-campos="semana" ${modo === "semana" ? "" : "hidden"}>
      <div class="segmentos" role="group" aria-label="Dias">${DIAS.map((n, d) => segmento("ae-dia", n, dias.includes(d), `data-dia="${d}"`)).join("")}</div>
      <label class="ae-curto">Hora<input type="time" id="ae-hora" value="${esc(hora)}"></label>
    </div>
    <div class="linha" data-modo-campos="uma_vez" ${modo === "uma_vez" ? "" : "hidden"}>
      <label class="ae-curto">Data<input type="date" id="ae-data" value="${prox ? dataLocal(prox) : ""}"></label>
      <label class="ae-curto">Hora<input type="time" id="ae-hora-unica" value="${esc(hora)}"></label>
    </div>
    <div class="linha" data-modo-campos="intervalo" ${modo === "intervalo" ? "" : "hidden"}>
      <label class="ae-curto">A cada<input type="number" id="ae-quantos" min="1" value="${esc(q.quantos || 1)}"></label>
      <label class="ae-curto">Unidade<select id="ae-unidade">${UNIDADES.map(([u, n]) => `<option value="${u}" ${u === (q.unidade || "h") ? "selected" : ""}>${n}</option>`).join("")}</select></label>
    </div>
  </div>`;
}

/** Os campos do tipo: o texto, o tema, os temas, a duração e publicar sozinho. @param {any} j */
function parametros(j) {
  const p = j.parametros || {};
  const campos = [];
  if ("texto" in p) campos.push(`<label class="largo">${j.tipo === "pergunta" ? "Pergunta" : "Texto"}<textarea id="ae-texto" rows="3" maxlength="600">${esc(p.texto)}</textarea></label>`);
  if ("tema" in p) campos.push(`<label class="largo">Tema<input id="ae-tema" value="${esc(p.tema)}" maxlength="120" placeholder="Opcional" autocomplete="off"></label>`);
  if ("temas" in p) campos.push(`<label class="largo">Temas<textarea id="ae-temas" rows="4" placeholder="Um por linha. Opcional.">${esc((p.temas || []).join("\n"))}</textarea></label>`);
  if ("duracao" in p) campos.push(`<label class="ae-curto">Duração<select id="ae-duracao">${(j.duracoes || [p.duracao]).map((/** @type {number} */ d) => `<option value="${d}" ${d === p.duracao ? "selected" : ""}>${d} s</option>`).join("")}</select></label>`);
  if ("publicar" in p) campos.push(`<label class="interruptor"><input type="checkbox" id="ae-publicar" ${p.publicar ? "checked" : ""}> Publicar sozinho</label>`);
  return campos.join("");
}

/** @param {any} j */
const formulario = (j) => `<div class="ae-form">
  <div class="campos">
    <label class="largo">Nome<input id="ae-nome" value="${esc(j.nome)}" maxlength="60" autocomplete="off"></label>
    ${quandoDe(j)}
    ${parametros(j)}
  </div>
  <div class="linha">${botao("Salvar", "ae-salvar", `data-id="${esc(j.id)}"`, "principal")}${botao("Cancelar", "ae-editar", `data-id="${esc(j.id)}"`, "discreta")}</div>
  <p class="resultado" id="ae-resultado"></p>
</div>`;

/** @param {any} j */
function linha(j) {
  const p = j.parametros || {};
  const titulo = `${esc(j.nome)} <span class="etiqueta">${esc(j.tipo_nome || j.tipo)}</span>${p.publicar ? ' <span class="etiqueta bom">Publica sozinho</span>' : ""}`;
  const detalhe = `${esc(j.agenda_frase || j.agenda)} · ${j.ativo ? `Próxima: ${quando(j.proxima)}` : "Pausada"}`;
  const aberto = editando === j.id;
  const direita = botao(aberto ? "Fechar" : "Editar", "ae-editar", `data-id="${esc(j.id)}" aria-expanded="${aberto}"`, "discreta")
    + liga(j.ativo, "automacao", `data-id="${esc(j.id)}"`, "Ativa") + xis("automacao-remover", `data-id="${esc(j.id)}"`, "Remover");
  return `<div class="automacao${aberto ? " aberta" : ""}">${item(titulo, detalhe, direita, !j.ativo)}${aberto ? formulario(j) : ""}</div>`;
}

const corpo = () => (lista.length ? `<div class="itens">${lista.map(linha).join("")}</div>` : vazio("Nada agendado."));

function desenhar() {
  const lugar = $("automacoes-lista");
  if (lugar) lugar.innerHTML = corpo();
}

PAGINAS.automacoes = async function() {
  lista = await api("automacoes");
  if (editando && !lista.some((j) => j.id === editando)) editando = null;
  return `${cabeca("Automações")}${sub("Tudo o que roda sozinho, na agenda. Para criar, peça ao Zé.")}<div id="automacoes-lista">${corpo()}</div>`;
};

/** O que o formulário diz, só com os campos que existem. @param {any} j */
function lido(j) {
  const valor = (/** @type {string} */ id) => /** @type {HTMLInputElement | null} */ ($(id))?.value;
  const modo = /** @type {HTMLElement | null} */ (document.querySelector('.ae-quando [data-acao="ae-modo"][aria-pressed="true"]'))?.dataset.modo || "outra";
  /** @type {any} */
  const dados = { id: j.id, nome: valor("ae-nome") };
  if (modo === "semana") {
    const dias = [...document.querySelectorAll('.ae-quando [data-acao="ae-dia"][aria-pressed="true"]')].map((b) => Number(/** @type {HTMLElement} */ (b).dataset.dia));
    dados.quando = { modo, dias, hora: valor("ae-hora") };
  } else if (modo === "uma_vez") dados.quando = { modo, data: valor("ae-data"), hora: valor("ae-hora-unica") };
  else if (modo === "intervalo") dados.quando = { modo, quantos: Number(valor("ae-quantos")), unidade: valor("ae-unidade") };
  const p = j.parametros || {};
  /** @type {any} */
  const novos = {};
  if ("texto" in p) novos.texto = valor("ae-texto");
  if ("tema" in p) novos.tema = valor("ae-tema");
  if ("temas" in p) novos.temas = valor("ae-temas");
  if ("duracao" in p) novos.duracao = Number(valor("ae-duracao"));
  if ("publicar" in p) novos.publicar = /** @type {HTMLInputElement} */ ($("ae-publicar")).checked;
  if (Object.keys(novos).length) dados.parametros = novos;
  return dados;
}

Object.assign(ACOES, {
  "ae-editar": (/** @type {HTMLButtonElement} */ b) => { editando = editando === b.dataset.id ? null : b.dataset.id || null; desenhar(); },
  "ae-modo": (/** @type {HTMLButtonElement} */ b) => {
    const quando = /** @type {HTMLElement} */ (b.closest(".ae-quando"));
    quando.querySelectorAll('[data-acao="ae-modo"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    quando.querySelectorAll("[data-modo-campos]").forEach((x) => { /** @type {HTMLElement} */ (x).hidden = /** @type {HTMLElement} */ (x).dataset.modoCampos !== b.dataset.modo; });
  },
  "ae-dia": (/** @type {HTMLButtonElement} */ b) => b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true")),
  "ae-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const j = lista.find((x) => x.id === b.dataset.id);
    if (!j) return;
    try {
      lista = await ocupado(b, () => api("automacao/editar", lido(j)));
      editando = null;
      desenhar();
      toast("Salvo.");
    } catch (erro) { mostrar("ae-resultado", false, erro.message); }
  },
});
