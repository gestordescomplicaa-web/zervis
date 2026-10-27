// --- o despachante: cada data-acao faz uma coisa ----------------------------------------------------

const recarregar = () => abrir();

/** @type {Record<string, (botao: HTMLButtonElement, evento?: Event) => unknown>} */
const ACOES = {
  "cerebro-escolher": async (b) => {
    const pedido = b.dataset.agente;
    const c = await ocupado(b, () => api("cerebro/escolher", { agente: pedido }));
    Object.assign(acessoTela, completo(c));
    // Sem a conexão, o OmniRoute não sobe: os campos aparecem e a troca sai depois de salvar.
    if (pedido === "omniroute" && c.completo.provedor !== "omniroute") Object.assign(acessoTela, { cerebro: "omniroute", omniPendente: true });
    desenharAcesso(); toast(c.aviso || "Agente atualizado.");
  },
  "omni-salvar": async (b) => {
    let c = await ocupado(b, () => api("omniroute/salvar", { endereco: valorCampo("omni-endereco").value, chave: valorCampo("omni-chave").value }));
    if (acessoTela.omniPendente) c = await api("cerebro/escolher", { agente: "omniroute" });
    const trocou = c.completo.provedor === "omniroute";
    Object.assign(acessoTela, completo(c), trocou ? { omniPendente: false } : { cerebro: "omniroute" });
    desenharAcesso(); mostrar("resultado-acesso", trocou, c.aviso);
  },
  "confirmar-sim": async (b) => { const f = pendentes.get(b.dataset.id); pendentes.delete(b.dataset.id); if (f) await f(); },
  "confirmar-nao": (b) => { const l = /** @type {HTMLElement} */ (b.closest("[data-antes]")); l.innerHTML = l.dataset.antes; delete l.dataset.antes; pendentes.delete(b.dataset.id); },
  // imersão
  "imersao-cheia": () => (/** @type {HTMLIFrameElement} */ (moldura.querySelector("iframe")) || moldura).requestFullscreen?.().catch(() => {}),
  "imersao-desligar": desligarImersao,
  "imersao-ligar": ligarImersao,
  // foco
  foco: async (b) => { await ocupado(b, () => api("foco/acao", { id: b.dataset.id, acao: b.dataset.foco })); await recarregar(); },
  "foco-passo": async (b) => { await ocupado(b, () => api("foco/acao", { id: b.dataset.id, acao: "passo_novo", texto: valorCampo("passo-novo").value })); await recarregar(); },
  "foco-descartar": (b) => confirmar(b, "Descartar?", async () => { await api("foco/acao", { id: b.dataset.id, acao: "descartar" }); await recarregar(); }),
  // automações
  "automacao-remover": (b) => confirmar(b, "Remover?", async () => { await api("automacao/remover", { id: b.dataset.id }); await recarregar(); }),
  // memória
  // modelos
  motor: (b) => {
    modelo.motor = b.dataset.motor;
    /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll('[data-acao="motor"]')).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    $("campo-modelo").innerHTML = "Modelo" + campoModelo(modelo.motor, b.dataset.modelo);
    desenharChave();
  },
  "modelo-salvar": async (b) => {
    const c = await ocupado(b, () => api("cerebro", lerModelo()));
    modelo.chaves = c.chaves;
    const r = $("resultado");
    r.className = "resultado " + (c.ativa || !c.via.ligada ? "ok" : "erro");
    r.textContent = c.aviso || (c.via.ligada ? "Em uso." : "Desligadas.");
  },
  "modelo-testar": async (b) => {
    const r = $("resultado");
    r.className = "resultado"; r.textContent = "Testando…";
    const { ligada, ...dados } = lerModelo();
    const t = await ocupado(b, () => api("testar", dados));
    r.className = "resultado " + (t.ok ? "ok" : "erro");
    r.textContent = t.ok ? `Primeira palavra em ${seg(t.primeira_palavra_ms)}.` : t.erro;
  },
  "chave-guardar": async (b) => {
    const c = await ocupado(b, () => api("chave", { motor: modelo.motor, chave: valorCampo("chave").value }));
    modelo.chaves = c.chaves; desenharChave(); toast(c.aviso || "Chave guardada.");
  },
  "perfil-salvar": async (b) => {
    const r = await ocupado(b, () => api("perfil", lerPerfil()));
    if (b.dataset.seguir) { passo = Number(b.dataset.seguir); await abrir(); toast(r.aviso); return; }
    mostrar("resultado-perfil", true, r.aviso);
  },
  passo: async (b) => { passo = Number(b.dataset.passo); await abrir(); },
  "configuracao-concluir": () => { passo = 1; location.hash = "#inicio"; toast("Configuração concluída."); },
  "conta-adicionar": async (b) => {
    const campo = /** @type {HTMLInputElement} */ (document.querySelector(`[data-nova-conta="${b.dataset.agente}"]`));
    const r = await ocupado(b, () => api("conta/adicionar", { agente: b.dataset.agente, nome: campo.value }));
    contasTela = r; desenharContas(); desenharAcesso(); mostrar("resultado-contas", true, r.aviso);
  },
  "conta-usar": async (b) => {
    const r = await ocupado(b, () => api("conta/usar", { id: b.dataset.id }));
    contasTela = r; desenharContas(); toast(r.aviso);
    await modelosDaConta();
  },
  "conta-entrar": async (b) => {
    const r = await ocupado(b, () => api("conta/entrar", { id: b.dataset.id }));
    loginTela = { id: r.login }; desenharContas(); mostrarLogin(r);
    acompanharLogin(r.login);
  },
  "login-codigo-enviar": async (b) => {
    await ocupado(b, () => api("conta/login/codigo", { id: b.dataset.id, codigo: valorCampo("login-codigo").value }));
    valorCampo("login-codigo").value = ""; mostrar("resultado-login", null, "Código enviado. Aguardando o agente…");
  },
  "login-cancelar": async (b) => {
    loginTela = null; await api("conta/login/fechar", { id: b.dataset.id }); desenharContas();
  },
  "conta-remover": (b) => confirmar(b, "Remover a conta e o login dela?", async () => {
    const r = await api("conta/remover", { id: b.dataset.id });
    contasTela = r; desenharContas(); toast(r.aviso); await modelosDaConta();
  }),
  "acesso-salvar": async (b) => {
    const r = await ocupado(b, () => api("acesso/chave", { chave: valorCampo("segredo-acesso").value }));
    acessoTela = { ...acessoTela, ...r.acesso, agentes: r.agentes }; desenharAcesso();
    mostrar("resultado-acesso", true, r.aviso);
  },
  "codex-chave-salvar": async (b) => {
    const r = await ocupado(b, () => api("acesso/chave-codex", { chave: valorCampo("segredo-codex").value }));
    await recarregarContas(); mostrar("resultado-acesso", true, r.aviso);
  },
  "codex-chave-reusar": async (b) => {
    const r = await ocupado(b, () => api("acesso/chave-codex", { reusar: true }));
    await recarregarContas(); mostrar("resultado-acesso", true, r.aviso);
  },
  "acesso-testar": async (b) => {
    mostrar("resultado-acesso", null, "Testando…");
    const t = await ocupado(b, () => api("acesso/testar", {}));
    mostrar("resultado-acesso", t.ok, t.mensagem);
  },
  "acesso-remover": (b) => confirmar(b, "Remover a chave?", async () => {
    const r = await api("acesso/remover", {});
    acessoTela = { ...acessoTela, ...r.acesso, agentes: r.agentes }; desenharAcesso(); toast(r.aviso);
  }),
  "escuta-guardar": async (b) => {
    const r = await ocupado(b, () => api("escuta/chave", { chave: valorCampo("chave-escuta").value }));
    escuta = r; desenharEscuta();
    const res = $("resultado-escuta");
    res.className = "resultado " + (r.valida ? "ok" : "erro"); res.textContent = r.aviso;
  },
  "escuta-testar": async (b) => {
    const res = $("resultado-escuta");
    res.className = "resultado"; res.textContent = "Testando…";
    const t = await ocupado(b, () => api("escuta/testar", { chave: valorCampo("chave-escuta").value }));
    res.className = "resultado " + (t.ok ? "ok" : "erro"); res.textContent = t.mensagem;
  },
  "escuta-apagar": (b) => confirmar(b, "Remover a chave?", async () => { escuta = await api("escuta/apagar", {}); desenharEscuta(); toast(escuta.aviso); }),
  "chave-apagar": (b) => confirmar(b, "Apagar a chave?", async () => { const c = await api("chave/apagar", { motor: modelo.motor }); modelo.chaves = c.chaves; desenharChave(); }),
  // sessões
  "sessoes-voltar": () => {
    fecharTerminalTela(); sessaoAberta = null; mostrarLado(false);
    /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll(".item-sessao")).forEach((x) => x.setAttribute("aria-current", "false"));
  },
  "sessao-nova": async () => { sessaoAberta = null; /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll(".item-sessao")).forEach((x) => x.setAttribute("aria-current", "false")); await formSessao(); },
  "sessao-abrir": (b) => abrirSessao(b.dataset.id),
  "ns-onde": (b) => {
    /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll('[data-acao="ns-onde"]')).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    const novo = b.dataset.onde === "novo";
    $("ns-campo-pasta").hidden = novo; $("ns-campo-projeto").hidden = !novo; $("ns-campo-isolada").hidden = novo;
  },
  "ns-motor": (b) => /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll('[data-acao="ns-motor"]')).forEach((x) => x.setAttribute("aria-pressed", String(x === b))),
  "ns-criar": async (b) => {
    const novo = !$("ns-campo-projeto").hidden;
    const motor = /** @type {HTMLElement} */ (document.querySelector('[data-acao="ns-motor"][aria-pressed="true"]')).dataset.motor;
    const s = await ocupado(b, () => api("sessao/criar", { nome: valorCampo("ns-nome").value, pasta: valorCampo("ns-pasta").value, motor, novo, projeto: valorCampo("ns-projeto").value, isolada: !novo && entradaCampo("ns-isolada").checked, conectores: conectoresMarcados("ns-conector") }));
    await listaSessoes(); await abrirSessao(s.id);
  },
  "copia-atualizar": () => carregarCopia(sessaoAberta),
  "copia-aplicar": (b) => confirmar(b, "Aplicar os commits ao projeto?", () => mudarCopia("aplicar")),
  "copia-descartar": (b) => confirmar(b, "Descartar commits e alterações da cópia? Arquivos ignorados ficam.", () => mudarCopia("descartar")),
  // A confirmação numa faixa larga, abaixo do cabeçalho: no cabeçalho o texto não cabia.
  "sessao-excluir": () => {
    $("excluir-sessao").innerHTML = `<div class="faixa limite" role="alert"><div><strong>Excluir a sessão ${esc(sessaoAtual?.nome || "")}?</strong>
      <span>O agente é encerrado e a conversa da sessão sai do Zé. A pasta do projeto fica.</span></div>
      <div class="botoes">${botao("Excluir", "sessao-excluir-sim", "", "perigo")}${botao("Cancelar", "sessao-excluir-nao", "", "discreta")}</div></div>`;
  },
  "interrompida-continuar": async (b) => { const r = await ocupado(b, () => api("sessao/interrompida", { id: sessaoAberta, continuar: true })); toast(r.aviso); await abrirSessao(sessaoAberta); },
  "permissao-aprovar": (b) => decidirPermissao(b, true),
  "permissao-negar": (b) => decidirPermissao(b, false),
  "interrompida-dispensar": async () => { const r = await api("sessao/interrompida", { id: sessaoAberta }); toast(r.aviso); $("interrompida-sessao")?.remove(); },
  "sessao-excluir-nao": () => { $("excluir-sessao").innerHTML = ""; },
  "sessao-interromper": () => {
    $("interromper-sessao").innerHTML = `<div class="faixa limite" role="alert"><div><strong>Interromper o trabalho?</strong>
      <span>O agente será encerrado. A conversa e os arquivos serão preservados.</span></div><div class="botoes">
      ${botao("Interromper", "sessao-interromper-sim", "", "perigo")}${botao("Cancelar", "sessao-interromper-nao", "", "discreta")}</div></div>`;
  },
  "sessao-interromper-nao": () => { $("interromper-sessao").innerHTML = ""; },
  "sessao-interromper-sim": async (b) => {
    const id = sessaoAberta;
    const r = await ocupado(b, () => api("terminal/fechar", { id }));
    toast(r.aviso);
    if (id !== sessaoAberta || !$("terminal")) return;
    fecharTerminalTela();
    $("terminal-fechado").hidden = false;
    $("interromper-sessao").innerHTML = "";
    await acompanharSessao();
    if (sessaoAtual?.melhorias) await desenharMelhorias();
  },
  "sessao-excluir-sim": async (b) => {
    const r = await ocupado(b, () => api("sessao/excluir", { id: sessaoAberta }));
    sessaoAberta = null; toast(r.aviso || "Sessão excluída."); await recarregar();
  },
  "escolha-abrir": (b) => {
    const menu = /** @type {HTMLElement} */ (b.nextElementSibling), abrir = menu.hidden;
    fecharEscolhas(menu);
    menu.hidden = !abrir;
    b.setAttribute("aria-expanded", String(abrir));
    if (abrir) (/** @type {HTMLElement} */ (menu.querySelector('[aria-selected="true"]')) || /** @type {HTMLElement} */ (menu.querySelector(".escolha-item")))?.focus();
  },
  "escolha-item": async (b) => {
    const caixa = /** @type {HTMLElement} */ (b.closest(".escolha")), valor = b.dataset.valor;
    fecharEscolhas();
    if (b.getAttribute("aria-selected") === "true") return;
    await ESCOLHAS[caixa.dataset.escolha]?.(valor);
  },
  "limite-continuar": async (b) => { await ocupado(b, () => trocarSessao(b.dataset.motor, b.dataset.conta, true)); },
  "md-abrir": () => { $("editor-md").hidden = false; $("md-nome").focus(); },
  "md-fechar": () => { $("editor-md").hidden = true; },
  "md-salvar": async (b) => {
    const r = await ocupado(b, () => api("sessao/arquivo", { id: sessaoAberta, nome: valorCampo("md-nome").value, conteudo: valorCampo("md-texto").value, sobrescrever: entradaCampo("md-substituir").checked }));
    $("editor-md").hidden = true; valorCampo("md-nome").value = valorCampo("md-texto").value = "";
    toast("Salvo: " + r.arquivo); await acompanharSessao(); await atualizarArvore();
  },
  anexar: () => $("arquivos").click(),
  "atualizacao-fechar": () => {
    try { sessionStorage.setItem("atualizacao-fechada", String(atualizacao?.fim || "")); } catch { /* sem armazenamento */ }
    desenharAtualizacao();
  },
  explorador: () => mostrarExplorador(!explorador),
  no: async (b) => {
    const no = /** @type {HTMLElement} */ (b.closest(".no"));
    if (!no.classList.contains("pasta")) return verArquivo(b.dataset.caminho);
    if (no.getAttribute("aria-expanded") === "true") {
      no.setAttribute("aria-expanded", "false"); /** @type {HTMLElement} */ (no.querySelector(".filhos")).innerHTML = "";
      for (const c of [...abertas]) if (c === no.dataset.caminho || c.startsWith(no.dataset.caminho + "/")) abertas.delete(c);
    } else await abrirPastaNo(no);
  },
  "ver-arquivo": (b) => verArquivo(b.dataset.caminho),
  "arvore-atualizar": () => atualizarArvore(),
  "arvore-recolher": async () => { abertas = new Set(); await carregarPasta("", $("arvore")); },
  "busca-modo": async (b) => { modoBusca = b.dataset.modo; /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll('[data-acao="busca-modo"]')).forEach((x) => x.setAttribute("aria-pressed", String(x === b))); await buscarArquivos(); },
  "previa-fechar": () => fecharPrevia(),
  mencionar: (b) => { fecharPrevia(); escreverNoTerminal("@" + b.dataset.caminho + " "); },
  "terminal-reabrir": () => abrirTerminal(sessaoAberta),
  "modo-fala": (b) => mudarModoFala(b.dataset.modo),
  "voz-remota": ligarVoz,
  "remoto-ativar": async (b) => { const r = await ocupado(b, () => api("remoto/ativar", {})); toast(r.aviso); await recarregar(); },
  "remoto-desativar": async (b) => { const r = await ocupado(b, () => api("remoto/desativar", {})); toast(r.aviso); await recarregar(); },
  "senha-salvar": async (b) => { const r = await ocupado(b, () => api("acesso/senha", { senha: valorCampo("senha-acesso").value })); toast(r.aviso); await recarregar(); },
  "codigo-preparar": async (b) => { codigoPreparado = await ocupado(b, () => api("acesso/codigo/preparar", {})); await recarregar(); },
  "codigo-confirmar": async (b) => { const r = await ocupado(b, () => api("acesso/codigo/confirmar", { codigo: valorCampo("codigo-confirmar").value })); codigoPreparado = null; toast(r.aviso); await recarregar(); },
  "codigo-desligar": (b) => confirmar(b, "Desligar o código? O acesso de fora também será desativado.", async () => { const r = await api("acesso/codigo/desligar", {}); toast(r.aviso); await recarregar(); }),
  "aparelho-desconectar": async (b) => { const r = await ocupado(b, () => api("acesso/desconectar", { id: b.dataset.id })); toast(r.aviso); await recarregar(); },
  "tunel-ativar": async (b) => { const r = await ocupado(b, () => api("tunel/ativar", {})); toast(r.aviso); await recarregar(); },
  whatsapp: async (b) => { const r = await ocupado(b, () => api("mensagens/whatsapp", { ligar: !!b.dataset.ligar })); toast(r.aviso); await recarregar(); },
  "tunel-desativar": async (b) => { const r = await ocupado(b, () => api("tunel/desativar", {})); toast(r.aviso); await recarregar(); },
  "tunel-fixar": async (b) => {
    try {
      const r = await ocupado(b, () => api("tunel/fixar", { colado: valorCampo("fixo-colado").value, endereco: valorCampo("fixo-endereco").value }));
      toast(r.aviso, 8000); await recarregar();
    } catch (erro) { mostrar("resultado-fixo", false, erro.message); }
  },
  "tunel-rapido": (b) => confirmar(b, "Voltar ao endereço automático?", async () => { const r = await api("tunel/rapido", {}); toast(r.aviso); await recarregar(); }),
  "remoto-copiar": async (b) => { await navigator.clipboard.writeText(b.dataset.endereco); toast("Endereço copiado."); },
  grupo: alternarGrupo,
  menu: () => {
    const aberto = document.body.classList.toggle("menu-aberto");
    /** @type {HTMLElement} */ (document.querySelector(".botao-menu")).setAttribute("aria-expanded", String(aberto));
  },
  "espera-modo": async (b) => { const r = await api("voz/espera", { modo: b.dataset.modo }); toast(r.aviso); await recarregar(); },
  "chamado-modo": async (b) => { const r = await api("voz/chamado", { modo: b.dataset.modo }); toast(r.aviso); await recarregar(); },
  "escuta-modo": async (b) => { const r = await api("escuta/modo", { modo: b.dataset.modo }); toast(r.aviso); await recarregar(); },
};

