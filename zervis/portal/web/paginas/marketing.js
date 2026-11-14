import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { carregadas } from "../modulos/estado.js";
import { PAGINAS, $, api, botao, cabeca, cartao, esc, item, mostrar, ocupado, sub, vazio } from "../painel.js";

// A página Marketing (ADR 0091): o site e o blog de quem usa. Cada pedido vira uma sessão numa
// cópia isolada; o Zé abre o PR e a pessoa publica no merge.

/** @param {any} s */
const cartaoSite = (s) => cartao(`Site <span class="etiqueta ${s.configurado && s.blog ? "bom" : s.configurado ? "alerta" : ""}">${esc(s.estado)}</span>`,
  `${sub("O repositório do site no GitHub. Os pedidos partem da branch base e voltam como PR.")}
  <div class="campos">
    <label>Pasta do site<input id="mk-pasta" class="mono" value="${esc(s.pasta)}" placeholder="~/projetos/meu-site" spellcheck="false"></label>
    <label>Branch base<input id="mk-base" class="mono" value="${esc(s.base)}" placeholder="main" spellcheck="false"></label>
  </div>
  <div class="linha">${botao("Salvar", "mk-salvar", "", "principal")}</div>
  <p class="resultado" id="mk-resultado-site"></p>`);

/** @param {any} r */
const cartaoPedir = (r) => cartao("Novo pedido",
  `${sub("O artigo segue o manual do blog do próprio site e chega como rascunho.")}
  <div class="campos">
    <label>Tema do artigo ou mudança no site<input id="mk-texto" placeholder="Opcional para artigo" autocomplete="off"></label>
  </div>
  <div class="linha">${botao("Escrever artigo", "mk-pedir", 'data-tipo="artigo"', r.site.blog ? "principal" : "")}${botao("Mudar o site", "mk-pedir", 'data-tipo="site"', "discreta")}</div>
  <p class="resultado" id="mk-resultado-pedido"></p>`);

/** O estado de um pedido, em uma ou duas palavras. @param {any} p */
const estadoPedido = (p) => p.publicando ? "Publicando" : p.estado === "trabalhando" ? "Trabalhando"
  : p.estado === "erro" ? "Erro" : p.pr ? "PR aberto" : "Concluída";

/** @param {any} p */
const acoesPedido = (p) => {
  const sessao = botao("Abrir sessão", "mk-sessao", `data-id="${esc(p.id)}"`, "discreta");
  if (p.estado === "trabalhando" || p.publicando) return sessao;
  if (p.pr) return `${sessao}<a class="acao discreta" href="${esc(p.pr)}" target="_blank" rel="noopener">Revisar</a>${botao("Publicar", "mk-publicar", `data-id="${esc(p.id)}"`, "principal")}`;
  return sessao + botao("Abrir PR", "mk-pr", `data-id="${esc(p.id)}"`, "principal");
};

/** @param {any[]} pedidos */
const cartaoPedidos = (pedidos) => cartao("Pedidos", pedidos.length
  ? `<div class="itens">${pedidos.map((p) => item(esc(p.nome), estadoPedido(p), acoesPedido(p))).join("")}</div>
     <p class="resultado" id="mk-resultado-pr"></p>`
  : vazio("Nenhum pedido em andamento."));

const AGENDAS = [
  ["cron 0 9 * * 1,4", "Segunda e quinta, 9h"],
  ["cron 0 9 * * 1", "Toda segunda, 9h"],
  ["cron 0 9 * * 1-5", "Todo dia útil, 9h"],
];

/** @param {any} r */
const cartaoAutomaticos = (r) => cartao(`Artigos automáticos <span class="etiqueta ${r.automaticos.some((/** @type {any} */ j) => j.ativo) ? "bom" : ""}">${r.automaticos.some((/** @type {any} */ j) => j.ativo) ? "Ativo" : "Desligado"}</span>`,
  `${sub("O Zé escreve o artigo, abre o PR e publica com a sua aprovação.")}
  ${r.automaticos.length ? `<div class="itens">${r.automaticos.map((/** @type {any} */ j) => item(esc(j.agenda), j.ativo ? `Próximo: ${esc(String(j.proxima).slice(0, 16).replace("T", " "))}` : "Pausado", "")).join("")}</div>` : ""}
  <div class="campos"><label>Quando<select id="mk-agenda">${AGENDAS.map(([v, n]) => `<option value="${v}">${n}</option>`).join("")}</select></label></div>
  <div class="linha">${botao("Agendar", "mk-agendar", "", r.automaticos.length ? "discreta" : "principal")}<a class="acao discreta" href="#automacoes">Automações</a></div>
  <p class="resultado" id="mk-resultado-agenda"></p>`);

