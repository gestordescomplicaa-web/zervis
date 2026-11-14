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

// --- Instagram (ADR 0093): o Zé cria o carrossel, você vê e aprova; nada sai sozinho ---

const ESTADOS_POST = { criando: "Criando", rascunho: "Para revisar", publicando: "Publicando", publicado: "Publicado", erro: "Erro" };
const CORES = [["fundo", "Fundo"], ["texto", "Texto"], ["destaque", "Destaque"], ["destaque2", "Destaque 2"]];
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

/** @param {any} m */
const cartaoMarca = (m) => cartao(`Marca <span class="etiqueta">${m.paleta === "propria" ? "Paleta própria" : "Cores do site"}</span>`,
  `${sub(m.declarada ? "As cores dos posts. Por padrão, as que o site declara." : "O site não declara uma marca; vale a paleta padrão até você escolher a sua.")}
  <div class="segmentos" role="group" aria-label="Paleta">${botao("Cores do site", "mk-paleta", `data-paleta="site" aria-pressed="${m.paleta === "site"}"`)}${botao("Paleta própria", "mk-paleta", `data-paleta="propria" aria-pressed="${m.paleta === "propria"}"`)}</div>
  <div class="campos cores-marca">${CORES.map(([chave, nome]) => `<label>${nome}<input type="color" data-cor="${chave}" value="${esc(m.atual[chave] || m.site[chave])}" ${m.paleta === "site" ? "disabled" : ""}></label>`).join("")}</div>
  <div class="linha">${botao("Salvar", "mk-paleta-salvar", "", "principal")}</div>
  <p class="resultado" id="mk-resultado-marca"></p>`);

PAGINAS.marketing = async () => {
  const r = await api("marketing");
  const corpo = r.site.configurado
    ? `${cartaoPedir(r)}${cartaoPedidos(r.pedidos)}${r.site.blog ? cartaoAutomaticos(r) : ""}${cartaoPRs(r.prs)}${cartaoBlog(r)}${cartaoInstagram(r)}${cartaoMarca(r.marca)}${cartaoSite(r.site)}`
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
  "mk-paleta": (/** @type {HTMLButtonElement} */ b) => {
    document.querySelectorAll('[data-acao="mk-paleta"]').forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    document.querySelectorAll(".cores-marca input").forEach((x) => { /** @type {HTMLInputElement} */ (x).disabled = b.dataset.paleta === "site"; });
  },
  "mk-paleta-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const paleta = /** @type {HTMLElement} */ (document.querySelector('[data-acao="mk-paleta"][aria-pressed="true"]')).dataset.paleta;
    /** @type {Record<string, string>} */ const cores = {};
    document.querySelectorAll(".cores-marca input").forEach((x) => { const c = /** @type {HTMLInputElement} */ (x); cores[c.dataset.cor || ""] = c.value; });
    try { await ocupado(b, () => api("marketing/paleta", { paleta, cores })); await abrir(); } catch (erro) { mostrar("mk-resultado-marca", false, erro.message); }
  },
  "mk-sessao": async (/** @type {HTMLButtonElement} */ b) => {
    location.hash = "#sessoes";
    for (let i = 0; i < 50 && !(carregadas.abrirSessao && document.querySelector(".sessoes")); i++) await new Promise((r) => setTimeout(r, 100));
    await carregadas.abrirSessao?.(b.dataset.id);
  },
});