// O que cada menu de escolha faz com o valor escolhido.
/** @type {Record<string, (valor: string) => unknown>} */
const ESCOLHAS = {
  "modo-fala": mudarModoFala,
  "modelo-sessao": async (valor) => {
    const r = await api("sessao/modelo", { id: sessaoAberta, modelo: valor });
    toast(r.aviso); await abrirSessao(sessaoAberta);
  },
  "conta-sessao": async (valor) => {
    const [motor, conta] = valor.split("|");
    await trocarSessao(motor, conta, false);
  },
};

/** @type {Record<string, (campo: HTMLInputElement) => unknown>} */
const MUDAR = {
  automacao: async (el) => { await api("automacao/ativar", { id: el.dataset.id, ativo: el.checked }); await recarregar(); },
  "via-ligada": () => {},
  "cerebro-modelo": async (el) => {
    el.disabled = true; toast("Testando o modelo…");
    try {
      const c = await api("cerebro/modelo", { agente: acessoTela.cerebro, modelo: el.value });
      Object.assign(acessoTela, completo(c)); toast(c.aviso);
    } finally { desenharAcesso(); } // recusado: volta a mostrar o modelo em uso
  },

};

document.addEventListener("click", (ev) => { if (!/** @type {HTMLElement} */ (/** @type {HTMLElement} */ (ev.target).closest(".escolha"))) fecharEscolhas(); }, true);
document.addEventListener("keydown", (ev) => {
  if (!ev.altKey || ev.ctrlKey || ev.metaKey || ev.code !== "KeyM" || !modoFala) return;
  ev.preventDefault(); ev.stopPropagation();
  const i = MODOS_FALA.findIndex((m) => m.valor === modoFala);
  mudarModoFala(MODOS_FALA[(i + 1) % MODOS_FALA.length].valor).catch((erro) => toast(erro.message));
}, true);
document.addEventListener("keydown", (ev) => {
  const menu = /** @type {HTMLElement} */ (/** @type {HTMLElement} */ (ev.target).closest?.(".escolha-menu"));
  if (ev.key === "Escape" && /** @type {HTMLElement} */ (document.querySelector(".escolha-menu:not([hidden])"))) { fecharEscolhas(); return; }
  if (!menu || !["ArrowDown", "ArrowUp"].includes(ev.key)) return;
  ev.preventDefault();
  const itens = [.../** @type {NodeListOf<HTMLElement>} */ (menu.querySelectorAll(".escolha-item"))], i = itens.indexOf(/** @type {HTMLElement} */ (ev.target));
  itens[(i + (ev.key === "ArrowDown" ? 1 : itens.length - 1)) % itens.length]?.focus();
});

