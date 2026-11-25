import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { TOKEN, $, api, botao, cartao, esc, mostrar, ocupado, sub, xis } from "../painel.js";
import { ajustesInstagram, chaveAvisos } from "./marketing-direct.js";
import { ajustesVideos, chavePixabay } from "./marketing-videos.js";

// A aba Ajustes do Marketing (ADR 0134): o que se configura uma vez, separado por assunto, fora
// dos cartões de trabalho. Cada ajuste continua pedindo ao Zé o mesmo de antes.

/** @param {any} s */
const cartaoSite = (s) => cartao(`Site <span class="etiqueta ${s.configurado && s.blog ? "bom" : s.configurado ? "alerta" : ""}">${esc(s.estado)}</span>`,
  `${sub("O repositório do site no GitHub. Os pedidos partem da branch base e voltam como PR.")}
  <div class="campos">
    <label>Pasta do site<input id="mk-pasta" class="mono" value="${esc(s.pasta)}" placeholder="~/projetos/meu-site" spellcheck="false"></label>
    <label>Branch base<input id="mk-base" class="mono" value="${esc(s.base)}" placeholder="main" spellcheck="false"></label>
  </div>
  <div class="linha">${botao("Salvar", "mk-salvar", "", "principal")}</div>
  <p class="resultado" id="mk-resultado-site"></p>`);

const CORES = [["fundo", "Fundo"], ["texto", "Texto"], ["destaque", "Destaque"], ["destaque2", "Destaque 2"]];
/** @param {any} m */
const cartaoMarca = (m) => cartao(`Marca <span class="etiqueta">${m.paleta === "propria" ? "Paleta própria" : "Cores do site"}</span>`,
  `${sub(m.declarada ? "As cores dos posts. Por padrão, as que o site declara." : "O site não declara uma marca; vale a paleta padrão até você escolher a sua.")}
  <div class="segmentos" role="group" aria-label="Paleta">${botao("Cores do site", "mk-paleta", `data-paleta="site" aria-pressed="${m.paleta === "site"}"`)}${botao("Paleta própria", "mk-paleta", `data-paleta="propria" aria-pressed="${m.paleta === "propria"}"`)}</div>
  <div class="campos cores-marca">${CORES.map(([chave, nome]) => `<label>${nome}<input type="color" data-cor="${chave}" value="${esc(m.atual[chave] || m.site[chave])}" ${m.paleta === "site" ? "disabled" : ""}></label>`).join("")}</div>
  <div class="linha">${botao("Salvar", "mk-paleta-salvar", "", "principal")}</div>
  <p class="resultado" id="mk-resultado-marca"></p>`);

/** @param {any[]} fotos */
const cartaoFotos = (fotos) => cartao(`Fotos da marca <span class="etiqueta">${fotos.length} ${fotos.length === 1 ? "foto" : "fotos"}</span>`,
  `${sub("Fotos suas e do seu trabalho. O nome do arquivo descreve a foto: é por ele que o Zé escolhe a capa do post.")}
  ${fotos.length ? `<div class="fotos-marca">${fotos.map((f) => `<figure><img src="${f.miniatura}" alt="${esc(f.nome)}"><figcaption>${esc(f.nome)}</figcaption>${xis("mk-foto-remover", `data-nome="${esc(f.nome)}"`, "Remover")}</figure>`).join("")}</div>` : ""}
  <input type="file" id="mk-fotos" accept="image/*" multiple hidden>
  <div class="linha">${botao("Enviar fotos", "mk-fotos-escolher", "", fotos.length ? "discreta" : "principal")}</div>
  <p class="resultado" id="mk-resultado-fotos"></p>`);

/** @param {File} arquivo */
async function subirFoto(arquivo) {
  const r = await fetch(`/api/marketing/foto?nome=${encodeURIComponent(arquivo.name)}`,
    { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: arquivo });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`${arquivo.name}: ${dados.erro || "falha"}`);
}

const SECOES = [["site", "Site e blog"], ["videos", "Vídeos"], ["instagram", "Instagram"], ["marca", "Marca"], ["chaves", "Chaves e contas"]];

/** A aba Ajustes inteira. @param {any} r a leitura "marketing" @param {any[]} fotos */
export function abaAjustes(r, fotos) {
  const secoes = SECOES.filter(([id]) => id !== "marca" || r.site.configurado);
  return `<div class="linha indice" role="group" aria-label="Assuntos">${secoes.map(([id, nome]) => botao(nome, "mk-ir", `data-alvo="mk-ajuste-${id}"`, "discreta")).join("")}</div>
    <div id="mk-ajuste-site">${cartaoSite(r.site)}</div>
    <div id="mk-ajuste-videos">${ajustesVideos(r.videos)}</div>
    <div id="mk-ajuste-instagram">${ajustesInstagram(r)}</div>
    ${r.site.configurado ? `<div id="mk-ajuste-marca" class="grupo-ajuste">${cartaoMarca(r.marca)}${cartaoFotos(fotos)}</div>` : ""}
    <div id="mk-ajuste-chaves">${cartao("Chaves e contas", `${sub("As chaves de outros serviços que o Marketing usa.")}${chavePixabay(r.videos)}${chaveAvisos(r)}`)}</div>`;
}

Object.assign(ACOES, {
  "mk-ir": (/** @type {HTMLButtonElement} */ b) => $(b.dataset.alvo || "")?.scrollIntoView({ behavior: "smooth", block: "start" }),
  "mk-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { pasta: /** @type {HTMLInputElement} */ ($("mk-pasta")).value, base: /** @type {HTMLInputElement} */ ($("mk-base")).value };
    try { await ocupado(b, () => api("marketing/site", dados)); await abrir(); } catch (erro) { mostrar("mk-resultado-site", false, erro.message); }
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
  "mk-fotos-escolher": () => {
    const campo = /** @type {HTMLInputElement} */ ($("mk-fotos"));
    campo.onchange = async () => {
      const lista = Array.from(campo.files || []);
      for (const arquivo of lista) {
        if (arquivo.size > 20 * 1024 * 1024) { mostrar("mk-resultado-fotos", false, `${arquivo.name}: maior que 20 MB.`); continue; }
        try { await subirFoto(arquivo); } catch (erro) { mostrar("mk-resultado-fotos", false, erro.message); return; }
      }
      await abrir();
    };
    campo.click();
  },
  "mk-foto-remover": async (/** @type {HTMLButtonElement} */ b) => {
    try { await api("marketing/foto/remover", { nome: b.dataset.nome }); await abrir(); } catch (erro) { mostrar("mk-resultado-fotos", false, erro.message); }
  },
});
