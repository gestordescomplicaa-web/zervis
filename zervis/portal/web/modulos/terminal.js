import { atualizando } from "./navegacao.js";
import { $, TOKEN, api, fecharEscolhas, fecharTerminalTela, toast } from "../painel.js";
import { compartilhado, carregadas } from "./estado.js";

// --- o terminal real da sessão (xterm.js): o agente com todos os comandos dele ---

const TEMA_TERMINAL = { background: "#070c11", foreground: "#e6f4f5", cursor: "#46d9de", cursorAccent: "#070c11",
  selectionBackground: "rgba(70, 217, 222, .28)", black: "#0b131a", brightBlack: "#5c7a80",
  scrollbarSliderBackground: "rgba(147, 170, 176, .45)", scrollbarSliderHoverBackground: "rgba(147, 170, 176, .65)",
  scrollbarSliderActiveBackground: "rgba(147, 170, 176, .8)" };

export async function abrirTerminal(id) {
  fecharTerminalTela();
  const caixa = $("terminal");
  compartilhado.term = new Terminal({ fontFamily: 'ui-monospace, "JetBrains Mono", "SF Mono", Menlo, monospace', fontSize: 13,
    lineHeight: 1.15, cursorBlink: true, scrollback: 8000, theme: TEMA_TERMINAL });
  const ajuste = new FitAddon.FitAddon();
  compartilhado.term.loadAddon(ajuste);
  compartilhado.term.open(caixa);
  try { ajuste.fit(); } catch { /* fora da tela */ }
  compartilhado.termId = id;
  window.desenharTravaSessoes?.();
  const parar = new AbortController();
  compartilhado.termParar = parar;
  $("terminal-fechado").hidden = true;
  try {
    const { posicao } = await api("terminal/abrir", { id, colunas: compartilhado.term.cols, linhas: compartilhado.term.rows }, parar.signal);
    compartilhado.termPos = posicao;
  } catch (erro) {
    if (parar.signal.aborted) return;
    toast(erro.message);
    $("terminal-fechado").hidden = false;
    return;
  }
  ecoTerminal.amostras = [];
  ecoTerminal.desde = 0;
  ecoTerminal.via = "";
  // A saída chega pelo WebSocket; se ele não abrir (ou cair), pela leitura HTTP de sempre.
  conectarTerminal(id, parar.signal, () => lerTerminal(id, parar.signal));
  compartilhado.term.onData((d) => escreverNoTerminal(d));
  // O tamanho vai ao agente quando a tela para de mudar: cada mudança o faz redesenhar a tela.
  let prazoTamanho = 0;
  compartilhado.term.onResize(({ cols, rows }) => {
    clearTimeout(prazoTamanho);
    prazoTamanho = setTimeout(() => { if (!parar.signal.aborted) api("terminal/tamanho", { id, colunas: cols, linhas: rows }).catch(() => {}); }, 150);
  });
  compartilhado.termObservador = new ResizeObserver(() => { try { ajuste.fit(); } catch { /* fora da tela */ } });
  compartilhado.termObservador.observe(caixa);
  compartilhado.term.focus();
}

// O medidor: da tecla enviada até a tela do agente mudar (mediana das últimas). Aparece embaixo do
// terminal, para comparar o PC com a VPS em números, não no "parece".
const ecoTerminal = { amostras: [], desde: 0, via: "" };

function ecoChegou(via) {
  ecoTerminal.via = via;
  if (!ecoTerminal.desde) return;
  ecoTerminal.amostras = [...ecoTerminal.amostras.slice(-29), performance.now() - ecoTerminal.desde];
  ecoTerminal.desde = 0;
  mostrarEco();
}