document.addEventListener("click", async (ev) => {
  const b = /** @type {HTMLButtonElement} */ (/** @type {HTMLElement} */ (ev.target).closest("[data-acao]"));
  if (!b || !ACOES[b.dataset.acao]) return;
  try { await ACOES[b.dataset.acao](b, ev); }
  catch (erro) {
    const r = /** @type {HTMLElement} */ (document.querySelector(".resultado:not([data-resultado])"));
    if (r) { r.className = "resultado erro"; r.textContent = erro.message; }
    toast(erro.message);
  }
});

document.addEventListener("change", async (ev) => {
  const el = /** @type {HTMLInputElement} */ (ev.target);
  try {
    if (el.dataset.mudar && MUDAR[el.dataset.mudar]) await MUDAR[el.dataset.mudar](el);
    else if (el.id === "arquivos") { anexar(el.files); el.value = ""; }
  } catch (erro) { toast(erro.message); if (el.type === "checkbox") el.checked = !el.checked; }
});

conteudo.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && (/** @type {HTMLElement} */ (ev.target).dataset.nova || /** @type {HTMLElement} */ (ev.target).dataset.novaConta || /** @type {HTMLElement} */ (ev.target).id === "passo-novo")) { ev.preventDefault(); /** @type {HTMLButtonElement} */ (/** @type {HTMLElement} */ (/** @type {HTMLElement} */ (ev.target).closest(".add")).querySelector("button")).click(); }
});

