import { ACOES } from "../modulos/acoes.js";
import { PAGINAS, $, api, botao, cabeca, cartao, confirmar, esc, item, mostrar, ocupado, sub, vazio } from "../painel.js";

// As empresas que quem usa gere (ADR 0105): o grupo de WhatsApp de cada uma, a pasta do projeto e
// a vitrine (o que foi publicado para ela). Nesta etapa só o cadastro: nada é enviado aos grupos.

/** @type {{empresas: any[], pastas: string[]}} */
let ultimo = { empresas: [], pastas: [] };
/** @type {any[] | null} */
let grupos = null;
/** A empresa em edição ("" = nova), ou null com o formulário fechado. @type {string | null} */
let editando = null;

/** @param {any} e */
const estado = (e) => !e.grupo ? ["Sem grupo", ""] : e.ligada ? ["Ligada", "bom"] : ["Desligada", ""];

/** @param {any} e */
function linhaEmpresa(e) {
  const [rotulo, classe] = estado(e);
  const detalhes = [
    e.grupo ? `Grupo: ${esc(e.grupo_nome || e.grupo)}` : "Nenhum grupo ligado",
    e.pasta ? `Projeto: ${esc(e.pasta)}` : "",
    `Vitrine: ${e.publicados} ${e.publicados === 1 ? "arquivo" : "arquivos"}`,
  ].filter(Boolean).join(" · ");
  const botoes = botao("Editar", "empresa-editar", `data-id="${esc(e.id)}"`, "discreta") + botao("Remover", "empresa-remover", `data-id="${esc(e.id)}"`, "discreta");
  return item(`${esc(e.nome)} <span class="etiqueta ${classe}">${rotulo}</span>`, detalhes, botoes);
}

function formulario() {
  const e = ultimo.empresas.find((x) => x.id === editando) || { nome: "", grupo: "", grupo_nome: "", pasta: "", ligada: false };
  const opcoesGrupo = grupos === null
    ? `<option value="${esc(e.grupo)}">${esc(e.grupo_nome || (e.grupo ? e.grupo : "Carregando grupos…"))}</option>`
    : `<option value="">Nenhum</option>${grupos.map((g) => {
      const outra = g.empresa && g.chat !== e.grupo;
      return `<option value="${esc(g.chat)}" data-nome="${esc(g.nome)}" ${g.chat === e.grupo ? "selected" : ""} ${outra ? "disabled" : ""}>${esc(g.nome || g.chat)} (${g.participantes})${outra ? ` · ${esc(g.empresa)}` : ""}</option>`;
    }).join("")}`;
  const pastas = [...new Set([e.pasta, ...ultimo.pastas].filter(Boolean))];
  return cartao(editando ? "Editar empresa" : "Nova empresa", `
  <div class="campos">
    <label>Nome<input id="empresa-nome" value="${esc(e.nome)}" maxlength="60" autocomplete="off"></label>
    <label>Grupo do WhatsApp<select id="empresa-grupo">${opcoesGrupo}</select></label>
    <label>Projeto<select id="empresa-pasta"><option value="">Nenhum</option>${pastas.map((p) => `<option value="${esc(p)}" ${p === e.pasta ? "selected" : ""}>${esc(p)}</option>`).join("")}</select></label>
    <label class="interruptor"><input type="checkbox" id="empresa-ligada" ${e.ligada ? "checked" : ""}> Ligada</label>
  </div>
  ${sub("O grupo lista os grupos em que o número do Zé está. Ligada: a empresa entra nos relatórios e nas respostas do grupo, quando existirem.")}
  <div class="linha">${botao("Salvar", "empresa-salvar", "", "principal")}${botao("Cancelar", "empresa-cancelar", "", "discreta")}</div>
  <p class="resultado" id="resultado-empresa"></p>`);
}

function desenhar() {
  const lugar = $("empresas");
  if (!lugar) return;
  const lista = ultimo.empresas.length ? ultimo.empresas.map(linhaEmpresa).join("") : vazio("Nenhuma empresa cadastrada.");
  lugar.innerHTML = (editando === null ? "" : formulario()) + cartao("", `<div class="lista">${lista}</div>`);
}

/** Os grupos do número do Zé, uma vez por abertura do formulário. */
async function carregarGrupos() {
  try {
    grupos = (await api("empresas/grupos", {})).grupos;
    desenhar();
  } catch (erro) {
    grupos = [];
    desenhar();
    mostrar("resultado-empresa", false, erro.message);
  }
}

/** @param {string} id */
function abrir(id) {
  editando = id;
  grupos = null;
  desenhar();
  $("empresa-nome")?.focus();
  carregarGrupos();
}

PAGINAS.empresas = async () => {
  ultimo = await api("empresas");
  editando = null;
  return `${cabeca("Empresas", botao("Adicionar empresa", "empresa-nova", "", "principal"))}${sub("As empresas que você gere e o grupo de WhatsApp de cada uma.")}<div id="empresas">${cartao("", `<div class="lista">${ultimo.empresas.length ? ultimo.empresas.map(linhaEmpresa).join("") : vazio("Nenhuma empresa cadastrada.")}</div>`)}</div>`;
};

Object.assign(ACOES, {
  "empresa-nova": () => abrir(""),
  "empresa-editar": (/** @type {HTMLButtonElement} */ b) => abrir(b.dataset.id || ""),
  "empresa-cancelar": () => { editando = null; desenhar(); },
  "empresa-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const grupo = /** @type {HTMLSelectElement} */ ($("empresa-grupo"));
    const escolhido = grupo.selectedOptions[0];
    const dados = {
      id: editando || "",
      nome: /** @type {HTMLInputElement} */ ($("empresa-nome")).value,
      grupo: grupo.value,
      grupo_nome: escolhido?.dataset.nome || escolhido?.textContent || "",
      pasta: /** @type {HTMLSelectElement} */ ($("empresa-pasta")).value,
      ligada: /** @type {HTMLInputElement} */ ($("empresa-ligada")).checked,
    };
    try {
      ultimo = await ocupado(b, () => api("empresas/salvar", dados));
      editando = null;
      desenhar();
    } catch (erro) { mostrar("resultado-empresa", false, erro.message); }
  },
  "empresa-remover": (/** @type {HTMLButtonElement} */ b) => confirmar(b, "Remover do cadastro?", async () => {
    ultimo = await api("empresas/remover", { id: b.dataset.id });
    if (editando === b.dataset.id) editando = null;
    desenhar();
  }),
});