function mostrarEco() {
  const caixa = $("terminal");
  if (!caixa || ecoTerminal.amostras.length < 3) return;
  let rotulo = $("eco-terminal");
  if (!rotulo) {
    rotulo = document.createElement("small");
    rotulo.id = "eco-terminal";
    rotulo.className = "eco-terminal";
    caixa.after(rotulo);
  }
  const ordem = [...ecoTerminal.amostras].sort((a, b) => a - b);
  const mediana = Math.round(ordem[Math.floor(ordem.length / 2)]);
  rotulo.textContent = `Resposta do terminal: ${mediana} ms · ${ecoTerminal.via === "ws" ? "tempo real" : "modo compatível"}`;
  rotulo.title = `Mediana das últimas ${ordem.length} teclas, da tecla até a tela mudar.`;
}

function terminalPodeEnviar(id, ciclo) {
  return id === compartilhado.termId && ciclo === compartilhado.cicloAtualizacao && !atualizando()
    && !(sessaoDaTela()?.melhorias && window.unificandoSessoes);
}

function escreverTerminalHttp(id, dados, ciclo) {
  compartilhado.filaEscrita = compartilhado.filaEscrita.then(() => {
    if (terminalPodeEnviar(id, ciclo)) return api("terminal/escrever", { id, dados });
  }).catch((erro) => toast(erro.message));
}

