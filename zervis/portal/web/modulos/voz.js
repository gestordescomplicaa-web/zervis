// --- Modo de fala: quando o Zé fala sem ser chamado (ADR 0018) ---

const MODOS_FALA = [
  { valor: "silencioso", nome: "Silencioso", curto: "Sem voz", detalhe: "Não fala nem ouve. Tudo pela tela." },
  { valor: "avisos", nome: "Normal", curto: "Avisos e resultados", detalhe: "Fala avisos, urgências e um resumo do resultado de cada sessão." },
  { valor: "live", nome: "Live", curto: "Conversa em tempo real", detalhe: "Conversa como numa ligação: dá para cortar o Zé falando. Anuncia os resultados e responde na hora." },
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

/** @param {string} evento @param {unknown} [detalhe] */
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
  const holo = /** @type {HTMLElement} */ (document.querySelector(".holo"));
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
  if (modoFala === "silencioso") return toast("Microfone desligado no modo Silencioso.");
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
      ws.onopen = () => { ws.send(JSON.stringify({ token: TOKEN, taxa: captura.sampleRate })); ok(undefined); };
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
lerFechados().forEach((g) => /** @type {HTMLElement} */ (document.querySelector(`.grupo[data-grupo="${g}"] .grupo-titulo`))?.setAttribute("aria-expanded", "false"));
/** @type {HTMLElement} */ (document.querySelector("nav")).addEventListener("click", (ev) => { if (/** @type {HTMLAnchorElement} */ (/** @type {HTMLElement} */ (ev.target).closest("a"))) document.body.classList.remove("menu-aberto"); });
function alternarGrupo(b) {
  const aberto = b.getAttribute("aria-expanded") === "true", fechados = lerFechados(), g = /** @type {HTMLElement} */ (b.closest(".grupo")).dataset.grupo;
  b.setAttribute("aria-expanded", String(!aberto));
  aberto ? fechados.add(g) : fechados.delete(g);
  try { localStorage.setItem(GRUPOS, JSON.stringify([...fechados])); } catch { /* sem armazenamento: vale só agora */ }
}

// --- Segurar para falar (ADR 0022): segurar envia ao soltar; um toque começa e outro envia ---

let falando = false, travado = false, apertouEm = 0;

function marcarFalar() {
  /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll("[data-falar]")).forEach((b) => {
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

document.addEventListener("pointerdown", (ev) => { if (/** @type {HTMLElement} */ (/** @type {HTMLElement} */ (ev.target).closest?.("[data-falar]"))) { ev.preventDefault(); apertarFalar(); } });
document.addEventListener("pointerup", (ev) => { if (/** @type {HTMLElement} */ (/** @type {HTMLElement} */ (ev.target).closest?.("[data-falar]"))) soltarFalar(false); });
document.addEventListener("pointercancel", (ev) => { if (/** @type {HTMLElement} */ (/** @type {HTMLElement} */ (ev.target).closest?.("[data-falar]"))) soltarFalar(false); });
const editavel = (el) => /** @type {HTMLInputElement} */ (el.closest?.("input, textarea, select, [contenteditable], .terminal-sessao"));
document.addEventListener("keydown", (ev) => { if (ev.code === "Space" && !ev.repeat && !editavel(/** @type {HTMLElement} */ (ev.target))) { ev.preventDefault(); apertarFalar(); } });
document.addEventListener("keyup", (ev) => { if (ev.code === "Space" && !editavel(/** @type {HTMLElement} */ (ev.target))) soltarFalar(false); });
