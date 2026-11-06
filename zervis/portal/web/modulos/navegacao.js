// --- navegação e batimento ---

// Páginas pouco usadas carregam sob demanda: o painel abre leve (docs/plano-painel.md).
/** @type {Record<string, string>} */
const SOB_DEMANDA = {"atividade":"/paginas/atividade.js","melhorias":"/paginas/melhorias.js","conectores":"/paginas/conectores.js","conversa":"/paginas/conversa.js","skills":"/paginas/skills.js","memoria":"/paginas/memoria.js","atendimento":"/paginas/atendimento.js","sessoes":"/paginas/sessoes.js","inicio":"/paginas/inicio.js","foco":"/paginas/foco.js","automacoes":"/paginas/automacoes.js","modelos":"/paginas/modelos.js","perfil":"/paginas/perfil.js","configurar":"/paginas/configurar.js","voz":"/paginas/voz.js","atualizacoes":"/paginas/atualizacoes.js","pesquisas":"/paginas/pesquisas.js"};
const CHEIAS = ["sessoes", "melhorias", "conversa"]; // páginas sem margem, que ocupam a tela
/** @type {Record<string, string[]>} */
const DEPENDENCIAS = {
 modelos: ['/modulos/modelos.js'], perfil: ['/modulos/modelos.js'], configurar: ['/modulos/modelos.js'],
 sessoes: ['/vendor/xterm/xterm.js', '/vendor/xterm/addon-fit.js', '/modulos/terminal.js', '/modulos/conectores-sessao.js', '/modulos/permissoes-sessao.js'],
 melhorias: ['/vendor/xterm/xterm.js', '/vendor/xterm/addon-fit.js', '/modulos/terminal.js', '/modulos/conectores-sessao.js', '/modulos/permissoes-sessao.js', '/paginas/sessoes.js'],
};
/** @type {Record<string, Promise<void>>} */
const carregados = {};
/** @param {string} caminho @returns {Promise<void>} */
function carregarScript(caminho) {
 return (carregados[caminho] ??= new Promise((ok, erro) => {
  const s = document.createElement('script');
  s.src = caminho; s.onload = () => ok();
  s.onerror = () => { delete carregados[caminho]; erro(new Error('Página indisponível.')); };
  document.head.appendChild(s);
 }));
}
/** @param {string} caminho @returns {Promise<void>} */
function carregarEstilo(caminho) {
 return (carregados[caminho] ??= new Promise((ok, erro) => {
  const estilo = document.createElement('link');
  estilo.rel = 'stylesheet'; estilo.href = caminho;
  estilo.onload = () => ok();
  estilo.onerror = () => { delete carregados[caminho]; estilo.remove(); erro(new Error('Página indisponível.')); };
  document.head.appendChild(estilo);
 }));
}
/** @param {string} nome */
async function carregarPagina(nome) {
 if (["sessoes", "melhorias"].includes(nome)) await carregarEstilo("/vendor/xterm/xterm.css");
 for (const caminho of DEPENDENCIAS[nome] || []) await carregarScript(caminho);
 await carregarScript(SOB_DEMANDA[nome]);
}

// Sem cópia guardada: páginas com terminal ou relógio próprio, e a configuração inicial.
const SEM_GUARDA = [...CHEIAS, "atendimento", "configurar", "pesquisas"];

/** Desenha uma página no conteúdo e liga o que depende dela.
 * @param {string} secao @param {string} html */
function mostrarPagina(secao, html) {
  conteudo.innerHTML = CHEIAS.includes(secao) ? html : `<div class="secao">${html}</div>`;
  if (secao === "modelos") { desenharChave(); desenharEscuta(); desenharAcesso(); desenharContas(); }
  if (secao === "configurar") { desenharAcesso(); desenharEscuta(); desenharContas(); }
  encher();
}

/** A pessoa está digitando na página: trocar o desenho apagaria o que ela escreveu. */
function editando() {
  const a = document.activeElement;
  return !!a && conteudo.contains(a) && a.matches("input, textarea, select, [contenteditable]");
}

