// Página automacoes, carregada sob demanda.
PAGINAS.automacoes = async function() {
    const a = await api("automacoes");
    const repete = (ag) => (/^\d{4}-\d{2}-\d{2}/.test(ag) ? "" : " · " + esc(ag));
    const linhas = a.map((j) => item(esc(j.nome), `${TIPO_AUTOMACAO[j.tipo] || esc(j.tipo)} · ${j.ativo ? quando(j.proxima) : "pausada"}${repete(j.agenda)}`,
      liga(j.ativo, "automacao", `data-id="${esc(j.id)}"`, "Ativa") + xis("automacao-remover", `data-id="${esc(j.id)}"`, "Remover"), !j.ativo));
    return `${cabeca("Automações")}${sub("Para criar, peça ao Zé: “me lembra amanhã às nove de…”.")}
      ${a.length ? `<div class="itens">${linhas.join("")}</div>` : vazio("Nada agendado.")}`;
  };
