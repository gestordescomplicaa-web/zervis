import { ACOES, MUDAR } from "../modulos/acoes.js";
import { $, api, botao, cartao, esc, item, mostrar, ocupado, sub } from "../painel.js";

// --- Vídeos (Reels) da marca (ADR 0106): o Zé escreve o roteiro, narra e monta com a marca ---
// O cartão se redesenha sozinho enquanto um vídeo é criado (a etapa muda a cada poucos segundos).

/** @type {string | null} */
let aberto = null;
/** @type {ReturnType<typeof setTimeout> | undefined} */
let vigia;

/** @param {any} v */
const estado = (v) => v.estado === "criando" ? esc(v.etapa || "Na fila")
  : v.estado === "erro" ? `Erro · ${esc(v.erro)}`
  : v.estado === "publicando" ? "Publicando no Instagram"
  : v.estado === "publicado" ? `Publicado · ${Math.round(v.duracao)} s`
  : `Pronto · ${Math.round(v.duracao)} s${v.erro ? ` · ${esc(v.erro)}` : ""}`;

/** O botão de publicar, ou o motivo de não poder. @param {any} v @param {any} vs */
const publicar = (v, vs) => v.estado === "publicado"
  ? (v.permalink ? `<a class="acao principal" href="${esc(v.permalink)}" target="_blank" rel="noopener">Ver no Instagram</a>` : "")
  : v.estado !== "rascunho" ? ""
  : !vs.instagram ? `<p class="nota">Conecte o Instagram em Redes sociais para publicar.</p>`
  : !vs.publicavel ? `<p class="nota">Publicar exige o acesso de qualquer lugar com endereço fixo.</p>`
  : botao("Publicar no Instagram", "mk-video-publicar", `data-id="${esc(v.id)}"`, "principal");

/** @param {any} v @param {any} vs */
const previa = (v, vs) => `<div class="previa-video">
  <video controls playsinline preload="none" poster="/fluxo/marketing/video?id=${esc(v.id)}&qual=capa" src="/fluxo/marketing/video?id=${esc(v.id)}"></video>
  <div class="previa-video-lado">
    ${v.palavra ? `<p class="nota">Comentário: <strong>${esc(v.palavra)}</strong>${v.entrega ? ` · Entrega: ${esc(v.entrega)}` : ""}</p>` : ""}
    ${v.legenda ? `<pre class="legenda-post">${esc(v.legenda)}</pre>` : ""}
    <div class="campos"><label>Ajuste<input id="mk-video-ajuste" placeholder="Ex.: gancho mais curto, sem a cena do número" autocomplete="off"></label></div>
    <div class="linha">${publicar(v, vs)}${v.estado === "publicado" ? "" : botao("Refazer", "mk-video-refazer", `data-id="${esc(v.id)}"`)}<a class="acao" href="/fluxo/marketing/video?id=${esc(v.id)}" download="${esc((v.titulo || "video").slice(0, 40))}.mp4">Baixar</a>${botao("Descartar", "mk-video-descartar", `data-id="${esc(v.id)}"`, "discreta")}</div>
    <p class="resultado" id="mk-resultado-video-previa"></p>
  </div></div>`;

/** A paleta dos vídeos: a da marca ou a tirada de um site, com as amostras. @param {any} vs */
const paleta = (vs) => {
  const p = vs.paleta || { origem: "marca" };
  const amostras = p.origem === "site" ? `<span class="amostras">${["fundo", "texto", "destaque", "destaque2"].map((k) => `<i style="background:${esc(p.cores[k])}" title="${k}"></i>`).join("")}</span>` : "";
  return `<div class="campos">
      <label>Paleta<input id="mk-video-paleta" placeholder="Endereço de um site. Ex.: nubank.com.br" value="${esc(p.url || "")}" autocomplete="off"></label>
    </div>
    <div class="linha">${botao("Usar cores do site", "mk-video-paleta", "", "discreta")}${p.origem === "site" ? botao("Usar cores da marca", "mk-video-paleta-marca", "", "discreta") : ""}<span class="nota">${p.origem === "site" ? `Cores de ${esc(p.url)}` : "Cores da marca"}</span>${amostras}</div>
    <p class="resultado" id="mk-resultado-video-paleta"></p>`;
};

