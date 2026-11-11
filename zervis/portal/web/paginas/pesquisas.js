import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { PAGINAS, api, botao, cabeca, cartao, confirmar, esc, item, quando, sub, toast, vazio } from "../painel.js";

// A página Pesquisas, carregada sob demanda: cada pesquisa que o Zé fez (a profunda e a
// resumida), guardada com as fontes e os trechos lidos (zervis/pesquisa/guardadas.py, ADR 0060).
// O que veio das páginas é texto de terceiros: tudo passa por esc(), e link só http(s).

let pesquisaAberta = "";
let buscaPesquisas = "";

const linkSeguro = (url) => /^https?:\/\//i.test(String(url || "")) ? esc(url) : "";
const dataPesquisa = (em) => (em ? quando(new Date(em * 1000).toISOString()) : "");

/** @param {any} f */
function fontePesquisa(f) {
  const href = linkSeguro(f.url);
  const titulo = esc(f.titulo || f.site || f.url);
  const cabecalho = href ? `<a class="externo" href="${href}" target="_blank" rel="noopener noreferrer">${titulo} ↗</a>` : titulo;
  const meta = [f.site, f.data].filter(Boolean).map(esc).join(" · ");
  const trechos = (f.trechos || []).map((t) => `<blockquote class="trecho">${esc(t)}</blockquote>`).join("");
  return `<div class="fonte-pesquisa"><h3 class="titulo-fonte">${f.n ? `${f.n}. ` : ""}${cabecalho}</h3>${meta ? `<p class="nota">${meta}</p>` : ""}${trechos}</div>`;
}

async function pesquisaDetalhe() {
  const p = await api("pesquisas/ler", { id: pesquisaAberta });
  const voltar = botao("← Todas", "pesquisas-voltar", "", "discreta");
  const apagar = botao("Apagar", "pesquisas-apagar", `data-id="${esc(p.id)}"`, "perigo");
  const consultas = (p.consultas || []).length ? `<br><small>Buscado como: ${(p.consultas || []).map(esc).join(" · ")}</small>` : "";
  const resumo = p.resumo ? cartao("Resumo", `<p class="quebra">${esc(p.resumo).replace(/(https?:\/\/[^\s<]+)/g, (u) => `<a class="externo" href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`)}</p>`) : "";
  const fontes = (p.fontes || []).length ? cartao(`Fontes lidas <span class="etiqueta">${p.fontes.length}</span>`, p.fontes.map(fontePesquisa).join("")) : "";
  const outros = (p.outros_resultados || []).filter((o) => linkSeguro(o.url));
  const mais = outros.length ? cartao("", `<details class="detalhes"><summary>Outros resultados da busca (${outros.length})</summary><div class="itens">${outros.map((o) =>
    item(`<a class="externo" href="${linkSeguro(o.url)}" target="_blank" rel="noopener noreferrer">${esc(o.titulo || o.url)} ↗</a>`, esc(o.trecho))).join("")}</div></details>`) : "";
  const tipo = p.tipo === "resumida" ? "Pesquisa resumida" : "Pesquisa profunda";
  return `${cabeca(esc(p.pergunta), `<div class="botoes">${voltar}${apagar}</div>`)}${sub(`${tipo} · ${dataPesquisa(p.em)}${consultas}`)}${resumo}${fontes}${mais}`;
}

PAGINAS.pesquisas = async () => {
  if (pesquisaAberta) {
    try { return await pesquisaDetalhe(); } catch { pesquisaAberta = ""; } // apagada: volta à lista
  }
  const r = buscaPesquisas ? await api("pesquisas/buscar", { busca: buscaPesquisas }) : await api("pesquisas");
  const lista = r.pesquisas.map((p) => {
    const sites = (p.sites || []).map(esc).join(", ");
    const detalhe = [dataPesquisa(p.em), p.tipo === "resumida" ? "resumida" : `${p.fontes} fontes`, sites].filter(Boolean).join(" · ");
    return item(esc(p.pergunta), detalhe, botao("Abrir", "pesquisas-abrir", `data-id="${esc(p.id)}"`));
  }).join("");
  const busca = `<div class="add"><input data-nova="pesquisas" id="busca-pesquisas" type="search" placeholder="Buscar nas pesquisas: embalagens, concorrentes…" value="${esc(buscaPesquisas)}" autocomplete="off">${botao("Buscar", "pesquisas-buscar")}</div>`;
  const vazia = buscaPesquisas ? vazio("Nenhuma pesquisa fala disso.") : vazio('Nenhuma pesquisa ainda. Peça ao Zé: "pesquisa a fundo os concorrentes da loja X".');
  return `${cabeca("Pesquisas")}${sub("Tudo o que o Zé pesquisou, com as fontes. Pela voz: \"o que achamos sobre…?\".")}
    ${cartao("", `${busca}${buscaPesquisas ? `<p class="nota">${r.pesquisas.length} encontrada(s) · ${botao("Limpar", "pesquisas-limpar", "", "discreta")}</p>` : ""}<div class="itens">${lista || vazia}</div>`)}`;
};

Object.assign(ACOES, {
  "pesquisas-abrir": async (b) => { pesquisaAberta = b.dataset.id || ""; await abrir(); window.scrollTo(0, 0); },
  "pesquisas-voltar": async () => { pesquisaAberta = ""; await abrir(); },
  "pesquisas-buscar": async () => {
    buscaPesquisas = /** @type {HTMLInputElement} */ (document.getElementById("busca-pesquisas")).value.trim();
    await abrir();
  },
  "pesquisas-limpar": async () => { buscaPesquisas = ""; await abrir(); },
  "pesquisas-apagar": (b) => confirmar(b, "Apagar esta pesquisa?", async () => {
    await api("pesquisas/apagar", { id: b.dataset.id });
    pesquisaAberta = "";
    toast("Pesquisa apagada.");
    await abrir();
  }),
});
