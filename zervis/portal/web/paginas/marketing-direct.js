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
    <p class="resultado" id="mk-resultado-comentarios"></p>
    ${conversa(c.direct || { ligado: false, link: "", como: "", contatos: [] })}`)}</div>`;
}

/** A conversa no direct (ADR 0119): o link, o como conversar e os contatos. @param {any} d */
const conversa = (d) => `<h3 class="subtitulo">Conversa no direct <span class="etiqueta ${d.ligado ? "bom" : ""}">${d.ligado ? "Ligada" : "Desligada"}</span></h3>
    ${sub("Quando a pessoa responde, o Zé entende o negócio dela e manda o link para ela marcar a reunião.")}
    <div class="campos">
      <label class="largo">Link de agendamento<input id="mk-direct-link" value="${esc(d.link)}" placeholder="https://calendar.app.google/..." autocomplete="off"></label>
      <label class="largo">Como conversar<textarea id="mk-direct-como" rows="7">${esc(d.como)}</textarea></label>
      <label class="interruptor"><input type="checkbox" id="mk-direct-ligado" ${d.ligado ? "checked" : ""}> Conversar no direct</label>
    </div>
    <div class="linha">${botao("Salvar", "mk-direct-salvar", "", "principal")}</div>
    <p class="resultado" id="mk-resultado-direct"></p>
    ${d.contatos.length ? `<div class="itens">${d.contatos.map((/** @type {any} */ x) => item(`@${esc(x.usuario)} · ${esc(x.etapa || "")}`,
      esc(x.pausado ? `Com você: ${x.motivo || ""}` : (x.resumo || `${x.respostas || 0} resposta(s)`)),
      x.pausado ? botao("Devolver ao Zé", "mk-direct-devolver", `data-usuario="${esc(x.usuario)}"`, "discreta") : "")).join("")}</div>` : ""}`;

/** Redesenha o cartão com a leitura nova. @param {any} r */
function redesenhar(r) {
  const novo = document.createElement("div");
  novo.innerHTML = cartaoComentarios(r);
  $("mk-comentarios")?.replaceWith(/** @type {Element} */ (novo.firstElementChild));
}

Object.assign(ACOES, {
  "mk-direct-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = {
      ligado: /** @type {HTMLInputElement} */ ($("mk-direct-ligado")).checked,
      link: /** @type {HTMLInputElement} */ ($("mk-direct-link")).value,
      como: /** @type {HTMLTextAreaElement} */ ($("mk-direct-como")).value,
    };
    try {
      const r = await ocupado(b, () => api("marketing/instagram/direct", dados));
      redesenhar(r);
      mostrar("mk-resultado-direct", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-direct", false, erro.message); }
  },
  "mk-direct-devolver": async (/** @type {HTMLButtonElement} */ b) => {
    try { redesenhar(await ocupado(b, () => api("marketing/instagram/direct/devolver", { usuario: b.dataset.usuario }))); }
    catch (erro) { mostrar("mk-resultado-direct", false, erro.message); }
  },
  "mk-comentarios": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/instagram/comentarios", { ligado: b.dataset.ligado === "1" }));
      redesenhar(r);
      mostrar("mk-resultado-comentarios", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-comentarios", false, erro.message); }
  },
});