async function abrir() {
  const vez = ++navegacao;
  const nome = (location.hash || "#inicio").slice(1);
  const secao = PAGINAS[nome] || SOB_DEMANDA[nome] || nome === "imersao" ? nome : "inicio";
  /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll("nav a")).forEach((a) => (a.dataset.secao === secao ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  const grupo = document.querySelector(`nav a[data-secao="${secao}"]`)?.closest(".grupo");
  grupo?.querySelector(".grupo-titulo")?.setAttribute("aria-expanded", "true");
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
    const guardada = SEM_GUARDA.includes(secao) ? undefined : cachePaginas.get(secao);
    if (guardada !== undefined) mostrarPagina(secao, guardada); // na hora; abaixo, a versão nova
    const gravacoesAntes = gravacoes;
    /** @type {string} */ let html;
    try { html = await PAGINAS[secao](); } catch (erro) {
      if (guardada !== undefined) return; // sem resposta: fica o que já estava; a faixa avisa a queda
      throw erro;
    }
    if (vez !== navegacao) return;
    if (!SEM_GUARDA.includes(secao) && gravacoes === gravacoesAntes) cachePaginas.set(secao, html);
    if (html !== guardada && !(guardada !== undefined && editando())) mostrarPagina(secao, html);
    if (secao === "sessoes") await prepararSessoes(vez);
    if (secao === "melhorias") await prepararMelhorias(vez);
    if (secao === "conversa") await prepararConversa(vez);
  } catch (erro) {
    if (vez !== navegacao) return;
    conteudo.innerHTML = `<div class="secao">${cabeca("Não foi possível abrir a página")}<p class="aviso">${esc(erro.message)}</p></div>`;
  }
}

// --- aplicar as melhorias: etapas reais; percentual e duração são estimativas ---

/** @type {Record<string, string>} */
const TITULOS_ATUALIZACAO = {
  aguardando: "Aguardando sessões", aplicando: "Aplicando melhorias", falhou: "Atualização interrompida",
  pronto: "Atualização aplicada", voltou: "Versão anterior restaurada",
};
/** @type {Atualizacao | null} */
let atualizacao = null;
let atualizacaoRecebida = 0;
let cicloAtualizacao = 0;

