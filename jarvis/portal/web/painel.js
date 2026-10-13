// O painel do Zé (docs/plano-painel.md). Uma página, sem framework e sem nada de fora.
// Regras de tela (09/10/2026): tudo em português; cada página tem título, no máximo uma linha
// e a ação principal; o que aparece dá para mexer; detalhe técnico fica em "Detalhes".
// Todo botão diz o que faz em data-acao; um despachante só executa. A regra mora no jarvisd.
"use strict";

const TOKEN = document.querySelector('meta[name="ze-token"]').content;
const NO_PC = ["127.0.0.1", "localhost"].includes(location.hostname); // o próprio PC, não outro aparelho
const conteudo = document.getElementById("conteudo");

const ESTADOS = { inativo: "inativo", ativo: "pronto", ouvindo: "ouvindo", pensando: "pensando", falando: "falando", confirmando: "esperando o seu sim" };
const ESTADO_SESSAO = { parada: "pronta", trabalhando: "trabalhando", erro: "erro" };
const estadoSessao = (s) => (s.limite ? "sem créditos" : ESTADO_SESSAO[s.estado] || s.estado);
const TIPO_AUTOMACAO = { lembrete: "Lembrete", pergunta: "Pergunta ao Zé" };
const NOME_MOTOR = { contas: "Automático", codex: "Codex", plano: "Claude", openai: "OpenAI API", anthropic: "Anthropic", openrouter: "OpenRouter", ponte: "Ponte" };

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

// --- pedaços de tela ---

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

// --- as páginas ---

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


  async modelos() {
    const [c, esc_, cfg, ct] = await Promise.all([api("cerebro"), api("escuta"), api("configuracao"), api("contas")]);
    contasTela = ct;
    modelo = { ...c.via, chaves: c.chaves };
    escuta = esc_;
    prepararAcesso(cfg);
    acessoTela.modelo = c.completo.modelo;
    acessoTela.cerebro = c.completo.provedor;
    agentes = c.agentes;
    const sessoes = c.sessoes.total;
    return `${cabeca("Modelos")}${sub("Um modelo para cada tipo de tarefa.")}
      ${cartao("", `<div class="cabeca"><h2>Voz rápida</h2>${liga(c.via.ligada, "via-ligada", "", "Ligada")}</div>
        ${sub("Conversa simples por voz. Pedidos com ação vão ao cérebro.")}
        <div class="segmentos" role="group" aria-label="Provedor">${c.motores.map((m) => `<button type="button" data-acao="motor" data-motor="${m.id}" data-modelo="${esc(m.modelo)}" aria-pressed="${m.id === c.via.motor}">${esc(NOME_MOTOR[m.id] || m.nome)}</button>`).join("")}</div>
        <div class="linha"><label>Modelo<input id="modelo" class="mono" value="${esc(c.via.modelo)}" placeholder="Padrão da conta" autocomplete="off" spellcheck="false"></label>
          <label id="campo-endereco">Endereço<input id="endereco" class="mono" value="${esc(c.via.endereco)}" placeholder="http://127.0.0.1:20128/v1" autocomplete="off" spellcheck="false"></label></div>
        <div id="area-chave"></div>
        <div class="linha">${botao("Salvar", "modelo-salvar", "", "principal")}${botao("Testar", "modelo-testar")}<span class="resultado" id="resultado"></span></div>`)}
      <section class="cartao" id="cartao-acesso" data-contexto="cerebro"></section>
      <section class="cartao" id="cartao-contas"></section>
      ${cartao("", `<div class="cabeca"><h2>Sessões de código</h2><span class="etiqueta">${sessoes} ${sessoes === 1 ? "sessão" : "sessões"}</span><a class="externo" href="#sessoes">Abrir sessões</a></div>
        ${sub("Agentes que trabalham nos seus projetos e continuam de onde pararam.")}
        <p class="nota">Agentes: ${c.sessoes.agentes.filter((a) => a.disponivel).map((a) => esc(a.nome)).join(" e ")}. Você escolhe o agente ao criar a sessão; a conta é a que está em uso em Contas.</p>`)}
      <section class="cartao" id="cartao-escuta"></section>`;
  },

  async perfil() {
    const cfg = await api("configuracao");
    return `${cabeca("Perfil")}${sub("Usado pelo Zé em todas as conversas.")}
      ${cartao("", `${camposPerfil(cfg)}<div class="linha">${botao("Salvar", "perfil-salvar", "", "principal")}</div><p class="resultado" id="resultado-perfil"></p>`)}`;
  },

  async configurar() {
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
  },

  async voz() {
    const [e, o, r] = await Promise.all([api("estado"), api("escuta"), api("remoto")]);
    const etiqueta = (ok, sim, nao) => `<span class="etiqueta ${ok ? "bom" : "alerta"}">${ok ? sim : nao}</span>`;
    const linha = (titulo, estado, texto) => cartao("", `<div class="cabeca"><h2>${titulo}</h2>${estado}</div>${sub(texto)}`);
    return `${cabeca("Voz")}
      ${cartao("", `<div class="cabeca"><h2>Modo de fala</h2><span class="etiqueta bom">${esc(nomeModo(e.modo_fala))}</span></div>
        ${sub("Quando o Zé fala sem você pedir. Atalho: Alt+M.")}
        <div class="modos-fala" role="radiogroup" aria-label="Modo de fala">${MODOS_FALA.map((m) => `<button type="button" role="radio" class="modo" data-acao="modo-fala" data-modo="${m.valor}" aria-checked="${m.valor === e.modo_fala}"><strong>${m.nome}</strong><small>${m.detalhe}</small></button>`).join("")}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>Escuta</h2><span class="etiqueta bom">${esc(nomeEscuta(e.escuta.modo))}</span></div>
        ${sub("Quando o chamado “Ei Zé” funciona.")}
        <div class="modos-fala" role="radiogroup" aria-label="Escuta">${MODOS_ESCUTA.map((m) => { const sem = m.valor === "janela" && !e.escuta.janela; return `<button type="button" role="radio" class="modo" data-acao="escuta-modo" data-modo="${m.valor}" aria-checked="${m.valor === e.escuta.modo}" ${sem ? "disabled" : ""}><strong>${m.nome}</strong><small>${sem ? "Requer Hyprland." : m.detalhe}</small></button>`; }).join("")}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>Ativação</h2><span class="etiqueta bom">${e.chamado === "botao" ? "Só o botão" : "“Ei Zé”"}</span></div>
        ${sub("Como chamar o Zé no microfone deste computador. O botão vale nos dois.")}
        <div class="modos-fala" role="radiogroup" aria-label="Ativação">${[["voz", "“Ei Zé”", "O chamado falado ou o botão."], ["botao", "Só o botão", "Ouve só com o botão apertado. A voz conectada continua ao vivo."]].map(([v, n, d]) => `<button type="button" role="radio" class="modo" data-acao="chamado-modo" data-modo="${v}" aria-checked="${v === e.chamado}"><strong>${n}</strong><small>${d}</small></button>`).join("")}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>Acesso pelo celular</h2></div>
        ${sub("O Zé no navegador do celular, em casa ou fora. Exige senha e código do autenticador.")}
        <div class="linha"><label>Senha de acesso${r.senha ? " (definida)" : ""}<input id="senha-acesso" type="password" autocomplete="new-password" placeholder="${r.senha ? "Nova senha" : "Mínimo de 8 caracteres"}"></label>${botao("Salvar senha", "senha-salvar")}</div>
        <div class="parte"><div class="cabeca"><h3 class="subtitulo">Código do autenticador</h3>${etiqueta(r.codigo, "Ligado", "Desligado")}</div>
          ${codigoPreparado ? `<div class="acesso-qr">${codigoPreparado.qr}<div class="campos"><p>Leia com o aplicativo autenticador (Google Authenticator, Aegis…) ou digite a chave:</p><p class="mono">${esc(codigoPreparado.chave)}</p>
            <div class="linha"><label>Código de 6 dígitos<input id="codigo-confirmar" inputmode="numeric" autocomplete="one-time-code" maxlength="7"></label>${botao("Confirmar", "codigo-confirmar", "", "principal")}</div></div></div>`
            : `<div class="linha">${r.codigo ? botao("Desligar", "codigo-desligar", "", "discreta") : botao("Ligar", "codigo-preparar", r.senha ? "" : "disabled")}</div>`}</div>
        <div class="parte"><div class="cabeca"><h3 class="subtitulo">Acesso de qualquer lugar</h3>${etiqueta(!!r.tunel.endereco, "Ativo", "Inativo")}</div>
          ${r.tunel.endereco ? `<div class="acesso-qr">${r.tunel.qr}<div class="campos"><p>Aponte a câmera do celular para o código, ou abra:</p><p class="mono">${esc(r.tunel.endereco)}</p><p class="nota">O endereço muda quando o Zé reinicia.</p></div></div>`
            : `<p class="nota">${r.senha && r.codigo ? "Abre um endereço seguro pelo Cloudflare, para o Wi-Fi e o 4G." : "Requer a senha e o código do autenticador ligados."}</p>`}
          <div class="linha">${r.tunel.ativo ? botao("Copiar endereço", "remoto-copiar", `data-endereco="${esc(r.tunel.endereco)}"`) + botao("Desativar", "tunel-desativar", "", "discreta") : botao("Ativar", "tunel-ativar", r.senha && r.codigo ? "" : "disabled", "principal")}</div></div>
        ${r.lista.length ? `<div class="parte"><h3 class="subtitulo">Aparelhos conectados</h3>${r.lista.map((a) => `<div class="linha aparelho"><span>${esc(a.aparelho)}</span><small>${new Date(a.desde * 1000).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}${a.origem ? ` · ${esc(a.origem)}` : ""}</small>${botao("Desconectar", "aparelho-desconectar", `data-id="${esc(a.id)}"`, "discreta")}</div>`).join("")}</div>` : ""}
        ${r.instalado ? `<div class="parte"><h3 class="subtitulo">Rede privada (Tailscale)</h3>${sub(r.ativo ? `Ativa em <span class="mono">${esc(r.endereco)}</span>` : "Alternativa ao túnel, para quem já usa o Tailscale.")}
          ${r.ativo && r.firewall ? `<p class="aviso">Libere a voz no firewall: <span class="mono">${esc(r.firewall)}</span></p>` : ""}
          ${r.conectado ? `<div class="linha">${r.ativo ? botao("Desativar", "remoto-desativar", "", "discreta") : botao("Ativar", "remoto-ativar")}</div>` : ""}</div>` : ""}`)}
      ${linha("Palavra de ativação", etiqueta(o.ativacao, "Ativa", "Não treinada"), o.ativacao ? "“Ei Zé”." : "“Ei Zé”. Necessária para os comandos de voz.")}
      ${linha("Reconhecimento de fala", etiqueta(o.deepgram.tem, "Configurado", "Não configurado"), o.deepgram.tem ? "Deepgram." : 'Deepgram. Configure em <a href="#modelos">Modelos</a>.')}
      ${linha("Síntese de voz", etiqueta(true, "Ativa", ""), "Piper, voz Cadu (pt-BR). Processamento local.")}`;
  },
};

