import { $, api, botao, esc, ocupado, toast } from "../painel.js";
import { compartilhado, carregadas } from "./estado.js";

// Os pedidos de permissão das sessões do Claude, aprovados ou negados pelo painel (também do
// celular), ao mesmo tempo que o terminal pergunta (ADR 0039). Carregado com a página de sessões.

/** A linha da sessão na lista: o pedido de aprovação vem antes de tudo. */
export const rotuloSessao = (s) => s.permissoes?.length ? "pede aprovação" : s.estado === "trabalhando" ? "trabalhando…" : esc(s.resumo || s.pasta);

/** O que a sessão espera aprovar (ADR 0039): a frase do Zé, os argumentos e Aprovar/Negar. O
 * terminal pergunta ao mesmo tempo; o primeiro que responde decide. Um formulário de perguntas
 * mostra a próxima pergunta com um botão por opção (ou caixas, quando vale mais de uma), outra
 * resposta escrita e "Responder no terminal". */
function faixaPermissao(sessao) {
  return (sessao.permissoes || []).map((p) => p.tipo === "pergunta" ? faixaPergunta(p) : `<div class="faixa limite" role="alert"><div><strong>A sessão quer ${esc(p.frase)}</strong>
    <span class="mono">${esc(p.detalhe)}</span></div><div class="botoes">${botao("Aprovar", "permissao-aprovar", `data-pedido="${esc(p.id)}"`, "principal")}${botao("Negar", "permissao-negar", `data-pedido="${esc(p.id)}"`, "discreta")}</div></div>`).join("");
}

/** @param {{id: string, perguntas: {pergunta: string, titulo: string, opcoes: string[], multipla: boolean}[], respostas: Record<string, string>}} p */
function faixaPergunta(p) {
  const q = p.perguntas.find((x) => !(x.pergunta in (p.respostas || {})));
  if (!q) return "";
  const n = p.perguntas.indexOf(q), total = p.perguntas.length;
  const dados = `data-pedido="${esc(p.id)}" data-pergunta="${esc(q.pergunta)}"`;
  const opcoes = q.multipla
    ? `<div class="opcoes-pergunta">${q.opcoes.map((o) => `<label><input type="checkbox" value="${esc(o)}"> ${esc(o)}</label>`).join("")}</div>
      <div class="botoes">${botao("Enviar", "pergunta-enviar-marcadas", dados, "principal")}</div>`
    : `<div class="botoes">${q.opcoes.map((o) => botao(esc(o), "pergunta-opcao", `${dados} data-valor="${esc(o)}"`, "principal")).join("")}</div>`;
  return `<div class="faixa limite pergunta-sessao" role="alert" ${dados}><div><strong>A sessão pergunta${total > 1 ? ` (${n + 1} de ${total})` : ""}</strong>
    <span>${esc(q.pergunta)}</span></div>${opcoes}
    <div class="botoes outra-resposta"><input type="text" placeholder="Outra resposta" aria-label="Outra resposta" maxlength="500">
    ${botao("Enviar", "pergunta-outra", dados, "discreta")}${botao("Responder no terminal", "permissao-negar", `data-pedido="${esc(p.id)}"`, "discreta")}</div></div>`;
}

/** Uma resposta do formulário pelo painel: a opção, as marcadas ou o texto escrito.
 * @param {HTMLButtonElement} b @param {string} valor */
export async function responderPergunta(b, valor) {
  const id = compartilhado.sessaoAberta;
  if (!valor.trim()) return toast("Escolha uma opção ou escreva a resposta.");
  try {
    const r = await ocupado(b, () => api("sessao/permissao", { id, pedido: b.dataset.pedido, pergunta: b.dataset.pergunta, valor }));
    toast(r.aviso);
  } catch (erro) {
    toast(erro.message);
  }
  if (id === compartilhado.sessaoAberta) await carregadas.acompanharSessao();
}

/** Redesenha a faixa só quando os pedidos mudam (o relógio da página passa a cada 1,5 s). */
export function atualizarPermissao(sessao) {
  if (!$("permissao-sessao")) $("limite-sessao")?.insertAdjacentHTML("afterend", '<div id="permissao-sessao"></div>');
  const area = $("permissao-sessao");
  const versao = JSON.stringify((sessao.permissoes || []).map((p) => [p.id, Object.keys(p.respostas || {}).length]));
  if (!area || area.dataset.pedidos === versao) return;
  area.dataset.pedidos = versao;
  area.innerHTML = faixaPermissao(sessao);
}

/** Aprovar ou negar pelo painel; se o terminal respondeu antes, o Zé diz que já foi respondido.
 * @param {HTMLButtonElement} b @param {boolean} aprovar */
export async function decidirPermissao(b, aprovar) {
  const id = compartilhado.sessaoAberta;
  try {
    const r = await ocupado(b, () => api("sessao/permissao", { id, pedido: b.dataset.pedido, aprovar }));
    toast(r.aviso);
  } catch (erro) {
    toast(erro.message);
  }
  if (id === compartilhado.sessaoAberta) await carregadas.acompanharSessao();
}

// Para o núcleo do painel (as ações, a navegação), que chama este módulo depois que ele carrega.
Object.assign(carregadas, { decidirPermissao, responderPergunta });
