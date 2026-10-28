// A página Conversa, carregada sob demanda pelo painel: o fio de hoje com o Zé (o que a pessoa
// falou ou escreveu, as respostas e os avisos) e o campo para escrever. É onde fica o que o Zé não
// falou no Silencioso.
//
// Funciona como um chat (pedido de 27/10/2026): a mensagem escrita aparece na hora, com o "digitando"
// do Zé; a resposta aparece enquanto ele responde (a troca em curso vem marcada como pendente, antes
// de ir para o histórico) e, nesse meio-tempo, o fio é lido a cada 0,3 s em vez de 1,5 s.

PAGINAS.conversa = async () => `<div class="pagina-conversa">
  <header class="conversa-cabeca">${cabeca("Conversa")}${sub("O que você falou com o Zé hoje, as respostas e os avisos.")}<p class="esperando" id="esperando" hidden></p></header>
  <div class="fio" id="fio" aria-live="polite"></div>
  <form class="escrever" id="escrever">
    <textarea id="escrever-texto" rows="1" placeholder="Escreva para o Zé" autocomplete="off" aria-label="Mensagem"></textarea>
    <button type="submit" class="acao principal">Enviar</button>
  </form></div>`;

let fioVisto = "";
let fioTimer = null;
/** As mensagens escritas aqui que o Zé ainda não mostrou de volta (o envio leva um instante).
 * Um comando local ou o "sim" de uma confirmação não viram troca no histórico: com o Zé parado
 * de novo, a mensagem fica como entregue, sem o "digitando".
 * @type {{texto: string, quando: string, em: number, erro: boolean, entregue: boolean}[]} */
