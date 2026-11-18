import { ACOES } from "../modulos/acoes.js";
import { $, api, botao, cartao, esc, item, mostrar, ocupado, sub } from "../painel.js";

// --- Vídeos (Reels) da marca (ADR 0106): o Zé escreve o roteiro, narra e monta com a marca ---
// O cartão se redesenha sozinho enquanto um vídeo é criado (a etapa muda a cada poucos segundos).

/** @type {string | null} */
let aberto = null;
/** @type {ReturnType<typeof setTimeout> | undefined} */
let vigia;

/** @param {any} v */
const estado = (v) => v.estado === "criando" ? esc(v.etapa || "Na fila")
  : v.estado === "erro" ? `Erro · ${esc(v.erro)}` : `Pronto · ${Math.round(v.duracao)} s`;

/** @param {any} v */
const previa = (v) => `<div class="previa-video">
  <video controls playsinline preload="metadata" poster="/fluxo/marketing/video?id=${esc(v.id)}&qual=capa" src="/fluxo/marketing/video?id=${esc(v.id)}"></video>
  <div class="previa-video-lado">
    ${v.legenda ? `<pre class="legenda-post">${esc(v.legenda)}</pre>` : ""}
    <div class="campos"><label>Ajuste<input id="mk-video-ajuste" placeholder="Ex.: gancho mais curto, sem a cena do número" autocomplete="off"></label></div>
    <div class="linha">${botao("Refazer", "mk-video-refazer", `data-id="${esc(v.id)}"`)}<a class="acao" href="/fluxo/marketing/video?id=${esc(v.id)}" download="${esc((v.titulo || "video").slice(0, 40))}.mp4">Baixar</a>${botao("Descartar", "mk-video-descartar", `data-id="${esc(v.id)}"`, "discreta")}</div>
    <p class="resultado" id="mk-resultado-video-previa"></p>
  </div></div>`;

/** O cartão Vídeos da página Marketing. @param {any} r a leitura "marketing" @param {any} vs */
export function cartaoVideos(r, vs = r.videos) {
  const publicados = (r.artigos || []).filter((/** @type {any} */ a) => a.estado === "Publicado");
  const lista = vs.lista;
  const v = lista.find((/** @type {any} */ x) => x.id === aberto && x.pronto);
  vigiar(lista.some((/** @type {any} */ x) => x.estado === "criando"), r);
  return `<div id="mk-videos">${cartao(`Vídeos <span class="etiqueta">${lista.length} ${lista.length === 1 ? "vídeo" : "vídeos"}</span>`,
    `${sub("Reels explicativos com a sua marca: o Zé escreve o roteiro, narra e monta. Você assiste e decide.")}
    ${vs.indisponivel ? `<p class="nota">Indisponível: ${esc(vs.indisponivel.toLowerCase())}</p>` : ""}
    <div class="campos">
      <label>Tema do vídeo<input id="mk-video-tema" placeholder="Ex.: como o WhatsApp perde clientes à noite" autocomplete="off"></label>
      ${publicados.length ? `<label>Ou a partir de um artigo<select id="mk-video-artigo"><option value="">—</option>${publicados.map((/** @type {any} */ a) => `<option value="${esc(a.slug)}">${esc(a.titulo)}</option>`).join("")}</select></label>` : ""}
      <label>Estilo<select id="mk-video-estilo">${vs.estilos.map((/** @type {any} */ e) => `<option value="${esc(e.id)}" title="${esc(e.descricao)}">${esc(e.nome)}${e.proprio ? " (seu)" : ""}</option>`).join("")}</select></label>
      <label class="interruptor"><input type="checkbox" id="mk-video-voz" checked> Narração</label>
    </div>
    <div class="linha">${botao("Criar vídeo", "mk-video-criar", vs.indisponivel ? "disabled" : "", "principal")}</div>
    <p class="resultado" id="mk-resultado-video"></p>
    ${lista.length ? `<div class="itens">${lista.map((/** @type {any} */ x) => item(esc(x.titulo || x.tema || x.artigo), estado(x),
      x.estado === "criando" ? "" : (x.pronto ? botao(aberto === x.id ? "Fechar" : "Assistir", "mk-video-ver", `data-id="${esc(x.id)}"`, "discreta") : "")
        + botao("Descartar", "mk-video-descartar", `data-id="${esc(x.id)}"`, "discreta"))).join("")}</div>` : ""}
    ${v ? previa(v) : ""}`)}</div>`;
}

/** Redesenha só este cartão (sem recarregar a página, que lê o site e os PRs). @param {any} r */
async function redesenhar(r) {
  const lugar = $("mk-videos");
  if (!lugar) return;
  const vs = await api("marketing/videos");
  const novo = document.createElement("div");
  novo.innerHTML = cartaoVideos(r, vs);
  const tema = /** @type {HTMLInputElement | null} */ ($("mk-video-tema"))?.value || "";
  lugar.replaceWith(/** @type {Element} */ (novo.firstElementChild));
  const campo = /** @type {HTMLInputElement | null} */ ($("mk-video-tema"));
  if (campo) campo.value = tema;
}

/** Enquanto um vídeo é criado, o cartão se atualiza a cada 3 s. @param {boolean} criando @param {any} r */
function vigiar(criando, r) {
  clearTimeout(vigia);
  if (criando) vigia = setTimeout(() => { if ($("mk-videos")) redesenhar(r).catch(() => {}); }, 3000);
}

/** @type {any} */
let ultimaLeitura = { artigos: [] };
/** Guarda a leitura da página para os redesenhos. @param {any} r */
export function lembrarLeitura(r) { ultimaLeitura = r; }

Object.assign(ACOES, {
  "mk-video-criar": async (/** @type {HTMLButtonElement} */ b) => {
    const artigo = /** @type {HTMLSelectElement | null} */ ($("mk-video-artigo"));
    const dados = {
      tema: /** @type {HTMLInputElement} */ ($("mk-video-tema")).value,
      artigo: artigo?.value || "",
      estilo: /** @type {HTMLSelectElement} */ ($("mk-video-estilo")).value,
      voz: /** @type {HTMLInputElement} */ ($("mk-video-voz")).checked,
    };
    try {
      const r = await ocupado(b, () => api("marketing/video/criar", dados));
      /** @type {HTMLInputElement} */ ($("mk-video-tema")).value = "";
      await redesenhar(ultimaLeitura);
      mostrar("mk-resultado-video", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video", false, erro.message); }
  },
  "mk-video-ver": async (/** @type {HTMLButtonElement} */ b) => {
    aberto = aberto === b.dataset.id ? null : b.dataset.id || null;
    await redesenhar(ultimaLeitura);
  },
  "mk-video-refazer": async (/** @type {HTMLButtonElement} */ b) => {
    const instrucao = /** @type {HTMLInputElement} */ ($("mk-video-ajuste")).value;
    try {
      const r = await ocupado(b, () => api("marketing/video/refazer", { id: b.dataset.id, instrucao }));
      aberto = null;
      await redesenhar(ultimaLeitura);
      mostrar("mk-resultado-video", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video-previa", false, erro.message); }
  },
  "mk-video-descartar": async (/** @type {HTMLButtonElement} */ b) => {
    if (b.dataset.confirmar !== "1") { b.dataset.confirmar = "1"; b.textContent = "Confirmar"; return; }
    try {
      await ocupado(b, () => api("marketing/video/descartar", { id: b.dataset.id }));
      if (aberto === b.dataset.id) aberto = null;
      await redesenhar(ultimaLeitura);
    } catch (erro) { mostrar("mk-resultado-video", false, erro.message); }
  },
});
