import { ESTADOS, PAGINAS, api, cartao, esc, quando, seg, toast, vazio } from "../painel.js";
import { ACOES } from "../modulos/acoes.js";
import { linhaPrecisa } from "../modulos/avisos.js";
import { ICONES, icone } from "../modulos/casca.js";

// Página inicio, carregada sob demanda (ADR 0133): a voz no centro, o que precisa de você, o que o
// Zé está fazendo agora e os números de hoje.
const PEDIDOS = ["O que precisa de mim?", "Como está a prospecção?", "Resuma o meu dia", "O que as sessões estão fazendo?"];
const NO_INICIO = 5;

/** @param {{ secao: string, titulo: string, detalhe: string, vivo?: boolean, hora?: string, quando?: string }} a */
const linhaAgora = (a) => `<a class="linha-item agora" href="#${esc(a.secao)}"><span class="icone-area ${a.vivo ? "vivo" : ""}">${icone(ICONES[a.secao] || "activity")}</span><div class="texto"><strong>${esc(a.titulo)}</strong>${a.detalhe ? `<small>${esc(a.detalhe)}</small>` : ""}</div>${a.hora || a.quando ? `<span class="hora">${esc(a.hora || quando(a.quando || ""))}</span>` : ""}</a>`;

PAGINAS.inicio = async function() {
    const e = await api("inicio");
    const estado = /** @type {HTMLElement | null} */ (document.querySelector(".topo .icone-ze"))?.dataset.estado || e.ze;
    const vivos = e.agora.filter((/** @type {{ vivo?: boolean }} */ a) => a.vivo).length;
    const n = e.precisa.length;
    const voz = e.hoje.voz_s == null ? "—" : seg(e.hoje.voz_s * 1000);
    const numero = (/** @type {string | number} */ valor, /** @type {string} */ rotulo) => `<div><span class="numero">${valor}</span><span class="rotulo">${rotulo}</span></div>`;
    const foco = e.foco ? `<strong>${esc(e.foco.titulo)}</strong><p>${e.foco.passo ? "Próximo passo: " + esc(e.foco.passo) : "Sem próximo passo."}</p>` : vazio("Nenhuma frente em andamento.");
    return `<div class="inicio">
      <section class="voz-inicio">
        <span class="icone-ze grande" data-espelho data-estado="${esc(estado)}" title="Zé ${esc(ESTADOS[estado] || estado)}"><img class="anel" src="/ze.webp" alt="" width="96" height="96"></span>
        <h1>${esc(e.saudacao)} O que vamos fazer?</h1>
        <p class="sub">${e.chamado === "botao" ? "Toque em Falar ou escolha um pedido." : "Diga “Ei Zé” ou toque em Falar. Tudo aqui também se faz pela voz."}</p>
        <div class="pedidos">${PEDIDOS.map((p) => `<button type="button" class="pedido" data-acao="inicio-pedir" data-texto="${esc(p)}">${icone("message-square")}${esc(p)}</button>`).join("")}</div>
      </section>
      <div class="duas">
        <section class="cartao">
          <div class="cabeca"><h2>Precisa de você</h2>${n ? `<span class="etiqueta alerta">${n}</span>` : ""}${n > NO_INICIO ? `<button type="button" class="acao discreta ver-todos" data-acao="avisos">Ver todos</button>` : ""}</div>
          ${n ? `<div class="itens">${e.precisa.slice(0, NO_INICIO).map(linhaPrecisa).join("")}</div>` : vazio("Nada pendente.")}
        </section>
        <section class="cartao">
          <div class="cabeca"><h2>O Zé agora</h2>${vivos ? `<span class="etiqueta">${vivos} em andamento</span>` : ""}</div>
          ${e.agora.length ? `<div class="itens">${e.agora.map(linhaAgora).join("")}</div>` : vazio("Nada em andamento.")}
        </section>
      </div>
      <div class="grade">
        ${cartao(`<a href="#foco">Foco</a>`, foco)}
        ${cartao("Hoje", `<div class="numeros">${numero(e.hoje.respostas, "respostas")}${numero(e.hoje.tokens_mil + " mil", "tokens")}${numero(voz, "voz mais rápida")}</div>`)}
      </div>
    </div>`;
  };

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.inicio { max-width: 1120px; display: grid; gap: 20px; animation: entrar-pagina .32s var(--saida); }
.voz-inicio { display: grid; justify-items: center; text-align: center; gap: 10px; padding: 20px 0 12px; }
.icone-ze.grande { margin-bottom: 8px; }
.icone-ze.grande .anel { width: 96px; height: 96px; }
.icone-ze.grande::before, .icone-ze.grande::after { border-width: 2px; }
.voz-inicio h1 { font-size: 28px; }
.voz-inicio .sub { margin: 0; }
.pedidos { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 10px; }
.pedido { display: inline-flex; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border-radius: 18px; cursor: pointer; font: 500 13.5px var(--sans);
  color: var(--suave); background: var(--vidro); border: 1px solid var(--borda-forte); transition: color .15s, background .15s, border-color .15s, transform .12s; }
.pedido:hover { color: var(--texto); background: var(--realce); border-color: #33454f; }
.pedido:active { transform: scale(.97); }
.pedido svg { width: 15px; height: 15px; color: var(--acento); }
.duas { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: start; }
.duas .cabeca h2 { margin: 0; }
.ver-todos { margin-left: auto; padding: 4px 10px; }
@media (max-width: 960px) { .duas { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 720px) { .voz-inicio { padding-top: 4px; } .voz-inicio h1 { font-size: 22px; } .icone-ze.grande .anel { width: 72px; height: 72px; } .linha-item .hora { display: none; } }
` }));

Object.assign(ACOES, {
  /** Um pedido de exemplo vai ao Zé como se fosse escrito; a resposta aparece na Conversa. @param {HTMLButtonElement} b */
  "inicio-pedir": (b) => {
    location.hash = "#conversa";
    api("conversa/escrever", { texto: b.dataset.texto || "" }).then((r) => { if (r.aviso !== "Enviado.") toast(r.aviso); }, (erro) => toast(erro.message));
  },
});
