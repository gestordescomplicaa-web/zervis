import { ACOES, MUDAR } from "../modulos/acoes.js";
import { $, api, botao, cartao, esc, item, mostrar, ocupado, sub } from "../painel.js";

// --- Comentários do Instagram (ADR 0118): todo comentário vira conversa no direct ---------------

/** @param {number} quando segundos @returns {string} */
const hora = (quando) => new Date(quando * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

/** O cartão Comentários do Instagram. @param {any} r a leitura "marketing" */
export function cartaoComentarios(r) {
  const c = r.comentarios || { ligado: false, conectado: false, recentes: [], contatos: 0 };
  return `<div id="mk-comentarios">${cartao(`Comentários do Instagram <span class="etiqueta ${c.ligado ? "bom" : ""}">${c.ligado ? "Ligado" : "Desligado"}</span>`,
    `${sub("Cada comentário recebe uma resposta e uma mensagem no direct que puxa a conversa sobre o negócio da pessoa.")}
    ${!c.conectado ? `<p class="nota">Conecte o Instagram em Redes sociais.</p>` : ""}
    <div class="linha">${c.ligado ? botao("Desligar", "mk-comentarios", `data-ligado="0"`, "discreta") : botao("Ligar", "mk-comentarios", `data-ligado="1"${c.conectado ? "" : " disabled"}`, "principal")}${c.contatos ? `<span class="nota">${c.contatos} ${c.contatos === 1 ? "pessoa recebeu" : "pessoas receberam"} mensagem</span>` : ""}</div>
    <p class="resultado" id="mk-resultado-comentarios"></p>
    ${ignoradas(c.ignoradas || [])}
    ${avisos(c.avisos || { configurado: false, recebendo: false, endereco: "", verificacao: "", recusados: 0, ultimo: 0 })}
    ${conversa(c.direct || { ligado: false, link: "", como: "", contatos: [] })}`)}</div>`;
}

/** As contas que nunca recebem resposta automática. @param {string[]} contas */
const ignoradas = (contas) => `<h3 class="subtitulo">Contas ignoradas</h3>
    ${sub("Comentários e mensagens dessas contas não recebem resposta automática.")}
    <div class="campos"><label class="largo">Contas<textarea id="mk-ignoradas" rows="3" placeholder="@usuario, uma por linha">${esc(contas.map((u) => `@${u}`).join("\n"))}</textarea></label></div>
    <div class="linha">${botao("Salvar", "mk-ignoradas-salvar", "", "principal")}</div>
    <p class="resultado" id="mk-resultado-ignoradas"></p>`;

/** Os avisos na hora (ADR 0122): o endereço e o token para o painel de apps da Meta e a chave
 * secreta do app. @param {any} a */
const avisos = (a) => {
  const estado = a.recebendo ? ["bom", "Recebendo"] : a.configurado ? ["", "Aguardando o primeiro aviso"] : ["", "Não configurado"];
  return `<h3 class="subtitulo">Resposta na hora <span class="etiqueta ${estado[0]}">${estado[1]}</span></h3>
    ${sub("Recebe cada comentário e mensagem no momento em que é feito, pelos webhooks da Meta.")}
    ${a.endereco ? `<div class="campos">
      <label class="largo">URL de retorno<input readonly value="${esc(a.endereco)}"></label>
      <label class="largo">Token de verificação<input readonly value="${esc(a.verificacao)}"></label>
      <label class="largo">Chave secreta do app<input id="mk-avisos-segredo" type="password" autocomplete="off" placeholder="${a.configurado ? "Salva" : ""}"></label>
    </div>
    <div class="linha">${botao("Salvar", "mk-avisos-salvar", "", "principal")}${a.configurado ? botao("Remover", "mk-avisos-remover", "", "discreta") : ""}${a.recebendo ? `<span class="nota">Último aviso ${hora(a.ultimo)}</span>` : ""}${a.recusados ? `<span class="nota">${a.recusados} aviso(s) recusado(s): confira a chave</span>` : ""}</div>`
    : `<p class="nota">Ative o acesso de qualquer lugar com endereço fixo.</p>`}
    <p class="resultado" id="mk-resultado-avisos"></p>`;
};

/** A conversa no direct (ADR 0119): o link, o como conversar e os contatos. @param {any} d */
const conversa = (d) => `<h3 class="subtitulo">Conversa no direct <span class="etiqueta ${d.ligado ? "bom" : ""}">${d.ligado ? "Ligada" : "Desligada"}</span></h3>
    ${sub("Quando a pessoa responde, o Zé entende o negócio dela e manda o link para ela marcar a reunião.")}
    <div class="campos">
      <label class="largo">Link de agendamento<input id="mk-direct-link" data-mudar="direct-ajuste" value="${esc(d.link)}" placeholder="https://calendar.app.google/..." autocomplete="off"></label>
      <label class="largo">Como conversar<textarea id="mk-direct-como" data-mudar="direct-ajuste" rows="7">${esc(d.como)}</textarea></label>
      <label class="interruptor"><input type="checkbox" id="mk-direct-ligado" data-mudar="direct-ajuste" ${d.ligado ? "checked" : ""}> Conversar no direct</label>
    </div>
    <div class="linha">${botao("Salvar", "mk-direct-salvar", "", "principal")}</div>
    <p class="resultado" id="mk-resultado-direct"></p>
    ${comVoce(d.contatos)}`;

/** Só as conversas que o Zé passou para você: o resto fica no direct, não na tela.
 * @param {any[]} contatos */
const comVoce = (contatos) => {
  const pausados = contatos.filter((x) => x.pausado);
  return pausados.length ? `<div class="itens">${pausados.map((x) => item(`@${esc(x.usuario)}`, "Com você",
    botao("Devolver ao Zé", "mk-direct-devolver", `data-usuario="${esc(x.usuario)}"`, "discreta"))).join("")}</div>` : "";
};

/** Redesenha o cartão com a leitura nova. @param {any} r */
function redesenhar(r) {
  const novo = document.createElement("div");
  novo.innerHTML = cartaoComentarios(r);
  $("mk-comentarios")?.replaceWith(/** @type {Element} */ (novo.firstElementChild));
}

/** Os ajustes da conversa como estão na tela. */
const ajustes = () => ({
  ligado: /** @type {HTMLInputElement} */ ($("mk-direct-ligado")).checked,
  link: /** @type {HTMLInputElement} */ ($("mk-direct-link")).value,
  como: /** @type {HTMLTextAreaElement} */ ($("mk-direct-como")).value,
});

/** Cada ajuste fica guardado assim que muda (ao sair do campo), sem depender do Salvar. */
Object.assign(MUDAR, {
  "direct-ajuste": async () => {
    try {
      await api("marketing/instagram/direct", ajustes());
      mostrar("mk-resultado-direct", true, "Salvo.");
    } catch (erro) { mostrar("mk-resultado-direct", false, erro.message); }
  },
});

Object.assign(ACOES, {
  "mk-direct-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = ajustes();
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
  "mk-avisos-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const segredo = /** @type {HTMLInputElement} */ ($("mk-avisos-segredo")).value;
    try {
      const r = await ocupado(b, () => api("marketing/instagram/avisos", { segredo }));
      redesenhar(r);
      mostrar("mk-resultado-avisos", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-avisos", false, erro.message); }
  },
  "mk-avisos-remover": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/instagram/avisos/remover", {}));
      redesenhar(r);
      mostrar("mk-resultado-avisos", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-avisos", false, erro.message); }
  },
  "mk-ignoradas-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const contas = /** @type {HTMLTextAreaElement} */ ($("mk-ignoradas")).value;
    try {
      const r = await ocupado(b, () => api("marketing/instagram/ignoradas", { contas }));
      redesenhar(r);
      mostrar("mk-resultado-ignoradas", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-ignoradas", false, erro.message); }
  },
  "mk-comentarios": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/instagram/comentarios", { ligado: b.dataset.ligado === "1" }));
      redesenhar(r);
      mostrar("mk-resultado-comentarios", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-comentarios", false, erro.message); }
  },
});
