import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { carregadas } from "../modulos/estado.js";
import { PAGINAS, $, api, botao, cabeca, cartao, esc, item, mostrar, ocupado, sub, vazio } from "../painel.js";

// A página Marketing (ADR 0091): o site e o blog de quem usa. Cada pedido vira uma sessão numa
// cópia isolada; o Zé abre o PR e a pessoa publica no merge.

const ESTADOS_SESSAO = { trabalhando: "Trabalhando", parada: "Concluída", erro: "Erro" };

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

/** @param {any[]} pedidos */
const cartaoPedidos = (pedidos) => cartao("Pedidos", pedidos.length
  ? `<div class="itens">${pedidos.map((p) => item(esc(p.nome), ESTADOS_SESSAO[p.estado] || esc(p.estado),
      botao("Abrir sessão", "mk-sessao", `data-id="${esc(p.id)}"`, "discreta")
      + (p.estado === "trabalhando" ? "" : botao("Abrir PR", "mk-pr", `data-id="${esc(p.id)}"`, "principal")))).join("")}</div>
     <p class="resultado" id="mk-resultado-pr"></p>`
  : vazio("Nenhum pedido em andamento."));

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
    ? `${cartaoPedir(r)}${cartaoPedidos(r.pedidos)}${cartaoPRs(r.prs)}${cartaoBlog(r)}${cartaoSite(r.site)}`
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
  "mk-sessao": async (/** @type {HTMLButtonElement} */ b) => {
    location.hash = "#sessoes";
    for (let i = 0; i < 50 && !(carregadas.abrirSessao && document.querySelector(".sessoes")); i++) await new Promise((r) => setTimeout(r, 100));
    await carregadas.abrirSessao?.(b.dataset.id);
  },
});
