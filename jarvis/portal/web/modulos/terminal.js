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

// As teclas vão em ordem (uma requisição por vez); senão o agente recebe letras trocadas.
function escreverNoTerminal(dados) {
  const id = termId;
  const ciclo = cicloAtualizacao;
  if (!id || atualizando() || (sessaoAtual?.melhorias && window.unificandoSessoes)) return;
  filaEscrita = filaEscrita.then(() => {
    // A atualização descarta a fila anterior, mesmo se a rede só voltar depois de liberar.
    if (ciclo === cicloAtualizacao && !atualizando() && !(sessaoAtual?.melhorias && window.unificandoSessoes)) return api("terminal/escrever", { id, dados });
  }).catch((erro) => toast(erro.message));
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
