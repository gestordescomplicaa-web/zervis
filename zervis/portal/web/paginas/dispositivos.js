import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { PAGINAS, api, botao, cabeca, cartao, esc, sub, vazio } from "../painel.js";

// A seção Dispositivos (ADR 0089): os aparelhos da casa num lugar só. Quem não tem nenhum vê só
// "Adicionar dispositivo"; cada aparelho abre a página dele (câmera, impressora, TV).

let adicionando = false;

/** @param {any} d */
const aparelho = (d) => cartao(`${esc(d.nome)} <span class="etiqueta ${d.bom ? "bom" : ""}">${esc(d.estado)}</span>`,
  `${d.detalhe ? sub(`<span class="mono">${esc(d.detalhe)}</span>`) : ""}
  <div class="botoes">${botao("Abrir", "dispositivo-abrir", `data-id="${esc(d.id)}"`, "discreta")}</div>`);

/** @param {any[]} tipos */
const adicionar = (tipos) => cartao("Adicionar dispositivo", tipos.length
  ? `<div class="itens">${tipos.map((t) => `<div class="linha-item">
      <div class="texto"><strong>${esc(t.nome)}</strong><small>${esc(t.descricao)}</small></div>
      ${botao("Adicionar", "dispositivo-abrir", `data-id="${esc(t.id)}"`, "discreta")}
    </div>`).join("")}</div>`
  : vazio("Todos os tipos disponíveis já estão adicionados."));

PAGINAS.dispositivos = async () => {
  const r = await api("dispositivos");
  const lista = r.dispositivos.map(aparelho).join("");
  const acao = botao(adicionando ? "Cancelar" : "Adicionar dispositivo", "dispositivo-adicionar", "", adicionando ? "discreta" : "principal");
  return `${cabeca("Dispositivos", acao)}${sub("Aparelhos da casa que o Zé usa pela rede local.")}
    ${adicionando ? adicionar(r.tipos) : ""}${lista || (adicionando ? "" : cartao("", vazio("Nenhum dispositivo adicionado.")))}`;
};

Object.assign(ACOES, {
  "dispositivo-adicionar": async () => { adicionando = !adicionando; await abrir(); },
  "dispositivo-abrir": (/** @type {HTMLButtonElement} */ b) => { adicionando = false; location.hash = `#${b.dataset.id}`; },
});