conteudo.addEventListener("input", (ev) => {
  if (/** @type {HTMLElement} */ (ev.target).id !== "buscar-arquivos") return;
  clearTimeout(buscaPendente);
  buscaPendente = setTimeout(() => buscarArquivos().catch((e) => toast(e.message)), 250);
});

conteudo.addEventListener("paste", (ev) => {
  if (!$("terminal") || !ev.clipboardData?.files.length || /** @type {HTMLElement} */ (ev.target).id === "md-texto") return;
  ev.preventDefault(); anexar(ev.clipboardData.files);
});
for (const tipo of ["dragenter", "dragover"]) conteudo.addEventListener(tipo, (ev) => {
  if (!$("terminal") || !/** @type {DragEvent} */ (ev).dataTransfer?.types.includes("Files")) return;
  ev.preventDefault(); /** @type {HTMLElement} */ (document.querySelector(".conversa"))?.classList.add("soltando");
});
conteudo.addEventListener("dragleave", (ev) => { if (!/** @type {Node} */ (/** @type {DragEvent} */ (ev).relatedTarget) || !conteudo.contains(/** @type {Node} */ (/** @type {DragEvent} */ (ev).relatedTarget))) /** @type {HTMLElement} */ (document.querySelector(".conversa"))?.classList.remove("soltando"); });
conteudo.addEventListener("drop", (ev) => {
  if (!$("terminal") || !/** @type {DragEvent} */ (ev).dataTransfer?.files.length) return;
  ev.preventDefault(); /** @type {HTMLElement} */ (document.querySelector(".conversa"))?.classList.remove("soltando"); anexar(/** @type {DragEvent} */ (ev).dataTransfer.files);
});