/** As fotos do Pixabay (ADR 0124): a chave de quem usa. @param {any} vs */
const fotosLivres = (vs) => `<div class="campos">
      <label>Fotos do Pixabay <span class="etiqueta ${vs.pixabay ? "bom" : ""}">${vs.pixabay ? "Configurado" : "Não configurado"}</span><input id="mk-video-pixabay" type="password" placeholder="${vs.pixabay ? "Salva" : "Chave de API"}" autocomplete="off"></label>
    </div>
    <div class="linha">${botao("Salvar", "mk-video-pixabay", "", "discreta")}${vs.pixabay ? botao("Remover", "mk-video-pixabay-remover", "", "discreta") : ""}<a class="acao discreta" href="https://pixabay.com/api/docs/" target="_blank" rel="noopener">Obter chave de API</a></div>
    <p class="resultado" id="mk-resultado-video-pixabay"></p>`;

/** O cartão Vídeos da página Marketing. @param {any} r a leitura "marketing" @param {any} vs */
export function cartaoVideos(r, vs = r.videos) {
  // as escolhas guardadas no Zé (lembradas ao voltar à aba); sem elas, os padrões
  const pr = vs.preferencias || { linha: "", duracao: 30, modelo: "", estilo: "", voz: true, locutor: vs.locutor || "" };
  const publicados = (r.artigos || []).filter((/** @type {any} */ a) => a.estado === "Publicado");
  const lista = vs.lista;
  const v = lista.find((/** @type {any} */ x) => x.id === aberto && x.pronto);
  vigiar(lista.some((/** @type {any} */ x) => x.estado === "criando" || x.estado === "publicando"), r);
  return `<div id="mk-videos">${cartao(`Vídeos <span class="etiqueta">${lista.length} ${lista.length === 1 ? "vídeo" : "vídeos"}</span>`,
    `${sub("Reels explicativos com a sua marca: o Zé escreve o roteiro, narra e monta. Você assiste e decide.")}
    ${vs.indisponivel ? `<p class="nota">Indisponível: ${esc(vs.indisponivel.toLowerCase())}</p>` : ""}
    <div class="campos">
      <label>Tema do vídeo<input id="mk-video-tema" placeholder="Ex.: como o WhatsApp perde clientes à noite" autocomplete="off"></label>
      ${publicados.length ? `<label>Ou a partir de um artigo<select id="mk-video-artigo"><option value="">—</option>${publicados.map((/** @type {any} */ a) => `<option value="${esc(a.slug)}">${esc(a.titulo)}</option>`).join("")}</select></label>` : ""}
      <label>Para quem<select id="mk-video-linha" data-mudar="video-preferencia">${[["", "O Zé escolhe pelo tema"], ["empresarios", "Empresários"], ["ferramenta", "Ferramenta"]].map(([v, n]) => `<option value="${v}" ${v === pr.linha ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      <label>Entrega<input id="mk-video-entrega" placeholder="Opcional. Sem ela: uma conversa no direct sobre o negócio da pessoa" autocomplete="off"></label>
      <label>Palavra<input id="mk-video-palavra" placeholder="Ex.: COBRANÇA" maxlength="16" autocomplete="off"></label>
      <label>Duração<select id="mk-video-duracao" data-mudar="video-preferencia">${(vs.duracoes || [30]).map((/** @type {number} */ d) => `<option value="${d}" ${d === pr.duracao ? "selected" : ""}>${d} s</option>`).join("")}</select></label>
      <label>Diretor<select id="mk-video-modelo" data-mudar="video-preferencia">${(vs.modelos || []).map((/** @type {any} */ m) => `<option value="${esc(m.id)}" ${m.id === pr.modelo ? "selected" : ""}>${esc(m.nome)}</option>`).join("")}</select></label>
      <label>Estilo<select id="mk-video-estilo" data-mudar="video-preferencia">${vs.estilos.map((/** @type {any} */ e) => `<option value="${esc(e.id)}" title="${esc(e.descricao)}" ${e.id === pr.estilo ? "selected" : ""}>${esc(e.nome)}${e.proprio ? " (seu)" : ""}</option>`).join("")}</select></label>
      <label>Voz<select id="mk-video-locutor" data-mudar="video-preferencia">${(vs.vozes || []).map((/** @type {any} */ x) => `<option value="${esc(x.id)}" ${x.id === (pr.locutor || "") ? "selected" : ""}>${esc(x.nome)}${x.detalhe ? ` · ${esc(x.detalhe)}` : ""}</option>`).join("")}</select></label>
      <label>Qualidade da voz<select id="mk-video-modelo-voz" data-mudar="video-preferencia">${(vs.modelos_voz || []).map((/** @type {any} */ m) => `<option value="${esc(m.id)}" ${m.id === (pr.modelo_voz || "") ? "selected" : ""}>${esc(m.nome)}</option>`).join("")}</select></label>
      <label class="interruptor"><input type="checkbox" id="mk-video-voz" data-mudar="video-preferencia" ${pr.voz ? "checked" : ""}> Narração</label>
    </div>
    ${paleta(vs)}
    ${fotosLivres(vs)}
    <div class="linha">${botao("Criar vídeo", "mk-video-criar", vs.indisponivel ? "disabled" : "", "principal")}</div>
    <p class="resultado" id="mk-resultado-video"></p>
    ${lista.length ? `<div class="itens">${lista.map((/** @type {any} */ x) => item(esc(x.titulo || x.tema || x.artigo), estado(x),
      ["criando", "publicando"].includes(x.estado) ? "" : (x.pronto ? botao(aberto === x.id ? "Fechar" : "Assistir", "mk-video-ver", `data-id="${esc(x.id)}"`, "discreta") : "")
        + botao("Descartar", "mk-video-descartar", `data-id="${esc(x.id)}"`, "discreta"))).join("")}</div>` : ""}
    ${v ? previa(v, vs) : ""}`)}</div>`;
}

const AGENDAS = [
  ["cron 0 9 * * 1,4", "Segunda e quinta, 9h"],
  ["cron 0 9 * * 1,3,5", "Segunda, quarta e sexta, 9h"],
  ["cron 0 9 * * 1", "Toda segunda, 9h"],
  ["cron 0 10 * * 2,5", "Terça e sexta, 10h"],
  ["cron 0 9 * * 1-5", "Todo dia útil, 9h"],
];
/** @param {string} agenda */
const nomeAgenda = (agenda) => (AGENDAS.find(([v]) => v === agenda) || [agenda, agenda])[1];

/** O cartão Vídeos automáticos (ADR 0111). @param {any} r a leitura "marketing" */
export function cartaoVideosAutomaticos(r) {
  const jobs = r.videos_automaticos || [];
  const ativo = jobs.some((/** @type {any} */ j) => j.ativo);
  return `<div id="mk-videos-auto">${cartao(`Vídeos automáticos <span class="etiqueta ${ativo ? "bom" : ""}">${ativo ? "Ativo" : "Desligado"}</span>`,
    `${sub("O Zé cria os vídeos na agenda; publica com a sua aprovação ou sozinho, se marcado.")}
    ${jobs.length ? `<div class="itens">${jobs.map((/** @type {any} */ j) => item(esc(nomeAgenda(j.agenda)),
      `${j.ativo ? `Próximo: ${esc(String(j.proxima).slice(0, 16).replace("T", " "))}` : "Pausado"} · ${j.temas ? `${j.temas} ${j.temas === 1 ? "tema" : "temas"}` : "Tema pelo site"} · ${esc(String(j.duracao || 30))} s${j.publicar ? " · Publica sozinho" : ""}`, "")).join("")}</div>` : ""}
    <div class="campos">
      <label>Quando<select id="mk-video-agenda">${AGENDAS.map(([v, n]) => `<option value="${v}">${n}</option>`).join("")}</select></label>
      <label>Duração<select id="mk-video-agenda-duracao">${((r.videos && r.videos.duracoes) || [30]).map((/** @type {number} */ d) => `<option value="${d}" ${d === 30 ? "selected" : ""}>${d} s</option>`).join("")}</select></label>
      <label class="largo">Temas<textarea id="mk-video-temas" rows="4" placeholder="Um por linha. Opcional: sem temas, o Zé escolhe pelo site e pelos artigos."></textarea></label>
      <label class="interruptor"><input type="checkbox" id="mk-video-sozinho"> Publicar sozinho</label>
    </div>
    <div class="linha">${botao("Agendar", "mk-video-agendar", r.videos && r.videos.indisponivel ? "disabled" : "", jobs.length ? "discreta" : "principal")}<a class="acao discreta" href="#automacoes">Automações</a></div>
    <p class="resultado" id="mk-resultado-video-agenda"></p>`)}</div>`;
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
      duracao: Number(/** @type {HTMLSelectElement} */ ($("mk-video-duracao")).value),
      modelo: /** @type {HTMLSelectElement} */ ($("mk-video-modelo")).value,
      locutor: /** @type {HTMLSelectElement | null} */ ($("mk-video-locutor"))?.value || "",
      modelo_voz: /** @type {HTMLSelectElement | null} */ ($("mk-video-modelo-voz"))?.value || "",
      linha: /** @type {HTMLSelectElement} */ ($("mk-video-linha")).value,
      entrega: /** @type {HTMLInputElement} */ ($("mk-video-entrega")).value,
      palavra: /** @type {HTMLInputElement} */ ($("mk-video-palavra")).value,
    };
    try {
      const r = await ocupado(b, () => api("marketing/video/criar", dados));
      /** @type {HTMLInputElement} */ ($("mk-video-tema")).value = "";
      await redesenhar(ultimaLeitura);
      mostrar("mk-resultado-video", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video", false, erro.message); }
  },
  "mk-video-paleta": async (/** @type {HTMLButtonElement} */ b) => {
    const url = /** @type {HTMLInputElement} */ ($("mk-video-paleta")).value;
    try {
      const r = await ocupado(b, () => api("marketing/video/paleta", { url }));
      await redesenhar(ultimaLeitura);
      mostrar("mk-resultado-video-paleta", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video-paleta", false, erro.message); }
  },
  "mk-video-pixabay": async (/** @type {HTMLButtonElement} */ b) => {
    const chave = /** @type {HTMLInputElement} */ ($("mk-video-pixabay")).value;
    try {
      const r = await ocupado(b, () => api("marketing/video/pixabay", { chave }));
      await redesenhar(ultimaLeitura);
      mostrar("mk-resultado-video-pixabay", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video-pixabay", false, erro.message); }
  },
  "mk-video-pixabay-remover": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/video/pixabay", { chave: "" }));
      await redesenhar(ultimaLeitura);
      mostrar("mk-resultado-video-pixabay", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video-pixabay", false, erro.message); }
  },
  "mk-video-paleta-marca": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      const r = await ocupado(b, () => api("marketing/video/paleta", { origem: "marca" }));
      await redesenhar(ultimaLeitura);
      mostrar("mk-resultado-video-paleta", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video-paleta", false, erro.message); }
  },
  "mk-video-agendar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = {
      quando: /** @type {HTMLSelectElement} */ ($("mk-video-agenda")).value,
      duracao: Number(/** @type {HTMLSelectElement} */ ($("mk-video-agenda-duracao")).value),
      temas: /** @type {HTMLTextAreaElement} */ ($("mk-video-temas")).value,
      publicar: /** @type {HTMLInputElement} */ ($("mk-video-sozinho")).checked,
    };
    try {
      const r = await ocupado(b, () => api("marketing/video/agendar", dados));
      ultimaLeitura = r;
      const novo = document.createElement("div");
      novo.innerHTML = cartaoVideosAutomaticos(r);
      $("mk-videos-auto")?.replaceWith(/** @type {Element} */ (novo.firstElementChild));
      mostrar("mk-resultado-video-agenda", true, r.aviso);
    } catch (erro) { mostrar("mk-resultado-video-agenda", false, erro.message); }
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
  "mk-video-publicar": async (/** @type {HTMLButtonElement} */ b) => {
    if (b.dataset.confirmar !== "1") { b.dataset.confirmar = "1"; b.textContent = "Confirmar publicação"; return; }
    try {
      const r = await ocupado(b, () => api("marketing/video/publicar", { id: b.dataset.id }));
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

/** Cada escolha do cartão Vídeos fica guardada no Zé assim que muda. */
Object.assign(MUDAR, {
  "video-preferencia": async () => {
    const campo = (/** @type {string} */ id) => /** @type {HTMLSelectElement | null} */ ($(id));
    await api("marketing/video/preferencias", {
      linha: campo("mk-video-linha")?.value ?? "",
      duracao: Number(campo("mk-video-duracao")?.value || 30),
      modelo: campo("mk-video-modelo")?.value ?? "",
      estilo: campo("mk-video-estilo")?.value ?? "",
      locutor: campo("mk-video-locutor")?.value ?? "",
      modelo_voz: campo("mk-video-modelo-voz")?.value ?? "",
      voz: /** @type {HTMLInputElement | null} */ ($("mk-video-voz"))?.checked ?? true,
    });
  },
});
