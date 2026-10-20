// Página inicio, carregada sob demanda.
PAGINAS.inicio = async function() {
    const e = await api("inicio");
    const foco = e.foco ? `<strong>${esc(e.foco.titulo)}</strong><p>${e.foco.passo ? "Próximo passo: " + esc(e.foco.passo) : "Sem próximo passo."}</p>` : vazio("Nenhuma frente em andamento.");
    const sess = e.sessoes.trabalhando.length
      ? `<strong>${e.sessoes.trabalhando.length} trabalhando</strong><p>${e.sessoes.trabalhando.map(esc).join(", ")}</p>`
      : `<strong>${e.sessoes.total ? "Nenhuma trabalhando" : "Nenhuma sessão"}</strong>`;
    const prox = e.proximas.length ? `<div class="itens">${e.proximas.map((p) => item(esc(p.nome), quando(p.quando))).join("")}</div>` : vazio("Nada agendado.");
    const voz = e.hoje.voz_s == null ? "—" : seg(e.hoje.voz_s * 1000);
    const numero = (valor, rotulo) => `<div><span class="numero">${valor}</span><span class="rotulo">${rotulo}</span></div>`;
    return `${cabeca("Início", `<span class="etiqueta ${e.ze !== "inativo" ? "bom" : ""}">Zé ${esc(ESTADOS[e.ze] || e.ze)}</span>`)}
      ${cartao("Hoje", `<div class="numeros">${numero(e.hoje.respostas, "respostas")}${numero(e.hoje.tokens_mil + " mil", "tokens")}${numero(voz, "voz mais rápida")}</div>`)}
      <div class="grade">
        ${cartao(`<a href="#foco">Foco</a>`, foco)}
        ${cartao(`<a href="#sessoes">Sessões</a>`, sess)}
        ${cartao(`<a href="#automacoes">Próximos lembretes</a>`, prox)}
      </div>`;
  };
