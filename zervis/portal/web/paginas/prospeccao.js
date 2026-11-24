import { ACOES } from "../modulos/acoes.js";
import { PAGINAS, $, api, botao, cabeca, cartao, confirmar, esc, item, mostrar, ocupado, sub, toast, vazio } from "../painel.js";

// A prospecção (ADR 0127): o Zé encontra empresas da cidade no Google Maps, identifica quem decide
// pelo quadro de sócios da Receita e envia a primeira mensagem pelo WhatsApp, poucas por dia.
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

const CLASSES = { enviando: "alerta", enviada: "", respondeu: "bom", reuniao: "bom", sem_interesse: "alerta", descartada: "", fila: "", nova: "" };

/** @param {any} p */
function aguardando(p) {
  const mapa = linkSeguro(p.link) ? ` · <a class="externo" href="${linkSeguro(p.link)}" target="_blank" rel="noopener noreferrer">Ver no Maps ↗</a>` : "";
  return `<div class="campos">
    ${item(`${esc(p.nome)} <span class="etiqueta">Nota ${esc(p.nota)}</span>`, `${quem(p)}${mapa}${p.sinal ? `<br>${esc(p.sinal)}` : ""}`)}
    <label class="largo">Mensagem<textarea id="pr-msg-${esc(p.id)}" rows="5" maxlength="900">${esc(p.mensagem)}</textarea></label>
    <div class="linha">${botao("Aprovar", "pr-aprovar", `data-id="${esc(p.id)}"`, "principal")}${botao("Descartar", "pr-descartar", `data-id="${esc(p.id)}"`, "discreta")}</div>
  </div>`;
}

/** @param {any} p */
function empresa(p) {
  const etiqueta = `<span class="etiqueta ${CLASSES[p.status] ?? ""}">${esc(p.rotulo)}</span>`;
  const enviado = p.enviado ? `Enviada em ${new Date(p.enviado * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}` : "";
  const linhas = [
    quem(p),
    p.status === "descartada" ? esc(p.motivo) : esc(p.sinal),
    enviado,
    p.resposta ? `Resposta: “${esc(p.resposta)}”` : "",
    p.erro ? `Envio adiado: ${esc(p.erro)}` : "",
  ].filter(Boolean).join("<br>");
  const contatada = ["enviando", "enviada", "respondeu", "sem_interesse"].includes(p.status);
  const botoes = contatada
    ? botao("Reunião marcada", "pr-marcar", `data-id="${esc(p.id)}" data-status="reuniao"`, "discreta") +
      (p.status === "sem_interesse" ? "" : botao("Sem interesse", "pr-marcar", `data-id="${esc(p.id)}" data-status="sem_interesse"`, "discreta"))
    : p.status === "fila" ? botao("Descartar", "pr-descartar", `data-id="${esc(p.id)}"`, "discreta") : "";
  return item(`${esc(p.nome)} ${etiqueta}${p.nota ? ` <span class="etiqueta">Nota ${esc(p.nota)}</span>` : ""}`, linhas, botoes, p.status === "descartada");
}

function configuracao() {
  const c = ultimo.config;
  return cartao("Configuração", `
  <div class="campos">
    <label>Cidade<input id="pr-cidade" value="${esc(c.cidade)}" maxlength="80" placeholder="Caruaru, PE" autocomplete="off"></label>
    <label>Envios por dia<input id="pr-por-dia" type="number" min="1" max="5" value="${esc(c.por_dia)}"></label>
    <label class="largo">Ramos<textarea id="pr-ramos" rows="4" placeholder="Um por linha: clínica odontológica, imobiliária, autopeças">${esc((c.ramos || []).join("\n"))}</textarea></label>
    <label class="largo">O que você oferece<textarea id="pr-oferta" rows="4" maxlength="1500" placeholder="Em poucas linhas: o que você faz e para quem. Vai para a primeira mensagem.">${esc(c.oferta)}</textarea></label>
    <label class="interruptor"><input type="checkbox" id="pr-ligada" ${c.ligada ? "checked" : ""}> Ligada</label>
    <label class="interruptor"><input type="checkbox" id="pr-sozinho" ${c.sozinho ? "checked" : ""}> Enviar sozinho</label>
  </div>
  ${sub(`${esc(ultimo.horario)}, com pelo menos duas horas entre um envio e outro, em horários variados. Sem "Enviar sozinho", cada mensagem espera a sua aprovação.`)}
  <div class="linha">${botao("Salvar", "pr-salvar", "", "principal")}</div>
  <p class="resultado" id="pr-resultado"></p>`);
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
  if (lugar) lugar.innerHTML = corpo();
}

function corpo() {
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
  const lista = r.empresas.length ? r.empresas.map(empresa).join("") : vazio("Nenhuma empresa ainda.");
  return `${cartao("", item(`Prospecção ${estado}`, resumo))}${fila}${cartao("Empresas", `<div class="lista">${lista}</div>`)}${configuracao()}${fontes()}`;
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
    ligada: /** @type {HTMLInputElement} */ ($("pr-ligada")).checked,
    sozinho: /** @type {HTMLInputElement} */ ($("pr-sozinho")).checked,
  }, b, "pr-resultado"),
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
  "pr-marcar": (/** @type {HTMLButtonElement} */ b) => enviar("prospeccao/marcar", { id: b.dataset.id, status: b.dataset.status }, b, ""),
});
