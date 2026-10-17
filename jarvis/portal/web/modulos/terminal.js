// --- o terminal real da sessão (xterm.js): o agente com todos os comandos dele ---


const TEMA_TERMINAL = { background: "#070c11", foreground: "#e6f4f5", cursor: "#46d9de", cursorAccent: "#070c11",
  selectionBackground: "rgba(70, 217, 222, .28)", black: "#0b131a", brightBlack: "#5c7a80",
  scrollbarSliderBackground: "rgba(147, 170, 176, .45)", scrollbarSliderHoverBackground: "rgba(147, 170, 176, .65)",
  scrollbarSliderActiveBackground: "rgba(147, 170, 176, .8)" };



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
  window.desenharTravaSessoes?.();
  const parar = new AbortController();
  termParar = parar;
  $("terminal-fechado").hidden = true;
  try {
    const { posicao } = await api("terminal/abrir", { id, colunas: term.cols, linhas: term.rows }, parar.signal);
    termPos = posicao;
  } catch (erro) {
    if (parar.signal.aborted) return;
    toast(erro.message);
    $("terminal-fechado").hidden = false;
    return;
  }
  conectarTerminal(id, parar.signal);
  term.onData((d) => escreverNoTerminal(d));
  // O tamanho vai ao agente quando a tela para de mudar: cada mudança o faz redesenhar a tela.
  let prazoTamanho = 0;
  term.onResize(({ cols, rows }) => {
    clearTimeout(prazoTamanho);
    prazoTamanho = setTimeout(() => { if (!parar.signal.aborted) api("terminal/tamanho", { id, colunas: cols, linhas: rows }).catch(() => {}); }, 150);
  });
  termObservador = new ResizeObserver(() => { try { ajuste.fit(); } catch { /* fora da tela */ } });
  termObservador.observe(caixa);
  term.focus();
  lerTerminal(id, parar.signal);
}

function terminalPodeEnviar(id, ciclo) {
  return id === termId && ciclo === cicloAtualizacao && !atualizando()
    && !(sessaoAtual?.melhorias && window.unificandoSessoes);
}

function escreverTerminalHttp(id, dados, ciclo) {
  filaEscrita = filaEscrita.then(() => {
    if (terminalPodeEnviar(id, ciclo)) return api("terminal/escrever", { id, dados });
  }).catch((erro) => toast(erro.message));
}

function conectarTerminal(id, sinal) {
  if (typeof WebSocket === "undefined") return;
  let ws;
  try {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/terminal/ws`);
  } catch {
    return;
  }
  termWs = ws;
  termWsPronto = false;
  filaTerminalWs = [];
  let recusada = false;
  prazoTerminalWs = setTimeout(() => {
    if (termWs === ws && !termWsPronto) ws.close();
  }, 5000);
  ws.onopen = () => {
    if (termWs !== ws || sinal.aborted) { ws.close(); return; }
    try { ws.send(JSON.stringify({ id, token: TOKEN })); } catch { ws.close(); }
  };
  ws.onmessage = (evento) => {
    if (termWs !== ws || typeof evento.data !== "string") return;
    let resposta;
    try { resposta = JSON.parse(evento.data); } catch { ws.close(); return; }
    if (resposta.tipo === "erro") {
      recusada = true;
      filaTerminalWs = [];
      toast(resposta.erro || "Entrada do terminal recusada.");
      ws.close();
      return;
    }
    if (resposta.tipo !== "pronto") return;
    termWsPronto = true;
    clearTimeout(prazoTerminalWs);
    prazoTerminalWs = null;
    while (filaTerminalWs.length && termWs === ws) {
      const entrada = filaTerminalWs[0];
      filaTerminalWs.shift();
      if (!terminalPodeEnviar(entrada.id, entrada.ciclo)) continue;
      try { ws.send(entrada.dados); } catch {
        escreverTerminalHttp(entrada.id, entrada.dados, entrada.ciclo);
        ws.close();
        return;
      }
    }
  };
  ws.onerror = () => ws.close();
  ws.onclose = () => {
    if (termWs !== ws) return;
    termWs = null;
    termWsPronto = false;
    clearTimeout(prazoTerminalWs);
    prazoTerminalWs = null;
    const pendentes = filaTerminalWs;
    filaTerminalWs = [];
    if (!recusada) pendentes.forEach((entrada) => escreverTerminalHttp(entrada.id, entrada.dados, entrada.ciclo));
  };
}

// O WebSocket mantém a ordem sem uma ida HTTP por tecla. HTTP segue como fallback.
function escreverNoTerminal(dados) {
  const id = termId;
  const ciclo = cicloAtualizacao;
  if (!id || !terminalPodeEnviar(id, ciclo)) return;
  if (termWs && termWs.readyState !== WebSocket.CLOSED) {
    if (termWsPronto && termWs.readyState === WebSocket.OPEN) {
      try { termWs.send(dados); } catch {
        termWs.close();
        escreverTerminalHttp(id, dados, ciclo);
      }
    } else {
      filaTerminalWs.push({ id, ciclo, dados });
    }
    return;
  }
  escreverTerminalHttp(id, dados, ciclo);
}

// Um laço por terminal aberto: ao fechar, o sinal corta a leitura em andamento e o laço acaba.
// Antes, voltar à mesma sessão revivia o laço antigo, e os dois escreviam em dobro no terminal.
/** @param {string} id @param {AbortSignal} sinal */
async function lerTerminal(id, sinal) {
  let geracao = 0;
  while (!sinal.aborted) {
    try {
      const r = await api("terminal/ler", { id, desde: termPos, geracao }, sinal);
      if (sinal.aborted) return;
      if (r.reiniciado) term.reset();
      geracao = r.geracao || geracao;
      if (r.dados) term.write(Uint8Array.from(atob(r.dados), (c) => c.charCodeAt(0)));
      termPos = r.posicao;
      if (!r.vivo && !r.trocando) { $("terminal-fechado").hidden = false; return; }
      if (!r.vivo) await new Promise((ok) => setTimeout(ok, 300));
    } catch {
      if (sinal.aborted) return;
      await new Promise((ok) => setTimeout(ok, 1000));
    }
  }
}

window.desenharTravaSessoes = () => {
  const bloqueada = atualizando() || (!!sessaoAtual?.melhorias && !!window.unificandoSessoes);
  const aviso = $("reserva-sessoes");
  if (aviso) {
    aviso.hidden = !bloqueada;
    aviso.querySelector("strong").textContent = window.unificandoSessoes && sessaoAtual?.melhorias ? "Unificação em andamento" : "Atualização em andamento";
  }
  if (term) term.options.disableStdin = bloqueada;
  /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll('[data-acao="terminal-reabrir"], [data-acao="anexar"], [data-acao="interrompida-continuar"]')).forEach((b) => { b.disabled = bloqueada; });
  travarAjustes(sessaoAtual?.estado === "trabalhando");
};

// Enquanto o agente trabalha, a conta fica travada (a troca reabre o terminal).
function travarAjustes(trabalhando) {
  const bloqueado = trabalhando || atualizando() || (!!sessaoAtual?.melhorias && !!window.unificandoSessoes);
  /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll("#ajustes-sessao .escolha-botao")).forEach((el) => { el.disabled = bloqueado; });
  const parar = /** @type {HTMLButtonElement | null} */ ($("interromper-trabalho"));
  if (parar) { parar.hidden = !trabalhando; parar.disabled = atualizando() || (!!sessaoAtual?.melhorias && !!window.unificandoSessoes); }
  if (bloqueado) fecharEscolhas();
}