let enviadas = [];
let ultimoFio = { itens: [], esperando: [] };
const horaFio = (q) => q.slice(11, 16);
const agoraIso = () => { const d = new Date(), z = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`; };
const digitando = '<div class="fala ze digitando" aria-label="O Zé está respondendo"><p><i></i><i></i><i></i></p></div>';

/** O fio na tela: o histórico, a troca em curso e as mensagens que acabaram de sair daqui. */
function montarFio() {
  const fio = $("fio");
  if (!fio) return;
  const { itens, esperando } = ultimoFio;
  const fila = $("esperando");
  fila.hidden = !esperando.length;
  fila.textContent = esperando.length ? `Esperando: ${esperando.join(" · ")}.` : "";
  // Uma enviada some quando o servidor já a mostra (na troca em curso ou no histórico).
  const vistas = itens.filter((i) => i.tipo === "voce").map((i) => i.texto);
  enviadas = enviadas.filter((m) => m.erro || !vistas.includes(m.texto));
  const pensando = ["pensando", "falando"].includes(estadoZe);
  for (const m of enviadas) if (!m.erro && !pensando && Date.now() - m.em > 4000) m.entregue = true;
  const respondendo = itens.some((i) => i.pendente && i.tipo === "ze");
  const esperandoResposta = enviadas.some((m) => !m.erro && !m.entregue) || (pensando && !respondendo) || (itens.at(-1)?.pendente && !respondendo);
  const marca = JSON.stringify([itens.length, itens.at(-1), enviadas, esperandoResposta]);
  if (marca === fioVisto) return;
  fioVisto = marca;
  const embaixo = fio.scrollHeight - fio.scrollTop - fio.clientHeight < 80;
  const balao = (i) => i.tipo === "aviso"
    ? `<div class="fala aviso"><span>Aviso · ${horaFio(i.quando)}</span><p>${esc(i.texto)}</p></div>`
    : `<div class="fala ${i.tipo}${i.pendente ? " pendente" : ""}"><p>${esc(i.texto)}</p><span>${horaFio(i.quando)}</span></div>`;
  const minhas = enviadas.map((m) => `<div class="fala voce${m.erro ? " erro" : m.entregue ? "" : " enviando"}"><p>${esc(m.texto)}</p><span>${m.erro ? "Não enviado" : horaFio(m.quando)}</span></div>`);
  const tudo = [...itens.map(balao), ...minhas, ...(esperandoResposta ? [digitando] : [])];
  fio.innerHTML = tudo.length ? tudo.join("") : vazio("Nada por aqui hoje.");
  if (embaixo || !fio.dataset.lido) { fio.scrollTop = fio.scrollHeight; fio.dataset.lido = "1"; }
}

async function desenharFio() {
  if (!$("fio")) return;
  ultimoFio = await api("conversa");
  montarFio();
}

/** Lê o fio de novo: rápido enquanto o Zé responde, devagar parado. */
function vigiarFio(vez) {
  clearTimeout(fioTimer);
  if (vez !== navegacao || !$("fio")) return;
  const ativo = enviadas.some((m) => !m.erro && !m.entregue) || ["pensando", "falando"].includes(estadoZe) || ultimoFio.itens.some((i) => i.pendente);
  fioTimer = setTimeout(async () => {
    await desenharFio().catch(() => {});
    vigiarFio(vez);
  }, ativo ? 300 : 1500);
}

/** @param {number} vez */
async function prepararConversa(vez) {
  fioVisto = "";
  await desenharFio();
  if (vez !== navegacao) return;
  vigiarFio(vez);
  const campo = /** @type {HTMLTextAreaElement} */ (valorCampo("escrever-texto"));
  const enviar = async (ev) => {
    ev?.preventDefault();
    const texto = campo.value.trim();
    if (!texto) return;
    // Na hora, como num chat: o balão sai, o campo limpa e o Zé "digita".
    const msg = { texto: texto.replace(/\s+/g, " "), quando: agoraIso(), em: Date.now(), erro: false, entregue: false };
    enviadas.push(msg);
    campo.value = ""; campo.style.height = "";
    fioVisto = ""; montarFio();
    const fio = $("fio"); if (fio) fio.scrollTop = fio.scrollHeight;
    vigiarFio(vez);
    let r;
    try { r = await api("conversa/escrever", { texto }); } catch (erro) { r = { aviso: erro.message }; }
    if (r.aviso !== "Enviado.") {
      msg.erro = true; toast(r.aviso);
      if (!campo.value) campo.value = texto; // não se perde o que foi escrito
    }
    fioVisto = ""; await desenharFio().catch(() => montarFio());
  };
  $("escrever").addEventListener("submit", enviar);
  campo.addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) enviar(ev); });
  campo.addEventListener("input", () => { campo.style.height = ""; campo.style.height = Math.min(campo.scrollHeight, 160) + "px"; });
  campo.focus();
}

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.pagina-conversa { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; height: 100%; min-width: 0; flex: 1 1 auto; max-width: 860px; }
.conversa-cabeca { padding: 18px 20px 10px; }
.conversa-cabeca .sub { margin: 4px 0 0; }
.esperando { margin: 8px 0 0; padding: 6px 10px; border-radius: 10px; font-size: 13.5px; color: var(--alerta); border: 1px solid rgb(239 190 124 / .4); }
.fio { overflow-y: auto; padding: 8px 20px 16px; display: flex; flex-direction: column; gap: 10px; }
.fala { max-width: 78%; display: grid; gap: 2px; }
.fala p { margin: 0; padding: 9px 13px; border-radius: 14px; white-space: pre-wrap; overflow-wrap: anywhere; }
.fala span { font-size: 11.5px; color: var(--suave); padding: 0 4px; }
.fala.voce { align-self: flex-end; justify-items: end; }
.fala.voce p { background: var(--acento-escuro); border: 1px solid var(--borda-forte); }
.fala.voce.enviando p { opacity: .75; }
.fala.voce.erro p { border-color: var(--erro, #e06c6c); }
.fala.voce.erro span { color: var(--erro, #e06c6c); }
.fala.ze { align-self: flex-start; }
.fala.ze p { background: var(--vidro-forte); border: 1px solid var(--borda); }
.fala.digitando p { display: flex; gap: 5px; align-items: center; padding: 13px 15px; }
.fala.digitando i { width: 7px; height: 7px; border-radius: 50%; background: var(--suave); animation: pulo 1.2s infinite ease-in-out; }
.fala.digitando i:nth-child(2) { animation-delay: .15s; }
.fala.digitando i:nth-child(3) { animation-delay: .3s; }
@keyframes pulo { 0%, 60%, 100% { transform: translateY(0); opacity: .45; } 30% { transform: translateY(-4px); opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .fala.digitando i { animation: none; } }
.fala.aviso { align-self: center; max-width: 92%; justify-items: center; text-align: center; }
.fala.aviso p { padding: 4px 10px; color: var(--suave); font-size: 13.5px; }
.escrever { display: flex; gap: 10px; align-items: flex-end; padding: 12px 20px 18px; border-top: 1px solid var(--borda); }
.escrever textarea { flex: 1; resize: none; min-height: 44px; max-height: 160px; padding: 11px 13px; border-radius: 12px;
  font: inherit; color: var(--texto); background: var(--fundo-2); border: 1px solid var(--borda-forte); }
` }));
