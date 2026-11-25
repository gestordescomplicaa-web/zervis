import { ESTADOS, PAGINAS, api, esc, quando, seg } from "../painel.js";
import { ACOES } from "../modulos/acoes.js";
import { ICONES, icone } from "../modulos/casca.js";
import { carregadas, compartilhado } from "../modulos/estado.js";
import { campoEscrever, chat, enviarPronto } from "./conversa.js";

// O Início é a conversa com o Zé (ADR 0136): o chat no centro, com as sugestões quando o dia
// começa; ao lado, o que precisa de você, o que o Zé está fazendo, o foco e os números de hoje.
const PEDIDOS = ["O que precisa de mim?", "Como está a prospecção?", "Resuma o meu dia", "O que as sessões estão fazendo?"];
const NO_LADO = 5;

/** Uma linha do lado: o ícone da área, o título e o detalhe; leva à página.
 * @param {{ secao: string, titulo: string, detalhe?: string, area?: string, link?: string, vivo?: boolean, hora?: string, quando?: string | number }} a */
const linhaLado = (a) => {
  const detalhe = [a.area, a.detalhe].filter(Boolean).join(" · ");
  const hora = a.hora || (typeof a.quando === "string" ? quando(a.quando) : "");
  return `<a class="item-lado" href="${esc(a.link || `#${a.secao}`)}"><span class="icone-area ${a.vivo ? "vivo" : ""}">${icone(ICONES[a.secao] || "activity")}</span><span class="texto"><strong>${esc(a.titulo)}</strong>${detalhe ? `<small>${esc(detalhe)}</small>` : ""}</span>${hora ? `<span class="hora">${esc(hora)}</span>` : ""}</a>`;
};

/** O lado do chat. @param {any} e */
function lado(e) {
  // As aprovações aparecem no próprio chat, onde se resolvem.
  const precisa = e.precisa.filter((/** @type {{ aprovacao?: string }} */ p) => !p.aprovacao);
  const vivos = e.agora.filter((/** @type {{ vivo?: boolean }} */ a) => a.vivo).length;
  const voz = e.hoje.voz_s == null ? "—" : seg(e.hoje.voz_s * 1000);
  const numero = (/** @type {string | number} */ valor, /** @type {string} */ rotulo) => `<div><span class="numero">${valor}</span><span class="rotulo">${rotulo}</span></div>`;
  const bloco = (/** @type {string} */ titulo, /** @type {string} */ extra, /** @type {string} */ corpo) => `<section class="bloco-lado"><div class="cabeca-lado"><h2>${titulo}</h2>${extra}</div>${corpo}</section>`;
  return `${bloco("Precisa de você", precisa.length ? `<span class="etiqueta alerta">${precisa.length}</span>` : "",
      precisa.length ? `<div class="itens-lado">${precisa.slice(0, NO_LADO).map(linhaLado).join("")}</div>${precisa.length > NO_LADO ? `<button type="button" class="acao discreta ver-todos" data-acao="avisos">Ver todos</button>` : ""}` : `<p class="vazio">Nada pendente.</p>`)}
    ${bloco("O Zé agora", vivos ? `<span class="etiqueta">${vivos} em andamento</span>` : "",
      e.agora.length ? `<div class="itens-lado">${e.agora.map(linhaLado).join("")}</div>` : `<p class="vazio">Nada em andamento.</p>`)}
    ${bloco(`<a href="#foco">Foco</a>`, "", e.foco ? `<div class="foco-lado"><strong>${esc(e.foco.titulo)}</strong><small>${e.foco.passo ? "Próximo passo: " + esc(e.foco.passo) : "Sem próximo passo."}</small></div>` : `<p class="vazio">Nenhuma frente em andamento.</p>`)}
    ${bloco("Hoje", "", `<div class="numeros">${numero(e.hoje.respostas, "respostas")}${numero(e.hoje.tokens_mil + " mil", "tokens")}${numero(voz, "voz")}</div><details class="gasto consumo"><summary>Consumo detalhado</summary><p class="consumo-dia" id="consumo-dia" hidden></p></details>`)}`;
}

PAGINAS.inicio = async function() {
  const e = await api("inicio");
  const estado = /** @type {HTMLElement | null} */ (document.querySelector(".topo .icone-ze"))?.dataset.estado || e.ze;
  return `<div class="pagina-inicio vazia">
    <div class="coluna-chat">
      <div class="rolagem-chat" id="rolagem-chat">
        <div class="miolo-chat">
          <section class="boas-vindas">
            <span class="icone-ze grande" data-espelho data-estado="${esc(estado)}" title="Zé ${esc(ESTADOS[estado] || estado)}"><img class="anel" src="/ze.webp" alt="" width="72" height="72"></span>
            <h1>${esc(e.saudacao)} O que vamos fazer?</h1>
            <p class="sub">${e.chamado === "botao" ? "Escreva abaixo ou toque no microfone." : "Escreva abaixo ou diga “Ei Zé”."}</p>
          </section>
          ${chat()}
        </div>
      </div>
      <div class="pe-chat">
        ${campoEscrever()}
        <div class="pedidos">${PEDIDOS.map((p) => `<button type="button" class="pedido" data-acao="inicio-pedir" data-texto="${esc(p)}">${esc(p)}</button>`).join("")}</div>
      </div>
    </div>
    <aside class="lado-inicio" id="lado-inicio" aria-label="Resumo">${lado(e)}</aside>
  </div>`;
};

