// Página modelos, carregada sob demanda.
PAGINAS.modelos = async function() {
    const [c, esc_, cfg, ct] = await Promise.all([api("cerebro"), api("escuta"), api("configuracao"), api("contas")]);
    contasTela = ct;
    modelo = { ...c.via, chaves: c.chaves, listas: c.listas };
    escuta = esc_;
    prepararAcesso(cfg);
    Object.assign(acessoTela, completo(c));
    agentes = c.agentes;
    const sessoes = c.sessoes.total;
    return `${cabeca("Modelos")}${sub("Um modelo para cada tipo de tarefa.")}
      <section class="cartao" id="cartao-acesso" data-contexto="cerebro"></section>
      ${cartao("", `<div class="cabeca"><h2>Respostas rápidas</h2>${liga(c.via.ligada, "via-ligada", "", "Ligada")}</div>
        ${sub("Parte do cérebro: conversa simples com um modelo leve. Pedidos com ação vão ao modelo principal.")}
        <div class="segmentos" role="group" aria-label="Quando">${[["live", "Só no Live"], ["sempre", "Sempre"]].map(([v, n]) => `<button type="button" data-acao="via-quando" data-quando="${v}" aria-pressed="${v === (c.via.quando || "live")}">${n}</button>`).join("")}</div>
        <p class="nota" id="nota-quando">${notaDoQuando(c.via.quando, c.ativa)}</p>
        <div class="segmentos" role="group" aria-label="Provedor">${c.motores.map((m) => `<button type="button" data-acao="motor" data-motor="${m.id}" data-modelo="${esc(m.modelo)}" aria-pressed="${m.id === c.via.motor}">${esc(NOME_MOTOR[m.id] || m.nome)}</button>`).join("")}</div>
        <div class="linha"><label id="campo-modelo">Modelo${campoModelo(c.via.motor, c.via.modelo)}</label>
          <label id="campo-endereco">Endereço<input id="endereco" class="mono" value="${esc(c.via.endereco)}" placeholder="http://127.0.0.1:20128/v1" autocomplete="off" spellcheck="false"></label></div>
        <div id="area-chave"></div>
        <div class="linha">${botao("Salvar", "modelo-salvar", "", "principal")}${botao("Testar", "modelo-testar")}<span class="resultado" id="resultado"></span></div>`)}
      <section class="cartao" id="cartao-contas"></section>
      ${cartao("", `<div class="cabeca"><h2>Sessões de código</h2><span class="etiqueta">${sessoes} ${sessoes === 1 ? "sessão" : "sessões"}</span><a class="externo" href="#sessoes">Abrir sessões</a></div>
        ${sub("Agentes que trabalham nos seus projetos e continuam de onde pararam.")}
        <p class="nota">Agentes: ${c.sessoes.agentes.filter((a) => a.disponivel).map((a) => esc(a.nome)).join(" e ")}. Você escolhe o agente ao criar a sessão; a conta é a que está em uso em Contas.</p>`)}
      <section class="cartao" id="cartao-escuta"></section>`;
  };
