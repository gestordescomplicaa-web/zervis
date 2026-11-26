import { ACOES } from "../modulos/acoes.js";
import { PAGINAS, $, api, botao, cabeca, cartao, confirmar, esc, item, mostrar, ocupado, sub, toast, vazio } from "../painel.js";

// A prospecção (ADR 0127): o Zé encontra empresas da cidade no Google Maps, identifica quem decide
// pelo quadro de sócios da Receita e envia a primeira mensagem pelo WhatsApp, poucas por dia.
// A página cuida dessa primeira mensagem (ADR 0140): as empresas, por ramo, numa linha cada (nome,
// número e estado); as descartadas, só na contagem. A conversa depois quem usa faz no WhatsApp.
// Nome, avaliações e respostas vêm de terceiros: tudo passa por esc(), e link só https.

/** @type {any} */
let ultimo = null;

const linkSeguro = (/** @type {string} */ url) => /^https:\/\//i.test(String(url || "")) ? esc(url) : "";

/** @param {string} n "5581999887766" -> "(81) 99988-7766" */
function telefone(n) {
  const d = String(n || "").replace(/^55/, "");
  if (d.length < 10) return esc(n);
  const corpo = d.slice(2);
  return `(${d.slice(0, 2)}) ${corpo.slice(0, corpo.length - 4)}-${corpo.slice(-4)}`;
}

/** @param {any} p */
function quem(p) {
  const pessoa = p.dono ? `${esc(p.dono)}${p.cargo ? ` (${esc(p.cargo)})` : ""}` : "Responsável não identificado";
  const numero = (p.telefones || [])[0];
  return [pessoa, esc(p.ramo), numero ? `${telefone(numero.numero)} · ${esc(numero.origem)}` : ""].filter(Boolean).join(" · ");
}

const CLASSES = { enviando: "alerta", respondeu: "bom", reuniao: "bom", sem_interesse: "alerta" };
const CONTATADAS = ["enviando", "enviada", "respondeu", "reuniao", "sem_interesse"];
const plural = (/** @type {number} */ n, /** @type {string} */ um, /** @type {string} */ varios) => `${n} ${n === 1 ? um : varios}`;

/** @param {any} p */
function aguardando(p) {
  const mapa = linkSeguro(p.link) ? ` · <a class="externo" href="${linkSeguro(p.link)}" target="_blank" rel="noopener noreferrer">Ver no Maps ↗</a>` : "";
  return `<div class="campos">
    ${item(`${esc(p.nome)} <span class="etiqueta">Nota ${esc(p.nota)}</span>`, `${quem(p)}${mapa}${p.sinal ? `<br>${esc(p.sinal)}` : ""}`)}
    <label class="largo">Mensagem<textarea id="pr-msg-${esc(p.id)}" rows="5" maxlength="900">${esc(p.mensagem)}</textarea></label>
    <div class="linha">${botao("Aprovar", "pr-aprovar", `data-id="${esc(p.id)}"`, "principal")}${botao("Descartar", "pr-descartar", `data-id="${esc(p.id)}"`, "discreta")}</div>
  </div>`;
}

/** @param {any} p uma linha: o nome, o número e o estado */
function empresa(p) {
  const extra = [p.resposta ? `“${esc(p.resposta)}”` : "", p.erro ? `Envio adiado: ${esc(p.erro)}` : ""].filter(Boolean).join(" · ");
  const descartar = p.status === "fila" ? `<div class="botoes">${botao("Descartar", "pr-descartar", `data-id="${esc(p.id)}"`, "discreta")}</div>` : "";
  return `<div class="linha-item pr-linha">
    <strong class="pr-nome">${esc(p.nome)}</strong>
    <span class="pr-numero">${p.telefone ? telefone(p.telefone) : "Sem número"}</span>
    <span class="etiqueta ${CLASSES[p.status] ?? ""}">${esc(p.rotulo)}</span>${descartar}
    ${extra ? `<small class="pr-extra">${extra}</small>` : ""}
  </div>`;
}

/** @param {any} g o ramo: o total, a contagem por estado e as mais recentes @param {Map<string, boolean>} abertos */
function grupo(g, abertos) {
  const c = g.contagem || {};
  const contatadas = CONTATADAS.reduce((n, s) => n + (c[s] || 0), 0);
  const resumo = [
    contatadas ? plural(contatadas, "contatada", "contatadas") : "",
    c.respondeu ? plural(c.respondeu, "respondeu", "responderam") : "",
    c.fila ? `${c.fila} na fila` : "",
    c.nova ? `${c.nova} qualificando` : "",
  ].filter(Boolean).join(" · ");
  // Fechado por padrão; abre o ramo com resposta nova ou o único. O que a pessoa abriu ou fechou fica.
  const aberto = abertos.get(g.ramo) ?? (Boolean(c.respondeu) || ultimo.grupos.length === 1);
  const resto = g.total - g.empresas.length;
  return `<details class="pr-grupo" data-ramo="${esc(g.ramo)}" ${aberto ? "open" : ""}>
    <summary><span class="seta-escolha"></span><strong>${esc(g.ramo)}</strong><small>${resumo}</small></summary>
    <div class="lista">${g.empresas.map(empresa).join("")}</div>
    ${resto > 0 ? `<p class="vazio pr-resto">${resto === 1 ? "Outra empresa, mais antiga." : `Outras ${resto} empresas, mais antigas.`}</p>` : ""}
  </details>`;
}