// --- Modo de fala: quando o Zé fala sem ser chamado (ADR 0018) ---

const MODOS_FALA = [
  { valor: "silencioso", nome: "Silencioso", curto: "Sem voz", detalhe: "Não fala. Tudo fica na tela." },
  { valor: "avisos", nome: "Avisos", curto: "Avisos e urgências", detalhe: "Fala avisos e urgências. Respostas das sessões, só se você pedir." },
  { valor: "maos_livres", nome: "Mãos livres", curto: "Também as respostas", detalhe: "Fala também as respostas das sessões, resumidas." },
];
const MODOS_ESCUTA = [
  { valor: "sempre", nome: "Sempre", detalhe: "Enquanto o Zé estiver em execução." },
  { valor: "janela", nome: "Com a janela aberta", detalhe: "Só com a janela do Zé aberta." },
];
const nomeEscuta = (valor) => MODOS_ESCUTA.find((m) => m.valor === valor)?.nome || valor;
const nomeModo = (valor) => MODOS_FALA.find((m) => m.valor === valor)?.nome || valor;
let modoFala = null;

function desenharModoFala(valor) {
  if (valor === modoFala) return;
  modoFala = valor;
  const itens = MODOS_FALA.map((m) => ({ valor: m.valor, nome: m.nome, detalhe: m.curto }));
  $("modo-fala").innerHTML = escolha("modo-fala", `Fala: ${nomeModo(valor)}`, [{ itens }], valor, "Modo de fala (Alt+M)");
  $("modo-fala").dataset.modo = valor;
}

async function mudarModoFala(valor) {
  const r = await api("fala/modo", { modo: valor });
  desenharModoFala(r.modo);
  toast(r.aviso);
  if (location.hash === "#voz") await recarregar();
}

// --- Voz ao vivo pelo navegador: o microfone vai ao Zé pelo HTTPS do painel (WebSocket) ---

let salaVoz = null, vozConectando = false, codigoPreparado = null;

function desenharVozRemota() {
  const on = !!salaVoz;
  const html = `<button type="button" class="acao" data-acao="voz-remota" aria-pressed="${on}" title="${on ? "Desconectar a voz ao vivo" : "Conectar a voz ao vivo: ouve sem parar até desconectar"}" ${vozConectando ? "disabled" : ""}>${vozConectando ? "Conectando…" : "Ao vivo"}</button>`;
  for (const caixa of [$("voz-remota"), $("voz-holo")]) {
    if (!caixa) continue;
    caixa.hidden = false;
    if (caixa.innerHTML !== html) caixa.innerHTML = html;
  }
}

const avisarVoz = (evento, detalhe = "") => api("voz/evento", { evento, detalhe: String(detalhe), aparelho: navigator.userAgent }).catch(() => {});

// A voz do Zé chega em PCM de 16 bits; cada pedaço entra na fila logo depois do anterior.
// O volume de um sinal (0 a 1), para o holograma reagir à voz.
function medidor(ctx) {
  const a = ctx.createAnalyser(), dados = new Float32Array(512);
  a.fftSize = 512;
  return { no: a, nivel() { a.getFloatTimeDomainData(dados); let s = 0; for (const v of dados) s += v * v; return Math.min(1, Math.sqrt(s / dados.length) * 4); } };
}

let medidores = { voz: null, mic: null };
(function animarHolograma() {
  const holo = document.querySelector(".holo");
  if (holo) {
    holo.style.setProperty("--voz", (medidores.voz?.nivel() || 0).toFixed(3));
    holo.style.setProperty("--mic", (medidores.mic?.nivel() || 0).toFixed(3));
  }
  requestAnimationFrame(animarHolograma);
})();

