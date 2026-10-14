// A página Memória, carregada sob demanda pelo painel: a memória curta, as sugestões que o Zé
// aprendeu e o estado da memória dos projetos (ai-memory).

PAGINAS.memoria = async () => {
    const m = await api("memoria");
    const bloco = (titulo, alvo, entradas) => {
      const cheio = Math.min(100, Math.round((100 * entradas.join(" § ").length) / m.limites[alvo]));
      const barra = `<span class="cheio" title="Quanto do espaço desta memória já foi usado"><span class="barra"><span data-cheio="${cheio}"></span></span>${cheio}% cheio</span>`;
      return cartao(`${titulo} ${barra}`,
        `<div class="itens">${entradas.map((t) => item("", esc(t), xis("memoria-remover", `data-alvo="${alvo}" data-texto="${esc(t)}"`, "Remover"))).join("") || vazio("Vazia.")}</div>
         <div class="add"><input data-nova="${alvo}" placeholder="Algo para o Zé lembrar sempre" autocomplete="off">${botao("Adicionar", "memoria-adicionar", `data-alvo="${alvo}"`)}</div>`);
    };
    const sugestoes = m.sugestoes.length ? cartao("Sugestões", `${sub("O que o Zé aprendeu numa conversa e espera a sua aprovação.")}
      <div class="itens">${m.sugestoes.map((s) => item(s.tipo === "skill" ? "Skill" : "Memória", esc(s.resumo),
        botao("Aprovar", "sugestao", `data-id="${esc(s.id)}" data-aprovar="1"`, "principal") + botao("Descartar", "sugestao", `data-id="${esc(s.id)}"`, "discreta"))).join("")}</div>`) : "";
    const p = m.projetos || {};
    const projetos = cartao(`Memória dos projetos <span class="etiqueta ${p.ativa ? "bom" : "alerta"}">${p.ativa ? "Conectada" : "Desligada"}</span>`,
      `${sub("O que as sessões de código fazem fica guardado por projeto e volta na próxima sessão (ai-memory).")}${p.paginas != null ? `<p class="nota">${p.paginas} páginas guardadas.</p>` : ""}`);
    return `${cabeca("Memória")}${sub("O que o Zé sabe em toda conversa.")}
      ${sugestoes}${bloco("Sobre você", "usuario", m.usuario)}${bloco("Sobre a máquina e o Zé", "jarvis", m.jarvis)}${projetos}`;
  };

Object.assign(ACOES, {
  sugestao: async (b) => { const r = await ocupado(b, () => api("sugestao/decidir", { id: b.dataset.id, aprovar: !!b.dataset.aprovar })); toast(r.aviso); await recarregar(); },
  "memoria-remover": (b) => confirmar(b, "Remover?", async () => { await api("memoria/mudar", { acao: "remover", alvo: b.dataset.alvo, texto: b.dataset.texto }); await recarregar(); }),
  "memoria-adicionar": async (b) => {
    const campo = document.querySelector(`[data-nova="${b.dataset.alvo}"]`);
    await ocupado(b, () => api("memoria/mudar", { acao: "adicionar", alvo: b.dataset.alvo, texto: campo.value }));
    toast("Guardado."); await recarregar();
  },
});