/** @param {Map<string, boolean>} abertos */
function empresas(abertos) {
  const r = ultimo;
  const lista = r.grupos.length ? r.grupos.map((/** @type {any} */ g) => grupo(g, abertos)).join("") : vazio("Nenhuma empresa ainda.");
  const descartadas = r.descartadas ? `<p class="vazio pr-descartadas">${plural(r.descartadas, "descartada", "descartadas")}</p>` : "";
  return cartao("Empresas", `${lista}${descartadas}`);
}

function configuracao() {
  const c = ultimo.config;
  return cartao("Configuração", `
  <div class="campos">
    <label>Cidade<input id="pr-cidade" value="${esc(c.cidade)}" maxlength="80" placeholder="Caruaru, PE" autocomplete="off"></label>
    <label>Envios por dia<input id="pr-por-dia" type="number" min="1" max="5" value="${esc(c.por_dia)}"></label>
    <label class="largo">Ramos<textarea id="pr-ramos" rows="4" placeholder="Um por linha: clínica odontológica, imobiliária, autopeças">${esc((c.ramos || []).join("\n"))}</textarea></label>
    <label class="interruptor"><input type="checkbox" id="pr-ligada" ${c.ligada ? "checked" : ""}> Ligada</label>
    <label class="interruptor"><input type="checkbox" id="pr-sozinho" ${c.sozinho ? "checked" : ""}> Enviar sozinho</label>
  </div>
  ${sub(`${esc(ultimo.horario)}, com pelo menos duas horas entre um envio e outro, em horários variados. Sem "Enviar sozinho", cada mensagem espera a sua aprovação.`)}
  <div class="linha">${botao("Salvar", "pr-salvar", "", "principal")}</div>
  <p class="resultado" id="pr-resultado"></p>`);
}

function mensagem() {
  const c = ultimo.config;
  return cartao("Mensagem", `
  <div class="campos">
    <label class="largo">O que você oferece<textarea id="pr-oferta" rows="4" maxlength="1500" placeholder="Em poucas linhas: o que você faz e para quem.">${esc(c.oferta)}</textarea></label>
    <label>Convite<input id="pr-convite" value="${esc(c.convite)}" maxlength="120" placeholder="um diagnóstico gratuito de 20 minutos" autocomplete="off"></label>
    <label>Vagas<input id="pr-vagas" value="${esc(c.vagas)}" maxlength="120" placeholder="Opcional: 5 diagnósticos por mês" autocomplete="off"></label>
    <label class="largo">Link de agendamento<input id="pr-link" value="${esc(c.link)}" maxlength="300" placeholder="https://calendar.app.google/..." autocomplete="off"></label>
    <label class="interruptor"><input type="checkbox" id="pr-link-na-mensagem" ${c.link_na_mensagem ? "checked" : ""}> Link na primeira mensagem</label>
  </div>
  ${sub("Quem você é e o que faz, por que a empresa foi escolhida, o convite e o horário. Ao salvar, as mensagens que ainda não saíram são reescritas.")}
  <div class="linha">${botao("Salvar", "pr-salvar", 'data-resultado="pr-resultado-mensagem"', "principal")}</div>
  <p class="resultado" id="pr-resultado-mensagem"></p>`);
}

function fontes() {
  const tem = ultimo.apify;
  return cartao("Fontes", `
  <div class="campos">
    <label>Google Maps (Apify) <span class="etiqueta ${tem ? "bom" : ""}">${tem ? "Configurado" : "Não configurado"}</span><input id="pr-apify" type="password" placeholder="${tem ? "Salva" : "Chave de API"}" autocomplete="off"></label>
  </div>
  <div class="linha">${botao("Salvar", "pr-apify", "", "discreta")}${tem ? botao("Remover", "pr-apify-remover", "", "discreta") : ""}<a class="acao discreta" href="${linkSeguro(ultimo.obter_chave)}" target="_blank" rel="noopener noreferrer">Obter chave de API</a></div>
  <p class="resultado" id="pr-resultado-apify"></p>
  <div class="add"><input id="pr-cnpj" placeholder="Adicionar empresa pelo CNPJ" maxlength="20" autocomplete="off">${botao("Adicionar", "pr-adicionar")}</div>
  <p class="resultado" id="pr-resultado-cnpj"></p>`);
}

