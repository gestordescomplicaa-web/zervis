import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { carregadas } from "../modulos/estado.js";
import { PAGINAS, TOKEN, $, api, botao, cabeca, cartao, esc, ocupado, sub, toast, vazio } from "../painel.js";

// A página Projetos 3D (ADR 0082), carregada sob demanda: cada projeto é uma pasta com os
// arquivos da peça, e uma sessão de código modela nela. Os arquivos ficam aqui; a peça aparece
// como sólido na Imersão.

let formularioAberto = false;
let tvLigada = false;

const TIPOS = { peca: "Peça funcional", arte: "Arte a partir de imagem" };
const numero = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
/** @param {number} n */
const bytes = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${numero.format(n / 1024)} KB` : `${numero.format(n / 1048576)} MB`;
const MODELO = /\.(stl|glb)$/i;

/** O tamanho, o volume e se a malha é fechada, de um STL. @param {any} m */
function medidas(m) {
  if (!m) return "";
  const [x, y, z] = m.tamanho_mm.map((/** @type {number} */ v) => numero.format(v));
  return `${x} × ${y} × ${z} mm · ${numero.format(m.volume_cm3)} cm³ · ${m.fechada ? "fechada" : '<span class="etiqueta alerta">Malha aberta</span>'}`;
}

/** @param {any} p */
function projeto(p) {
  const arquivos = p.arquivos.map((/** @type {any} */ a) => `<div class="linha-item"><div class="texto"><strong class="mono">${esc(a.nome)}</strong>
    <small>${[bytes(a.tamanho), medidas(a.medidas)].filter(Boolean).join(" · ")}</small></div>
    ${MODELO.test(a.nome) ? `<div class="botoes">${botao("Mostrar na Imersão", "projeto3d-mostrar", `data-id="${esc(p.id)}" data-arquivo="${esc(a.nome)}"`)}${tvLigada ? botao("Mostrar na TV", "projeto3d-mostrar-tv", `data-id="${esc(p.id)}" data-arquivo="${esc(a.nome)}"`) : ""}</div>` : ""}</div>`).join("");
  const sessao = p.sessao
    ? botao("Abrir sessão", "projeto3d-sessao", `data-sessao="${esc(p.sessao)}"`, "discreta")
    : botao("Começar sessão", "projeto3d-comecar", `data-id="${esc(p.id)}"`, "principal");
  return cartao(`${esc(p.nome)} <span class="etiqueta">${esc(p.tipo_nome)}</span>`,
    `<p class="nota">${esc(p.pedido)}</p><p class="nota mono">${esc(p.pasta)}</p>
    <div class="itens">${arquivos || vazio("Nenhum arquivo ainda. A sessão está modelando.")}</div>
    <div class="botoes">${sessao}</div>`);
}

/** @param {any} a */
const ajustes = (a) => cartao("Ajustes", `${sub("A impressora que entra nas regras de cada projeto e a pasta da pipeline de arte.")}
  <div class="campos">
    <label>Impressora<input id="p3d-impressora" value="${esc(a.impressora)}" maxlength="60" placeholder="Modelo da impressora"></label>
    <label>Mesa (mm)<span class="mesa-3d">${a.mesa_mm.map((/** @type {number} */ v, /** @type {number} */ i) => `<input id="p3d-mesa-${i}" type="number" min="50" max="2000" value="${v}" aria-label="${"XYZ"[i]}">`).join("×")}</span></label>
    <label>Pipeline de arte<input id="p3d-pipeline" class="mono" value="${esc(a.pipeline_arte)}" placeholder="~/pasta-da-pipeline" spellcheck="false"></label>
  </div><div class="botoes">${botao("Salvar", "projeto3d-ajustes", "", "principal")}</div>`);

const formulario = () => cartao("Novo projeto", `<div class="campos">
    <label>Nome<input id="p3d-nome" maxlength="60" placeholder="Suporte de celular" autocomplete="off"></label>
    <label>Tipo<select id="p3d-tipo">${Object.entries(TIPOS).map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select></label>
    <label>Descrição<textarea id="p3d-pedido" rows="3" maxlength="2000" placeholder="Medidas, uso e detalhes: 8 cm de altura, para celular de até 9 mm, inclinado a 60°"></textarea></label>
    <label id="p3d-campo-imagem" hidden>Imagem de referência<input id="p3d-imagem" type="file" accept="image/png,image/jpeg,image/webp"></label>
  </div><div class="botoes">${botao("Criar", "projeto3d-criar", "", "principal")}${botao("Cancelar", "projeto3d-cancelar", "", "discreta")}</div>`);

PAGINAS.projetos3d = async () => {
  const r = await api("projetos3d");
  tvLigada = !!r.tv;
  const lista = r.projetos.map(projeto).join("");
  const vazia = vazio('Nenhum projeto ainda. Crie um aqui ou peça ao Zé: "cria um suporte de celular em 3D".');
  return `${cabeca("Projetos 3D", formularioAberto ? "" : botao("Novo projeto", "projeto3d-formulario", "", "principal"))}
    ${sub("Peças e artes para imprimir: os arquivos de cada projeto e a prévia na Imersão.")}
    ${formularioAberto ? formulario() : ""}${lista || cartao("", vazia)}${ajustes(r.ajustes)}`;
};

document.addEventListener("change", (e) => {
  const campo = /** @type {HTMLSelectElement} */ (e.target);
  if (campo.id === "p3d-tipo") $("p3d-campo-imagem")?.toggleAttribute("hidden", campo.value !== "arte");
});

/** @param {string} id */
const valor = (id) => /** @type {HTMLInputElement | null} */ ($(id))?.value.trim() || "";

Object.assign(ACOES, {
  "projeto3d-formulario": async () => { formularioAberto = true; await abrir(); },
  "projeto3d-cancelar": async () => { formularioAberto = false; await abrir(); },
  "projeto3d-criar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { nome: valor("p3d-nome"), tipo: valor("p3d-tipo"), pedido: valor("p3d-pedido") };
    const arquivo = /** @type {HTMLInputElement | null} */ ($("p3d-imagem"))?.files?.[0];
    try {
      const r = await ocupado(b, async () => {
        if (dados.tipo !== "arte") return api("projetos3d/criar", dados);
        if (!arquivo) throw new Error("Escolha a imagem de referência.");
        const busca = new URLSearchParams({ ...dados, nome_imagem: arquivo.name });
        const resposta = await fetch(`/api/projetos3d/imagem?${busca}`, { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: arquivo });
        const corpo = await resposta.json().catch(() => ({}));
        if (!resposta.ok) throw new Error(corpo.erro || "Falha ao criar.");
        return corpo;
      });
      toast(r.aviso);
      formularioAberto = false;
      await abrir();
    } catch (erro) {
      toast(erro.message);
    }
  },
  "projeto3d-comecar": async (/** @type {HTMLButtonElement} */ b) => {
    try { toast((await ocupado(b, () => api("projetos3d/comecar", { id: b.dataset.id }))).aviso); await abrir(); } catch (erro) { toast(erro.message); }
  },
  // A peça como sólido na Imersão; com ela fechada, o painel vai para a Imersão e tenta de novo.
  "projeto3d-mostrar": async (/** @type {HTMLButtonElement} */ b) => {
    const pedido = { id: b.dataset.id, arquivo: b.dataset.arquivo };
    try {
      toast((await ocupado(b, () => api("projetos3d/mostrar", pedido))).aviso);
    } catch {
      location.hash = "#imersao";
      await new Promise((r) => setTimeout(r, 4000));
      try { await api("projetos3d/mostrar", pedido); } catch (erro) { toast(erro.message); }
    }
  },
  "projeto3d-mostrar-tv": async (/** @type {HTMLButtonElement} */ b) => {
    try { toast((await ocupado(b, () => api("projetos3d/mostrar-tv", { id: b.dataset.id, arquivo: b.dataset.arquivo }))).aviso); } catch (erro) { toast(erro.message); }
  },
  "projeto3d-sessao": async (/** @type {HTMLButtonElement} */ b) => {
    location.hash = "#sessoes";
    for (let i = 0; i < 50 && !(carregadas.abrirSessao && document.querySelector(".sessoes")); i++) await new Promise((r) => setTimeout(r, 100));
    await carregadas.abrirSessao?.(b.dataset.sessao);
  },
  "projeto3d-ajustes": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { impressora: valor("p3d-impressora"), mesa_mm: [0, 1, 2].map((i) => Number(valor(`p3d-mesa-${i}`))), pipeline_arte: valor("p3d-pipeline") };
    try { toast((await ocupado(b, () => api("projetos3d/ajustes", dados))).aviso); } catch (erro) { toast(erro.message); }
  },
});
