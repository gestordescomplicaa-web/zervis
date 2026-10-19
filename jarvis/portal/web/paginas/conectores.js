// A página Conectores (MCP), carregada sob demanda pelo painel: usa as funções dele.

const PERMISSAO = { pergunta: "pede aprovação", livre: "livre", bloqueada: "bloqueada" };
const ESPERA_LOGIN_MS = 2000;
const LIMITE_LOGIN_MS = 10 * 60 * 1000; // o login em andamento vale 10 minutos (mcp_oauth.py)
let esperaLogin = 0;

/** Acompanha o login até o cartão ficar Conectado: a aba do fornecedor volta ao painel e fecha. */
function aguardarLogin(nome) {
  clearInterval(esperaLogin);
  const ate = Date.now() + LIMITE_LOGIN_MS;
  esperaLogin = setInterval(async () => {
    if (location.hash !== "#conectores" || Date.now() > ate) { clearInterval(esperaLogin); return; }
    try {
      const { conectores } = await api("conectores");
      if (conectores.find((k) => k.nome === nome)?.conectado) {
        clearInterval(esperaLogin);
        toast("Conectado. Aplique para valer na conversa.");
        await recarregar();
      }
    } catch { /* o próximo ciclo tenta de novo */ }
  }, ESPERA_LOGIN_MS);
}

PAGINAS.conectores = async () => {
    const { conectores, pendente } = await api("conectores");
    conectoresVistos = conectores;
    return `${cabeca("Conectores", botao("Adicionar", "conector-novo", "", "principal"))}${sub("Ligações do Zé com outros sistemas, por MCP.")}
      ${pendente ? `<div class="faixa"><span>Há mudanças ainda não aplicadas.</span>${botao("Aplicar agora", "conectores-aplicar", "", "principal")}</div>` : ""}
      <section class="cartao" id="form-conector" hidden></section>
      ${conectores.map(cartaoConector).join("") || vazio("Nenhum conector.")}`;
  };

let conectoresVistos = [];

function cartaoConector(k) {
  const id = `data-nome="${esc(k.nome)}"`;
  const segredos = Object.entries(k.segredos).map(([v, tem]) => `<div class="linha segredo"><span class="mono">${esc(v)}</span>
      <span class="etiqueta ${tem ? "bom" : "alerta"}">${tem ? "guardado" : "falta"}</span>
      <input type="password" class="mono" data-segredo="${esc(v)}" placeholder="valor" autocomplete="off">${botao("Guardar", "conector-segredo", `${id} data-variavel="${esc(v)}"`)}</div>`).join("");
  const login = k.oauth ? `<div class="linha segredo"><span>Login</span>
      <span class="etiqueta ${k.conectado ? "bom" : "alerta"}">${k.conectado ? "Conectado" : "Não conectado"}</span>
      ${k.conectado ? botao("Sair", "conector-sair", id) : botao("Entrar", "conector-entrar", id, "principal")}</div>
    <div class="login-conector" data-login="${esc(k.nome)}" hidden></div>` : "";
  return `<section class="cartao conector">
    <div class="cabeca"><h2>${esc(k.nome)}</h2><span class="etiqueta">${k.tipo === "http" ? "Remoto" : "Local"}</span>${k.origem === "arquivo" ? '<span class="etiqueta">arquivo de config</span>' : ""}
      ${liga(k.ligado, "conector", id, "Ligado")}</div>
    ${segredos}${login}
    <div class="botoes">${botao("Ferramentas", "conector-testar", id)}${k.origem === "painel" ? xis("conector-remover", id, "Remover") : ""}<span class="resultado" data-resultado="${esc(k.nome)}"></span></div>
    <div class="ferramentas-mcp" data-ferramentas="${esc(k.nome)}" hidden></div>
    <details class="detalhes"><summary>Detalhes</summary><p class="mono quebra">${esc(k.tipo === "http" ? k.url : [k.comando, ...k.argumentos].join(" "))}</p>
      ${k.origem === "painel" ? `<div class="linha"><label>Sessões de código (projetos)<input class="mono" data-projetos="${esc(k.nome)}" value="${esc(k.projetos.join(", "))}" placeholder="Nenhum" autocomplete="off" spellcheck="false"></label>${botao("Salvar", "conector-projetos", id)}</div>` : `<p>Sessões de código: ${esc(k.projetos.join(", ") || "nenhuma")}</p>`}</details></section>`;
}