/** @param {number} s */
const relogioMinutos = (s) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, "0")}`;
const atualizando = () => ["aplicando", "aguardando"].includes(atualizacao?.estado);
let versaoAplicada = 0; // quando a página Atualizações mandou atualizar (o Zé vai reiniciar)
// Só a fase de reinício explica a desconexão; nas demais, a faixa continua avisando a queda.
const reiniciando = () => (atualizacao?.estado === "aplicando"
  && atualizacao.etapas.some((e) => e.id === "reiniciando" && e.estado === "atual")
  && Date.now() - atualizacaoRecebida < 300000) || Date.now() - versaoAplicada < 180000;

/** @param {Atualizacao | null} [a] */
function desenharAtualizacao(a) {
  if (a !== undefined) {
    const estavaAtualizando = atualizando();
    atualizacao = a; atualizacaoRecebida = Date.now();
    if (!estavaAtualizando && atualizando()) cicloAtualizacao++;
  }
  window.desenharTravaSessoes?.();
  let cartao = /** @type {HTMLElement | null} */ (document.querySelector(".atualizacao"));
  let fechado = "";
  try { fechado = sessionStorage.getItem("atualizacao-fechada") || ""; } catch { /* sem armazenamento */ }
  if (!atualizacao || (atualizacao.fim && String(atualizacao.fim) === fechado)) { cartao?.remove(); return; }
  if (!cartao) {
    cartao = document.createElement("section");
    cartao.className = "atualizacao";
    cartao.setAttribute("aria-label", "Andamento da atualização");
    document.body.append(cartao);
  }
  const a2 = atualizacao;
  const extra = atualizando() ? Math.max(0, (Date.now() - atualizacaoRecebida) / 1000) : 0;
  const etapas = a2.etapas.map((e) => ({ ...e, segundos: e.segundos + (e.estado === "atual" ? extra : 0) }));
  const total = etapas.reduce((t, e) => t + (e.estado === "feita" ? e.segundos : e.estimado), 0) || 1;
  const feito = etapas.reduce((t, e) => t + (e.estado === "feita" ? e.segundos : ["atual", "falhou"].includes(e.estado) ? Math.min(e.segundos, e.estimado * 0.95) : 0), 0);
  const pct = a2.estado === "pronto" ? 100 : Math.min(99, Math.max(0, Math.round((feito / total) * 100)));
  /** @type {Record<string, string>} */
  const marca = { feita: "✓", atual: "●", pendente: "○", falhou: "!" };
  const lista = a2.estado === "aguardando" ? "" : `<ol>${etapas.map((e) => `<li class="${e.estado}"><span class="marca">${marca[e.estado]}</span><span>${esc(e.titulo)}</span>
    <small>${e.estado === "pendente" ? "~" + relogioMinutos(e.estimado) : relogioMinutos(e.segundos)}</small></li>`).join("")}</ol>`;
  const rodape = a2.estado === "aplicando" ? "Reinício automático ao concluir. Tempo estimado."
    : a2.estado === "aguardando" ? "A atualização começa quando as sessões terminarem." : a2.texto;
  const final = !atualizando();
  // Mantém o DOM entre etapas: o relógio não recria botões nem anúncios a cada segundo.
  const desenho = JSON.stringify([a2.estado, etapas.map((e) => e.estado), a2.texto]);
  cartao.dataset.estado = a2.estado;
  if (cartao.dataset.desenho !== desenho) {
    cartao.dataset.desenho = desenho;
    cartao.innerHTML = `<header><strong role="status">${TITULOS_ATUALIZACAO[a2.estado] || ""}</strong><span class="espaco"></span>
        <time aria-label="Tempo decorrido"></time>${final ? `<button type="button" class="icone" data-acao="atualizacao-fechar" aria-label="Fechar">✕</button>` : ""}</header>
      <div class="barra" role="progressbar" aria-label="Progresso estimado" aria-valuemin="0" aria-valuemax="100"><span></span></div>
      ${lista}<p>${esc(rodape)}</p>${a2.estado === "aplicando" ? '<small class="restante"></small>' : ""}`;
  }
  cartao.querySelector("time").textContent = relogioMinutos(a2.decorrido + extra);
  const barra = cartao.querySelector("[role=progressbar]");
  if (a2.estado === "aguardando") barra.removeAttribute("aria-valuenow");
  else barra.setAttribute("aria-valuenow", String(pct));
  /** @type {HTMLElement} */ (barra.firstElementChild).style.width = `${pct}%`;
  cartao.querySelectorAll("li small").forEach((el, i) => {
    const e = etapas[i];
    el.textContent = e.estado === "pendente" ? "~" + relogioMinutos(e.estimado) : relogioMinutos(e.segundos);
  });
  const restante = cartao.querySelector(".restante");
  if (restante) restante.textContent = `Restante estimado: ~${relogioMinutos(Math.max(1, total - feito))}`;

}

let telaVista = null;
let inicioZe = null; let semResposta = 0; let telaDita;
// Fora do ar: faixa no topo; o Zé volta noutro processo e o painel recarrega
function faixaFora(ligar) {
  let f = /** @type {HTMLElement} */ (document.querySelector(".faixa-fora"));
  if (ligar && !f) { f = document.createElement("div"); f.className = "faixa-fora"; f.role = "status"; f.textContent = "Reconectando…"; document.body.append(f); }
  if (!ligar) f?.remove();
}
// A barra de carregamento no topo (ADR 0064): um painel holográfico como as apresentações do Zé,
// com o que ele está fazendo e uma barra em células que anda como num jogo, rápida no começo e mais
// devagar perto do fim; só completa quando a resposta começa.
const andamento = { ativo: false, inicio: 0, base: 0, desde: 0, tau: 3, texto: "", visto: 0, saiu: 0, fim: 0, mostrado: 0 };
const ANDAMENTO_TETO = 0.95;
const agoraS = () => performance.now() / 1000;
const progressoAndamento = (t) => andamento.base + (ANDAMENTO_TETO - andamento.base) * (1 - Math.exp(-(t - andamento.desde) / andamento.tau));

/** @param {string} texto @param {number} esperado */
function etapaAndamento(texto, esperado) {
  const t = agoraS();
  andamento.base = Math.min(ANDAMENTO_TETO, andamento.ativo ? progressoAndamento(t) : 0);
  andamento.desde = t; andamento.tau = Math.max(0.6, esperado); andamento.texto = texto;
  const rotulo = /** @type {HTMLElement | null} */ (document.querySelector("#andamento .andamento-rotulo"));
  if (!rotulo) return;
  rotulo.textContent = `${texto}…`;
  rotulo.classList.remove("novo"); void rotulo.offsetWidth; rotulo.classList.add("novo");
}

/** @param {string} estado @param {{rotulo?: string, esperado_s?: number, ts?: number} | undefined} passo */
function andamentoPainel(estado, passo) {
  let barra = $("andamento");
  if (!barra) {
    barra = document.createElement("div");
    barra.id = "andamento"; barra.setAttribute("role", "progressbar"); barra.setAttribute("aria-label", "O que o Zé está fazendo");
    barra.setAttribute("aria-valuemin", "0"); barra.setAttribute("aria-valuemax", "100");
    const celulas = "<i></i>".repeat(30);
    barra.innerHTML = `<div class="vidro"><span class="varre"></span>
      <div class="cab"><i></i><span class="andamento-estado">Zé · processando</span><span class="relogio">T+00:00</span></div>
      <div class="linha"><span class="andamento-rotulo"></span><span class="pct">0%</span></div>
      <div class="trilho"><div class="celulas apagadas">${celulas}</div><div class="celulas acesas">${celulas}</div><span class="cabeca"></span></div></div>`;
    document.body.appendChild(barra);
    requestAnimationFrame(desenharAndamento);
  }
  const t = agoraS();
  if (estado === "pensando") {
    andamento.saiu = 0;
    if (!andamento.ativo) {
      // Um pedido novo começa do zero, não de onde o anterior parou.
      Object.assign(andamento, { ativo: true, inicio: t, base: 0, desde: t, fim: 0, mostrado: 0, visto: passo?.ts ?? 0 });
      barra.classList.remove("saindo", "pronto"); barra.classList.add("ativo");
      /** @type {HTMLElement} */ (barra.querySelector(".andamento-estado")).textContent = "Zé · processando";
      etapaAndamento("Pensando", 3);
    }
    if (passo?.ts && passo.ts !== andamento.visto) { andamento.visto = passo.ts; etapaAndamento(passo.rotulo || "Pensando", Number(passo.esperado_s) || 3); }
  } else if (andamento.ativo) {
    andamento.saiu = andamento.saiu || t;
    if (t - andamento.saiu > 1.5 || estado === "ativo" || estado === "inativo") {
      andamento.ativo = false; andamento.fim = t;
      barra.classList.add("pronto");
      /** @type {HTMLElement} */ (barra.querySelector(".andamento-estado")).textContent = "Zé · pronto";
      /** @type {HTMLElement} */ (barra.querySelector(".andamento-rotulo")).textContent = "Resposta pronta";
    }
  }
}

/** @param {HTMLElement} barra @param {number} p */
function mostrarAndamento(barra, p) {
  andamento.mostrado = p;
  barra.style.setProperty("--p", p.toFixed(4));
  const n = Math.round(p * 100);
  /** @type {HTMLElement} */ (barra.querySelector(".pct")).textContent = `${n}%`;
  barra.setAttribute("aria-valuenow", String(n));
}

function desenharAndamento() {
  const barra = $("andamento");
  if (!barra) return;
  const t = agoraS();
  if (andamento.ativo) {
    mostrarAndamento(barra, progressoAndamento(t));
    const s = t - andamento.inicio;
    /** @type {HTMLElement} */ (barra.querySelector(".relogio")).textContent =
      `T+${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  } else if (andamento.fim) {
    // Completa em ~0,3 s (não salta), brilha e se desfaz como os painéis do Zé.
    if (andamento.mostrado < 1) mostrarAndamento(barra, Math.min(1, andamento.mostrado + (1 - andamento.mostrado) * 0.25 + 0.01));
    if (t - andamento.fim > 0.9) barra.classList.add("saindo");
    if (t - andamento.fim > 1.45) { barra.classList.remove("ativo", "saindo", "pronto"); andamento.fim = 0; }
  }
  requestAnimationFrame(desenharAndamento);
}

