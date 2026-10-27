// Os pedidos de permissão das sessões do Claude, aprovados ou negados pelo painel (também do
// celular), ao mesmo tempo que o terminal pergunta (ADR 0039). Carregado com a página de sessões.

/** A linha da sessão na lista: o pedido de aprovação vem antes de tudo. */
const rotuloSessao = (s) => s.permissoes?.length ? "pede aprovação" : s.estado === "trabalhando" ? "trabalhando…" : esc(s.resumo || s.pasta);

/** O que a sessão espera aprovar (ADR 0039): a frase do Zé, os argumentos e Aprovar/Negar. O
 * terminal pergunta ao mesmo tempo; o primeiro que responde decide. */
function faixaPermissao(sessao) {
  return (sessao.permissoes || []).map((p) => `<div class="faixa limite" role="alert"><div><strong>A sessão quer ${esc(p.frase)}</strong>
    <span class="mono">${esc(p.detalhe)}</span></div><div class="botoes">${botao("Aprovar", "permissao-aprovar", `data-pedido="${esc(p.id)}"`, "principal")}${botao("Negar", "permissao-negar", `data-pedido="${esc(p.id)}"`, "discreta")}</div></div>`).join("");
}

/** Redesenha a faixa só quando os pedidos mudam (o relógio da página passa a cada 1,5 s). */
function atualizarPermissao(sessao) {
  if (!$("permissao-sessao")) $("limite-sessao")?.insertAdjacentHTML("afterend", '<div id="permissao-sessao"></div>');
  const area = $("permissao-sessao");
  const versao = JSON.stringify((sessao.permissoes || []).map((p) => p.id));
  if (!area || area.dataset.pedidos === versao) return;
  area.dataset.pedidos = versao;
  area.innerHTML = faixaPermissao(sessao);
}

/** Aprovar ou negar pelo painel; se o terminal respondeu antes, o Zé diz que já foi respondido.
 * @param {HTMLButtonElement} b @param {boolean} aprovar */
async function decidirPermissao(b, aprovar) {
  const id = sessaoAberta;
  try {
    const r = await ocupado(b, () => api("sessao/permissao", { id, pedido: b.dataset.pedido, aprovar }));
    toast(r.aviso);
  } catch (erro) {
    toast(erro.message);
  }
  if (id === sessaoAberta) await acompanharSessao();
}
