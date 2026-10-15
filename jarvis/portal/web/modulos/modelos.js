// --- Modelos: provedor, modelo e chave ---

/** @type {Record<string, any>} */
let modelo = {};

function desenharChave() {
  const area = $("area-chave");
  if (!area) return;
  $("campo-endereco").hidden = modelo.motor !== "ponte";
  const k = modelo.chaves[modelo.motor] || { usa: false };
  if (!k.usa) {
    area.innerHTML = modelo.motor === "contas" ? '<p class="nota">Usa as contas configuradas em Contas.</p>'
      : modelo.motor === "omniroute" ? '<p class="nota">Usa a conexão do OmniRoute configurada no Cérebro.</p>'
      : contaEmUso(modelo.motor === "codex" ? "codex" : "claude");
    return;
  }
  const estado = k.tem ? `<span class="etiqueta bom">chave guardada · …${esc(k.fim)}</span>` : '<span class="etiqueta alerta">sem chave</span>';
  area.innerHTML = `<div class="linha">${estado}<input id="chave" type="password" class="mono" placeholder="colar chave" autocomplete="off" spellcheck="false">
    ${botao("Guardar chave", "chave-guardar")}${k.tem && k.origem === "painel" ? xis("chave-apagar", "", "Apagar chave") : ""}</div>`;
}

// --- Perfil e acesso ao Claude (também na configuração inicial) ---

let passo = 1;
/** @type {Record<string, any>} */
let acessoTela = {};
let agentes = [];

const seletorAgente = (atual, lista = agentes) => `<div class="segmentos" role="group" aria-label="Agente">${lista.map((a) => a.disponivel
  ? `<button type="button" data-acao="cerebro-escolher" data-agente="${esc(a.id)}" aria-pressed="${a.id === atual}">${esc(a.nome)}</button>`
  : `<button type="button" disabled>${esc(a.nome)} <small>Em breve</small></button>`).join("")}</div>`;

function camposPerfil(cfg) {
  const p = cfg.perfil;
  const opcoes = cfg.fusos.map((f) => `<option value="${esc(f)}" ${f === p.fuso ? "selected" : ""}>${esc(f.replaceAll("_", " "))}</option>`).join("");
  return `<div class="campos">
    <label>Nome<input id="perfil-nome" value="${esc(p.nome)}" maxlength="60" placeholder="Como o Zé deve chamar você" autocomplete="given-name"></label>
    <label>Sobre você<textarea id="perfil-sobre" rows="4" maxlength="2000" placeholder="Profissão, projetos e preferências de trabalho.">${esc(p.sobre)}</textarea></label>
    <label>Fuso horário<select id="perfil-fuso"><option value="" ${p.fuso ? "" : "selected"}>Do sistema (${esc(cfg.fuso_sistema.replaceAll("_", " "))})</option>${opcoes}</select></label>
  </div>`;
}

function prepararAcesso(cfg) {
  acessoTela = { ...cfg.acesso, agentes: cfg.agentes, link: cfg.chave_anthropic, modelo: acessoTela.modelo };
}

// Outra conta, outro plano: as listas de modelos do Cérebro e das Respostas rápidas mudam.
async function modelosDaConta() {
  const c = await api("cerebro");
  Object.assign(acessoTela, completo(c)); modelo.listas = c.listas; desenharAcesso();
  if ($("campo-modelo")) $("campo-modelo").innerHTML = "Modelo" + campoModelo(modelo.motor, valorCampo("modelo")?.value);
}

const completo = (c) => ({ cerebro: c.completo.provedor, modelo: c.completo.modelo, modelos: c.completo.modelos, omniroute: c.completo.omniroute });

// O modelo das Respostas rápidas: lista com a versão para Claude, Codex e Anthropic; campo livre
// para os motores com modelos demais (OpenAI, OpenRouter, Ponte).
function campoModelo(motor, atual) {
  const lista = modelo.listas?.[motor];
  if (!lista?.length) return `<input id="modelo" class="mono" value="${esc(atual || "")}" placeholder="Padrão da conta" autocomplete="off" spellcheck="false">`;
  const escolhido = lista.find((m) => m.id === atual || m.id.includes(`-${atual}-`))?.id || atual || "";
  const opcoes = [...(lista.some((m) => m.id === escolhido) || !escolhido ? [] : [{ id: escolhido, nome: escolhido }]), ...lista];
  return `<select id="modelo">${motor === "codex" ? `<option value="" ${escolhido ? "" : "selected"}>Padrão da conta</option>` : ""}${opcoes.map((m) => `<option value="${esc(m.id)}" ${m.id === escolhido ? "selected" : ""}>${esc(m.nome)}</option>`).join("")}</select>`;
}

