import { ACOES } from "../modulos/acoes.js";
import { $, api, botao, cartao, esc, item, mostrar, ocupado, sub } from "../painel.js";

// --- Comentários do Instagram (ADR 0118): todo comentário vira conversa no direct ---------------

/** @param {number} quando segundos @returns {string} */
const hora = (quando) => new Date(quando * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

/** @param {any} x */
const resultado = (x) => x.erro ? `Erro · ${esc(x.erro)}`
  : `${x.publico ? "Respondido" : ""}${x.publico && x.direct ? " · " : ""}${x.direct ? "Direct enviado" : x.publico ? " · Já recebeu direct recentemente" : ""}`;

/** O cartão Comentários do Instagram. @param {any} r a leitura "marketing" */
export function cartaoComentarios(r) {
  const c = r.comentarios || { ligado: false, conectado: false, recentes: [], contatos: 0 };
  return `<div id="mk-comentarios">${cartao(`Comentários do Instagram <span class="etiqueta ${c.ligado ? "bom" : ""}">${c.ligado ? "Ligado" : "Desligado"}</span>`,
    `${sub("Cada comentário recebe uma resposta e uma mensagem no direct que puxa a conversa sobre o negócio da pessoa.")}
    ${!c.conectado ? `<p class="nota">Conecte o Instagram em Redes sociais.</p>` : ""}
    ${c.recentes.length ? `<div class="itens">${c.recentes.map((/** @type {any} */ x) => item(`@${esc(x.autor)} · ${esc(String(x.texto || "").slice(0, 60))}`, `${hora(x.quando)} · ${resultado(x)}`, "")).join("")}</div>` : ""}
    <div class="linha">${c.ligado ? botao("Desligar", "mk-comentarios", `data-ligado="0"`, "discreta") : botao("Ligar", "mk-comentarios", `data-ligado="1"${c.conectado ? "" : " disabled"}`, "principal")}${c.contatos ? `<span class="nota">${c.contatos} ${c.contatos === 1 ? "pessoa recebeu" : "pessoas receberam"} mensagem</span>` : ""}</div>
    <p class="resultado" id="mk-resultado-comentarios"></p>`)}</div>`;
}

Object.assign(ACOES, {
  "mk-comentarios": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/instagram/comentarios", { ligado: b.dataset.ligado === "1" }));
      const novo = document.createElement("div");
      novo.innerHTML = cartaoComentarios(r);
      $("mk-comentarios")?.replaceWith(/** @type {Element} */ (novo.firstElementChild));
      mostrar("mk-resultado-comentarios", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-comentarios", false, erro.message); }
  },
});