function desenhar() {
  const lugar = $("prospeccao");
  if (!lugar) return;
  /** @type {Map<string, boolean>} */
  const abertos = new Map();
  lugar.querySelectorAll("details.pr-grupo").forEach((d) => abertos.set(/** @type {HTMLElement} */ (d).dataset.ramo || "", /** @type {HTMLDetailsElement} */ (d).open));
  lugar.innerHTML = corpo(abertos);
}

function corpo(abertos = new Map()) {
  const r = ultimo;
  const estado = r.config.ligada ? `<span class="etiqueta bom">Ligada</span>` : `<span class="etiqueta">Desligada</span>`;
  const resumo = [
    `Enviadas hoje: ${esc(r.hoje.enviadas)} de ${esc(r.hoje.limite)}`,
    r.proximo ? `Próximo envio: ${esc(r.proximo)}` : "",
    r.ocupado ? "Buscando empresas…" : "",
    r.erro ? `Última busca: ${esc(r.erro)}` : "",
  ].filter(Boolean).join(" · ");
  const fila = r.aguardando.length
    ? cartao(`Aguardando aprovação <span class="etiqueta">${r.aguardando.length}</span>`, r.aguardando.map(aguardando).join(""))
    : "";
  return `${cartao("", item(`Prospecção ${estado}`, resumo))}${fila}${empresas(abertos)}${configuracao()}${mensagem()}${fontes()}`;
}

PAGINAS.prospeccao = async () => {
  ultimo = await api("prospeccao");
  return `${cabeca("Prospecção", botao("Buscar empresas", "pr-buscar", "", "principal"))}${sub("Empresas da sua cidade, quem decide em cada uma e a primeira mensagem pelo WhatsApp.")}<div id="prospeccao" class="secao">${corpo()}</div>`;
};

/** @param {string} caminho @param {any} dados @param {HTMLButtonElement} b @param {string} resultado */
async function enviar(caminho, dados, b, resultado) {
  try {
    ultimo = await ocupado(b, () => api(caminho, dados));
    desenhar();
    if (ultimo.aviso) (resultado && $(resultado) ? mostrar(resultado, true, ultimo.aviso) : toast(ultimo.aviso));
  } catch (erro) {
    if (resultado && $(resultado)) mostrar(resultado, false, erro.message); else toast(erro.message);
  }
}

Object.assign(ACOES, {
  "pr-salvar": (/** @type {HTMLButtonElement} */ b) => enviar("prospeccao/salvar", {
    cidade: /** @type {HTMLInputElement} */ ($("pr-cidade")).value,
    por_dia: Number(/** @type {HTMLInputElement} */ ($("pr-por-dia")).value),
    ramos: /** @type {HTMLTextAreaElement} */ ($("pr-ramos")).value,
    oferta: /** @type {HTMLTextAreaElement} */ ($("pr-oferta")).value,
    convite: /** @type {HTMLInputElement} */ ($("pr-convite")).value,
    vagas: /** @type {HTMLInputElement} */ ($("pr-vagas")).value,
    link: /** @type {HTMLInputElement} */ ($("pr-link")).value,
    link_na_mensagem: /** @type {HTMLInputElement} */ ($("pr-link-na-mensagem")).checked,
    ligada: /** @type {HTMLInputElement} */ ($("pr-ligada")).checked,
    sozinho: /** @type {HTMLInputElement} */ ($("pr-sozinho")).checked,
  }, b, b.dataset.resultado || "pr-resultado"),
  "pr-apify": (/** @type {HTMLButtonElement} */ b) => enviar("prospeccao/apify", { chave: /** @type {HTMLInputElement} */ ($("pr-apify")).value }, b, "pr-resultado-apify"),
  "pr-apify-remover": (/** @type {HTMLButtonElement} */ b) => confirmar(b, "Remover a chave?", () => enviar("prospeccao/apify", { chave: "" }, b, "pr-resultado-apify")),
  "pr-adicionar": (/** @type {HTMLButtonElement} */ b) => enviar("prospeccao/adicionar", { cnpj: /** @type {HTMLInputElement} */ ($("pr-cnpj")).value }, b, "pr-resultado-cnpj"),
  "pr-buscar": (/** @type {HTMLButtonElement} */ b) => enviar("prospeccao/buscar", {}, b, ""),
  "pr-aprovar": (/** @type {HTMLButtonElement} */ b) => {
    const id = b.dataset.id || "";
    const texto = /** @type {HTMLTextAreaElement | null} */ ($(`pr-msg-${id}`))?.value || "";
    return enviar("prospeccao/aprovar", { id, texto }, b, "");
  },
  "pr-descartar": (/** @type {HTMLButtonElement} */ b) => confirmar(b, "Descartar esta empresa?", () => enviar("prospeccao/descartar", { id: b.dataset.id }, b, "")),
});