/** Lê o lado de novo de tempos em tempos, sem tocar no chat. @param {number} vez */
export async function vigiarLado(vez) {
  await new Promise((r) => setTimeout(r, 15000));
  const caixa = document.getElementById("lado-inicio");
  if (vez !== compartilhado.navegacao || !caixa) return;
  try { caixa.innerHTML = lado(await api("inicio")); } catch { /* fica o que estava */ }
  vigiarLado(vez);
}

Object.assign(ACOES, {
  /** Uma sugestão vai ao Zé como se fosse escrita. @param {HTMLButtonElement} b */
  "inicio-pedir": (b) => enviarPronto(b.dataset.texto || ""),
});

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.pagina-inicio { flex: 1 1 auto; align-self: stretch; display: grid; grid-template-columns: minmax(0, 1fr) 320px; height: 100%; min-height: 0; min-width: 0; color: var(--texto); font-size: 14px; animation: entrar-pagina .32s var(--saida); }
.coluna-chat { display: grid; grid-template-rows: minmax(0, 1fr) auto; min-height: 0; min-width: 0; }
.rolagem-chat { overflow-y: auto; min-height: 0; padding: 28px clamp(16px, 4vw, 48px) 12px; }
.miolo-chat { max-width: 760px; margin: 0 auto; display: grid; gap: 14px; }
.pe-chat { width: min(760px, 100% - 2 * clamp(16px, 4vw, 48px)); margin: 0 auto; padding: 4px 0 20px; display: grid; gap: 14px; }
.boas-vindas { display: none; justify-items: center; text-align: center; gap: 10px; }
.boas-vindas h1 { font-size: 28px; }
.boas-vindas .sub { margin: 0; }
.icone-ze.grande { margin-bottom: 6px; }
.icone-ze.grande .anel { width: 72px; height: 72px; }
.icone-ze.grande::before, .icone-ze.grande::after { border-width: 2px; }
.pedidos { display: none; flex-wrap: wrap; justify-content: center; gap: 8px; }
.pedido { height: 34px; padding: 0 14px; border-radius: 17px; cursor: pointer; font: 500 13px var(--sans);
  color: var(--suave); background: none; border: 1px solid var(--borda-forte); transition: color .15s, background .15s, border-color .15s, transform .12s; }
.pedido:hover { color: var(--texto); background: var(--realce); border-color: #33454f; }
.pedido:active { transform: scale(.97); }
/* Sem conversa hoje: as boas-vindas, o campo e as sugestões no meio da tela. */
.pagina-inicio.vazia .coluna-chat { grid-template-rows: 1fr auto auto 1.4fr; }
.pagina-inicio.vazia .rolagem-chat { grid-row: 2; overflow: visible; padding-bottom: 24px; }
.pagina-inicio.vazia .pe-chat { grid-row: 3; }
.pagina-inicio.vazia .boas-vindas { display: grid; }
.pagina-inicio.vazia .pedidos { display: flex; }
.pagina-inicio.vazia .fio { display: none; }
.lado-inicio { overflow-y: auto; min-height: 0; padding: 24px 20px; border-left: 1px solid var(--borda); background: var(--fundo-2); display: grid; gap: 26px; align-content: start; }
.bloco-lado { display: grid; gap: 10px; }
.cabeca-lado { display: flex; align-items: center; gap: 8px; }
.cabeca-lado h2 { margin: 0; font-size: 13px; font-weight: 600; color: var(--suave); }
.cabeca-lado h2 a { color: inherit; }
.itens-lado { display: grid; gap: 2px; margin: 0 -8px; }
.item-lado { display: flex; align-items: center; gap: 10px; padding: 7px 8px; border-radius: 9px; color: inherit !important; text-decoration: none !important; transition: background .15s; }
.item-lado:hover { background: var(--realce); }
.item-lado .icone-area { width: 28px; height: 28px; }
.item-lado .icone-area svg { width: 15px; height: 15px; }
.item-lado .texto { display: grid; min-width: 0; flex: 1; }
.item-lado strong { font-weight: 500; font-size: 13.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-lado small { color: var(--suave); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-lado .hora { font-size: 11.5px; color: var(--apagado); white-space: nowrap; }
.foco-lado { display: grid; gap: 2px; }
.foco-lado small { color: var(--suave); }
.lado-inicio .numeros { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.consumo .consumo-dia { margin-top: 6px; }
.lado-inicio .numero { font-size: 20px; }
.consumo-dia { margin: 0; font-size: 12px; color: var(--apagado); font-variant-numeric: tabular-nums; }
.ver-todos { justify-self: start; padding: 4px 0; }
/* Tela menor: o resumo vem abaixo das boas-vindas; na conversa, fica no sino. */
@media (max-width: 1180px) {
  .pagina-inicio { grid-template-columns: minmax(0, 1fr); }
  .lado-inicio { display: none; }
  .pagina-inicio.vazia { grid-template-rows: minmax(min-content, 78%) auto; overflow-y: auto; }
  .pagina-inicio.vazia .lado-inicio { display: grid; overflow: visible; border-left: 0; border-top: 1px solid var(--borda); background: none;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); padding: 24px clamp(16px, 4vw, 48px) 32px; }
}
@media (max-width: 720px) {
  .rolagem-chat { padding-top: 16px; }
  .boas-vindas h1 { font-size: 22px; }
  .icone-ze.grande .anel { width: 60px; height: 60px; }
  .pe-chat { padding-bottom: calc(12px + env(safe-area-inset-bottom)); }
}
` }));

Object.assign(carregadas, { vigiarLado });