function conectarTerminal(id, sinal, lerPeloHttp) {
  let lendoHttp = false;
  const recorrer = () => {
    if (lendoHttp || sinal.aborted) return;
    lendoHttp = true;
    lerPeloHttp();
  };
  if (typeof WebSocket === "undefined") { recorrer(); return; }
  let ws;
  try {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/terminal/ws`);
  } catch {
    recorrer();
    return;
  }
  ws.binaryType = "arraybuffer";
  compartilhado.termWs = ws;
  compartilhado.termWsPronto = false;
  compartilhado.filaTerminalWs = [];
  let recusada = false, fechouSessao = false;
  compartilhado.prazoTerminalWs = setTimeout(() => {
    if (compartilhado.termWs === ws && !compartilhado.termWsPronto) ws.close();
  }, 5000);
  ws.onopen = () => {
    if (compartilhado.termWs !== ws || sinal.aborted) { ws.close(); return; }
    try { ws.send(JSON.stringify({ id, token: TOKEN, saida: true, desde: compartilhado.termPos })); } catch { ws.close(); }
  };
  ws.onmessage = (evento) => {
    if (compartilhado.termWs !== ws) return;
    if (evento.data instanceof ArrayBuffer) {
      // A saída: 8 bytes com a posição final e os bytes do terminal.
      if (evento.data.byteLength < 8 || !compartilhado.term) return;
      compartilhado.termPos = Number(new DataView(evento.data).getBigUint64(0));
      if (evento.data.byteLength > 8) {
        compartilhado.term.write(new Uint8Array(evento.data, 8));
        ecoChegou("ws");
      }
      return;
    }
    let resposta;
    try { resposta = JSON.parse(evento.data); } catch { ws.close(); return; }
    if (resposta.tipo === "erro") {
      recusada = true;
      compartilhado.filaTerminalWs = [];
      toast(resposta.erro || "Entrada do terminal recusada.");
      ws.close();
      return;
    }
    if (resposta.tipo === "reiniciado") { compartilhado.term?.reset(); return; }
    if (resposta.tipo === "fechado") {
      fechouSessao = true;
      $("terminal-fechado").hidden = false;
      return;
    }
    if (resposta.tipo !== "pronto") return;
    compartilhado.termWsPronto = true;
    clearTimeout(compartilhado.prazoTerminalWs);
    compartilhado.prazoTerminalWs = null;
    if (!resposta.saida) recorrer(); // servidor antigo ou sem a saída: só as teclas vão por aqui
    while (compartilhado.filaTerminalWs.length && compartilhado.termWs === ws) {
      const entrada = compartilhado.filaTerminalWs[0];
      compartilhado.filaTerminalWs.shift();
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
    if (compartilhado.termWs !== ws) return;
    compartilhado.termWs = null;
    compartilhado.termWsPronto = false;
    clearTimeout(compartilhado.prazoTerminalWs);
    compartilhado.prazoTerminalWs = null;
    const pendentes = compartilhado.filaTerminalWs;
    compartilhado.filaTerminalWs = [];
    if (!recusada) pendentes.forEach((entrada) => escreverTerminalHttp(entrada.id, entrada.dados, entrada.ciclo));
    if (!fechouSessao) recorrer();
  };
}

// O WebSocket mantém a ordem sem uma ida HTTP por tecla. HTTP segue como fallback.
export function escreverNoTerminal(dados) {
  const id = compartilhado.termId;
  const ciclo = compartilhado.cicloAtualizacao;
  if (!id || !terminalPodeEnviar(id, ciclo)) return;
  if (!ecoTerminal.desde) ecoTerminal.desde = performance.now();
  if (compartilhado.termWs && compartilhado.termWs.readyState !== WebSocket.CLOSED) {
    if (compartilhado.termWsPronto && compartilhado.termWs.readyState === WebSocket.OPEN) {
      try { compartilhado.termWs.send(dados); } catch {
        compartilhado.termWs.close();
        escreverTerminalHttp(id, dados, ciclo);
      }
    } else {
      compartilhado.filaTerminalWs.push({ id, ciclo, dados });
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
      const r = await api("terminal/ler", { id, desde: compartilhado.termPos, geracao }, sinal);
      if (sinal.aborted) return;
      if (r.reiniciado) compartilhado.term.reset();
      geracao = r.geracao || geracao;
      if (r.dados) {
        compartilhado.term.write(Uint8Array.from(atob(r.dados), (c) => c.charCodeAt(0)));
        ecoChegou("http");
      }
      compartilhado.termPos = r.posicao;
      if (!r.vivo && !r.trocando) { $("terminal-fechado").hidden = false; return; }
      if (!r.vivo) await new Promise((ok) => setTimeout(ok, 300));
    } catch {
      if (sinal.aborted) return;
      await new Promise((ok) => setTimeout(ok, 1000));
    }
  }
}

// A sessão aberta na página Sessões, que carrega sob demanda: no Autodesenvolvimento ela ainda
// não existe, e o batimento do painel quebrava aqui (ReferenceError, CI de 04/11/2026).
const sessaoDaTela = () => (typeof compartilhado.sessaoAtual === "undefined" ? null : compartilhado.sessaoAtual);

window.desenharTravaSessoes = () => {
  const sessaoAtual = sessaoDaTela();
  const bloqueada = atualizando() || (!!sessaoAtual?.melhorias && !!window.unificandoSessoes);
  const aviso = $("reserva-sessoes");
  if (aviso) {
    aviso.hidden = !bloqueada;
    aviso.querySelector("strong").textContent = window.unificandoSessoes && sessaoAtual?.melhorias ? "Unificação em andamento" : "Atualização em andamento";
  }
  if (compartilhado.term) compartilhado.term.options.disableStdin = bloqueada;
  /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll('[data-acao="terminal-reabrir"], [data-acao="anexar"], [data-acao="interrompida-continuar"]')).forEach((b) => { b.disabled = bloqueada; });
  travarAjustes(sessaoAtual?.estado === "trabalhando");
};

// Enquanto o agente trabalha, a conta fica travada (a troca reabre o terminal).
export function travarAjustes(trabalhando) {
  const sessaoAtual = sessaoDaTela();
  const bloqueado = trabalhando || atualizando() || (!!sessaoAtual?.melhorias && !!window.unificandoSessoes);
  /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll("#ajustes-sessao .escolha-botao")).forEach((el) => { el.disabled = bloqueado; });
  const parar = /** @type {HTMLButtonElement | null} */ ($("interromper-trabalho"));
  if (parar) { parar.hidden = !trabalhando; parar.disabled = atualizando() || (!!sessaoAtual?.melhorias && !!window.unificandoSessoes); }
  if (bloqueado) fecharEscolhas();
}

// Para o núcleo do painel (as ações, a navegação), que chama este módulo depois que ele carrega.
Object.assign(carregadas, { abrirTerminal, escreverNoTerminal });