// O modelo do cérebro, da mesma lista das sessões; o atual entra mesmo se não estiver nela.
function seletorModelo(a) {
  const lista = a.modelos || [];
  const atual = lista.find((m) => m.id === a.modelo || m.id.includes(`-${a.modelo}-`))?.id || a.modelo || "";
  const opcoes = [...(lista.some((m) => m.id === atual) || !atual ? [] : [{ id: atual, nome: atual }]), ...lista];
  if (!opcoes.length) return `<p class="nota">Modelo: padrão da conta</p>`;
  const padrao = a.cerebro === "codex" ? `<option value="" ${atual ? "" : "selected"}>Padrão da conta</option>` : "";
  return `<label>Modelo<select data-mudar="cerebro-modelo">${padrao}${opcoes.map((m) => `<option value="${esc(m.id)}" ${m.id === atual ? "selected" : ""}>${esc(m.nome)}</option>`).join("")}</select></label>`;
}

// O cérebro pelo OmniRoute de quem usa: endereço e chave; os modelos vêm do próprio OmniRoute.
function cartaoOmni(a) {
  const o = a.omniroute || {}, pronto = o.tem_chave && o.endereco && !a.omniPendente;
  return `<div class="cabeca"><h2>Cérebro</h2><span class="etiqueta ${pronto ? "bom" : "alerta"}">${pronto ? "Configurado" : "Não configurado"}</span></div>
    ${sub("Entende os pedidos com ação e usa as ferramentas do Zé.")}${seletorAgente("omniroute")}
    <div class="linha"><label>Endereço<input id="omni-endereco" class="mono" value="${esc(o.endereco || "")}" placeholder="http://127.0.0.1:20128" autocomplete="off" spellcheck="false"></label>
      <label>Chave de API<input id="omni-chave" type="password" class="mono" placeholder="${o.tem_chave ? "Salva" : "Chave do OmniRoute"}" autocomplete="off" spellcheck="false"></label></div>
    <div class="linha">${botao("Salvar", "omni-salvar", "", "principal")}${a.omniPendente ? "" : botao("Testar conexão", "acesso-testar")}</div>
    ${!a.omniPendente && a.modelos?.length ? seletorModelo(a) : ""}
    <p class="resultado" id="resultado-acesso"></p>`;
}

function desenharAcesso() {
  const area = $("cartao-acesso");
  if (!area) return;
  const a = acessoTela, cerebro = area.dataset.contexto === "cerebro";
  if (cerebro && a.cerebro === "omniroute") { area.innerHTML = cartaoOmni(a); return; }
  const agente = cerebro && a.cerebro === "codex" ? "codex" : "claude";
  const cs = contasTela.agentes.find((x) => x.id === agente);
  const pronto = agente === "codex" ? Boolean(cs?.contas.find((x) => x.id === cs.em_uso)?.logado) : Boolean(a.metodo);
  const estado = pronto ? '<span class="etiqueta bom">Configurado</span>' : '<span class="etiqueta alerta">Não configurado</span>';
  const temChave = a.metodo === "chave" && a.origem === "painel";
  const topo = cerebro
    ? `<div class="cabeca"><h2>Cérebro</h2>${estado}</div>
      ${sub("Entende os pedidos com ação e usa as ferramentas do Zé.")}
      ${seletorAgente(agente)}
      ${seletorModelo(a)}`
    : `<div class="cabeca"><h2>Agente</h2>${estado}</div>
      ${sub("O Zé usa o agente instalado nesta máquina, com o login feito nele.")}`;
  area.innerHTML = `${topo}
    ${contaEmUso(agente)}
    ${agente === "claude" ? `<details class="alternativa" ${temChave ? "open" : ""}><summary>Usar chave de API da Anthropic</summary>
      <div class="linha"><input id="segredo-acesso" type="password" class="mono" placeholder="${temChave ? "•••• " + esc(a.fim) : "Chave de API"}" autocomplete="off" spellcheck="false" aria-label="Chave de API da Anthropic">
        ${botao("Salvar", "acesso-salvar", "", "principal")}${temChave ? botao("Remover", "acesso-remover", "", "discreta") : ""}</div>
      <p class="nota"><a href="${esc(a.link)}" target="_blank" rel="noopener">Obter chave de API ↗</a> Pago por uso; vence o login quando preenchida.</p>
    </details>` : ""}
    <div class="linha">${botao("Testar conexão", "acesso-testar")}</div>
    <p class="resultado" id="resultado-acesso"></p>`;
}