async function batimento() {
  try {
    const e = await api("estado");
    if (inicioZe !== null && e.inicio !== inicioZe) { location.reload(); return; }
    inicioZe = e.inicio; semResposta = 0; faixaFora(false);
    // O que o Zé não falou (Silencioso) aparece em qualquer página
    const tela = e.tela?.[0] ?? null;
    if (telaDita !== undefined && tela !== telaDita && location.hash !== "#conversa") toast(e.tela[1], Math.min(15000, 5000 + 80 * e.tela[1].length)); // tempo de ler
    telaDita = tela;
    if (telaVista !== null && e.tela_ts > telaVista && imersaoLigada() && location.hash !== "#imersao") location.hash = "#imersao";
    telaVista = e.tela_ts;
    const icone = /** @type {HTMLElement} */ (document.querySelector(".icone-ze"));
    icone.dataset.estado = e.ze; icone.title = `Zé ${ESTADOS[e.ze] || e.ze}`;
    estadoZe = e.ze;
    const holo = /** @type {HTMLElement} */ (document.querySelector(".holo"));
    if (holo && holo.dataset.estado !== e.ze) { holo.dataset.estado = e.ze; $("holo-estado").textContent = ESTADO_HOLO[e.ze] || ""; }
    andamentoPainel(e.ze, e.andamento);
    desenharModoFala(e.modo_fala);
    desenharAtualizacao(e.atualizacao ?? null);
    $("ponto-atualizacoes").hidden = !e.versao?.disponivel;
    document.body.classList.toggle("manutencao", !!e.manutencao?.ligada); window.desenharManutencao?.(e.manutencao);
    desenharVozRemota();
    if (sessaoAberta && $("terminal") && document.visibilityState === "visible" && document.hasFocus()) {
      api("painel/vendo", { sessao: sessaoAberta }).catch(() => {});
    }
  } catch (erro) {
    if (erro.message === "token") { location.reload(); return; } // o Zé voltou com chave nova
    Object.assign(/** @type {HTMLElement} */ (document.querySelector(".icone-ze")), { title: "Zé desconectado" }).dataset.estado = "inativo";
    desenharAtualizacao();
    if (!reiniciando() && ++semResposta >= 3) faixaFora(true);
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
