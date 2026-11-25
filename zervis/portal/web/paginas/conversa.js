import { $, api, esc, toast, valorCampo } from "../painel.js";
import { anexosNaFala, botaoAnexar, caixaAnexos, devolverPendentes, ligarAnexos, subirAnexo, tirarPendentes } from "../modulos/anexos-chat.js";
import { icone } from "../modulos/casca.js";
import { compartilhado, carregadas } from "../modulos/estado.js";

// O chat com o Zé, que o Início mostra (ADR 0136; antes, a página Conversa): o fio de hoje (o que
// a pessoa falou ou escreveu, as respostas e os avisos) e o campo para escrever. É onde fica o que
// o Zé não falou no Silencioso.
//
// Funciona como um chat (pedido de 27/10/2026): a mensagem escrita aparece na hora, com o "digitando"
// do Zé; a resposta aparece enquanto ele responde (a troca em curso vem marcada como pendente, antes
// de ir para o histórico) e, nesse meio-tempo, o fio é lido a cada 0,3 s em vez de 1,5 s.
//
// Cada resposta mostra o que gastou (pedido de 27/10/2026: entender como o Zé gasta os tokens),
// por parte: a via rápida, o cérebro e a pesquisa; no topo, o dia e o que rodou em segundo plano.
//
// A conversa pelo WhatsApp é a mesma (ADR 0104): os pedidos de lá vêm marcados, e o que eles
// pedirem com efeito espera aqui, em "Aprovação pendente", porque só o painel exige login.

/** O chat do Início: os avisos de aprovação, o fio e o campo de escrever (ADR 0136). */
export const chat = () => `<div class="aprovacoes" id="aprovacoes" hidden></div><p class="esperando" id="esperando" hidden></p>
  <div class="fio" id="fio" aria-live="polite"></div>`;

/** O campo de escrever: os anexos, o texto, o anexar, o microfone e o enviar. */
export const campoEscrever = () => `<form class="escrever" id="escrever">
    ${caixaAnexos()}
    <textarea id="escrever-texto" rows="1" placeholder="Escreva para o Zé" autocomplete="off" aria-label="Mensagem"></textarea>
    <div class="botoes-escrever">
      ${botaoAnexar()}
      <span class="espaco"></span>
      <button type="button" class="redondo" data-falar aria-pressed="false" aria-label="Falar" title="Segure para falar">${icone("mic")}</button>
      <button type="submit" class="redondo principal" aria-label="Enviar">${icone("send")}</button>
    </div>
  </form>`;

let fioVisto = "";
/** Manda um pedido pronto (as sugestões do Início) como se fosse escrito. @type {(texto: string) => void} */
export let enviarPronto = () => {};
let fioTimer = null;
/** As mensagens escritas aqui que o Zé ainda não mostrou de volta (o envio leva um instante).
 * Um comando local ou o "sim" de uma confirmação não viram troca no histórico: com o Zé parado
 * de novo, a mensagem fica como entregue, sem o "digitando".
 * @type {{texto: string, quando: string, em: number, erro: boolean, entregue: boolean, anexos: import("../modulos/anexos-chat.js").Anexo[]}[]} */