function permissoes(nome, ferramentas, k) {
  const estado = (f) => (k.livres.includes(f) ? "livre" : k.bloqueadas.includes(f) ? "bloqueada" : "pergunta");
  const editavel = k.origem === "painel";
  return `<div class="itens">${ferramentas.map((f) => item(`<span class="mono">${esc(f.nome)}</span>`, esc(f.descricao),
      `<select data-permissao="${esc(f.nome)}" ${editavel ? "" : "disabled"}>${Object.entries(PERMISSAO).map(([v, r]) => `<option value="${v}" ${estado(f.nome) === v ? "selected" : ""}>${r}</option>`).join("")}</select>`)).join("")}</div>
    ${editavel ? botao("Salvar permissões", "conector-permissoes", `data-nome="${esc(nome)}"`) : sub("Este vem do arquivo de config: as permissões se ajustam lá.")}`;
}

const linhasDe = (t) => t.split("\n").map((l) => l.trim()).filter(Boolean);
const listaDe = (t) => t.split(",").map((v) => v.trim()).filter(Boolean);

/** O conector como o painel grava, com uma parte trocada (permissões ou projetos). */
const dadosDe = (k, troca) => ({ nome: k.nome, tipo: k.tipo, comando: k.comando, argumentos: k.argumentos, url: k.url, ambiente: k.ambiente, cabecalhos: k.cabecalhos, livres: k.livres, bloqueadas: k.bloqueadas, projetos: k.projetos, oauth: k.oauth, ...troca });

function formConector() {
  const f = $("form-conector");
  f.hidden = false;
  f.innerHTML = `<h2>Novo conector</h2>
    <div class="linha"><label>Nome<input id="cx-nome" class="mono" placeholder="github" autocomplete="off" spellcheck="false"></label></div>
    <div class="segmentos" role="group" aria-label="Tipo">${botao("Local", "cx-tipo", 'data-tipo="stdio" aria-pressed="true"')}${botao("Remoto", "cx-tipo", 'data-tipo="http" aria-pressed="false"')}</div>
    <label data-local>Comando<input id="cx-comando" class="mono" placeholder="npx" autocomplete="off" spellcheck="false"></label>
    <label data-local>Argumentos (um por linha)<textarea id="cx-argumentos" class="mono" rows="3"></textarea></label>
    <label data-remoto hidden>Endereço<input id="cx-url" class="mono" placeholder="https://…/mcp" autocomplete="off" spellcheck="false"></label>
    <label data-remoto hidden>Cabeçalhos (um por linha: Nome: VARIAVEL)<textarea id="cx-cabecalhos" class="mono" rows="2"></textarea></label>
    <label data-remoto hidden class="interruptor"><input type="checkbox" id="cx-oauth"> Login com OAuth</label>
    <label>Segredos que ele precisa (nomes, separados por vírgula)<input id="cx-ambiente" class="mono" placeholder="GITHUB_TOKEN" autocomplete="off" spellcheck="false"></label>
    <label>Sessões de código (projetos, separados por vírgula; * para todos)<input id="cx-projetos" class="mono" placeholder="Nenhum" autocomplete="off" spellcheck="false"></label>
    <div class="linha">${botao("Salvar", "cx-salvar", "", "principal")}${botao("Cancelar", "cx-cancelar", "", "discreta")}<span class="resultado" id="cx-resultado"></span></div>`;
  $("cx-nome").focus();
}

