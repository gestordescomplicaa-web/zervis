// Página foco, carregada sob demanda.
PAGINAS.foco = async function() {
    const q = await api("foco");
    const dados = (f) => `data-id="${esc(f.id)}"`;
    let agora;
    if (q.atual) {
      const f = q.atual;
      const passo = f.proximo_passo
        ? `<div class="linha-item"><div class="texto"><small>Próximo passo</small><strong>${esc(f.proximo_passo)}</strong></div><div class="botoes">${botao("✓ Feito", "foco", `${dados(f)} data-foco="passo"`, "principal")}</div></div>`
        : `<div class="add"><input id="passo-novo" placeholder="Qual é o próximo passo?" autocomplete="off">${botao("Salvar", "foco-passo", dados(f))}</div>`;
      agora = cartao("", `<p class="rotulo">Agora</p><p class="numero">${esc(f.titulo)}</p>${f.bloqueio ? `<p class="aviso">Travada: ${esc(f.bloqueio)}</p>` : ""}${passo}
        <div class="botoes">${botao("Concluir", "foco", `${dados(f)} data-foco="concluir"`)}${botao("Pausar", "foco", `${dados(f)} data-foco="pausar"`, "discreta")}</div>`);
    } else agora = cartao("", vazio("Nenhuma frente em andamento. Diga ao Zé: “comecei…”."));
    const lista = (titulo, frentes, acoes) => (frentes.length ? cartao(titulo, `<div class="itens">${frentes.map((f) => item(esc(f.titulo), esc(f.bloqueio ? "Travada: " + f.bloqueio : f.proximo_passo), acoes(f))).join("")}</div>`) : "");
    return `${cabeca("Foco")}${sub(`Até ${q.limite} frentes ativas.`)}${agora}
      ${lista("Outras ativas", q.ativas, (f) => botao("Focar", "foco", `${dados(f)} data-foco="focar"`) + botao("Concluir", "foco", `${dados(f)} data-foco="concluir"`, "discreta"))}
      ${lista("Paradas", [...q.travadas, ...q.pausadas], (f) => botao("Retomar", "foco", `${dados(f)} data-foco="focar"`) + xis("foco-descartar", dados(f), "Descartar"))}
      ${lista("Ideias", q.ideias, (f) => botao("Virar frente", "foco", `${dados(f)} data-foco="focar"`) + xis("foco-descartar", dados(f), "Descartar"))}`;
  };
