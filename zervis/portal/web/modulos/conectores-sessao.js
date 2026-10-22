// Os conectores (MCP) de cada projeto, escolhidos dentro da sessão: na criação e no topo da
// sessão aberta. Carregado com a página de sessões.

/** Os conectores (MCP) para ligar no projeto da sessão, com onde mais cada um já está. */
function listaConectores(lista, marca) {
  if (!lista.length) return `<div class="conectores-sessao"><p class="rotulo">Conectores MCP</p>${sub('Nenhum conector. Adicione em <a href="#conectores">Conectores</a>.')}</div>`;
  const detalhe = (k) => k.todos ? "Todos os projetos" : k.outros.length ? `Também em: ${esc(k.outros.join(", "))}` : "";
  return `<div class="conectores-sessao"><p class="rotulo">Conectores MCP</p><div class="itens">${lista.map((k) => item(
    `<span class="mono">${esc(k.nome)}</span> <span class="etiqueta">MCP</span>`, detalhe(k),
    `<label class="liga" title="Usar neste projeto"><input type="checkbox" data-${marca}="${esc(k.nome)}" ${k.marcado ? "checked" : ""} ${k.editavel ? "" : "disabled"} aria-label="Usar ${esc(k.nome)} neste projeto"><span></span></label>`)).join("")}</div></div>`;
}

/** Na sessão nova, a pasta pode nem existir: a lista sai da página Conectores. */
async function conectoresDaNovaSessao() {
  const { conectores } = await api("conectores").catch(() => ({ conectores: [] }));
  const lugar = document.getElementById("ns-campo-isolada");
  if (!lugar) return;
  lugar.insertAdjacentHTML("afterend", listaConectores(conectores.map((k) => {
    const todos = k.projetos.includes("*");
    return { nome: k.nome, tipo: k.tipo, marcado: todos, todos, editavel: k.origem === "painel" && !todos, outros: todos ? [] : k.projetos.map((p) => p.split("/").pop()) };
  }), "ns-conector"));
}

/** Os conectores marcados na lista (os travados contam: continuam como estão). */
const conectoresMarcados = (marca) => [.../** @type {NodeListOf<HTMLInputElement>} */ (document.querySelectorAll(`[data-${marca}]:checked`))].map((c) => c.getAttribute(`data-${marca}`));

Object.assign(ACOES, {
  "sessao-conectores": async (b) => {
    // A caixa entra logo abaixo da faixa da cópia isolada, no topo da conversa.
    if (!document.getElementById("conectores-da-sessao")) $("copia-sessao").insertAdjacentHTML("afterend", '<section id="conectores-da-sessao" class="cartao" hidden></section>');
    const area = $("conectores-da-sessao");
    if (!area.hidden) { area.hidden = true; b.setAttribute("aria-expanded", "false"); return; }
    const { conectores } = await ocupado(b, () => api("sessao/conectores", { id: sessaoAberta }));
    area.innerHTML = `${listaConectores(conectores, "conector-sessao")}
      ${conectores.length ? sub("Valem em todas as sessões deste projeto. Ao salvar, o agente reabre e a conversa continua.") : ""}
      <div class="linha">${conectores.length ? botao("Salvar", "sessao-conectores-salvar", "", "principal") : ""}${botao("Fechar", "sessao-conectores", "", "discreta")}</div>`;
    area.hidden = false; b.setAttribute("aria-expanded", "true");
  },
  "sessao-conectores-salvar": async (b) => {
    const id = sessaoAberta;
    const r = await ocupado(b, () => api("sessao/conectores/salvar", { id, nomes: conectoresMarcados("conector-sessao") }));
    toast(r.aviso); await abrirSessao(id);
  },
});