Object.assign(ACOES, {
  "conector-novo": formConector,
  "cx-cancelar": () => { $("form-conector").hidden = true; },
  "cx-tipo": (b) => {
    /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll('[data-acao="cx-tipo"]')).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    const remoto = b.dataset.tipo === "http";
    /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll("[data-local]")).forEach((x) => { x.hidden = remoto; });
    /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll("[data-remoto]")).forEach((x) => { x.hidden = !remoto; });
  },
  "cx-salvar": async (b) => {
    const remoto = /** @type {HTMLElement} */ (document.querySelector('[data-acao="cx-tipo"][aria-pressed="true"]')).dataset.tipo === "http";
    const cab = Object.fromEntries(linhasDe(valorCampo("cx-cabecalhos").value).map((l) => l.split(":").map((x) => x.trim())).filter((p) => p.length === 2));
    await ocupado(b, () => api("conector/salvar", {
      nome: valorCampo("cx-nome").value.trim(), tipo: remoto ? "http" : "stdio", comando: valorCampo("cx-comando").value.trim(),
      argumentos: linhasDe(valorCampo("cx-argumentos").value), url: valorCampo("cx-url").value.trim(), cabecalhos: remoto ? cab : {},
      ambiente: listaDe(valorCampo("cx-ambiente").value), projetos: listaDe(valorCampo("cx-projetos").value),
      oauth: remoto && /** @type {HTMLInputElement} */ ($("cx-oauth")).checked,
    }));
    toast("Conector salvo."); await recarregar();
  },
  "conector-segredo": async (b) => {
    const campo = /** @type {HTMLInputElement} */ (/** @type {HTMLElement} */ (b.closest(".segredo")).querySelector("input"));
    await ocupado(b, () => api("conector/segredo", { nome: b.dataset.nome, variavel: b.dataset.variavel, valor: campo.value }));
    toast("Segredo guardado."); await recarregar();
  },
  "conector-testar": async (b) => {
    const nome = b.dataset.nome;
    const saida = /** @type {HTMLElement} */ (document.querySelector(`[data-resultado="${CSS.escape(nome)}"]`));
    saida.className = "resultado"; saida.textContent = "Conectando…";
    const r = await ocupado(b, () => api("conector/testar", { nome }));
    saida.className = "resultado " + (r.ok ? "ok" : "erro");
    saida.textContent = r.ok ? `${r.ferramentas.length} ferramentas` : r.erro;
    if (r.ok) {
      const area = /** @type {HTMLElement} */ (document.querySelector(`[data-ferramentas="${CSS.escape(nome)}"]`));
      area.innerHTML = permissoes(nome, r.ferramentas, conectoresVistos.find((k) => k.nome === nome));
      area.hidden = false;
    }
  },
  "conector-permissoes": async (b) => {
    const k = conectoresVistos.find((x) => x.nome === b.dataset.nome);
    const escolhas = [.../** @type {NodeListOf<HTMLSelectElement>} */ (/** @type {HTMLElement} */ (b.closest(".ferramentas-mcp")).querySelectorAll("[data-permissao]"))];
    const de = (v) => escolhas.filter((e) => e.value === v).map((e) => e.dataset.permissao);
    await ocupado(b, () => api("conector/salvar", dadosDe(k, { livres: de("livre"), bloqueadas: de("bloqueada") })));
    toast("Permissões salvas."); await recarregar();
  },
  "conector-projetos": async (b) => {
    const k = conectoresVistos.find((x) => x.nome === b.dataset.nome);
    const campo = /** @type {HTMLInputElement} */ (document.querySelector(`[data-projetos="${CSS.escape(k.nome)}"]`));
    await ocupado(b, () => api("conector/salvar", dadosDe(k, { projetos: listaDe(campo.value) })));
    toast("Projetos salvos."); await recarregar();
  },
  "conector-entrar": async (b) => {
    const nome = b.dataset.nome;
    const area = /** @type {HTMLElement} */ (document.querySelector(`[data-login="${CSS.escape(nome)}"]`));
    // A aba abre já no clique (o navegador só permite assim) e segue ao login quando o endereço chega.
    const aba = window.open("about:blank", "_blank");
    if (aba) aba.opener = null; // a página do fornecedor não alcança o painel
    area.hidden = false;
    area.innerHTML = sub("Preparando o login…");
    let r;
    try {
      r = await ocupado(b, () => api("conector/entrar", { nome, retorno: `${location.origin}/oauth/retorno` }));
    } catch (erro) {
      if (aba) aba.close();
      area.hidden = true;
      throw erro;
    }
    const manual = `<details class="detalhes"><summary>A página não voltou ao painel?</summary>
      <div class="linha"><label>Endereço em que a aba parou<input class="mono" data-retorno="${esc(nome)}" autocomplete="off" spellcheck="false"></label>${botao("Concluir", "conector-concluir", `data-nome="${esc(nome)}"`)}</div></details>`;
    if (aba) {
      aba.location.href = r.url;
      area.innerHTML = sub("Aguardando o login na outra aba.") + manual;
    } else {
      area.innerHTML = `${sub("O navegador bloqueou a nova aba.")}<div class="linha"><a class="acao principal" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Abrir login</a></div>${manual}`;
    }
    aguardarLogin(nome);
  },
  "conector-concluir": async (b) => {
    const campo = /** @type {HTMLInputElement} */ (document.querySelector(`[data-retorno="${CSS.escape(b.dataset.nome)}"]`));
    const r = await ocupado(b, () => api("conector/entrar/concluir", { endereco: campo.value }));
    toast(r.aviso); await recarregar();
  },
  "conector-sair": async (b) => { await ocupado(b, () => api("conector/sair", { nome: b.dataset.nome })); await recarregar(); },
  "conector-remover": (b) => confirmar(b, "Remover?", async () => { await api("conector/remover", { nome: b.dataset.nome }); await recarregar(); }),
  "conectores-aplicar": async (b) => { const r = await ocupado(b, () => api("conectores/aplicar", {})); toast(r.aviso); await recarregar(); },
});

Object.assign(MUDAR, {
  conector: async (el) => { await api("conector/ligar", { nome: el.dataset.nome, ligado: el.checked }); await recarregar(); },
});