/** @param {any[]} prs */
const cartaoPRs = (prs) => cartao("PRs abertos", prs.length
  ? `<div class="itens">${prs.map((p) => item(`#${esc(String(p.numero))} ${esc(p.titulo)}`, "",
      `<a class="acao discreta" href="${esc(p.endereco)}" target="_blank" rel="noopener">Revisar</a>`)).join("")}</div>`
  : vazio("Nenhum PR aberto."));

/** @param {any} r */
const cartaoBlog = (r) => {
  const categorias = Object.entries(r.categorias);
  return cartao(`Blog <span class="etiqueta">${r.artigos.length} ${r.artigos.length === 1 ? "artigo" : "artigos"}</span>`,
    `${categorias.length ? `<p class="sub">${categorias.map(([c, n]) => `${esc(c)}: ${n}`).join(" · ")}</p>` : ""}
    ${r.artigos.length
      ? `<div class="itens">${r.artigos.map((a) => item(esc(a.titulo), `${esc(a.data)} · ${esc(a.categoria)}`, `<span class="etiqueta ${a.estado === "Publicado" ? "bom" : ""}">${esc(a.estado)}</span>`)).join("")}</div>`
      : vazio(r.site.blog ? "Nenhum artigo ainda." : "O site não declara um blog no zervis.json.")}`);
};

PAGINAS.marketing = async () => {
  const r = await api("marketing");
  const corpo = r.site.configurado
    ? `${cartaoPedir(r)}${cartaoPedidos(r.pedidos)}${r.site.blog ? cartaoAutomaticos(r) : ""}${cartaoPRs(r.prs)}${cartaoBlog(r)}${cartaoSite(r.site)}`
    : cartaoSite(r.site);
  return `${cabeca("Marketing")}${sub("O site e o blog, sempre por Pull Request: nada vai ao ar sem você.")}${corpo}`;
};

Object.assign(ACOES, {
  "mk-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { pasta: /** @type {HTMLInputElement} */ ($("mk-pasta")).value, base: /** @type {HTMLInputElement} */ ($("mk-base")).value };
    try { await ocupado(b, () => api("marketing/site", dados)); await abrir(); } catch (erro) { mostrar("mk-resultado-site", false, erro.message); }
  },
  "mk-pedir": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { tipo: b.dataset.tipo, texto: /** @type {HTMLInputElement} */ ($("mk-texto")).value };
    try { await ocupado(b, () => api("marketing/pedir", dados)); await abrir(); } catch (erro) { mostrar("mk-resultado-pedido", false, erro.message); }
  },
  "mk-pr": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/pr", { sessao: b.dataset.id }));
      await abrir();
      mostrar("mk-resultado-pr", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-pr", false, erro.message); }
  },
  "mk-publicar": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/publicar", { sessao: b.dataset.id }));
      await abrir();
      mostrar("mk-resultado-pr", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-pr", false, erro.message); }
  },
  "mk-agendar": async (/** @type {HTMLButtonElement} */ b) => {
    const quando = /** @type {HTMLSelectElement} */ ($("mk-agenda")).value;
    try { await ocupado(b, () => api("marketing/agendar", { quando })); await abrir(); } catch (erro) { mostrar("mk-resultado-agenda", false, erro.message); }
  },
  "mk-sessao": async (/** @type {HTMLButtonElement} */ b) => {
    location.hash = "#sessoes";
    for (let i = 0; i < 50 && !(carregadas.abrirSessao && document.querySelector(".sessoes")); i++) await new Promise((r) => setTimeout(r, 100));
    await carregadas.abrirSessao?.(b.dataset.id);
  },
});