function tocadorVoz() {
  const ctx = new AudioContext(), tocando = new Set(), m = medidor(ctx);
  m.no.connect(ctx.destination); medidores.voz = m;
  let taxa = 22050, proximo = 0;
  return {
    ctx,
    controle(m) {
      if (m.tipo === "voz") taxa = m.taxa;
      if (m.tipo === "parar") { tocando.forEach((f) => f.stop()); tocando.clear(); proximo = 0; }
    },
    pedaco(dados) {
      const pcm = new Int16Array(dados), buf = ctx.createBuffer(1, pcm.length, taxa), canal = buf.getChannelData(0);
      for (let i = 0; i < pcm.length; i++) canal[i] = pcm[i] / 32768;
      const f = ctx.createBufferSource();
      f.buffer = buf; f.connect(m.no);
      proximo = Math.max(proximo, ctx.currentTime + 0.05);
      f.start(proximo); proximo += buf.duration;
      tocando.add(f); f.onended = () => tocando.delete(f);
    },
  };
}

// A tela fica ligada durante o ao vivo: bloqueada, o navegador para o microfone.
let telaLigada = null;
async function manterTela(ligar) {
  try {
    if (ligar && !telaLigada) telaLigada = await navigator.wakeLock?.request("screen");
    if (!ligar) { await telaLigada?.release(); telaLigada = null; }
  } catch { /* sem suporte: segue sem */ }
}
document.addEventListener("visibilitychange", () => { if (salaVoz && document.visibilityState === "visible") { telaLigada = null; manterTela(true); } });

// Queda da rede (código 1006: túnel, 4G, Wi-Fi): reconecta sozinho algumas vezes. Fechamento
// limpo do Zé (outro aparelho assumiu a voz) ou pedido aqui não reconecta.
const RELIGAR_MS = [1000, 3000, 8000];
let religarVoz = { tentativas: 0, espera: null };

function agendarReligar() {
  if (religarVoz.tentativas >= RELIGAR_MS.length) { religarVoz.tentativas = 0; toast("Voz desconectada."); return; }
  toast("Reconectando a voz…");
  const tentar = () => {
    religarVoz.espera = null;
    if (salaVoz || vozConectando) return;
    if (document.visibilityState !== "visible") {
      document.addEventListener("visibilitychange", tentar, { once: true });
      return;
    }
    conectarVoz(true);
  };
  religarVoz.espera = setTimeout(tentar, RELIGAR_MS[religarVoz.tentativas++]);
}

function ligarVoz() {
  clearTimeout(religarVoz.espera); religarVoz = { tentativas: 0, espera: null };
  if (salaVoz) { salaVoz.encerrar(); toast("Voz desconectada."); return; }
  conectarVoz(false);
}

