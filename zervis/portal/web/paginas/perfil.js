// Página perfil, carregada sob demanda.
PAGINAS.perfil = async function() {
    const cfg = await api("configuracao");
    return `${cabeca("Perfil")}${sub("Usado pelo Zé em todas as conversas.")}
      ${cartao("", `${camposPerfil(cfg)}<div class="linha">${botao("Salvar", "perfil-salvar", "", "principal")}</div><p class="resultado" id="resultado-perfil"></p>`)}`;
  };
