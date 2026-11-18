import { $, api, botao, cartao, esc, item, liga, toast } from "../painel.js";
import { ACOES, MUDAR, recarregar } from "./acoes.js";

// A conversa com o Zé pelo WhatsApp (ADR 0102): o número conectado é o do Zé, e só o seu número,
// autorizado aqui, fala com ele como você. Carregado com a página Redes sociais.

/** @param {{ligado: boolean, numero: string}} c */
export function cartaoConversa(c = { ligado: false, numero: "" }) {
  return cartao("", `<div class="cabeca"><h2>Conversa com o Zé</h2></div>
    ${item("Conversa pelo WhatsApp", "Mensagens do seu número para o número conectado vão ao Zé.", liga(c.ligado, "conversa-ze", "", "Conversa pelo WhatsApp"))}
    <div class="linha"><label>Seu número<input type="tel" id="conversa-numero" class="mono" inputmode="numeric" placeholder="5511999990000" autocomplete="off" value="${esc(c.numero)}"></label>
      <div class="botoes">${botao("Salvar", "conversa-ze-salvar", "", "principal")}</div></div>`);
}

/** @param {boolean} ligar */
async function salvarConversa(ligar) {
  const campo = /** @type {HTMLInputElement | null} */ ($("conversa-numero"));
  const r = await api("whatsapp/conversa", { ligar, numero: campo?.value || "" });
  toast(r.aviso);
  await recarregar();
}

Object.assign(MUDAR, { "conversa-ze": (/** @type {HTMLInputElement} */ el) => salvarConversa(el.checked) });
Object.assign(ACOES, {
  "conversa-ze-salvar": () => {
    const chave = /** @type {HTMLInputElement | null} */ (document.querySelector('[data-mudar="conversa-ze"]'));
    return salvarConversa(Boolean(chave?.checked));
  },
});
