// O painel do Zé (docs/plano-painel.md). Uma página, sem framework e sem nada de fora.
// Regras de tela (09/10/2026): tudo em português; cada página tem título, no máximo uma linha
// e a ação principal; o que aparece dá para mexer; detalhe técnico fica em "Detalhes".
// Todo botão diz o que faz em data-acao; um despachante só executa. A regra mora no jarvisd.
"use strict";

const TOKEN = document.querySelector('meta[name="ze-token"]').content;
const conteudo = document.getElementById("conteudo");

const ESTADOS = { inativo: "inativo", ativo: "pronto", ouvindo: "ouvindo", pensando: "pensando", falando: "falando", confirmando: "esperando o seu sim" };
const ESTADO_SESSAO = { parada: "pronta", trabalhando: "trabalhando", erro: "erro" };
const TIPO_AUTOMACAO = { lembrete: "Lembrete", pergunta: "Pergunta ao Zé" };
const PERMISSAO = { pergunta: "pede aprovação", livre: "livre", bloqueada: "bloqueada" };
const NOME_MOTOR = { plano: "Claude (assinatura)", openai: "OpenAI", anthropic: "Anthropic", openrouter: "OpenRouter", ponte: "Ponte" };
const NOME_CEREBRO = { claude: "Claude", gpt: "GPT", gemini: "Gemini", auto: "Automático" };

