// A página Conversa, carregada sob demanda pelo painel: o fio de hoje com o Zé (o que a pessoa
// falou ou escreveu, as respostas e os avisos) e o campo para escrever. É onde fica o que o Zé não
// falou no Silencioso.
//
// Funciona como um chat (pedido de 27/10/2026): a mensagem escrita aparece na hora, com o "digitando"
// do Zé; a resposta aparece enquanto ele responde (a troca em curso vem marcada como pendente, antes
// de ir para o histórico) e, nesse meio-tempo, o fio é lido a cada 0,3 s em vez de 1,5 s.
//
// Cada resposta mostra o que gastou (pedido de 27/10/2026: entender como o Zé gasta os tokens),
// por parte: a via rápida, o cérebro e a pesquisa; no topo, o dia e o que rodou em segundo plano.

PAGINAS.conversa = async () => `<div class="pagina-conversa">
  <header class="conversa-cabeca">${cabeca("Conversa")}${sub("O que você falou com o Zé hoje, as respostas e os avisos.")}<p class="consumo-dia" id="consumo-dia" hidden></p><p class="esperando" id="esperando" hidden></p></header>
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
let ultimoFio = { itens: [], esperando: [], consumo: null };
const horaFio = (q) => q.slice(11, 16);
const agoraIso = () => { const d = new Date(), z = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`; };
const digitando = '<div class="fala ze digitando" aria-label="O Zé está respondendo"><p><i></i><i></i><i></i></p></div>';

const ROTULOS_DO_GASTO = { rapida: "Respostas rápidas", completo: "Cérebro", pesquisa: "Pesquisa na internet" };
/** 840, "14,2 mil", "1,3 mi". */
const tokens = (n) => n < 1000 ? String(n) : n < 1e6 ? `${(n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: n < 1e4 ? 1 : 0 })} mil` : `${(n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
const lidos = (p) => (p.entrada || 0) + (p.cache_lido || 0) + (p.cache_criado || 0);
const somaPartes = (partes) => partes.reduce((t, p) => ({ lidos: t.lidos + lidos(p), cache: t.cache + (p.cache_lido || 0), saida: t.saida + (p.saida || 0) }), { lidos: 0, cache: 0, saida: 0 });
const emCache = (t) => t.lidos ? Math.round(100 * t.cache / t.lidos) : 0;

/** A linha do gasto de uma resposta e, ao abrir, cada parte. */
function gastoDaResposta(g) {
  if (!g?.partes?.length) return "";
  const t = somaPartes(g.partes);
  const partes = g.partes.map((p) => `<li><b>${esc(ROTULOS_DO_GASTO[p.rotulo] || p.rotulo)}</b>${p.modelo ? ` · ${esc(p.modelo)}` : ""}<br>${tokens(lidos(p))} lidos (${tokens(p.cache_lido || 0)} em cache${p.cache_criado ? `, ${tokens(p.cache_criado)} gravados no cache` : ""}) · ${tokens(p.saida || 0)} gerados</li>`).join("");
  const ferramentas = g.ferramentas?.length ? `<li><b>Ferramentas</b><br>${esc(g.ferramentas.join(", "))}</li>` : "";
  return `<details class="gasto"><summary>${tokens(t.lidos + t.saida)} tokens · ${emCache(t)}% em cache</summary><ul>${partes}${ferramentas}</ul></details>`;
}

/** O dia: as respostas com gasto, as resolvidas sem modelo e o segundo plano. */
function consumoDoDia(itens, consumo) {
  const gastos = itens.filter((i) => i.gasto?.partes?.length).map((i) => somaPartes(i.gasto.partes));
  const t = gastos.reduce((a, g) => ({ lidos: a.lidos + g.lidos, cache: a.cache + g.cache, saida: a.saida + g.saida }), { lidos: 0, cache: 0, saida: 0 });
  const partes = [];
  if (gastos.length) {
    const total = t.lidos + t.saida;
    partes.push(`Hoje: ${gastos.length} ${gastos.length === 1 ? "resposta" : "respostas"} · ${tokens(total)} tokens · ${emCache(t)}% em cache · média de ${tokens(Math.round(total / gastos.length))} por resposta`);
  }
  if (consumo?.locais) partes.push(`${consumo.locais} sem modelo`);
  const f = consumo?.fundo;
  if (f && consumo.fundo_vezes) partes.push(`segundo plano: ${tokens(lidos(f) + (f.saida || 0))} tokens em ${consumo.fundo_vezes} ${consumo.fundo_vezes === 1 ? "tarefa" : "tarefas"}`);
  return partes.join(" · ");
}

/** O fio na tela: o histórico, a troca em curso e as mensagens que acabaram de sair daqui. */
function montarFio() {
  const fio = $("fio");
  if (!fio) return;
  const { itens, esperando, consumo } = ultimoFio;
  const dia = $("consumo-dia");
  const resumo = consumoDoDia(itens, consumo);
  dia.hidden = !resumo; dia.textContent = resumo;
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
  const abertos = new Set([...fio.querySelectorAll("details.gasto[open]")].map((d) => /** @type {HTMLElement} */ (d).dataset.quando));
  if (marca === fioVisto) return;
  fioVisto = marca;
  const embaixo = fio.scrollHeight - fio.scrollTop - fio.clientHeight < 80;
  const balao = (i) => i.tipo === "aviso"
    ? `<div class="fala aviso"><span>Aviso · ${horaFio(i.quando)}</span><p>${esc(i.texto)}</p></div>`
    : `<div class="fala ${i.tipo}${i.pendente ? " pendente" : ""}"><p>${esc(i.texto)}</p><span>${horaFio(i.quando)}</span>${i.tipo === "ze" ? gastoDaResposta(i.gasto).replace("<details", `<details data-quando="${esc(i.quando)}"${abertos.has(i.quando) ? " open" : ""}`) : ""}</div>`;
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
.consumo-dia { margin: 6px 0 0; font-size: 12.5px; color: var(--suave); font-variant-numeric: tabular-nums; }
.gasto { font-size: 11.5px; color: var(--suave); padding: 0 4px; font-variant-numeric: tabular-nums; }
.gasto summary { cursor: pointer; list-style: none; width: fit-content; }
.gasto summary::-webkit-details-marker { display: none; }
.gasto summary::after { content: " ▾"; opacity: .7; }
.gasto[open] summary::after { content: " ▴"; }
.gasto ul { margin: 6px 0 2px; padding: 8px 10px; list-style: none; display: grid; gap: 6px; border: 1px solid var(--borda); border-radius: 10px; background: var(--fundo-2); }
.gasto b { color: var(--texto); font-weight: 600; }
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