const lerPerfil = () => ({ nome: valorCampo("perfil-nome").value, sobre: valorCampo("perfil-sobre").value, fuso: valorCampo("perfil-fuso").value });



// --- Contas dos agentes (ADR 0016): cada conta é uma pasta de login do próprio agente ---

let contasTela = { agentes: [] };
let vigiaContas = null;

function contaEmUso(agente) {
  const ag = contasTela.agentes.find((x) => x.id === agente);
  const c = ag?.contas.find((x) => x.id === ag.em_uso);
  if (!c) return "";
  return `<p class="nota">Conta: <strong>${esc(c.nome)}</strong>${c.email ? ` · ${esc(c.email)}` : ""}${c.logado ? "" : " · sem login"}</p>`;
}

function linhaConta(ag, c) {
  const emUso = ag.em_uso === c.id;
  const estado = emUso && c.logado ? '<span class="etiqueta bom">Em uso</span>'
    : c.logado ? '<span class="etiqueta">Conectada</span>' : '<span class="etiqueta alerta">Sem login</span>';
  const detalhe = c.logado ? [c.email, c.plano && c.plano[0].toUpperCase() + c.plano.slice(1)].filter(Boolean).map(esc).join(" · ")
    : `Entre pelo ${esc(ag.nome)}: <code>${esc(c.comando)}</code>`;
  const dados = `data-id="${esc(c.id)}"`;
  const acoes = (c.logado && !emUso ? botao("Usar", "conta-usar", dados) : "")
    + botao(c.logado ? "Trocar login" : "Entrar", "conta-entrar", dados, c.logado ? "discreta" : "principal")
    + (c.padrao ? "" : xis("conta-remover", dados, "Remover conta"));
  return item(esc(c.nome), detalhe, estado + acoes);
}

function desenharContas() {
  const area = $("cartao-contas");
  if (!area) return;
  area.innerHTML = `<div class="cabeca"><h2>Contas</h2></div>
    ${sub("Contas dos agentes nesta máquina. O login é feito no próprio agente; o Zé só usa.")}
    ${contasTela.agentes.map((ag) => `<h3 class="subtitulo">${esc(ag.nome)}${ag.instalado ? "" : ' <span class="etiqueta">Não instalado</span>'}</h3>
      <div class="itens">${ag.contas.map((c) => linhaConta(ag, c)).join("")}</div>
      <div class="add"><input data-nova-conta="${esc(ag.id)}" placeholder="Nome de outra conta do ${esc(ag.nome)}" maxlength="40" autocomplete="off">${botao("Adicionar", "conta-adicionar", `data-agente="${esc(ag.id)}"`)}</div>`).join("")}
    <p class="resultado" id="resultado-contas"></p>`;
}

async function recarregarContas() {
  contasTela = await api("contas");
  desenharContas(); desenharAcesso();
}

// Depois de "Entrar", a tela confere sozinha por alguns minutos até o login aparecer.
function vigiarContas() {
  clearInterval(vigiaContas);
  let voltas = 0;
  vigiaContas = setInterval(async () => {
    if (++voltas > 60 || !$("cartao-contas")) { clearInterval(vigiaContas); return; }
    try { await recarregarContas(); } catch { /* o batimento mostra se o Zé caiu */ }
  }, 3000);
}

// --- Escuta: a chave do Deepgram ---

let escuta = {};

function desenharEscuta() {
  const area = $("cartao-escuta");
  if (!area) return;
  const k = escuta.deepgram;
  const estado = k.tem ? '<span class="etiqueta bom">Configurado</span>' : '<span class="etiqueta alerta">Não configurado</span>';
  area.innerHTML = `<div class="cabeca"><h2>Reconhecimento de fala</h2>${estado}<a class="externo" href="${esc(escuta.cadastro)}" target="_blank" rel="noopener">Obter chave de API ↗</a></div>
    ${sub("Deepgram. Converte a fala em texto nos comandos de voz.")}
    <div class="linha"><input id="chave-escuta" type="password" class="mono" placeholder="${k.tem ? "•••• " + esc(k.fim) : "Chave de API"}" autocomplete="off" spellcheck="false" aria-label="Chave de API do Deepgram">
      ${botao("Salvar", "escuta-guardar", "", "principal")}${botao("Testar conexão", "escuta-testar")}${k.tem ? botao("Remover", "escuta-apagar", "", "discreta") : ""}</div>
    <p class="resultado" id="resultado-escuta"></p>`;
}

const lerModelo = () => ({ ligada: /** @type {HTMLInputElement} */ (document.querySelector('[data-mudar="via-ligada"]')).checked, motor: modelo.motor, modelo: valorCampo("modelo").value.trim(), endereco: valorCampo("endereco").value.trim() });