const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const seg = (ms) => (ms == null ? "—" : (ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " s");
const quando = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const $ = (id) => document.getElementById(id);

async function api(caminho, corpo) {
  const opcoes = { headers: { "X-Ze-Token": TOKEN } };
  if (corpo !== undefined) {
    opcoes.method = "POST";
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  const r = await fetch("/api/" + caminho, opcoes);
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || "falha " + r.status);
  return dados;
}

function toast(texto) {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status"); document.body.append(t); }
  t.textContent = texto;
  t.classList.add("on");
  clearTimeout(toast.prazo);
  toast.prazo = setTimeout(() => t.classList.remove("on"), 2600);
}

async function ocupado(botao, trabalho) {
  if (botao) botao.disabled = true;
  try { return await trabalho(); } finally { if (botao) botao.disabled = false; }
}

// --- pedaços de tela --------------------------------------------------------------------------

const cabeca = (titulo, acoes = "") => `<div class="cabeca"><h1>${titulo}</h1>${acoes}</div>`;
const sub = (texto) => `<p class="sub">${texto}</p>`;
const cartao = (titulo, corpo, extra = "") => `<section class="cartao ${extra}">${titulo ? `<h2>${titulo}</h2>` : ""}${corpo}</section>`;
const vazio = (texto) => `<p class="vazio">${texto}</p>`;
const liga = (ligado, mudar, dados = "", rotulo = "Ligar ou desligar") =>
  `<label class="liga" title="${rotulo}"><input type="checkbox" data-mudar="${mudar}" ${dados} ${ligado ? "checked" : ""} aria-label="${rotulo}"><span></span></label>`;
const botao = (texto, acao, dados = "", classe = "") => `<button type="button" class="acao ${classe}" data-acao="${acao}" ${dados}>${texto}</button>`;
const xis = (acao, dados, rotulo) => `<button type="button" class="x" data-acao="${acao}" ${dados} aria-label="${rotulo}" title="${rotulo}">×</button>`;
const item = (titulo, detalhe, direita = "", apagado = false) =>
  `<div class="linha-item ${apagado ? "apagado" : ""}"><div class="texto">${titulo ? `<strong>${titulo}</strong>` : ""}${detalhe ? (titulo ? `<small>${detalhe}</small>` : `<span>${detalhe}</span>`) : ""}</div>${direita ? `<div class="botoes">${direita}</div>` : ""}</div>`;

// Confirmação dentro da própria tela (o navegador do painel não usa confirm()).
const pendentes = new Map();
function confirmar(el, pergunta, fazer) {
  const id = Math.random().toString(36).slice(2);
  pendentes.set(id, fazer);
  const lugar = el.closest(".botoes") || el.parentElement;
  lugar.dataset.antes = lugar.innerHTML;
  lugar.innerHTML = `<span class="confirmar">${pergunta} ${botao("Sim", "confirmar-sim", `data-id="${id}"`, "perigo")} ${botao("Não", "confirmar-nao", `data-id="${id}"`, "discreta")}</span>`;
}

// --- as páginas ---------------------------------------------------------------------------------

const PAGINAS = {
  async inicio() {
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
  },

  async foco() {
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
  },

  async automacoes() {
    const a = await api("automacoes");
    const repete = (ag) => (/^\d{4}-\d{2}-\d{2}/.test(ag) ? "" : " · " + esc(ag));
    const linhas = a.map((j) => item(esc(j.nome), `${TIPO_AUTOMACAO[j.tipo] || esc(j.tipo)} · ${j.ativo ? quando(j.proxima) : "pausada"}${repete(j.agenda)}`,
      liga(j.ativo, "automacao", `data-id="${esc(j.id)}"`, "Ativa") + xis("automacao-remover", `data-id="${esc(j.id)}"`, "Remover"), !j.ativo));
    return `${cabeca("Automações")}${sub("Para criar, peça ao Zé: “me lembra amanhã às nove de…”.")}
      ${a.length ? `<div class="itens">${linhas.join("")}</div>` : vazio("Nada agendado.")}`;
  },

  async memoria() {
    const m = await api("memoria");
    const bloco = (titulo, alvo, entradas) => {
      const cheio = Math.min(100, Math.round((100 * entradas.join(" § ").length) / m.limites[alvo]));
      const barra = `<span class="cheio" title="Quanto do espaço desta memória já foi usado"><span class="barra"><span data-cheio="${cheio}"></span></span>${cheio}% cheio</span>`;
      return cartao(`${titulo} ${barra}`,
        `<div class="itens">${entradas.map((t) => item("", esc(t), xis("memoria-remover", `data-alvo="${alvo}" data-texto="${esc(t)}"`, "Remover"))).join("") || vazio("Vazia.")}</div>
         <div class="add"><input data-nova="${alvo}" placeholder="Algo para o Zé lembrar sempre" autocomplete="off">${botao("Adicionar", "memoria-adicionar", `data-alvo="${alvo}"`)}</div>`);
    };
    return `${cabeca("Memória")}${sub("O que o Zé sabe em toda conversa. Mudanças valem a partir da próxima conversa.")}
      ${bloco("Sobre você", "usuario", m.usuario)}${bloco("Sobre a máquina e o Zé", "jarvis", m.jarvis)}`;
  },

  async skills() {
    const s = await api("skills");
    const linhas = s.map((k) => item(esc(k.nome), esc(k.descricao),
      liga(k.ligada, "skill", `data-nome="${esc(k.nome)}"`, "Ligada") + botao("Editar", "skill-editar", `data-nome="${esc(k.nome)}"`, "discreta") + xis("skill-excluir", `data-nome="${esc(k.nome)}"`, "Excluir"), !k.ligada));
    return `${cabeca("Skills", botao("Nova skill", "skill-nova", "", "principal"))}${sub("Do seu jeito: o Zé e as sessões seguem antes de agir.")}
      <section class="cartao" id="editor-skill" hidden></section>
      ${s.length ? `<div class="itens">${linhas.join("")}</div>` : vazio("Nenhuma skill ainda.")}`;
  },

  async conectores() {
    const { conectores, pendente } = await api("conectores");
    conectoresVistos = conectores;
    return `${cabeca("Conectores", botao("Adicionar", "conector-novo", "", "principal"))}${sub("Ligações do Zé com outros sistemas, por MCP.")}
      ${pendente ? `<div class="faixa"><span>Há mudanças ainda não aplicadas.</span>${botao("Aplicar agora", "conectores-aplicar", "", "principal")}</div>` : ""}
      <section class="cartao" id="form-conector" hidden></section>
      ${conectores.map(cartaoConector).join("") || vazio("Nenhum conector.")}`;
  },

  async modelos() {
    const [c, esc_] = await Promise.all([api("cerebro"), api("escuta")]);
    modelo = { ...c.via, chaves: c.chaves };
    escuta = esc_;
    return `${cabeca("Modelos")}
      <section class="cartao" id="cartao-escuta"></section>
      ${cartao("", `<div class="cabeca"><h2>Respostas rápidas</h2>${liga(c.via.ligada, "via-ligada", "", "Ligadas")}</div>
        ${sub("Conversa simples vai a um modelo rápido; o resto, ao cérebro principal.")}
        <div class="segmentos" role="group" aria-label="Provedor">${c.motores.map((m) => `<button type="button" data-acao="motor" data-motor="${m.id}" data-modelo="${esc(m.modelo)}" aria-pressed="${m.id === c.via.motor}">${esc(NOME_MOTOR[m.id] || m.nome)}</button>`).join("")}</div>
        <div class="linha"><label>Modelo<input id="modelo" class="mono" value="${esc(c.via.modelo)}" autocomplete="off" spellcheck="false"></label>
          <label id="campo-endereco">Endereço<input id="endereco" class="mono" value="${esc(c.via.endereco)}" placeholder="http://127.0.0.1:20128/v1" autocomplete="off" spellcheck="false"></label></div>
        <div id="area-chave"></div>
        <div class="linha">${botao("Salvar", "modelo-salvar", "", "principal")}${botao("Testar", "modelo-testar")}<span class="resultado" id="resultado"></span></div>`)}
      ${cartao("Cérebro principal", `<p><strong>${esc(NOME_CEREBRO[c.completo.provedor] || c.completo.provedor)}</strong> <span class="mono">${esc(c.completo.modelo)}</span></p>${sub("Usado quando o pedido precisa de ferramentas.")}`)}`;
  },

  async voz() {
    const [e, o] = await Promise.all([api("estado"), api("escuta")]);
    const etiqueta = (ok, sim, nao) => `<span class="etiqueta ${ok ? "bom" : "alerta"}">${ok ? sim : nao}</span>`;
    const linha = (titulo, estado, texto) => cartao("", `<div class="cabeca"><h2>${titulo}</h2>${estado}</div>${sub(texto)}`);
    return `${cabeca("Voz")}
      ${linha("Palavra de ativação", etiqueta(o.ativacao, "Ativa", "Não treinada"), o.ativacao ? "“Ei Zé”." : "“Ei Zé”. Necessária para os comandos de voz.")}
      ${linha("Reconhecimento de fala", etiqueta(o.deepgram.tem, "Configurado", "Não configurado"), o.deepgram.tem ? "Deepgram." : 'Deepgram. Configure em <a href="#modelos">Modelos</a>.')}
      ${linha("Síntese de voz", etiqueta(true, "Ativa", ""), "Piper, voz Cadu (pt-BR). Processamento local.")}
      ${cartao("", `<div class="cabeca"><h2>Conversa contínua</h2><span class="etiqueta">Em breve</span></div>${sub("Escuta contínua com interrupção.")}`)}`;
  },
};

// --- Modelos: provedor, modelo e chave ---------------------------------------------------------------

let modelo = {};

function desenharChave() {
  const area = $("area-chave");
  if (!area) return;
  $("campo-endereco").hidden = modelo.motor !== "ponte";
  const k = modelo.chaves[modelo.motor] || { usa: false };
  if (!k.usa) { area.innerHTML = ""; return; }
  const estado = k.tem ? `<span class="etiqueta bom">chave guardada · …${esc(k.fim)}</span>` : '<span class="etiqueta alerta">sem chave</span>';
  area.innerHTML = `<div class="linha">${estado}<input id="chave" type="password" class="mono" placeholder="colar chave" autocomplete="off" spellcheck="false">
    ${botao("Guardar chave", "chave-guardar")}${k.tem && k.origem === "painel" ? xis("chave-apagar", "", "Apagar chave") : ""}</div>`;
}

// --- Escuta: a chave do Deepgram -------------------------------------------------------------------

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

const lerModelo = () => ({ ligada: document.querySelector('[data-mudar="via-ligada"]').checked, motor: modelo.motor, modelo: $("modelo").value.trim(), endereco: $("endereco").value.trim() });

// --- Conectores ------------------------------------------------------------------------------------

let conectoresVistos = [];

function cartaoConector(k) {
  const id = `data-nome="${esc(k.nome)}"`;
  const segredos = Object.entries(k.segredos).map(([v, tem]) => `<div class="linha segredo"><span class="mono">${esc(v)}</span>
      <span class="etiqueta ${tem ? "bom" : "alerta"}">${tem ? "guardado" : "falta"}</span>
      <input type="password" class="mono" data-segredo="${esc(v)}" placeholder="valor" autocomplete="off">${botao("Guardar", "conector-segredo", `${id} data-variavel="${esc(v)}"`)}</div>`).join("");
  return `<section class="cartao conector">
    <div class="cabeca"><h2>${esc(k.nome)}</h2><span class="etiqueta">${k.tipo === "http" ? "Remoto" : "Local"}</span>${k.origem === "arquivo" ? '<span class="etiqueta">arquivo de config</span>' : ""}
      ${liga(k.ligado, "conector", id, "Ligado")}</div>
    ${segredos}
    <div class="botoes">${botao("Ferramentas", "conector-testar", id)}${k.origem === "painel" ? xis("conector-remover", id, "Remover") : ""}<span class="resultado" data-resultado="${esc(k.nome)}"></span></div>
    <div class="ferramentas-mcp" data-ferramentas="${esc(k.nome)}" hidden></div>
    <details class="detalhes"><summary>Detalhes</summary><p class="mono quebra">${esc(k.tipo === "http" ? k.url : [k.comando, ...k.argumentos].join(" "))}</p></details></section>`;
}

function permissoes(nome, ferramentas, k) {
  const estado = (f) => (k.livres.includes(f) ? "livre" : k.bloqueadas.includes(f) ? "bloqueada" : "pergunta");
  const editavel = k.origem === "painel";
  return `<div class="itens">${ferramentas.map((f) => item(`<span class="mono">${esc(f.nome)}</span>`, esc(f.descricao),
      `<select data-permissao="${esc(f.nome)}" ${editavel ? "" : "disabled"}>${Object.entries(PERMISSAO).map(([v, r]) => `<option value="${v}" ${estado(f.nome) === v ? "selected" : ""}>${r}</option>`).join("")}</select>`)).join("")}</div>
    ${editavel ? botao("Salvar permissões", "conector-permissoes", `data-nome="${esc(nome)}"`) : sub("Este vem do arquivo de config: as permissões se ajustam lá.")}`;
}

const linhasDe = (t) => t.split("\n").map((l) => l.trim()).filter(Boolean);

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
    <label>Segredos que ele precisa (nomes, separados por vírgula)<input id="cx-ambiente" class="mono" placeholder="GITHUB_TOKEN" autocomplete="off" spellcheck="false"></label>
    <div class="linha">${botao("Salvar", "cx-salvar", "", "principal")}${botao("Cancelar", "cx-cancelar", "", "discreta")}<span class="resultado" id="cx-resultado"></span></div>`;
  $("cx-nome").focus();
}

// --- Skills ---------------------------------------------------------------------------------------------

const MODELO_SKILL = (nome) => `---
name: ${nome}
description: Quando usar (uma linha).
---
# ${nome}

## Do meu jeito
-

## Passos
1.

## Pronto quando
-
`;

function editorSkill(nome, texto, nova) {
  const ed = $("editor-skill");
  ed.hidden = false;
  ed.innerHTML = `<h2>${nova ? "Nova skill" : esc(nome)}</h2>
    ${nova ? '<label>Nome<input id="sk-nome" class="mono" placeholder="publicar-no-site" autocomplete="off" spellcheck="false"></label>' : ""}
    <textarea id="sk-texto" class="mono editor-texto" rows="16" spellcheck="false">${esc(texto)}</textarea>
    <div class="linha">${botao("Salvar", "skill-salvar", `data-nome="${esc(nome)}"`, "principal")}${botao("Fechar", "skill-fechar", "", "discreta")}<span class="resultado" id="sk-resultado"></span></div>`;
  ed.scrollIntoView({ block: "nearest" });
}

// --- Sessões: agentes de código com pasta, conversa, anexos e explorador ------------------------

let sessaoAberta = null;
let vistas = 0;
let relogioSessoes = null;
let anexos = [];
let explorador = innerWidth > 1100;
let abertas = new Set();
let modoBusca = "nomes";
let buscaPendente = null;

const matiz = (t) => [...t].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const inicial = (n) => esc((n.trim()[0] || "?").toUpperCase());
const ha = (iso) => { const s = (Date.now() - new Date(iso)) / 1000; return s < 60 ? "agora" : s < 3600 ? Math.floor(s / 60) + " min" : s < 86400 ? Math.floor(s / 3600) + " h" : Math.floor(s / 86400) + " d"; };
const leve = (t) => esc(t).replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>").replace(/`([^`\n]+)`/g, "<code>$1</code>");
const encher = () => document.querySelectorAll("[data-cheio]").forEach((b) => b.style.setProperty("--cheio", b.dataset.cheio + "%"));
const pintar = (raiz) => raiz.querySelectorAll(".avatar[data-matiz]").forEach((a) => a.style.setProperty("--matiz", a.dataset.matiz));

PAGINAS.sessoes = async () => `<div class="sessoes">
  <aside class="sessoes-lista"><div class="sessoes-topo"><p class="rotulo">Sessões</p><button type="button" class="mais" data-acao="sessao-nova" aria-label="Nova sessão">+</button></div><div id="lista-sessoes"></div></aside>
  <div id="lado-sessao" class="lado"><div class="nova-sessao">${vazio("Escolha uma sessão ou crie uma no +.")}</div></div></div>`;

const itemSessao = (s) => `<button type="button" class="item-sessao" data-acao="sessao-abrir" data-id="${s.id}" aria-current="${s.id === sessaoAberta}">
  <span class="avatar ${s.estado === "trabalhando" ? "trabalhando" : ""}" data-matiz="${matiz(s.nome)}">${inicial(s.nome)}</span>
  <strong>${esc(s.nome)}</strong><time>${ha(s.atualizada)}</time><small>${s.estado === "trabalhando" ? "trabalhando…" : esc(s.resumo || s.pasta)}</small></button>`;

async function listaSessoes() {
  const lista = $("lista-sessoes");
  if (!lista) return;
  const sessoes = await api("sessoes");
  lista.innerHTML = sessoes.length ? sessoes.map(itemSessao).join("") : vazio("Nenhuma sessão.");
  pintar(lista);
  $("ponto-sessoes").hidden = !sessoes.some((s) => s.estado === "trabalhando");
}

function linhaMensagem(m) {
  const chips = (m.anexos || []).map((a) => `<span class="anexo">📎 ${esc(a.replace(/^\d{6}-[0-9a-f]{4}-/, ""))}</span>`).join("");
  return `<div class="msg ${esc(m.quem)}">${m.quem === "agente" ? leve(m.texto) : esc(m.texto)}${chips ? `<div class="anexos">${chips}</div>` : ""}</div>`;
}

async function formSessao() {
  const pastas = await api("pastas");
  $("lado-sessao").innerHTML = `<div class="nova-sessao">${cartao("Nova sessão", `
    <label>Nome<input id="ns-nome" placeholder="Ligatia — testes" autocomplete="off"></label>
    <div class="segmentos" role="group" aria-label="Onde">${botao("Pasta existente", "ns-onde", 'data-onde="existente" aria-pressed="true"')}${botao("Projeto novo", "ns-onde", 'data-onde="novo" aria-pressed="false"')}</div>
    <label id="ns-campo-pasta">Pasta<input id="ns-pasta" class="mono" list="ns-pastas" placeholder="~/projetos/…" autocomplete="off" spellcheck="false"></label>
    <datalist id="ns-pastas">${pastas.map((p) => `<option value="${esc(p)}">`).join("")}</datalist>
    <label id="ns-campo-projeto" hidden>Nome da pasta<input id="ns-projeto" class="mono" placeholder="minha-loja" autocomplete="off" spellcheck="false"></label>
    <label class="interruptor" id="ns-campo-isolada"><input type="checkbox" id="ns-isolada"> Cópia isolada (só mexe no projeto quando você aprovar)</label>
    <div class="linha">${botao("Criar", "ns-criar", "", "principal")}<span class="resultado" id="ns-resultado"></span></div>`)}</div>`;
}

async function abrirSessao(id) {
  sessaoAberta = id;
  vistas = 0;
  document.querySelectorAll(".item-sessao").forEach((b) => b.setAttribute("aria-current", String(b.dataset.id === id)));
  const { sessao, mensagens } = await api("sessao/ler", { id, desde: 0 });
  const lado = $("lado-sessao");
  const trabalhando = sessao.estado === "trabalhando";
  lado.innerHTML = `<div class="sessao-aberta ${explorador ? "" : "sem-explorador"}"><section class="conversa">
    <header class="conversa-topo"><span class="avatar" data-matiz="${matiz(sessao.nome)}">${inicial(sessao.nome)}</span>
      <h2>${esc(sessao.nome)}</h2><span class="etiqueta ${trabalhando ? "bom" : ""}" id="estado-sessao" data-estado="${esc(sessao.estado)}">${ESTADO_SESSAO[sessao.estado] || esc(sessao.estado)}</span>
      <div class="botoes">${botao("Novo arquivo", "md-abrir")}${botao("Arquivos", "explorador", `aria-pressed="${explorador}"`)}
        ${botao("Parar", "sessao-parar", trabalhando ? "" : "hidden", "discreta")}${xis("sessao-excluir", "", "Excluir sessão")}</div></header>
    <div class="mensagens" id="mensagens">${mensagens.map(linhaMensagem).join("")}</div>
    <section class="previa-arquivo" id="previa" hidden></section>
    <form class="compor" id="compor">
      <section class="editor-md" id="editor-md" hidden>
        <div class="linha"><label>Arquivo<input id="md-nome" class="mono" placeholder="NOTAS.md" autocomplete="off" spellcheck="false"></label>
          <label class="interruptor"><input type="checkbox" id="md-substituir"> Substituir se existir</label></div>
        <textarea id="md-texto" class="mono" rows="10"></textarea>
        <div class="linha">${botao("Salvar na pasta", "md-salvar", "", "principal")}${botao("Cancelar", "md-fechar", "", "discreta")}</div>
      </section>
      <div class="pendentes" id="anexos" hidden></div>
      <textarea id="texto-sessao" placeholder="O que você precisa?" rows="2"></textarea>
      <div class="compor-rodape"><button type="button" class="mais" data-acao="anexar" aria-label="Anexar arquivo" title="Anexar (ou arraste, ou cole uma imagem)">+</button><input type="file" id="arquivos" multiple hidden>
        <small>${esc(sessao.pasta)}${sessao.branch ? " · cópia isolada" : ""}</small>
        <button type="submit" class="acao principal">Enviar</button></div>
    </form></section>
    <aside class="explorador" aria-label="Arquivos">
      <header><strong title="${esc(sessao.pasta)}">${esc(sessao.pasta.split("/").pop())}</strong>
        <button type="button" class="icone" data-acao="arvore-recolher" title="Recolher tudo" aria-label="Recolher tudo">⇤</button>
        <button type="button" class="icone" data-acao="arvore-atualizar" title="Atualizar" aria-label="Atualizar">↻</button>
        <button type="button" class="icone" id="fechar-explorador" data-acao="explorador" title="Voltar à conversa" aria-label="Voltar à conversa">✕</button></header>
      <input id="buscar-arquivos" type="search" placeholder="Buscar" autocomplete="off" spellcheck="false">
      <div class="seg" role="group" aria-label="Buscar por">${botao("Nome", "busca-modo", 'data-modo="nomes" aria-pressed="true"')}${botao("Conteúdo", "busca-modo", 'data-modo="conteudo" aria-pressed="false"')}</div>
      <div class="arvore" id="arvore" role="tree"></div>
    </aside></div>`;
  pintar(lado);
  limparAnexos();
  abertas = new Set();
  vistas = mensagens.length;
  const caixa = $("mensagens");
  caixa.scrollTop = caixa.scrollHeight;
  await carregarPasta("", $("arvore"));
  $("texto-sessao").focus();
}

async function acompanharSessao() {
  if (!sessaoAberta || !$("mensagens")) return;
  const { sessao, mensagens } = await api("sessao/ler", { id: sessaoAberta, desde: vistas });
  const caixa = $("mensagens");
  if (mensagens.length) {
    const noFim = caixa.scrollHeight - caixa.scrollTop - caixa.clientHeight < 80;
    caixa.insertAdjacentHTML("beforeend", mensagens.map(linhaMensagem).join(""));
    vistas += mensagens.length;
    if (noFim) caixa.scrollTop = caixa.scrollHeight;
  }
  const etiqueta = $("estado-sessao");
  if (etiqueta.dataset.estado === "trabalhando" && sessao.estado !== "trabalhando") atualizarArvore();
  etiqueta.dataset.estado = sessao.estado;
  etiqueta.textContent = ESTADO_SESSAO[sessao.estado] || sessao.estado;
  etiqueta.classList.toggle("bom", sessao.estado === "trabalhando");
  document.querySelector('[data-acao="sessao-parar"]').hidden = sessao.estado !== "trabalhando";
}

async function prepararSessoes() {
  await listaSessoes();
  if (sessaoAberta) await abrirSessao(sessaoAberta).catch(() => { sessaoAberta = null; });
  let volta = 0;
  relogioSessoes = setInterval(async () => {
    try { await acompanharSessao(); if (++volta % 2 === 0) await listaSessoes(); } catch { /* o batimento mostra se o Zé caiu */ }
  }, 1500);
}

// anexos: arrastar, colar ou "+"
function desenharAnexos() {
  const area = $("anexos");
  if (!area) return;
  area.hidden = !anexos.length;
  area.replaceChildren(...anexos.map((p, i) => {
    const chip = document.createElement("span");
    chip.className = "pendente";
    if (p.previa) { const img = document.createElement("img"); img.src = p.previa; img.alt = ""; chip.append(img); }
    chip.append(p.arquivo.name);
    const tirar = document.createElement("button");
    tirar.type = "button"; tirar.textContent = "×"; tirar.dataset.acao = "anexo-tirar"; tirar.dataset.i = String(i);
    tirar.setAttribute("aria-label", "Tirar " + p.arquivo.name);
    chip.append(tirar);
    return chip;
  }));
}

function anexar(lista) {
  for (const a of lista) {
    if (anexos.length >= 10) { toast("No máximo dez anexos."); break; }
    if (a.size > 20 * 1024 * 1024) { toast(a.name + ": maior que 20 MB."); continue; }
    const f = a.name ? a : new File([a], "colado-" + Date.now() + "." + (a.type.split("/")[1] || "png"), { type: a.type });
    anexos.push({ arquivo: f, previa: f.type.startsWith("image/") ? URL.createObjectURL(f) : "" });
  }
  desenharAnexos();
}

function limparAnexos() { anexos.forEach((p) => p.previa && URL.revokeObjectURL(p.previa)); anexos = []; desenharAnexos(); }

async function subirAnexo(arquivo) {
  const r = await fetch(`/api/sessao/anexo?id=${encodeURIComponent(sessaoAberta)}&nome=${encodeURIComponent(arquivo.name)}`,
    { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: arquivo });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(arquivo.name + ": " + (dados.erro || "falha"));
  return dados.anexo;
}

// explorador
const noArvore = (i) => `<div class="no ${i.pasta ? "pasta" : ""} ${i.ignorado ? "ignorado" : ""}" role="treeitem" data-caminho="${esc(i.caminho)}" ${i.pasta ? 'aria-expanded="false"' : ""}>
  <button type="button" class="linha-no" data-acao="no" data-caminho="${esc(i.caminho)}"><span class="seta">${i.pasta ? "›" : ""}</span><span class="nome-no">${esc(i.nome)}</span>${i.ignorado ? '<span class="sinal" title="ignorado pelo git">⊘</span>' : ""}</button>
  ${i.pasta ? '<div class="filhos" role="group"></div>' : ""}</div>`;

async function carregarPasta(caminho, recipiente) {
  const { itens } = await api("sessao/arquivos", { id: sessaoAberta, pasta: caminho });
  recipiente.innerHTML = itens.length ? itens.map(noArvore).join("") : vazio("vazia");
  for (const sub of abertas) {
    const no = recipiente.querySelector(`:scope > .no[data-caminho="${CSS.escape(sub)}"]`);
    if (no) await abrirPastaNo(no);
  }
}

async function abrirPastaNo(no) {
  no.setAttribute("aria-expanded", "true");
  abertas.add(no.dataset.caminho);
  await carregarPasta(no.dataset.caminho, no.querySelector(".filhos"));
}

async function atualizarArvore() {
  if (!$("arvore")) return;
  if ($("buscar-arquivos").value.trim()) await buscarArquivos(); else await carregarPasta("", $("arvore"));
}

async function buscarArquivos() {
  const termo = $("buscar-arquivos").value.trim();
  if (termo.length < 2) { await carregarPasta("", $("arvore")); return; }
  const { achados } = await api("sessao/buscar", { id: sessaoAberta, termo, modo: modoBusca });
  $("arvore").innerHTML = achados.length
    ? achados.map((a) => `<button type="button" class="achado" data-acao="ver-arquivo" data-caminho="${esc(a.caminho)}"><span class="mono">${esc(a.caminho)}${a.linha ? ":" + a.linha : ""}</span>${a.trecho ? `<small>${esc(a.trecho)}</small>` : ""}</button>`).join("")
    : vazio("Nada encontrado.");
}

async function verArquivo(caminho) {
  const a = await api("sessao/ver", { id: sessaoAberta, caminho });
  const corpo = a.tipo === "texto" ? `<pre class="codigo">${esc(a.texto)}</pre>` : a.tipo === "imagem" ? `<img class="imagem-previa" src="${a.url}" alt="">` : vazio(a.tipo === "grande" ? "Imagem grande demais." : "Sem prévia.");
  $("previa").innerHTML = `<header><span class="mono">${esc(caminho)}</span>${botao("Mencionar", "mencionar", `data-caminho="${esc(caminho)}"`)}${botao("Fechar", "previa-fechar", "", "discreta")}</header>${corpo}`;
  $("previa").hidden = false;
  $("mensagens").hidden = true;
}

function fecharPrevia() {
  if ($("previa")) { $("previa").hidden = true; $("previa").innerHTML = ""; }
  if ($("mensagens")) $("mensagens").hidden = false;
}

// --- Imersão: o modo imersivo de sempre, numa moldura ---------------------------------------------

const IMERSIVO = "http://127.0.0.1:8794/stage.html?res=1280x720&fps=auto";
const imersao = $("imersao");
const moldura = $("moldura");
const imersaoLigada = () => !!moldura.querySelector("iframe");

function ligarImersao() {
  if (imersaoLigada()) return;
  const q = document.createElement("iframe");
  q.src = IMERSIVO; q.title = "Imersão"; q.allow = "camera; autoplay; fullscreen";
  moldura.replaceChildren(q);
  $("ponto-imersao").hidden = false;
}

function desligarImersao() {
  moldura.innerHTML = `<p class="vazio">Desligada. ${botao("Ligar", "imersao-ligar")}</p>`;
  $("ponto-imersao").hidden = true;
}

// --- o despachante: cada data-acao faz uma coisa ----------------------------------------------------

const recarregar = () => abrir();

const ACOES = {
  "confirmar-sim": async (b) => { const f = pendentes.get(b.dataset.id); pendentes.delete(b.dataset.id); if (f) await f(); },
  "confirmar-nao": (b) => { const l = b.closest("[data-antes]"); l.innerHTML = l.dataset.antes; delete l.dataset.antes; pendentes.delete(b.dataset.id); },
  // imersão
  "imersao-cheia": () => (moldura.querySelector("iframe") || moldura).requestFullscreen?.().catch(() => {}),
  "imersao-desligar": desligarImersao,
  "imersao-ligar": ligarImersao,
  // foco
  foco: async (b) => { await ocupado(b, () => api("foco/acao", { id: b.dataset.id, acao: b.dataset.foco })); await recarregar(); },
  "foco-passo": async (b) => { await ocupado(b, () => api("foco/acao", { id: b.dataset.id, acao: "passo_novo", texto: $("passo-novo").value })); await recarregar(); },
  "foco-descartar": (b) => confirmar(b, "Descartar?", async () => { await api("foco/acao", { id: b.dataset.id, acao: "descartar" }); await recarregar(); }),
  // automações
  "automacao-remover": (b) => confirmar(b, "Remover?", async () => { await api("automacao/remover", { id: b.dataset.id }); await recarregar(); }),
  // memória
  "memoria-remover": (b) => confirmar(b, "Remover?", async () => { await api("memoria/mudar", { acao: "remover", alvo: b.dataset.alvo, texto: b.dataset.texto }); await recarregar(); }),
  "memoria-adicionar": async (b) => {
    const campo = document.querySelector(`[data-nova="${b.dataset.alvo}"]`);
    await ocupado(b, () => api("memoria/mudar", { acao: "adicionar", alvo: b.dataset.alvo, texto: campo.value }));
    toast("Guardado."); await recarregar();
  },
  // skills
  "skill-nova": () => editorSkill("", MODELO_SKILL("nome-da-skill"), true),
  "skill-editar": async (b) => { const k = await api("skill/ver", { nome: b.dataset.nome }); editorSkill(k.nome, k.conteudo, false); },
  "skill-fechar": () => { $("editor-skill").hidden = true; },
  "skill-salvar": async (b) => {
    const nome = b.dataset.nome || $("sk-nome").value.trim();
    let texto = $("sk-texto").value;
    if (!b.dataset.nome) texto = texto.replace(/^name: .*$/m, "name: " + nome).replace(/^# nome-da-skill$/m, "# " + nome);
    await ocupado(b, () => api("skill/salvar", { nome, conteudo: texto }));
    toast("Skill salva."); await recarregar();
  },
  "skill-excluir": (b) => confirmar(b, "Excluir?", async () => { await api("skill/excluir", { nome: b.dataset.nome }); toast("Excluída."); await recarregar(); }),
  // conectores
  "conector-novo": formConector,
  "cx-cancelar": () => { $("form-conector").hidden = true; },
  "cx-tipo": (b) => {
    document.querySelectorAll('[data-acao="cx-tipo"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    const remoto = b.dataset.tipo === "http";
    document.querySelectorAll("[data-local]").forEach((x) => { x.hidden = remoto; });
    document.querySelectorAll("[data-remoto]").forEach((x) => { x.hidden = !remoto; });
  },
  "cx-salvar": async (b) => {
    const remoto = document.querySelector('[data-acao="cx-tipo"][aria-pressed="true"]').dataset.tipo === "http";
    const cab = Object.fromEntries(linhasDe($("cx-cabecalhos").value).map((l) => l.split(":").map((x) => x.trim())).filter((p) => p.length === 2));
    await ocupado(b, () => api("conector/salvar", {
      nome: $("cx-nome").value.trim(), tipo: remoto ? "http" : "stdio", comando: $("cx-comando").value.trim(),
      argumentos: linhasDe($("cx-argumentos").value), url: $("cx-url").value.trim(), cabecalhos: remoto ? cab : {},
      ambiente: $("cx-ambiente").value.split(",").map((v) => v.trim()).filter(Boolean),
    }));
    toast("Conector salvo."); await recarregar();
  },
  "conector-segredo": async (b) => {
    const campo = b.closest(".segredo").querySelector("input");
    await ocupado(b, () => api("conector/segredo", { nome: b.dataset.nome, variavel: b.dataset.variavel, valor: campo.value }));
    toast("Segredo guardado."); await recarregar();
  },
  "conector-testar": async (b) => {
    const nome = b.dataset.nome;
    const saida = document.querySelector(`[data-resultado="${CSS.escape(nome)}"]`);
    saida.className = "resultado"; saida.textContent = "Conectando…";
    const r = await ocupado(b, () => api("conector/testar", { nome }));
    saida.className = "resultado " + (r.ok ? "ok" : "erro");
    saida.textContent = r.ok ? `${r.ferramentas.length} ferramentas` : r.erro;
    if (r.ok) {
      const area = document.querySelector(`[data-ferramentas="${CSS.escape(nome)}"]`);
      area.innerHTML = permissoes(nome, r.ferramentas, conectoresVistos.find((k) => k.nome === nome));
      area.hidden = false;
    }
  },
  "conector-permissoes": async (b) => {
    const k = conectoresVistos.find((x) => x.nome === b.dataset.nome);
    const escolhas = [...b.closest(".ferramentas-mcp").querySelectorAll("[data-permissao]")];
    const de = (v) => escolhas.filter((e) => e.value === v).map((e) => e.dataset.permissao);
    await ocupado(b, () => api("conector/salvar", { nome: k.nome, tipo: k.tipo, comando: k.comando, argumentos: k.argumentos, url: k.url, ambiente: k.ambiente, cabecalhos: k.cabecalhos, livres: de("livre"), bloqueadas: de("bloqueada") }));
    toast("Permissões salvas."); await recarregar();
  },
  "conector-remover": (b) => confirmar(b, "Remover?", async () => { await api("conector/remover", { nome: b.dataset.nome }); await recarregar(); }),
  "conectores-aplicar": async (b) => { const r = await ocupado(b, () => api("conectores/aplicar", {})); toast(r.aviso); await recarregar(); },
  // modelos
  motor: (b) => {
    modelo.motor = b.dataset.motor;
    document.querySelectorAll('[data-acao="motor"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    if (b.dataset.modelo) $("modelo").value = b.dataset.modelo;
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
    const c = await ocupado(b, () => api("chave", { motor: modelo.motor, chave: $("chave").value }));
    modelo.chaves = c.chaves; desenharChave(); toast(c.aviso || "Chave guardada.");
  },
  "escuta-guardar": async (b) => {
    const r = await ocupado(b, () => api("escuta/chave", { chave: $("chave-escuta").value }));
    escuta = r; desenharEscuta();
    const res = $("resultado-escuta");
    res.className = "resultado " + (r.valida ? "ok" : "erro"); res.textContent = r.aviso;
  },
  "escuta-testar": async (b) => {
    const res = $("resultado-escuta");
    res.className = "resultado"; res.textContent = "Testando…";
    const t = await ocupado(b, () => api("escuta/testar", { chave: $("chave-escuta").value }));
    res.className = "resultado " + (t.ok ? "ok" : "erro"); res.textContent = t.mensagem;
  },
  "escuta-apagar": (b) => confirmar(b, "Remover a chave?", async () => { escuta = await api("escuta/apagar", {}); desenharEscuta(); toast(escuta.aviso); }),
  "chave-apagar": (b) => confirmar(b, "Apagar a chave?", async () => { const c = await api("chave/apagar", { motor: modelo.motor }); modelo.chaves = c.chaves; desenharChave(); }),
  // sessões
  "sessao-nova": async () => { sessaoAberta = null; document.querySelectorAll(".item-sessao").forEach((x) => x.setAttribute("aria-current", "false")); await formSessao(); },
  "sessao-abrir": (b) => abrirSessao(b.dataset.id),
  "ns-onde": (b) => {
    document.querySelectorAll('[data-acao="ns-onde"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    const novo = b.dataset.onde === "novo";
    $("ns-campo-pasta").hidden = novo; $("ns-campo-projeto").hidden = !novo; $("ns-campo-isolada").hidden = novo;
  },
  "ns-criar": async (b) => {
    const novo = !$("ns-campo-projeto").hidden;
    const s = await ocupado(b, () => api("sessao/criar", { nome: $("ns-nome").value, pasta: $("ns-pasta").value, novo, projeto: $("ns-projeto").value, isolada: !novo && $("ns-isolada").checked }));
    await listaSessoes(); await abrirSessao(s.id);
  },
  "sessao-parar": async () => { await api("sessao/parar", { id: sessaoAberta }); toast("Parando…"); },
  "sessao-excluir": (b) => confirmar(b, "Excluir a sessão? A pasta do projeto fica.", async () => {
    const r = await api("sessao/excluir", { id: sessaoAberta });
    sessaoAberta = null; toast(r.aviso || "Sessão excluída."); await recarregar();
  }),
  "md-abrir": () => { $("editor-md").hidden = false; $("md-nome").focus(); },
  "md-fechar": () => { $("editor-md").hidden = true; },
  "md-salvar": async (b) => {
    const r = await ocupado(b, () => api("sessao/arquivo", { id: sessaoAberta, nome: $("md-nome").value, conteudo: $("md-texto").value, sobrescrever: $("md-substituir").checked }));
    $("editor-md").hidden = true; $("md-nome").value = $("md-texto").value = "";
    toast("Salvo: " + r.arquivo); await acompanharSessao(); await atualizarArvore();
  },
  anexar: () => $("arquivos").click(),
  "anexo-tirar": (b) => { const i = Number(b.dataset.i); anexos[i].previa && URL.revokeObjectURL(anexos[i].previa); anexos.splice(i, 1); desenharAnexos(); },
  explorador: () => {
    explorador = !explorador;
    document.querySelector('.conversa-topo [data-acao="explorador"]').setAttribute("aria-pressed", String(explorador));
    document.querySelector(".sessao-aberta").classList.toggle("sem-explorador", !explorador);
  },
  no: async (b) => {
    const no = b.closest(".no");
    if (!no.classList.contains("pasta")) return verArquivo(b.dataset.caminho);
    if (no.getAttribute("aria-expanded") === "true") {
      no.setAttribute("aria-expanded", "false"); no.querySelector(".filhos").innerHTML = "";
      for (const c of [...abertas]) if (c === no.dataset.caminho || c.startsWith(no.dataset.caminho + "/")) abertas.delete(c);
    } else await abrirPastaNo(no);
  },
  "ver-arquivo": (b) => verArquivo(b.dataset.caminho),
  "arvore-atualizar": atualizarArvore,
  "arvore-recolher": async () => { abertas = new Set(); await carregarPasta("", $("arvore")); },
  "busca-modo": async (b) => { modoBusca = b.dataset.modo; document.querySelectorAll('[data-acao="busca-modo"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b))); await buscarArquivos(); },
  "previa-fechar": fecharPrevia,
  mencionar: (b) => {
    const campo = $("texto-sessao");
    const antes = campo.value.slice(0, campo.selectionStart), depois = campo.value.slice(campo.selectionEnd);
    const trecho = (antes && !antes.endsWith(" ") ? " " : "") + "@" + b.dataset.caminho + " ";
    campo.value = antes + trecho + depois; fecharPrevia(); campo.focus();
  },
};

const MUDAR = {
  automacao: async (el) => { await api("automacao/ativar", { id: el.dataset.id, ativo: el.checked }); await recarregar(); },
  skill: async (el) => { await api("skill/ligar", { nome: el.dataset.nome, ligada: el.checked }); toast(el.checked ? "Ligada." : "Desligada."); await recarregar(); },
  conector: async (el) => { await api("conector/ligar", { nome: el.dataset.nome, ligado: el.checked }); await recarregar(); },
  "via-ligada": () => {},
};

document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-acao]");
  if (!b || !ACOES[b.dataset.acao]) return;
  try { await ACOES[b.dataset.acao](b, ev); }
  catch (erro) {
    const r = document.querySelector(".resultado:not([data-resultado])");
    if (r) { r.className = "resultado erro"; r.textContent = erro.message; }
    toast(erro.message);
  }
});

document.addEventListener("change", async (ev) => {
  const el = ev.target;
  try {
    if (el.dataset.mudar && MUDAR[el.dataset.mudar]) await MUDAR[el.dataset.mudar](el);
    else if (el.id === "arquivos") { anexar(el.files); el.value = ""; }
  } catch (erro) { toast(erro.message); if (el.type === "checkbox") el.checked = !el.checked; }
});

conteudo.addEventListener("submit", async (ev) => {
  if (ev.target.id !== "compor") return;
  ev.preventDefault();
  const campo = $("texto-sessao"), texto = campo.value.trim();
  if (!texto && !anexos.length) return;
  try {
    await ocupado(ev.target.querySelector('button[type="submit"]'), async () => {
      const nomes = [];
      for (const p of anexos) nomes.push(await subirAnexo(p.arquivo));
      await api("sessao/enviar", { id: sessaoAberta, texto, anexos: nomes });
    });
    campo.value = ""; limparAnexos(); await acompanharSessao(); await listaSessoes();
  } catch (erro) { toast(erro.message); }
});

conteudo.addEventListener("keydown", (ev) => {
  if (ev.target.id === "texto-sessao" && ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); $("compor").requestSubmit(); }
  else if (ev.key === "Enter" && (ev.target.dataset.nova || ev.target.id === "passo-novo")) { ev.preventDefault(); ev.target.closest(".add").querySelector("button").click(); }
});

conteudo.addEventListener("input", (ev) => {
  if (ev.target.id !== "buscar-arquivos") return;
  clearTimeout(buscaPendente);
  buscaPendente = setTimeout(() => buscarArquivos().catch((e) => toast(e.message)), 250);
});

conteudo.addEventListener("paste", (ev) => {
  if (!$("compor") || !ev.clipboardData?.files.length || ev.target.id === "md-texto") return;
  ev.preventDefault(); anexar(ev.clipboardData.files);
});
for (const tipo of ["dragenter", "dragover"]) conteudo.addEventListener(tipo, (ev) => {
  if (!$("compor") || !ev.dataTransfer?.types.includes("Files")) return;
  ev.preventDefault(); document.querySelector(".conversa")?.classList.add("soltando");
});
conteudo.addEventListener("dragleave", (ev) => { if (!ev.relatedTarget || !conteudo.contains(ev.relatedTarget)) document.querySelector(".conversa")?.classList.remove("soltando"); });
conteudo.addEventListener("drop", (ev) => {
  if (!$("compor") || !ev.dataTransfer?.files.length) return;
  ev.preventDefault(); document.querySelector(".conversa")?.classList.remove("soltando"); anexar(ev.dataTransfer.files);
});

// --- navegação e batimento -----------------------------------------------------------------------------

async function abrir() {
  const nome = (location.hash || "#inicio").slice(1);
  const secao = PAGINAS[nome] || nome === "imersao" ? nome : "inicio";
  document.querySelectorAll("nav a").forEach((a) => (a.dataset.secao === secao ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  imersao.hidden = secao !== "imersao";
  conteudo.hidden = secao === "imersao";
  conteudo.classList.toggle("cheio", secao === "sessoes");
  clearInterval(relogioSessoes);
  if (secao === "imersao") { ligarImersao(); return; }
  try {
    const html = await PAGINAS[secao]();
    conteudo.innerHTML = secao === "sessoes" ? html : `<div class="secao">${html}</div>`;
    if (secao === "modelos") { desenharChave(); desenharEscuta(); }
    encher();
    if (secao === "sessoes") await prepararSessoes();
  } catch (erro) {
    conteudo.innerHTML = `<div class="secao">${cabeca("Sem conexão com o Zé")}<p class="aviso">${esc(erro.message)}</p></div>`;
  }
}

let telaVista = null;
async function batimento() {
  try {
    const e = await api("estado");
    if (telaVista !== null && e.tela_ts > telaVista && imersaoLigada() && location.hash !== "#imersao") location.hash = "#imersao";
    telaVista = e.tela_ts;
    $("estado-ze").textContent = ESTADOS[e.ze] || e.ze;
    document.querySelector(".marca .anel").classList.toggle("ativo", e.ze !== "inativo");
  } catch { $("estado-ze").textContent = "desconectado"; }
}

window.addEventListener("hashchange", abrir);
abrir();
batimento();
setInterval(batimento, 2000);
