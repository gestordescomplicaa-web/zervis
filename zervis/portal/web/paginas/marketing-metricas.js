import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { $, api, botao, cartao, confirmar, esc, item, mostrar, ocupado, sub, toast, vazio } from "../painel.js";

// --- Métricas do site (ADR 0094): o Search Console e o GA4, só leitura ---

const COMO_CONFIGURAR = "https://github.com/gestordescomplicaa-web/zervis/blob/master/docs/metricas-site.md";
/** @param {number} n */
const fmt = (n) => Number(n || 0).toLocaleString("pt-BR");
/** @param {number} s */
const tempo = (s) => s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
/** @param {string} valor @param {string} rotulo */
const numero = (valor, rotulo) => `<div><span class="numero">${valor}</span><span class="rotulo">${rotulo}</span></div>`;
/** @param {number} n */
const decimal = (n) => String(n).replace(".", ",");

/** @param {any} b */
const secaoBusca = (b) => `<h3 class="subtitulo">Google</h3>${b.erro ? `<p class="nota">${esc(b.erro)}</p>`
  : `<div class="numeros">${numero(fmt(b.cliques), "cliques")}${numero(fmt(b.impressoes), "impressões")}${numero(`${decimal(b.ctr)}%`, "CTR")}${numero(decimal(b.posicao), "posição média")}</div>
    ${b.linhas.length ? `<div class="itens">${b.linhas.map((/** @type {any} */ l) => item(esc(l.nome), `${fmt(l.cliques)} cliques · ${fmt(l.impressoes)} impressões`)).join("")}</div>` : vazio("Nenhuma busca no período.")}`}`;

/** @param {any} v */
const secaoVisitas = (v) => `<h3 class="subtitulo">Visitas</h3>${v.erro ? `<p class="nota">${esc(v.erro)}</p>`
  : `<div class="numeros">${numero(fmt(v.visitantes), "visitantes")}${numero(fmt(v.visitas), "visitas")}${numero(fmt(v.visualizacoes), "visualizações")}${numero(tempo(v.tempo_medio_s), "tempo médio")}</div>
    ${v.linhas.length ? `<div class="itens">${v.linhas.map((/** @type {any} */ l) => item(esc(l.titulo || l.nome), `${esc(l.nome)} · ${fmt(l.visualizacoes)} visualizações`)).join("")}</div>` : vazio("Nenhuma visita no período.")}`}`;

/** @param {any} m */
const corpoMetricas = (m) => m.configurado
  ? `${sub(`Como o site aparece no Google e quem o visita, nos últimos ${m.dias} dias.`)}
    ${secaoBusca(m.busca)}${secaoVisitas(m.visitas)}
    <div class="linha"><span class="sub">${esc(m.conta)}</span>${botao("Remover chave", "mk-met-remover", "", "discreta")}</div>`
  : `${sub("Como o site aparece no Google e quem o visita, pelo Search Console e pelo Google Analytics. Só leitura.")}
    <div class="campos"><label>Chave da conta de serviço (JSON)<textarea id="mk-met-chave" rows="4" class="mono" spellcheck="false" placeholder='{"type": "service_account", ...}'></textarea></label></div>
    <div class="linha">${botao("Salvar", "mk-met-salvar", "", "principal")}<a class="acao discreta" href="${COMO_CONFIGURAR}" target="_blank" rel="noopener">Como configurar</a></div>
    <p class="resultado" id="mk-resultado-metricas"></p>`;

/** @param {any} m */
const etiquetaMetricas = (m) => m ? `<span class="etiqueta ${m.configurado ? "bom" : ""}">${m.configurado ? "Configurado" : "Não configurado"}</span>` : "";
/** @param {any} m */
export const cartaoMetricas = (m) => `<div id="mk-metricas">${cartao(`Métricas do site ${etiquetaMetricas(m)}`, m ? corpoMetricas(m) : sub("Carregando…"))}</div>`;

/** O Google pode demorar: a página espera só um instante, e o cartão chega depois. */
export async function metricasSemTravar() {
  /** @param {Error} erro */
  const falhou = (erro) => ({ configurado: true, conta: "", dias: 28, busca: { erro: erro.message }, visitas: { erro: erro.message } });
  const pedido = api("marketing/metricas").catch(falhou);
  const cedo = await Promise.race([pedido, new Promise((r) => setTimeout(() => r(null), 300))]);
  if (!cedo) pedido.then((m) => { const lugar = $("mk-metricas"); if (lugar) lugar.outerHTML = cartaoMetricas(m); });
  return cedo;
}

Object.assign(ACOES, {
  "mk-met-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const chave = /** @type {HTMLTextAreaElement} */ ($("mk-met-chave")).value.trim();
    mostrar("mk-resultado-metricas", null, "Conferindo a chave…");
    try { const r = await ocupado(b, () => api("marketing/metricas/chave", { chave })); toast(r.aviso); await abrir(); } catch (erro) { mostrar("mk-resultado-metricas", false, erro.message); }
  },
  "mk-met-remover": (/** @type {HTMLButtonElement} */ b) => confirmar(b, "Remover a chave?", async () => {
    const r = await api("marketing/metricas/remover", { confirmado: true });
    toast(r.aviso);
    await abrir();
  }),
});