let enviadas = [];
let ultimoFio = { itens: [], esperando: [], consumo: null, aprovacoes: [] };
let aprovacoesVistas = "";
const horaFio = (q) => q.slice(11, 16);
const agoraIso = () => { const d = new Date(), z = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`; };
const ANEL = '<img class="anel-fala" src="/ze.webp" alt="" width="26" height="26">';
const digitando = `<div class="fala ze digitando" aria-label="O Zé está respondendo">${ANEL}<p><i></i><i></i><i></i></p></div>`;

const ROTULOS_DO_GASTO = { rapida: "Respostas rápidas", completo: "Cérebro", pesquisa: "Pesquisa na internet" };
/** 840, "14,2 mil", "1,3 mi". */
const tokens = (n) => n < 1000 ? String(n) : n < 1e6 ? `${(n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: n < 1e4 ? 1 : 0 })} mil` : `${(n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
const lidos = (p) => (p.entrada || 0) + (p.cache_lido || 0) + (p.cache_criado || 0);
const somaPartes = (partes) => partes.reduce((t, p) => ({ lidos: t.lidos + lidos(p), cache: t.cache + (p.cache_lido || 0), saida: t.saida + (p.saida || 0) }), { lidos: 0, cache: 0, saida: 0 });
// O que pesa de verdade é o novo: o lido do cache custa uma fração e não esgota a conta igual.
const resumo = (t) => `${tokens(t.lidos - t.cache)} novos + ${tokens(t.cache)} do cache · ${tokens(t.saida)} gerados`;

/** A linha do gasto de uma resposta e, ao abrir, cada parte. */
function gastoDaResposta(g) {
  if (!g?.partes?.length) return "";
  const t = somaPartes(g.partes);
  const partes = g.partes.map((p) => `<li><b>${esc(ROTULOS_DO_GASTO[p.rotulo] || p.rotulo)}</b>${p.modelo ? ` · ${esc(p.modelo)}` : ""}<br>${tokens(lidos(p))} lidos (${tokens(p.cache_lido || 0)} em cache${p.cache_criado ? `, ${tokens(p.cache_criado)} gravados no cache` : ""}) · ${tokens(p.saida || 0)} gerados</li>`).join("");
  const ferramentas = g.ferramentas?.length ? `<li><b>Ferramentas</b><br>${esc(g.ferramentas.join(", "))}</li>` : "";
  return `<details class="gasto"><summary>${resumo(t)}</summary><ul>${partes}${ferramentas}</ul></details>`;
}

/** O dia: as respostas com gasto, as resolvidas sem modelo e o segundo plano. */
function consumoDoDia(itens, consumo) {
  const gastos = itens.filter((i) => i.gasto?.partes?.length).map((i) => somaPartes(i.gasto.partes));
  const t = gastos.reduce((a, g) => ({ lidos: a.lidos + g.lidos, cache: a.cache + g.cache, saida: a.saida + g.saida }), { lidos: 0, cache: 0, saida: 0 });
  const partes = [];
  if (gastos.length) {
    const novos = t.lidos - t.cache + t.saida;
    partes.push(`Hoje: ${gastos.length} ${gastos.length === 1 ? "resposta" : "respostas"} · ${resumo(t)} · média de ${tokens(Math.round(novos / gastos.length))} novos por resposta`);
  }
  if (consumo?.locais) partes.push(`${consumo.locais} sem modelo`);
  const f = consumo?.fundo;
  if (f && consumo.fundo_vezes) partes.push(`segundo plano: ${tokens(lidos(f) + (f.saida || 0))} tokens em ${consumo.fundo_vezes} ${consumo.fundo_vezes === 1 ? "tarefa" : "tarefas"}`);
  return partes.join(" · ");
}

/** As ações pedidas pelo WhatsApp que esperam o "sim" daqui. */
function montarAprovacoes() {
  const caixa = $("aprovacoes");
  const lista = ultimoFio.aprovacoes || [];
  const marca = JSON.stringify(lista);
  if (!caixa || marca === aprovacoesVistas) return;
  aprovacoesVistas = marca;
  caixa.hidden = !lista.length;
  caixa.innerHTML = lista.map((a) => `<div class="aprovacao" data-id="${esc(a.id)}"><div><b>Aprovação pendente</b><span>WhatsApp · ${horaFio(a.quando)}</span><p>${esc(a.descricao)}</p></div><div class="botoes"><button type="button" class="acao principal" data-aprovar="1">Aprovar</button><button type="button" class="acao" data-aprovar="0">Negar</button></div></div>`).join("");
}

/** O fio na tela: o histórico, a troca em curso e as mensagens que acabaram de sair daqui. */
function montarFio() {
  const fio = $("fio");
  if (!fio) return;
  montarAprovacoes();
  const { itens, esperando, consumo } = ultimoFio;
  const dia = $("consumo-dia");
  const resumo = consumoDoDia(itens, consumo);
  if (dia) { dia.hidden = !resumo; dia.textContent = resumo; }
  const fila = $("esperando");
  fila.hidden = !esperando.length;
  fila.textContent = esperando.length ? `Esperando: ${esperando.join(" · ")}.` : "";
  // Uma enviada some quando o servidor já a mostra (na troca em curso ou no histórico).
  const vistas = itens.filter((i) => i.tipo === "voce").map((i) => i.texto);
  enviadas = enviadas.filter((m) => m.erro || !vistas.includes(m.texto));
  const pensando = ["pensando", "falando"].includes(compartilhado.estadoZe);
  for (const m of enviadas) if (!m.erro && !pensando && Date.now() - m.em > 4000) m.entregue = true;
  const respondendo = itens.some((i) => i.pendente && i.tipo === "ze");
  const esperandoResposta = enviadas.some((m) => !m.erro && !m.entregue) || (pensando && !respondendo) || (itens.at(-1)?.pendente && !respondendo);
  const marca = JSON.stringify([itens.length, itens.at(-1), enviadas, esperandoResposta]);
  const abertos = new Set([...fio.querySelectorAll("details.gasto[open]")].map((d) => /** @type {HTMLElement} */ (d).dataset.quando));
  if (marca === fioVisto) return;
  fioVisto = marca;
  const rolagem = $("rolagem-chat") || fio;
  const embaixo = rolagem.scrollHeight - rolagem.scrollTop - rolagem.clientHeight < 80;
  const balao = (i) => i.tipo === "aviso"
    ? `<div class="fala aviso"><span>Aviso · ${horaFio(i.quando)}</span><p>${esc(i.texto)}</p></div>`
    : `<div class="fala ${i.tipo}${i.pendente ? " pendente" : ""}">${i.tipo === "ze" ? ANEL : ""}${anexosNaFala(i.anexos)}${i.texto ? `<p>${esc(i.texto)}</p>` : ""}<span>${i.origem === "whatsapp" ? "WhatsApp · " : ""}${horaFio(i.quando)}</span>${i.tipo === "ze" ? gastoDaResposta(i.gasto).replace("<details", `<details data-quando="${esc(i.quando)}"${abertos.has(i.quando) ? " open" : ""}`) : ""}</div>`;
  const minhas = enviadas.map((m) => `<div class="fala voce${m.erro ? " erro" : m.entregue ? "" : " enviando"}">${anexosNaFala(m.anexos)}${m.texto ? `<p>${esc(m.texto)}</p>` : ""}<span>${m.erro ? "Não enviado" : horaFio(m.quando)}</span></div>`);
  const tudo = [...itens.map(balao), ...minhas, ...(esperandoResposta ? [digitando] : [])];
  fio.innerHTML = tudo.join("");
  fio.closest(".pagina-inicio")?.classList.toggle("vazia", !tudo.length);
  if (embaixo || !fio.dataset.lido) { rolagem.scrollTop = rolagem.scrollHeight; fio.dataset.lido = "1"; }
}

async function desenharFio() {
  if (!$("fio")) return;
  ultimoFio = await api("conversa");
  montarFio();
}

/** Lê o fio de novo: rápido enquanto o Zé responde, devagar parado. */
function vigiarFio(vez) {
  clearTimeout(fioTimer);
  if (vez !== compartilhado.navegacao || !$("fio")) return;
  const ativo = enviadas.some((m) => !m.erro && !m.entregue) || ["pensando", "falando"].includes(compartilhado.estadoZe) || ultimoFio.itens.some((i) => i.pendente);
  fioTimer = setTimeout(async () => {
    await desenharFio().catch(() => {});
    vigiarFio(vez);
  }, ativo ? 300 : 1500);
}

/** @param {number} vez */
export async function prepararConversa(vez) {
  fioVisto = ""; aprovacoesVistas = "";
  await desenharFio();
  if (vez !== compartilhado.navegacao) return;
  vigiarFio(vez);
  const campo = /** @type {HTMLTextAreaElement} */ (valorCampo("escrever-texto"));
  const enviar = async (ev, pronto = "") => {
    ev?.preventDefault();
    const indo = pronto ? [] : tirarPendentes();
    // Só o anexo: o mesmo texto que o servidor põe, para o balão daqui achar o de lá.
    const texto = (pronto || campo.value).trim() || (indo.length === 1 ? "Veja o anexo." : indo.length ? "Veja os anexos." : "");
    if (!texto) return;
    // Na hora, como num chat: o balão sai, o campo limpa e o Zé "digita".
    const anexos = indo.map(({ arquivo, url }) => ({ nome: arquivo.name, tipo: arquivo.type, tamanho: arquivo.size, miniatura: url }));
    const msg = { texto: texto.replace(/\s+/g, " "), quando: agoraIso(), em: Date.now(), erro: false, entregue: false, anexos };
    enviadas.push(msg);
    campo.value = ""; campo.style.height = "";
    fioVisto = ""; montarFio();
    const rolagem = $("rolagem-chat"); if (rolagem) rolagem.scrollTop = rolagem.scrollHeight;
    vigiarFio(vez);
    let r;
    try {
      const nomes = [];
      for (const { arquivo } of indo) nomes.push(await subirAnexo(arquivo));
      r = await api("conversa/escrever", nomes.length ? { texto, anexos: nomes } : { texto });
    } catch (erro) { r = { aviso: erro.message }; }
    if (r.aviso !== "Enviado.") {
      msg.erro = true; toast(r.aviso);
      if (!campo.value) campo.value = texto; // não se perde o que foi escrito
      devolverPendentes(indo); // nem o que foi anexado
    }
    fioVisto = ""; await desenharFio().catch(() => montarFio());
  };
  $("escrever").addEventListener("submit", enviar);
  enviarPronto = (texto) => enviar(null, texto);
  $("aprovacoes").addEventListener("click", async (ev) => {
    const botao = /** @type {HTMLButtonElement | null} */ (/** @type {HTMLElement} */ (ev.target).closest("button[data-aprovar]"));
    const id = /** @type {HTMLElement | null} */ (botao?.closest("[data-id]"))?.dataset.id;
    if (!botao || !id) return;
    for (const b of botao.parentElement?.querySelectorAll("button") || []) /** @type {HTMLButtonElement} */ (b).disabled = true;
    try { toast((await api("conversa/aprovacao", { id, aprovar: botao.dataset.aprovar === "1" })).aviso); } catch (erro) { toast(erro.message); }
    aprovacoesVistas = ""; await desenharFio().catch(() => {});
  });
  ligarAnexos(campo);
  campo.addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) enviar(ev); });
  campo.addEventListener("input", () => { campo.style.height = ""; campo.style.height = Math.min(campo.scrollHeight, 160) + "px"; });
  if (matchMedia("(pointer: fine)").matches) campo.focus();
}

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.gasto { font-size: 11.5px; color: var(--suave); padding: 0 4px; font-variant-numeric: tabular-nums; }
.gasto summary { cursor: pointer; list-style: none; width: fit-content; }
.gasto summary::-webkit-details-marker { display: none; }
.gasto summary::after { content: " ▾"; opacity: .7; }
.gasto[open] summary::after { content: " ▴"; }
.gasto ul { margin: 6px 0 2px; padding: 8px 10px; list-style: none; display: grid; gap: 6px; border: 1px solid var(--borda); border-radius: 10px; background: var(--fundo-2); }
.gasto b { color: var(--texto); font-weight: 600; }
.esperando { margin: 0; padding: 6px 10px; border-radius: 10px; font-size: 13.5px; color: var(--alerta); border: 1px solid rgb(239 190 124 / .4); }
.aprovacoes { display: grid; gap: 8px; }
.aprovacao { display: flex; gap: 12px; align-items: center; justify-content: space-between; flex-wrap: wrap; padding: 12px 14px; border-radius: 12px; border: 1px solid rgb(239 190 124 / .45); background: var(--fundo-2); }
.aprovacao > div:first-child { display: grid; gap: 2px; min-width: 0; flex: 1 1 260px; }
.aprovacao span { font-size: 11.5px; color: var(--suave); }
.aprovacao p { margin: 2px 0 0; overflow-wrap: anywhere; }
.aprovacao .botoes { display: flex; gap: 8px; }
.fio { display: flex; flex-direction: column; gap: 18px; }
.fala { max-width: 82%; display: grid; gap: 3px; }
.fala p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
.fala > span { font-size: 11.5px; color: var(--apagado); padding: 0 4px; }
.fala.voce { align-self: flex-end; justify-items: end; }
.fala.voce p { padding: 9px 14px; border-radius: 16px 16px 4px 16px; background: var(--acento-escuro); border: 1px solid var(--borda-forte); }
.fala.voce.enviando p { opacity: .75; }
.fala.voce.erro p { border-color: var(--erro); }
.fala.voce.erro span { color: var(--erro); }
.fala.ze { max-width: 100%; align-self: flex-start; grid-template-columns: 26px minmax(0, 1fr); column-gap: 12px; }
.fala.ze > :not(.anel-fala) { grid-column: 2; }
.fala.ze p { padding-top: 2px; }
.fala.ze > span, .fala.ze .gasto { padding: 0; }
.anel-fala { grid-row: 1 / span 3; width: 26px; height: 26px; border-radius: 50%; }
.fala.digitando p { display: flex; gap: 5px; align-items: center; height: 26px; }
.fala.digitando i { width: 7px; height: 7px; border-radius: 50%; background: var(--suave); animation: pulo 1.2s infinite ease-in-out; }
.fala.digitando i:nth-child(2) { animation-delay: .15s; }
.fala.digitando i:nth-child(3) { animation-delay: .3s; }
@keyframes pulo { 0%, 60%, 100% { transform: translateY(0); opacity: .45; } 30% { transform: translateY(-4px); opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .fala.digitando i { animation: none; } }
.fala.aviso { align-self: center; max-width: 92%; justify-items: center; text-align: center; padding: 0; border: 0; background: none; color: inherit; }
.fala.aviso p { padding: 4px 12px; color: var(--suave); font-size: 13px; border-radius: 12px; background: rgb(255 255 255 / .03); }
.escrever { display: grid; gap: 4px; padding: 10px 10px 10px 16px; border-radius: 18px; background: var(--vidro); border: 1px solid var(--borda-forte); box-shadow: 0 8px 28px rgb(0 0 0 / .35); transition: border-color .15s; }
.escrever:focus-within { border-color: #33454f; }
.escrever textarea { resize: none; min-height: 28px; max-height: 200px; padding: 6px 0 0; border: 0; border-radius: 0; background: none; font: inherit; font-size: 15px; color: var(--texto); outline: none; }
.escrever textarea:focus { outline: none; }
.botoes-escrever { display: flex; align-items: center; gap: 6px; }
.botoes-escrever .espaco { flex: 1; }
.redondo { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--borda-forte); background: none; color: var(--suave); cursor: pointer; transition: color .15s, background .15s, border-color .15s; }
.redondo:hover { color: var(--texto); background: var(--realce); }
.redondo[aria-pressed="true"] { color: var(--sobre-acento); background: var(--acento); border-color: var(--acento); }
.redondo.principal { color: var(--sobre-acento); background: var(--acento); border-color: var(--acento); }
.redondo.principal:hover { filter: brightness(1.08); }
.redondo svg { width: 16px; height: 16px; }
` }));

// Para quem chama esta página depois que ela carrega (a navegação, as ações).
Object.assign(carregadas, { prepararConversa });