async function conectarVoz(religando) {
  vozConectando = true; desenharVozRemota();
  let mic = null;
  try {
    mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    const captura = new AudioContext({ sampleRate: 16000 });
    await captura.audioWorklet.addModule("/voz-captura.js");
    const no = new AudioWorkletNode(captura, "captura"), mudo = captura.createGain();
    mudo.gain.value = 0;
    const entrada = captura.createMediaStreamSource(mic), mm = medidor(captura);
    entrada.connect(no); entrada.connect(mm.no); medidores.mic = mm;
    no.connect(mudo).connect(captura.destination);
    const saida = tocadorVoz();
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/voz/ws`);
    ws.binaryType = "arraybuffer";
    const conexao = {
      pedido: false,
      encerrar() { conexao.pedido = true; ws.close(); },
    };
    const fim = () => {
      mic.getTracks().forEach((t) => t.stop()); captura.close(); saida.ctx.close(); manterTela(false);
      medidores = { voz: null, mic: null };
      if (salaVoz === conexao) { salaVoz = null; desenharVozRemota(); }
    };
    await new Promise((ok, erro) => {
      ws.onopen = () => { ws.send(JSON.stringify({ token: TOKEN, taxa: captura.sampleRate })); ok(); };
      ws.onerror = () => erro(new Error("Sem conexão com o Zé."));
    });
    no.port.onmessage = (ev) => { if (ws.readyState === 1) ws.send(ev.data); };
    ws.onmessage = (ev) => (typeof ev.data === "string" ? saida.controle(JSON.parse(ev.data)) : saida.pedaco(ev.data));
    const inicio = Date.now();
    ws.onclose = (ev) => {
      const queda = !conexao.pedido && ev.code === 1006;
      avisarVoz(conexao.pedido ? "desligou" : queda ? "caiu" : "encerrada", ev.code);
      fim();
      if (queda) {
        if (Date.now() - inicio > 30000) religarVoz.tentativas = 0;
        agendarReligar();
      }
    };
    salaVoz = conexao; manterTela(true);
    toast(religando ? "Voz reconectada." : "Voz ao vivo."); avisarVoz("conectou", `${captura.sampleRate} Hz`);
  } catch (erro) {
    if (!salaVoz) mic?.getTracks().forEach((t) => t.stop());
    avisarVoz("falhou", `${erro.name}: ${erro.message}`);
    if (religando && erro.name !== "NotAllowedError") agendarReligar();
    else toast(erro.name === "NotAllowedError" ? "Microfone bloqueado no navegador." : erro.message);
  }
  vozConectando = false; desenharVozRemota();
}

// --- Menu lateral: grupos recolhíveis, lembrados neste navegador ---

const GRUPOS = "ze.grupos-fechados";
function lerFechados() { try { return new Set(JSON.parse(localStorage.getItem(GRUPOS) || "[]")); } catch { return new Set(); } }
lerFechados().forEach((g) => document.querySelector(`.grupo[data-grupo="${g}"] .grupo-titulo`)?.setAttribute("aria-expanded", "false"));
document.querySelector("nav").addEventListener("click", (ev) => { if (ev.target.closest("a")) document.body.classList.remove("menu-aberto"); });
function alternarGrupo(b) {
  const aberto = b.getAttribute("aria-expanded") === "true", fechados = lerFechados(), g = b.closest(".grupo").dataset.grupo;
  b.setAttribute("aria-expanded", String(!aberto));
  aberto ? fechados.add(g) : fechados.delete(g);
  try { localStorage.setItem(GRUPOS, JSON.stringify([...fechados])); } catch { /* sem armazenamento: vale só agora */ }
}

// --- Segurar para falar (ADR 0022): segurar envia ao soltar; um toque começa e outro envia ---

let falando = false, travado = false, apertouEm = 0;

function marcarFalar() {
  document.querySelectorAll("[data-falar]").forEach((b) => {
    b.setAttribute("aria-pressed", String(falando));
    b.textContent = !falando ? "Falar" : travado ? "Enviar" : "Ouvindo…";
  });
}

async function apertarFalar() {
  if (travado) return soltarFalar(true);
  if (falando) return;
  // Fora do PC, sem a voz conectada, quem ouviria é o microfone do PC.
  if (!salaVoz && !NO_PC) return toast("Conecte o Ao vivo para falar por aqui.");
  falando = true; apertouEm = Date.now(); marcarFalar();
  api("voz/apertar", {}).catch((erro) => toast(erro.message));
}

async function soltarFalar(enviar) {
  if (!falando || travado && !enviar) return;
  if (!enviar && Date.now() - apertouEm < 300) { travado = true; marcarFalar(); return; }
  falando = travado = false; marcarFalar();
  // O fim da fala ainda está a caminho (rede e fila do áudio): fecha o pedido 0,3 s depois.
  await new Promise((ok) => setTimeout(ok, 300));
  await api("voz/soltar", {}).catch((erro) => toast(erro.message));
}

document.addEventListener("pointerdown", (ev) => { if (ev.target.closest?.("[data-falar]")) { ev.preventDefault(); apertarFalar(); } });
document.addEventListener("pointerup", (ev) => { if (ev.target.closest?.("[data-falar]")) soltarFalar(false); });
document.addEventListener("pointercancel", (ev) => { if (ev.target.closest?.("[data-falar]")) soltarFalar(false); });
const editavel = (el) => el.closest?.("input, textarea, select, [contenteditable], .terminal-sessao");
document.addEventListener("keydown", (ev) => { if (ev.code === "Space" && !ev.repeat && !editavel(ev.target)) { ev.preventDefault(); apertarFalar(); } });
document.addEventListener("keyup", (ev) => { if (ev.code === "Space" && !editavel(ev.target)) soltarFalar(false); });

// --- Modelos: provedor, modelo e chave ---

let modelo = {};

function desenharChave() {
  const area = $("area-chave");
  if (!area) return;
  $("campo-endereco").hidden = modelo.motor !== "ponte";
  const k = modelo.chaves[modelo.motor] || { usa: false };
  if (!k.usa) {
    area.innerHTML = modelo.motor === "contas" ? '<p class="nota">Usa as contas configuradas em Contas.</p>'
      : contaEmUso(modelo.motor === "codex" ? "codex" : "claude");
    return;
  }
  const estado = k.tem ? `<span class="etiqueta bom">chave guardada · …${esc(k.fim)}</span>` : '<span class="etiqueta alerta">sem chave</span>';
  area.innerHTML = `<div class="linha">${estado}<input id="chave" type="password" class="mono" placeholder="colar chave" autocomplete="off" spellcheck="false">
    ${botao("Guardar chave", "chave-guardar")}${k.tem && k.origem === "painel" ? xis("chave-apagar", "", "Apagar chave") : ""}</div>`;
}

// --- Perfil e acesso ao Claude (também na configuração inicial) ---

let passo = 1;
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

function desenharAcesso() {
  const area = $("cartao-acesso");
  if (!area) return;
  const a = acessoTela, cerebro = area.dataset.contexto === "cerebro";
  const agente = cerebro && a.cerebro === "codex" ? "codex" : "claude";
  const cs = contasTela.agentes.find((x) => x.id === agente);
  const pronto = agente === "codex" ? Boolean(cs?.contas.find((x) => x.id === cs.em_uso)?.logado) : Boolean(a.metodo);
  const estado = pronto ? '<span class="etiqueta bom">Configurado</span>' : '<span class="etiqueta alerta">Não configurado</span>';
  const temChave = a.metodo === "chave" && a.origem === "painel";
  const topo = cerebro
    ? `<div class="cabeca"><h2>Cérebro</h2>${estado}</div>
      ${sub("Entende os pedidos com ação e usa as ferramentas do Zé.")}
      ${seletorAgente(agente)}
      <p class="nota">Modelo <span class="mono">${esc(a.modelo || "Padrão da conta")}</span></p>`
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

const lerPerfil = () => ({ nome: $("perfil-nome").value, sobre: $("perfil-sobre").value, fuso: $("perfil-fuso").value });

function mostrar(id, ok, texto) {
  const r = $(id);
  if (!r) return;
  r.className = "resultado " + (ok === null ? "" : ok ? "ok" : "erro");
  r.textContent = texto;
}

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

const lerModelo = () => ({ ligada: document.querySelector('[data-mudar="via-ligada"]').checked, motor: modelo.motor, modelo: $("modelo").value.trim(), endereco: $("endereco").value.trim() });

// --- Skills ---

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

// --- Sessões: o terminal do agente, com pasta, anexos e explorador ---

let sessaoAberta = null;
let relogioSessoes = null;
let explorador = innerWidth > 1100;
let abertas = new Set();
let modoBusca = "nomes";
let buscaPendente = null;

const matiz = (t) => [...t].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const inicial = (n) => esc((n.trim()[0] || "?").toUpperCase());
const ha = (iso) => { const s = (Date.now() - new Date(iso)) / 1000; return s < 60 ? "agora" : s < 3600 ? Math.floor(s / 60) + " min" : s < 86400 ? Math.floor(s / 3600) + " h" : Math.floor(s / 86400) + " d"; };
const encher = () => document.querySelectorAll("[data-cheio]").forEach((b) => b.style.setProperty("--cheio", b.dataset.cheio + "%"));
const pintar = (raiz) => raiz.querySelectorAll(".avatar[data-matiz]").forEach((a) => a.style.setProperty("--matiz", a.dataset.matiz));

PAGINAS.sessoes = async () => `<div class="sessoes">
  <aside class="sessoes-lista"><div class="sessoes-topo"><p class="rotulo">Sessões</p><button type="button" class="mais" data-acao="sessao-nova" aria-label="Nova sessão">+</button></div><div id="lista-sessoes"></div></aside>
  <div class="barra-voltar"><button type="button" class="voltar" data-acao="sessoes-voltar">Sessões</button></div>
  <div id="lado-sessao" class="lado"><div class="nova-sessao">${vazio("Escolha uma sessão ou crie uma no +.")}</div></div></div>`;

// No celular, uma coisa por vez: a lista ou a sessão aberta (com "Sessões" para voltar).
const mostrarLado = (sim) => document.querySelector(".sessoes")?.classList.toggle("no-lado", sim);

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

async function formSessao() {
  mostrarLado(true);
  const pastas = await api("pastas");
  $("lado-sessao").innerHTML = `<div class="nova-sessao">${cartao("Nova sessão", `
    <label>Nome<input id="ns-nome" placeholder="Ligatia — testes" autocomplete="off"></label>
    <div class="segmentos" role="group" aria-label="Onde">${botao("Pasta existente", "ns-onde", 'data-onde="existente" aria-pressed="true"')}${botao("Projeto novo", "ns-onde", 'data-onde="novo" aria-pressed="false"')}</div>
    <div class="segmentos" role="group" aria-label="Agente">${botao("Claude", "ns-motor", 'data-motor="claude" aria-pressed="true"')}${botao("Codex", "ns-motor", 'data-motor="codex" aria-pressed="false"')}</div>
    <label id="ns-campo-pasta">Pasta<input id="ns-pasta" class="mono" list="ns-pastas" placeholder="~/projetos/…" autocomplete="off" spellcheck="false"></label>
    <datalist id="ns-pastas">${pastas.map((p) => `<option value="${esc(p)}">`).join("")}</datalist>
    <label id="ns-campo-projeto" hidden>Nome da pasta<input id="ns-projeto" class="mono" placeholder="minha-loja" autocomplete="off" spellcheck="false"></label>
    <label class="interruptor" id="ns-campo-isolada"><input type="checkbox" id="ns-isolada"> Cópia isolada (só mexe no projeto quando você aprovar)</label>
    <div class="linha">${botao("Criar", "ns-criar", "", "principal")}<span class="resultado" id="ns-resultado"></span></div>`)}</div>`;
}

// Agente e conta da sessão, trocáveis ali mesmo; a faixa avisa quando a conta acabou.
let contasSessao = { agentes: [] };

const contasComLogin = () => contasSessao.agentes.flatMap((ag) =>
  ag.contas.filter((c) => c.logado).map((c) => ({ ...c, motor: ag.id, agente: ag.nome })));

// Menu de escolha próprio do painel (o <select> nativo abre com o tema do sistema, claro no Linux):
// um botão em pílula com o valor atual e uma lista que abre para cima, com grupos e o ✓ no escolhido.
function escolha(nome, rotulo, grupos, atual, titulo) {
  const itens = grupos.map((g) => (g.titulo ? `<div class="escolha-grupo">${esc(g.titulo)}</div>` : "") + g.itens.map((i) =>
    `<button type="button" role="option" class="escolha-item" data-acao="escolha-item" data-valor="${esc(i.valor)}" aria-selected="${i.valor === atual}">
      <span class="marca-escolha">${i.valor === atual ? "✓" : ""}</span><span class="texto-escolha"><strong>${esc(i.nome)}</strong>${i.detalhe ? `<small>${esc(i.detalhe)}</small>` : ""}</span></button>`).join("")).join("");
  return `<div class="escolha" data-escolha="${esc(nome)}">
    <button type="button" class="escolha-botao" data-acao="escolha-abrir" aria-haspopup="listbox" aria-expanded="false" title="${esc(titulo)}">${esc(rotulo)}<span class="seta" aria-hidden="true">▾</span></button>
    <div class="escolha-menu" role="listbox" aria-label="${esc(titulo)}" hidden>${itens}</div></div>`;
}

function fecharEscolhas(exceto) {
  document.querySelectorAll(".escolha-menu:not([hidden])").forEach((m) => {
    if (m === exceto) return;
    m.hidden = true;
    m.previousElementSibling.setAttribute("aria-expanded", "false");
  });
}

function seletorConta(sessao) {
  const grupos = contasSessao.agentes.map((ag) => ({
    titulo: ag.nome,
    itens: ag.contas.filter((c) => c.logado || c.id === sessao.conta_id).map((c) => ({
      valor: `${ag.id}|${c.id}`, nome: c.nome,
      detalhe: [c.email, c.plano && c.plano[0].toUpperCase() + c.plano.slice(1)].filter(Boolean).join(" · "),
    })),
  })).filter((g) => g.itens.length);
  const rotulo = `${sessao.agente} · ${sessao.conta || "conta em uso"}`;
  return escolha("conta-sessao", rotulo, grupos, `${sessao.motor}|${sessao.conta_id}`, "Agente e conta: a conversa continua na troca");
}

function faixaLimite(sessao) {
  if (!sessao.limite) return "";
  const outras = contasComLogin().filter((c) => c.id !== sessao.conta_id)
    .sort((a, b) => Number(b.motor === sessao.motor) - Number(a.motor === sessao.motor));
  const botoes = outras.map((c) => botao(`Continuar com ${esc(c.agente)} · ${esc(c.nome)}`, "limite-continuar",
    `data-motor="${esc(c.motor)}" data-conta="${esc(c.id)}"`, "principal")).join("");
  return `<div class="faixa limite" role="alert"><div><strong>Créditos esgotados</strong>
    <span>A conta ${esc(sessao.conta)} do ${esc(sessao.agente)} atingiu o limite de uso. Escolha outra conta para continuar de onde parou.</span></div>
    <div class="botoes">${botoes || '<span class="nota">Nenhuma outra conta com login. Adicione uma em Modelos → Contas.</span>'}</div></div>`;
}

let sessaoAtual = null;

// Enquanto o agente trabalha, a conta fica travada (a troca reabre o terminal).
function travarAjustes(trabalhando) {
  document.querySelectorAll("#ajustes-sessao .escolha-botao").forEach((el) => { el.disabled = trabalhando; });
  if (trabalhando) fecharEscolhas();
}

async function trocarSessao(motor, conta, continuar) {
  const r = await api("sessao/trocar", { id: sessaoAberta, motor, conta, continuar });
  toast(r.aviso);
  await abrirSessao(sessaoAberta);
}

async function abrirSessao(id) {
  mostrarLado(true);
  sessaoAberta = id;
  document.querySelectorAll(".item-sessao").forEach((b) => b.setAttribute("aria-current", String(b.dataset.id === id)));
  const [{ sessao }, ct] = await Promise.all([api("sessao/ler", { id, desde: 1e9 }), api("contas")]);
  contasSessao = ct;
  sessaoAtual = sessao;
  const lado = $("lado-sessao");
  const trabalhando = sessao.estado === "trabalhando";
  lado.innerHTML = `<div class="sessao-aberta ${explorador ? "" : "sem-explorador"}"><section class="conversa">
    <header class="conversa-topo"><span class="avatar" data-matiz="${matiz(sessao.nome)}">${inicial(sessao.nome)}</span>
      <div class="titulo-sessao"><h2>${esc(sessao.nome)}</h2><small title="${esc(sessao.pasta)}">${esc(sessao.pasta)}${sessao.branch ? " · cópia isolada" : ""}</small></div>
      <div class="ajustes-sessao" id="ajustes-sessao">${seletorConta(sessao)}</div>
      <span class="etiqueta ${trabalhando ? "bom" : sessao.limite ? "alerta" : ""}" id="estado-sessao" data-estado="${esc(sessao.estado)}">${esc(estadoSessao(sessao))}</span>
      <div class="botoes"><button type="button" class="mais" data-acao="anexar" aria-label="Anexar arquivo" title="Anexar arquivo (ou arraste, ou cole uma imagem)">+</button><input type="file" id="arquivos" multiple hidden>
        ${botao("Arquivos", "explorador", `aria-pressed="${explorador}"`)}${xis("sessao-excluir", "", "Excluir sessão")}</div></header>
    <div id="limite-sessao" data-limite="${sessao.limite}">${faixaLimite(sessao)}</div>
    <div id="melhorias-ze"></div>
    <section class="editor-md" id="editor-md" hidden>
      <div class="linha"><label>Arquivo<input id="md-nome" class="mono" placeholder="NOTAS.md" autocomplete="off" spellcheck="false"></label>
        <label class="interruptor"><input type="checkbox" id="md-substituir"> Substituir se existir</label></div>
      <textarea id="md-texto" class="mono" rows="10"></textarea>
      <div class="linha">${botao("Salvar na pasta", "md-salvar", "", "principal")}${botao("Cancelar", "md-fechar", "", "discreta")}</div>
    </section>
    <section class="previa-arquivo" id="previa" hidden></section>
    <div class="terminal-sessao" id="terminal"></div>
    <div class="terminal-fechado" id="terminal-fechado" hidden><strong>Terminal fechado</strong>
      <span>Ao reabrir, a conversa continua de onde parou.</span>${botao("Reabrir", "terminal-reabrir", "", "principal")}</div>
    </section>
    <aside class="explorador" aria-label="Arquivos">
      <header><strong title="${esc(sessao.pasta)}">${esc(sessao.pasta.split("/").pop())}</strong>
        <button type="button" class="icone" data-acao="md-abrir" title="Novo arquivo" aria-label="Novo arquivo">+</button>
        <button type="button" class="icone" data-acao="arvore-recolher" title="Recolher tudo" aria-label="Recolher tudo">⇤</button>
        <button type="button" class="icone" data-acao="arvore-atualizar" title="Atualizar" aria-label="Atualizar">↻</button>
        <button type="button" class="icone" id="fechar-explorador" data-acao="explorador" title="Voltar ao terminal" aria-label="Voltar ao terminal">✕</button></header>
      <input id="buscar-arquivos" type="search" placeholder="Buscar" autocomplete="off" spellcheck="false">
      <div class="seg" role="group" aria-label="Buscar por">${botao("Nome", "busca-modo", 'data-modo="nomes" aria-pressed="true"')}${botao("Conteúdo", "busca-modo", 'data-modo="conteudo" aria-pressed="false"')}</div>
      <div class="arvore" id="arvore" role="tree"></div>
    </aside></div>`;
  pintar(lado);
  abertas = new Set();
  travarAjustes(trabalhando);
  if (sessao.melhorias) carregarPagina("melhorias").then(() => desenharMelhorias()).catch(() => {});
  await abrirTerminal(id);
  await carregarPasta("", $("arvore"));
}

// --- o terminal real da sessão (xterm.js): o agente com todos os comandos dele ---

let term = null, termId = null, termPos = 0, termObservador = null, filaEscrita = Promise.resolve();
const TEMA_TERMINAL = { background: "#070c11", foreground: "#e6f4f5", cursor: "#46d9de", cursorAccent: "#070c11",
  selectionBackground: "rgba(70, 217, 222, .28)", black: "#0b131a", brightBlack: "#5c7a80" };

function fecharTerminalTela() {
  termId = null;
  termObservador?.disconnect();
  termObservador = null;
  term?.dispose();
  term = null;
}

async function abrirTerminal(id) {
  fecharTerminalTela();
  const caixa = $("terminal");
  term = new Terminal({ fontFamily: 'ui-monospace, "JetBrains Mono", "SF Mono", Menlo, monospace', fontSize: 13,
    lineHeight: 1.15, cursorBlink: true, scrollback: 8000, theme: TEMA_TERMINAL });
  const ajuste = new FitAddon.FitAddon();
  term.loadAddon(ajuste);
  term.open(caixa);
  try { ajuste.fit(); } catch { /* fora da tela */ }
  termId = id;
  $("terminal-fechado").hidden = true;
  try {
    const { posicao } = await api("terminal/abrir", { id, colunas: term.cols, linhas: term.rows });
    termPos = posicao;
  } catch (erro) {
    toast(erro.message);
    $("terminal-fechado").hidden = false;
    return;
  }
  term.onData((d) => escreverNoTerminal(d));
  term.onResize(({ cols, rows }) => api("terminal/tamanho", { id, colunas: cols, linhas: rows }).catch(() => {}));
  termObservador = new ResizeObserver(() => { try { ajuste.fit(); } catch { /* fora da tela */ } });
  termObservador.observe(caixa);
  term.focus();
  lerTerminal(id);
}

// As teclas vão em ordem (uma requisição por vez); senão o agente recebe letras trocadas.
function escreverNoTerminal(dados) {
  const id = termId;
  if (!id) return;
  filaEscrita = filaEscrita.then(() => api("terminal/escrever", { id, dados })).catch(() => {});
}

async function lerTerminal(id) {
  while (termId === id) {
    try {
      const r = await api("terminal/ler", { id, desde: termPos });
      if (termId !== id) return;
      if (r.dados) term.write(Uint8Array.from(atob(r.dados), (c) => c.charCodeAt(0)));
      termPos = r.posicao;
      if (!r.vivo) { $("terminal-fechado").hidden = false; return; }
    } catch { await new Promise((ok) => setTimeout(ok, 1000)); }
  }
}

async function acompanharSessao() {
  if (!sessaoAberta || !$("terminal")) return;
  const { sessao } = await api("sessao/ler", { id: sessaoAberta, desde: 1e9 });
  sessaoAtual = sessao;
  const etiqueta = $("estado-sessao");
  if (etiqueta.dataset.estado === "trabalhando" && sessao.estado !== "trabalhando") {
    atualizarArvore();
    if (sessao.melhorias) window.desenharMelhorias?.();
  }
  etiqueta.dataset.estado = sessao.estado;
  etiqueta.textContent = estadoSessao(sessao);
  etiqueta.classList.toggle("alerta", !!sessao.limite);
  etiqueta.classList.toggle("bom", sessao.estado === "trabalhando");
  travarAjustes(sessao.estado === "trabalhando");
  const faixa = $("limite-sessao");
  if (faixa.dataset.limite !== String(sessao.limite)) {
    faixa.dataset.limite = String(sessao.limite);
    faixa.innerHTML = faixaLimite(sessao);
  }
}

async function prepararSessoes() {
  await listaSessoes();
  // A sessão do Zé (Melhorias) não abre aqui: só as que estão na lista.
  if (sessaoAberta && !document.querySelector(`.item-sessao[data-id="${sessaoAberta}"]`)) sessaoAberta = null;
  if (sessaoAberta) await abrirSessao(sessaoAberta).catch(() => { sessaoAberta = null; });
  let volta = 0;
  relogioSessoes = setInterval(async () => {
    try { await acompanharSessao(); if (++volta % 2 === 0) await listaSessoes(); } catch { /* o batimento mostra se o Zé caiu */ }
  }, 1500);
}

// Anexos (arrastar, colar ou "+"): o arquivo sobe para a pasta da sessão e o caminho vai para o
// terminal, onde o agente lê.
async function anexar(lista) {
  for (const a of lista) {
    if (a.size > 20 * 1024 * 1024) { toast(a.name + ": maior que 20 MB."); continue; }
    const f = a.name ? a : new File([a], "colado-" + Date.now() + "." + (a.type.split("/")[1] || "png"), { type: a.type });
    try { escreverNoTerminal(`"${await subirAnexo(f)}" `); } catch (erro) { toast(erro.message); }
  }
  term?.focus();
}

async function subirAnexo(arquivo) {
  const r = await fetch(`/api/sessao/anexo?id=${encodeURIComponent(sessaoAberta)}&nome=${encodeURIComponent(arquivo.name)}`,
    { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: arquivo });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(arquivo.name + ": " + (dados.erro || "falha"));
  return dados.caminho;
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
  $("terminal").hidden = true;
}

function fecharPrevia() {
  if ($("previa")) { $("previa").hidden = true; $("previa").innerHTML = ""; }
  if ($("terminal")) { $("terminal").hidden = false; term?.focus(); }
}

// --- Imersão no celular: o holograma do Zé reagindo à conversa (a completa é só do PC) ---

const ESTADO_HOLO = { inativo: "Inativo", ativo: "Pronto", ouvindo: "Ouvindo", pensando: "Pensando", falando: "Falando", confirmando: "Esperando o seu sim" };
let estadoZe = "inativo";
const telaHolograma = () => `<div class="holo" data-estado="${estadoZe}">
  <div class="holo-palco"><img src="/imagens/holograma.webp" alt="O Zé" width="780" height="780" decoding="async"></div>
  <p class="holo-estado" id="holo-estado">${ESTADO_HOLO[estadoZe] || ""}</p>
  <div class="holo-botoes"><div class="voz-remota" id="voz-holo"></div><button type="button" class="acao" data-falar aria-pressed="false">Falar</button></div>
</div>`;

// --- Imersão: o modo imersivo de sempre, numa moldura ---

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

// A Imersão só roda à vista: sair dela ou esconder o painel desliga a câmera e o holograma.
document.addEventListener("visibilitychange", () => {
  if (location.hash !== "#imersao" || !NO_PC) return;
  if (document.visibilityState === "hidden") desligarImersao(); else ligarImersao();
});

// --- o despachante: cada data-acao faz uma coisa ----------------------------------------------------

const recarregar = () => abrir();

const ACOES = {
  "cerebro-escolher": async (b) => {
    const c = await ocupado(b, () => api("cerebro/escolher", { agente: b.dataset.agente }));
    acessoTela.cerebro = c.completo.provedor; acessoTela.modelo = c.completo.modelo;
    desenharAcesso(); toast(c.aviso || "Agente atualizado.");
  },
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
  "perfil-salvar": async (b) => {
    const r = await ocupado(b, () => api("perfil", lerPerfil()));
    if (b.dataset.seguir) { passo = Number(b.dataset.seguir); await abrir(); toast(r.aviso); return; }
    mostrar("resultado-perfil", true, r.aviso);
  },
  passo: async (b) => { passo = Number(b.dataset.passo); await abrir(); },
  "configuracao-concluir": () => { passo = 1; location.hash = "#inicio"; toast("Configuração concluída."); },
  "conta-adicionar": async (b) => {
    const campo = document.querySelector(`[data-nova-conta="${b.dataset.agente}"]`);
    const r = await ocupado(b, () => api("conta/adicionar", { agente: b.dataset.agente, nome: campo.value }));
    contasTela = r; desenharContas(); desenharAcesso(); mostrar("resultado-contas", true, r.aviso);
  },
  "conta-usar": async (b) => {
    const r = await ocupado(b, () => api("conta/usar", { id: b.dataset.id }));
    contasTela = r; desenharContas(); desenharAcesso(); toast(r.aviso);
  },
  "conta-entrar": async (b) => {
    const r = await ocupado(b, () => api("conta/entrar", { id: b.dataset.id }));
    mostrar("resultado-contas", r.aberto, r.aviso);
    vigiarContas();
  },
  "conta-remover": (b) => confirmar(b, "Remover a conta e o login dela?", async () => {
    const r = await api("conta/remover", { id: b.dataset.id });
    contasTela = r; desenharContas(); desenharAcesso(); toast(r.aviso);
  }),
  "acesso-salvar": async (b) => {
    const r = await ocupado(b, () => api("acesso/chave", { chave: $("segredo-acesso").value }));
    acessoTela = { ...acessoTela, ...r.acesso, agentes: r.agentes }; desenharAcesso();
    mostrar("resultado-acesso", true, r.aviso);
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
  "sessoes-voltar": () => {
    fecharTerminalTela(); sessaoAberta = null; mostrarLado(false);
    document.querySelectorAll(".item-sessao").forEach((x) => x.setAttribute("aria-current", "false"));
  },
  "sessao-nova": async () => { sessaoAberta = null; document.querySelectorAll(".item-sessao").forEach((x) => x.setAttribute("aria-current", "false")); await formSessao(); },
  "sessao-abrir": (b) => abrirSessao(b.dataset.id),
  "ns-onde": (b) => {
    document.querySelectorAll('[data-acao="ns-onde"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    const novo = b.dataset.onde === "novo";
    $("ns-campo-pasta").hidden = novo; $("ns-campo-projeto").hidden = !novo; $("ns-campo-isolada").hidden = novo;
  },
  "ns-motor": (b) => document.querySelectorAll('[data-acao="ns-motor"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b))),
  "ns-criar": async (b) => {
    const novo = !$("ns-campo-projeto").hidden;
    const motor = document.querySelector('[data-acao="ns-motor"][aria-pressed="true"]').dataset.motor;
    const s = await ocupado(b, () => api("sessao/criar", { nome: $("ns-nome").value, pasta: $("ns-pasta").value, motor, novo, projeto: $("ns-projeto").value, isolada: !novo && $("ns-isolada").checked }));
    await listaSessoes(); await abrirSessao(s.id);
  },
  "sessao-excluir": (b) => confirmar(b, "Excluir sessão e encerrar o agente? A pasta do projeto fica.", async () => {
    const r = await api("sessao/excluir", { id: sessaoAberta });
    sessaoAberta = null; toast(r.aviso || "Sessão excluída."); await recarregar();
  }),
  "escolha-abrir": (b) => {
    const menu = b.nextElementSibling, abrir = menu.hidden;
    fecharEscolhas(menu);
    menu.hidden = !abrir;
    b.setAttribute("aria-expanded", String(abrir));
    if (abrir) (menu.querySelector('[aria-selected="true"]') || menu.querySelector(".escolha-item"))?.focus();
  },
  "escolha-item": async (b) => {
    const caixa = b.closest(".escolha"), valor = b.dataset.valor;
    fecharEscolhas();
    if (b.getAttribute("aria-selected") === "true") return;
    await ESCOLHAS[caixa.dataset.escolha]?.(valor);
  },
  "limite-continuar": async (b) => { await ocupado(b, () => trocarSessao(b.dataset.motor, b.dataset.conta, true)); },
  "md-abrir": () => { $("editor-md").hidden = false; $("md-nome").focus(); },
  "md-fechar": () => { $("editor-md").hidden = true; },
  "md-salvar": async (b) => {
    const r = await ocupado(b, () => api("sessao/arquivo", { id: sessaoAberta, nome: $("md-nome").value, conteudo: $("md-texto").value, sobrescrever: $("md-substituir").checked }));
    $("editor-md").hidden = true; $("md-nome").value = $("md-texto").value = "";
    toast("Salvo: " + r.arquivo); await acompanharSessao(); await atualizarArvore();
  },
  anexar: () => $("arquivos").click(),
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
  mencionar: (b) => { fecharPrevia(); escreverNoTerminal("@" + b.dataset.caminho + " "); },
  "terminal-reabrir": () => abrirTerminal(sessaoAberta),
  "modo-fala": (b) => mudarModoFala(b.dataset.modo),
  "voz-remota": ligarVoz,
  "remoto-ativar": async (b) => { const r = await ocupado(b, () => api("remoto/ativar", {})); toast(r.aviso); await recarregar(); },
  "remoto-desativar": async (b) => { const r = await ocupado(b, () => api("remoto/desativar", {})); toast(r.aviso); await recarregar(); },
  "senha-salvar": async (b) => { const r = await ocupado(b, () => api("acesso/senha", { senha: $("senha-acesso").value })); toast(r.aviso); await recarregar(); },
  "codigo-preparar": async (b) => { codigoPreparado = await ocupado(b, () => api("acesso/codigo/preparar", {})); await recarregar(); },
  "codigo-confirmar": async (b) => { const r = await ocupado(b, () => api("acesso/codigo/confirmar", { codigo: $("codigo-confirmar").value })); codigoPreparado = null; toast(r.aviso); await recarregar(); },
  "codigo-desligar": (b) => confirmar(b, "Desligar o código? O acesso de fora também será desativado.", async () => { const r = await api("acesso/codigo/desligar", {}); toast(r.aviso); await recarregar(); }),
  "aparelho-desconectar": async (b) => { const r = await ocupado(b, () => api("acesso/desconectar", { id: b.dataset.id })); toast(r.aviso); await recarregar(); },
  "tunel-ativar": async (b) => { const r = await ocupado(b, () => api("tunel/ativar", {})); toast(r.aviso); await recarregar(); },
  "tunel-desativar": async (b) => { const r = await ocupado(b, () => api("tunel/desativar", {})); toast(r.aviso); await recarregar(); },
  "remoto-copiar": async (b) => { await navigator.clipboard.writeText(b.dataset.endereco); toast("Endereço copiado."); },
  grupo: alternarGrupo,
  menu: () => {
    const aberto = document.body.classList.toggle("menu-aberto");
    document.querySelector(".botao-menu").setAttribute("aria-expanded", String(aberto));
  },
  "chamado-modo": async (b) => { const r = await api("voz/chamado", { modo: b.dataset.modo }); toast(r.aviso); await recarregar(); },
  "escuta-modo": async (b) => { const r = await api("escuta/modo", { modo: b.dataset.modo }); toast(r.aviso); await recarregar(); },
};

// O que cada menu de escolha faz com o valor escolhido.
const ESCOLHAS = {
  "modo-fala": mudarModoFala,
  "conta-sessao": async (valor) => {
    const [motor, conta] = valor.split("|");
    await trocarSessao(motor, conta, !!document.querySelector(".faixa.limite"));
  },
};

const MUDAR = {
  automacao: async (el) => { await api("automacao/ativar", { id: el.dataset.id, ativo: el.checked }); await recarregar(); },
  skill: async (el) => { await api("skill/ligar", { nome: el.dataset.nome, ligada: el.checked }); toast(el.checked ? "Ligada." : "Desligada."); await recarregar(); },
  "via-ligada": () => {},

};

document.addEventListener("click", (ev) => { if (!ev.target.closest(".escolha")) fecharEscolhas(); }, true);
document.addEventListener("keydown", (ev) => {
  if (!ev.altKey || ev.ctrlKey || ev.metaKey || ev.code !== "KeyM" || !modoFala) return;
  ev.preventDefault(); ev.stopPropagation();
  const i = MODOS_FALA.findIndex((m) => m.valor === modoFala);
  mudarModoFala(MODOS_FALA[(i + 1) % MODOS_FALA.length].valor).catch((erro) => toast(erro.message));
}, true);
document.addEventListener("keydown", (ev) => {
  const menu = ev.target.closest?.(".escolha-menu");
  if (ev.key === "Escape" && document.querySelector(".escolha-menu:not([hidden])")) { fecharEscolhas(); return; }
  if (!menu || !["ArrowDown", "ArrowUp"].includes(ev.key)) return;
  ev.preventDefault();
  const itens = [...menu.querySelectorAll(".escolha-item")], i = itens.indexOf(ev.target);
  itens[(i + (ev.key === "ArrowDown" ? 1 : itens.length - 1)) % itens.length]?.focus();
});

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

conteudo.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && (ev.target.dataset.nova || ev.target.dataset.novaConta || ev.target.id === "passo-novo")) { ev.preventDefault(); ev.target.closest(".add").querySelector("button").click(); }
});

conteudo.addEventListener("input", (ev) => {
  if (ev.target.id !== "buscar-arquivos") return;
  clearTimeout(buscaPendente);
  buscaPendente = setTimeout(() => buscarArquivos().catch((e) => toast(e.message)), 250);
});

conteudo.addEventListener("paste", (ev) => {
  if (!$("terminal") || !ev.clipboardData?.files.length || ev.target.id === "md-texto") return;
  ev.preventDefault(); anexar(ev.clipboardData.files);
});
for (const tipo of ["dragenter", "dragover"]) conteudo.addEventListener(tipo, (ev) => {
  if (!$("terminal") || !ev.dataTransfer?.types.includes("Files")) return;
  ev.preventDefault(); document.querySelector(".conversa")?.classList.add("soltando");
});
conteudo.addEventListener("dragleave", (ev) => { if (!ev.relatedTarget || !conteudo.contains(ev.relatedTarget)) document.querySelector(".conversa")?.classList.remove("soltando"); });
conteudo.addEventListener("drop", (ev) => {
  if (!$("terminal") || !ev.dataTransfer?.files.length) return;
  ev.preventDefault(); document.querySelector(".conversa")?.classList.remove("soltando"); anexar(ev.dataTransfer.files);
});

// --- navegação e batimento ---

// Páginas pouco usadas carregam sob demanda: o painel abre leve (docs/plano-painel.md).
const SOB_DEMANDA = { atividade: "/paginas/atividade.js", melhorias: "/paginas/melhorias.js", conectores: "/paginas/conectores.js", conversa: "/paginas/conversa.js" };
const CHEIAS = ["sessoes", "melhorias", "conversa"]; // páginas sem margem, que ocupam a tela
const carregados = {};
const carregarPagina = (nome) => (carregados[nome] ??= new Promise((ok, erro) => {
  const s = document.createElement("script");
  s.src = SOB_DEMANDA[nome]; s.onload = ok; s.onerror = () => { delete carregados[nome]; erro(new Error("Página indisponível.")); };
  document.head.appendChild(s);
}));

async function abrir() {
  const nome = (location.hash || "#inicio").slice(1);
  const secao = PAGINAS[nome] || SOB_DEMANDA[nome] || nome === "imersao" ? nome : "inicio";
  document.querySelectorAll("nav a").forEach((a) => (a.dataset.secao === secao ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  document.querySelector(`nav a[data-secao="${secao}"]`)?.closest(".grupo")?.querySelector(".grupo-titulo").setAttribute("aria-expanded", "true");
  imersao.hidden = secao !== "imersao";
  conteudo.hidden = secao === "imersao";
  document.body.classList.remove("menu-aberto");
  document.body.classList.toggle("tela-holo", secao === "imersao" && !NO_PC);
  conteudo.classList.toggle("cheio", CHEIAS.includes(secao));
  clearInterval(relogioSessoes);
  fecharTerminalTela();
  if (secao !== "imersao" && imersaoLigada()) desligarImersao();
  if (secao === "imersao" && !NO_PC) {
    imersao.hidden = true; conteudo.hidden = false;
    conteudo.innerHTML = telaHolograma(); desenharVozRemota();
    return;
  }
  if (secao === "imersao") { ligarImersao(); return; }
  try {
    if (SOB_DEMANDA[secao]) await carregarPagina(secao);
    const html = await PAGINAS[secao]();
    conteudo.innerHTML = CHEIAS.includes(secao) ? html : `<div class="secao">${html}</div>`;
    if (secao === "modelos") { desenharChave(); desenharEscuta(); desenharAcesso(); desenharContas(); }
    if (secao === "configurar") { desenharAcesso(); desenharEscuta(); desenharContas(); }
    encher();
    if (secao === "sessoes") await prepararSessoes();
    if (secao === "melhorias") await prepararMelhorias();
    if (secao === "conversa") await prepararConversa();
  } catch (erro) {
    conteudo.innerHTML = `<div class="secao">${cabeca("Sem conexão com o Zé")}<p class="aviso">${esc(erro.message)}</p></div>`;
  }
}

let telaVista = null;
let inicioZe = null; let semResposta = 0; let telaDita;
// Fora do ar: faixa no topo; o Zé volta noutro processo e o painel recarrega
function faixaFora(ligar) {
  let f = document.querySelector(".faixa-fora");
  if (ligar && !f) { f = document.createElement("div"); f.className = "faixa-fora"; f.role = "status"; f.textContent = "Reconectando…"; document.body.append(f); }
  if (!ligar) f?.remove();
}
async function batimento() {
  try {
    const e = await api("estado");
    if (inicioZe !== null && e.inicio !== inicioZe) { location.reload(); return; }
    inicioZe = e.inicio; semResposta = 0; faixaFora(false);
    // O que o Zé não falou (Silencioso) aparece em qualquer página
    const tela = e.tela?.[0] ?? null;
    if (telaDita !== undefined && tela !== telaDita && location.hash !== "#conversa") toast(e.tela[1]);
    telaDita = tela;
    if (telaVista !== null && e.tela_ts > telaVista && imersaoLigada() && location.hash !== "#imersao") location.hash = "#imersao";
    telaVista = e.tela_ts;
    const icone = document.querySelector(".icone-ze");
    icone.dataset.estado = e.ze; icone.title = `Zé ${ESTADOS[e.ze] || e.ze}`;
    estadoZe = e.ze;
    const holo = document.querySelector(".holo");
    if (holo && holo.dataset.estado !== e.ze) { holo.dataset.estado = e.ze; $("holo-estado").textContent = ESTADO_HOLO[e.ze] || ""; }
    desenharModoFala(e.modo_fala);
    document.body.classList.toggle("manutencao", !!e.manutencao?.ligada); window.desenharManutencao?.(e.manutencao);
    desenharVozRemota();
    if (sessaoAberta && $("terminal") && document.visibilityState === "visible" && document.hasFocus()) {
      api("painel/vendo", { sessao: sessaoAberta }).catch(() => {});
    }
  } catch (erro) {
    if (erro.message === "token") { location.reload(); return; } // o Zé voltou com chave nova
    Object.assign(document.querySelector(".icone-ze"), { title: "Zé desconectado" }).dataset.estado = "inativo";
    if (++semResposta >= 3) faixaFora(true);
  }
}

// Sem perfil, o painel abre na configuração inicial.
async function comecar() {
  try { if (!location.hash && !(await api("configuracao")).feita) location.hash = "#configurar"; } catch { /* o batimento mostra */ }
  abrir();
}

window.addEventListener("hashchange", abrir);
comecar();
batimento();
setInterval(batimento, 1000);
