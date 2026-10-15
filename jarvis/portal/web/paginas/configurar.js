// Página configurar, carregada sob demanda.
PAGINAS.configurar = async function() {
    const [cfg, esc_, ct] = await Promise.all([api("configuracao"), api("escuta"), api("contas")]);
    escuta = esc_;
    contasTela = ct;
    prepararAcesso(cfg);
    const passos = ["Perfil", "Agente", "Reconhecimento de fala"];
    const trilha = `<ol class="passos">${passos.map((t, i) => `<li ${i + 1 === passo ? 'aria-current="step"' : i + 1 < passo ? 'class="feito"' : ""}><span>${i + 1}</span>${t}</li>`).join("")}</ol>`;
    const voltar = passo > 1 ? botao("Voltar", "passo", `data-passo="${passo - 1}"`, "discreta") : "";
    const corpo = {
      1: cartao("Perfil", `${sub("Como o Zé chama você e o que deve saber sobre o seu trabalho.")}${camposPerfil(cfg)}<p class="resultado" id="resultado-perfil"></p>`),
      2: '<section class="cartao" id="cartao-acesso"></section><section class="cartao" id="cartao-contas"></section>',
      3: '<section class="cartao" id="cartao-escuta"></section>',
    }[passo];
    const seguir = passo === 1 ? botao("Continuar", "perfil-salvar", 'data-seguir="2"', "principal")
      : passo === 2 ? botao("Continuar", "passo", 'data-passo="3"', "principal")
      : botao("Concluir", "configuracao-concluir", "", "principal");
    return `${cabeca("Configuração inicial")}${sub("Tudo pode ser alterado depois em Ajustes.")}${trilha}${corpo}
      <div class="linha rodape-passos">${voltar}<span class="espaco"></span>${seguir}</div>`;
  };
