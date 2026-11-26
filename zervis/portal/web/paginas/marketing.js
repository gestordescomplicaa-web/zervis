import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { carregadas } from "../modulos/estado.js";
import { PAGINAS, $, api, botao, cabeca, cartao, esc, item, mostrar, ocupado, sub, vazio } from "../painel.js";
import { abaAjustes } from "./marketing-ajustes.js";
import { cartaoMetricas, metricasSemTravar } from "./marketing-metricas.js";
import { cartaoComentarios } from "./marketing-direct.js";
import { cartaoVideos, lembrarLeitura, pelaVoz } from "./marketing-videos.js";

// A página Marketing (ADR 0091): o site e o blog de quem usa. Cada pedido vira uma sessão numa
// cópia isolada; o Zé abre o PR e a pessoa publica no merge. Em abas (ADR 0134): o trabalho de
// cada canal numa, os ajustes de todos em outra.


/** @param {any} r */
const cartaoPedir = (r) => cartao("Novo pedido",
  `${sub("O artigo segue o manual do blog do próprio site e chega como rascunho.")}
  <div class="campos">
    <label>Tema do artigo ou mudança no site<input id="mk-texto" placeholder="Opcional para artigo" autocomplete="off"></label>
  </div>
  ${pelaVoz("Zé, escreve um artigo sobre agendamento pelo WhatsApp")}
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

/** @param {any[] | null | undefined} prs undefined: ainda chegando; null: o GitHub falhou */
const corpoPRs = (prs) => prs === undefined ? sub("Carregando…") : prs === null ? sub("Sem conexão com o GitHub.") : prs.length
  ? `<div class="itens">${prs.map((p) => item(`#${esc(String(p.numero))} ${esc(p.titulo)}`, "",
      `<a class="acao discreta" href="${esc(p.endereco)}" target="_blank" rel="noopener">Revisar</a>`)).join("")}</div>`
  : vazio("Nenhum PR aberto.");
/** @param {any[] | null | undefined} prs */
const cartaoPRs = (prs) => `<div id="mk-prs">${cartao("PRs abertos", corpoPRs(prs))}</div>`;

/** @type {any[] | null | undefined} a última lista, mostrada enquanto a nova chega */
let ultimosPRs;

/** O GitHub leva quase um segundo: a página não espera por ele, e o cartão chega depois. */
async function prsSemTravar() {
  const pedido = api("marketing/prs").catch(() => null).then((prs) => (ultimosPRs = prs));
  const cedo = await Promise.race([pedido, new Promise((r) => setTimeout(() => r(undefined), 300))]);
  if (cedo === undefined) pedido.then((prs) => { const lugar = $("mk-prs"); if (lugar) lugar.outerHTML = cartaoPRs(prs); });
  return cedo === undefined ? ultimosPRs : cedo;
}

/** @param {any} r */
const cartaoBlog = (r) => {
  const categorias = Object.entries(r.categorias);
  return cartao(`Blog <span class="etiqueta">${r.artigos.length} ${r.artigos.length === 1 ? "artigo" : "artigos"}</span>`,
    `${categorias.length ? `<p class="sub">${categorias.map(([c, n]) => `${esc(c)}: ${n}`).join(" · ")}</p>` : ""}
    ${r.artigos.length
      ? `<div class="itens">${r.artigos.map((a) => item(esc(a.titulo), `${esc(a.data)} · ${esc(a.categoria)}`, `<span class="etiqueta ${a.estado === "Publicado" ? "bom" : ""}">${esc(a.estado)}</span>`)).join("")}</div>`
      : vazio(r.site.blog ? "Nenhum artigo ainda." : "O site não declara um blog no zervis.json.")}`);
};

// --- Instagram (ADR 0093): o Zé cria o carrossel, você vê e aprova; nada sai sozinho ---

const ESTADOS_POST = { criando: "Criando", rascunho: "Para revisar", publicando: "Publicando", publicado: "Publicado", erro: "Erro" };
/** @type {any} */
let postAberto = null;

/** @param {any} r */
const cartaoInstagram = (r) => {
  const publicados = r.artigos.filter((/** @type {any} */ a) => a.estado === "Publicado");
  const aviso = !r.marca.instagram ? "Conecte o Instagram em Redes sociais para publicar."
    : !r.marca.publicavel ? "Publicar exige o acesso de qualquer lugar com endereço fixo." : "";
  return cartao(`Instagram <span class="etiqueta ${r.marca.instagram ? "bom" : ""}">${r.marca.instagram ? "Conectado" : "Não conectado"}</span>`,
    `${sub("O Zé cria o carrossel e a legenda com a sua marca. Você vê a prévia e aprova; nada é publicado sozinho.")}
    ${aviso ? `<p class="nota">${aviso}</p>` : ""}
    <div class="campos">
      <label>Tema do post<input id="mk-post-tema" placeholder="Ex.: atendimento fora do horário" autocomplete="off"></label>
      ${publicados.length ? `<label>Ou a partir de um artigo<select id="mk-post-artigo"><option value="">—</option>${publicados.map((/** @type {any} */ a) => `<option value="${esc(a.slug)}">${esc(a.titulo)}</option>`).join("")}</select></label>` : ""}
    </div>
    ${pelaVoz("Zé, cria um post sobre atendimento fora do horário")}
    <div class="linha">${botao("Criar post", "mk-post-criar", "", "principal")}</div>
    <p class="resultado" id="mk-resultado-post"></p>
    ${r.posts.length ? `<div class="itens">${r.posts.map((/** @type {any} */ p) => item(esc(p.tema || p.artigo), `${ESTADOS_POST[p.estado] || esc(p.estado)}${p.erro ? ` · ${esc(p.erro)}` : ""}`,
      p.estado === "criando" ? "" : p.permalink ? `<a class="acao discreta" href="${esc(p.permalink)}" target="_blank" rel="noopener">Ver no Instagram</a>`
        : botao(postAberto?.id === p.id ? "Fechar" : "Ver", "mk-post-ver", `data-id="${esc(p.id)}"`, "discreta"))).join("")}</div>` : ""}
    ${postAberto ? previa(postAberto) : ""}`);
};

/** @param {any} p */
const previa = (p) => `<div class="previa-post">
  <div class="slides-post">${(p.imagens || []).map((/** @type {string} */ src, /** @type {number} */ i) => `<img src="${src}" alt="Slide ${i + 1} de ${p.imagens.length}">`).join("")}</div>
  <pre class="legenda-post">${esc(p.legenda)}</pre>
  ${p.estado === "rascunho" ? `<div class="campos"><label>Ajuste<input id="mk-post-ajuste" placeholder="Ex.: deixe o slide 2 mais curto" autocomplete="off"></label></div>
  <div class="linha">${botao("Publicar no Instagram", "mk-post-publicar", `data-id="${esc(p.id)}"`, "principal")}${botao("Refazer", "mk-post-refazer", `data-id="${esc(p.id)}"`)}${botao("Descartar", "mk-post-descartar", `data-id="${esc(p.id)}"`, "discreta")}</div>` : ""}
  <p class="resultado" id="mk-resultado-previa"></p></div>`;




const ABAS = [["visao", "Visão geral"], ["blog", "Blog"], ["videos", "Vídeos"], ["instagram", "Instagram"], ["ajustes", "Ajustes"]];
const LEMBRAR = "ze.marketing-aba";
let aba = "visao";
try { aba = localStorage.getItem(LEMBRAR) || aba; } catch { /* sem armazenamento: começa na Visão geral */ }

const abas = () => `<div class="abas" role="tablist" aria-label="Marketing">${ABAS.map(([id, nome]) =>
  `<button type="button" role="tab" class="aba" id="mk-tab-${id}" data-acao="mk-aba" data-aba="${id}" aria-selected="${id === aba}" aria-controls="mk-aba-${id}">${nome}</button>`).join("")}</div>`;
/** @param {string} id @param {string} corpo */
const painel = (id, corpo) => `<div class="painel-aba" role="tabpanel" id="mk-aba-${id}" aria-labelledby="mk-tab-${id}"${id === aba ? "" : " hidden"}>${corpo}</div>`;

/** O que espera o seu sim, de todos os canais, cada um levando à sua aba. @param {any} r */
const cartaoAprovar = (r) => {
  const itens = [
    ...(r.pedidos || []).filter((/** @type {any} */ p) => p.pr && !p.publicando).map((/** @type {any} */ p) => ["blog", p.nome, "Blog · PR aberto"]),
    ...((r.videos && r.videos.lista) || []).filter((/** @type {any} */ v) => v.estado === "rascunho" && v.pronto).map((/** @type {any} */ v) => ["videos", v.titulo || v.tema, "Vídeo · Pronto para publicar"]),
    ...(r.posts || []).filter((/** @type {any} */ p) => p.estado === "rascunho").map((/** @type {any} */ p) => ["instagram", p.tema || p.artigo, "Post · Para revisar"]),
  ];
  return cartao(`Para aprovar${itens.length ? ` <span class="etiqueta alerta">${itens.length}</span>` : ""}`, itens.length
    ? `<div class="itens">${itens.map(([alvo, titulo, detalhe]) => item(esc(titulo), detalhe, botao("Abrir", "mk-aba", `data-aba="${alvo}"`, "discreta"))).join("")}</div>`
    : vazio("Nada esperando aprovação."));
};

/** No lugar do trabalho que depende do site, enquanto ele não está configurado. */
const semSite = () => cartao("Site", `${sub("Configure o repositório do site para escrever artigos e mudar o site.")}<div class="linha">${botao("Configurar", "mk-aba", 'data-aba="ajustes"', "principal")}</div>`);

PAGINAS.marketing = async () => {
  try { aba = localStorage.getItem(LEMBRAR) || aba; } catch { /* fica a de agora */ } // a página Ajustes pode ter escolhido
  const [r, fotos, metricas, prs] = await Promise.all([api("marketing"), api("marketing/fotos", {}).catch(() => []), metricasSemTravar(), prsSemTravar()]);
  lembrarLeitura(r);
  const site = r.site.configurado;
  return `${cabeca("Marketing")}${sub("O site, o blog, os vídeos e o Instagram, com o seu sim antes de publicar.")}${abas()}
    ${painel("visao", `${cartaoAprovar(r)}${site ? cartaoMetricas(metricas) : semSite()}`)}
    ${painel("blog", site ? `${cartaoPedir(r)}${cartaoPedidos(r.pedidos)}${cartaoPRs(prs)}${cartaoBlog(r)}` : semSite())}
    ${painel("videos", cartaoVideos(r))}
    ${painel("instagram", `${site ? cartaoInstagram(r) : ""}${cartaoComentarios(r)}`)}
    ${painel("ajustes", abaAjustes(r, fotos))}`;
};

Object.assign(ACOES, {
  "mk-aba": (/** @type {HTMLButtonElement} */ b) => {
    aba = b.dataset.aba || "visao";
    try { localStorage.setItem(LEMBRAR, aba); } catch { /* vale só agora */ }
    for (const t of document.querySelectorAll(".abas [role=tab]")) t.setAttribute("aria-selected", String(/** @type {HTMLElement} */ (t).dataset.aba === aba));
    for (const x of document.querySelectorAll(".painel-aba")) /** @type {HTMLElement} */ (x).hidden = x.id !== `mk-aba-${aba}`;
    if (!b.closest(".abas")) $("conteudo").scrollTo({ top: 0, behavior: "smooth" });
    document.querySelector(`#mk-tab-${aba}`)?.scrollIntoView({ inline: "nearest", block: "nearest" });
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
  "mk-post-criar": async (/** @type {HTMLButtonElement} */ b) => {
    const artigo = /** @type {HTMLSelectElement | null} */ ($("mk-post-artigo"));
    const dados = { tema: /** @type {HTMLInputElement} */ ($("mk-post-tema")).value, artigo: artigo?.value || "" };
    try { const r = await ocupado(b, () => api("marketing/post/criar", dados)); await abrir(); mostrar("mk-resultado-post", true, r.aviso); } catch (erro) { mostrar("mk-resultado-post", false, erro.message); }
  },
  "mk-post-ver": async (/** @type {HTMLButtonElement} */ b) => {
    if (postAberto?.id === b.dataset.id) { postAberto = null; await abrir(); return; }
    try { postAberto = await ocupado(b, () => api("marketing/post", { id: b.dataset.id })); await abrir(); } catch (erro) { mostrar("mk-resultado-post", false, erro.message); }
  },
  "mk-post-publicar": async (/** @type {HTMLButtonElement} */ b) => {
    if (b.dataset.confirmar !== "1") { b.dataset.confirmar = "1"; b.textContent = "Confirmar publicação"; return; }
    try { const r = await ocupado(b, () => api("marketing/post/publicar", { id: b.dataset.id })); postAberto = null; await abrir(); mostrar("mk-resultado-post", true, r.aviso); } catch (erro) { mostrar("mk-resultado-previa", false, erro.message); }
  },
  "mk-post-refazer": async (/** @type {HTMLButtonElement} */ b) => {
    const instrucao = /** @type {HTMLInputElement} */ ($("mk-post-ajuste")).value;
    try { const r = await ocupado(b, () => api("marketing/post/refazer", { id: b.dataset.id, instrucao })); postAberto = null; await abrir(); mostrar("mk-resultado-post", true, r.aviso); } catch (erro) { mostrar("mk-resultado-previa", false, erro.message); }
  },
  "mk-post-descartar": async (/** @type {HTMLButtonElement} */ b) => {
    try { await ocupado(b, () => api("marketing/post/descartar", { id: b.dataset.id })); postAberto = null; await abrir(); } catch (erro) { mostrar("mk-resultado-previa", false, erro.message); }
  },
  "mk-sessao": async (/** @type {HTMLButtonElement} */ b) => {
    location.hash = "#sessoes";
    for (let i = 0; i < 50 && !(carregadas.abrirSessao && document.querySelector(".sessoes")); i++) await new Promise((r) => setTimeout(r, 100));
    await carregadas.abrirSessao?.(b.dataset.id);
  },
});
