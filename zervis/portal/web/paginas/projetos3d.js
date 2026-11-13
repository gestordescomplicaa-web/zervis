import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { carregadas } from "../modulos/estado.js";
import { PAGINAS, TOKEN, $, api, botao, cabeca, cartao, confirmar, esc, ocupado, sub, toast, vazio } from "../painel.js";

// A página Projetos 3D (ADR 0082), carregada sob demanda: cada projeto é uma pasta com os
// arquivos da peça, e uma sessão de código modela nela. Os arquivos ficam aqui; a peça aparece
// como sólido na Imersão. Fatiar e imprimir (ADR 0083): o tempo e o filamento antes, e imprimir só
// com a confirmação.

let formularioAberto = false;
let tvLigada = false;

const TIPOS = { peca: "Peça funcional", arte: "Arte a partir de imagem" };
const numero = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
/** @param {number} n */
const bytes = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${numero.format(n / 1024)} KB` : `${numero.format(n / 1048576)} MB`;
const MODELO = /\.(stl|glb)$/i;
let impressoraConfigurada = false;
/** @param {number} min */
const duracao = (min) => min >= 60 ? `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")}` : `${min} min`;
/** @param {string} nome */
const filamento = (nome) => String(nome).split(" @")[0].replace(/^(Bambu|Generic) /, "");

/** O tamanho, o volume e se a malha é fechada, de um STL. @param {any} m */
function medidas(m) {
  if (!m) return "";
  const [x, y, z] = m.tamanho_mm.map((/** @type {number} */ v) => numero.format(v));
  return `${x} × ${y} × ${z} mm · ${numero.format(m.volume_cm3)} cm³ · ${m.fechada ? "fechada" : '<span class="etiqueta alerta">Malha aberta</span>'}`;
}

/** @param {any} p */
function projeto(p) {
  const arquivos = p.arquivos.map((/** @type {any} */ a) => {
    const dados = `data-id="${esc(p.id)}" data-arquivo="${esc(a.nome)}"`;
    const stl = /\.stl$/i.test(a.nome) && impressoraConfigurada;
    const fatia = a.fatiado ? `Fatiado: ${duracao(a.fatiado.minutos)} · ${numero.format(a.fatiado.gramas)} g de ${esc(filamento(a.fatiado.filamento))}${a.fatiado.suporte ? " · com suporte" : ""}` : "";
    const botoes = [
      MODELO.test(a.nome) ? botao("Mostrar na Imersão", "projeto3d-mostrar", dados) : "",
      MODELO.test(a.nome) && tvLigada ? botao("Mostrar na TV", "projeto3d-mostrar-tv", dados) : "",
      stl ? botao(a.fatiado ? "Fatiar de novo" : "Fatiar", "projeto3d-fatiar", dados, "discreta") : "",
      stl && a.fatiado ? botao("Ver fatiamento", "projeto3d-trajetos", dados, "discreta") : "",
      stl && a.fatiado ? botao("Imprimir", "projeto3d-imprimir", `${dados} data-resumo="${esc(`${duracao(a.fatiado.minutos)} e ${Math.round(a.fatiado.gramas)} g de ${filamento(a.fatiado.filamento)}`)}"`, "principal") : "",
    ].join("");
    return `<div class="linha-item"><div class="texto"><strong class="mono">${esc(a.nome)}</strong>
      <small>${[bytes(a.tamanho), medidas(a.medidas)].filter(Boolean).join(" · ")}</small>${fatia ? `<small>${fatia}</small>` : ""}</div>
      ${botoes ? `<div class="botoes">${botoes}</div>` : ""}</div>
      <div class="previa-fatia" data-previa="${esc(p.id)}|${esc(a.nome)}" hidden></div>`;
  }).join("");
  const sessao = p.sessao
    ? botao("Abrir sessão", "projeto3d-sessao", `data-sessao="${esc(p.sessao)}"`, "discreta")
    : botao("Começar sessão", "projeto3d-comecar", `data-id="${esc(p.id)}"`, "principal");
  return cartao(`${esc(p.nome)} <span class="etiqueta">${esc(p.tipo_nome)}</span>`,
    `<p class="nota">${esc(p.pedido)}</p><p class="nota mono">${esc(p.pasta)}</p>
    <div class="itens">${arquivos || vazio("Nenhum arquivo ainda. A sessão está modelando.")}</div>
    <div class="botoes">${sessao}</div>`);
}

/** @param {any} a @param {string} raiz */
const ajustes = (a, raiz) => cartao("Ajustes", `${sub(`Os projetos ficam em <span class="mono">${esc(raiz)}</span>. A mesa entra nas regras de cada peça.`)}
  <div class="campos">
    <label>Nome da impressora<input id="p3d-impressora" value="${esc(a.impressora)}" maxlength="60" placeholder="Modelo da impressora"></label>
    <label>Mesa (mm)<span class="mesa-3d">${a.mesa_mm.map((/** @type {number} */ v, /** @type {number} */ i) => `<input id="p3d-mesa-${i}" type="number" min="50" max="2000" value="${v}" aria-label="${"XYZ"[i]}">`).join("×")}</span></label>
    <label>Pasta da pipeline de arte (opcional)<input id="p3d-pipeline" class="mono" value="${esc(a.pipeline_arte)}" placeholder="Onde estão os scripts de imagem para relevo" spellcheck="false"></label>
  </div><div class="botoes">${botao("Salvar", "projeto3d-ajustes", "", "principal")}</div>`);

const CORES = { parede: "#8ff0e4", preenchimento: "rgba(143,240,228,.28)", ponte: "#b9a8ff", suporte: "#ffb36b" };
/** A prévia do fatiamento em perspectiva isométrica, até a camada escolhida.
 * @param {HTMLCanvasElement} tela @param {any} t @param {number} ate */
function desenharTrajetos(tela, t, ate) {
  const ctx = /** @type {CanvasRenderingContext2D} */ (tela.getContext("2d"));
  const cos = Math.cos(Math.PI / 6), sen = Math.sin(Math.PI / 6), alto = 2.2;
  const proj = (/** @type {number} */ x, /** @type {number} */ y, /** @type {number} */ z) => [(x - y) * cos, (x + y) * sen - z * alto];
  let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const c of t.camadas) for (const l of c.linhas) for (let i = 1; i < l.length; i += 2) {
    const [px, py] = proj(l[i] / 10, l[i + 1] / 10, c.z);
    x0 = Math.min(x0, px); x1 = Math.max(x1, px); y0 = Math.min(y0, py); y1 = Math.max(y1, py);
  }
  const escala = Math.min((tela.width - 20) / (x1 - x0 || 1), (tela.height - 20) / (y1 - y0 || 1));
  ctx.clearRect(0, 0, tela.width, tela.height);
  ctx.lineWidth = 1;
  t.camadas.slice(0, ate).forEach((/** @type {any} */ c, /** @type {number} */ n) => {
    const ultima = n === ate - 1;
    for (const l of c.linhas) {
      ctx.strokeStyle = ultima && l[0] !== "preenchimento" ? "#ffffff" : CORES[l[0]] || CORES.parede;
      ctx.beginPath();
      for (let i = 1; i < l.length; i += 2) {
        const [px, py] = proj(l[i] / 10, l[i + 1] / 10, c.z);
        const sx = 10 + (px - x0) * escala, sy = 10 + (py - y0) * escala;
        i === 1 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
      }
      ctx.stroke();
    }
  });
}

const formulario = () => cartao("Novo projeto", `<div class="campos">
    <label>Nome<input id="p3d-nome" maxlength="60" placeholder="Suporte de celular" autocomplete="off"></label>
    <label>Tipo<select id="p3d-tipo">${Object.entries(TIPOS).map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select></label>
    <label>Descrição<textarea id="p3d-pedido" rows="3" maxlength="2000" placeholder="Medidas, uso e detalhes: 8 cm de altura, para celular de até 9 mm, inclinado a 60°"></textarea></label>
    <label id="p3d-campo-imagem" hidden>Imagem de referência<input id="p3d-imagem" type="file" accept="image/png,image/jpeg,image/webp"></label>
  </div><div class="botoes">${botao("Criar", "projeto3d-criar", "", "principal")}${botao("Cancelar", "projeto3d-cancelar", "", "discreta")}</div>`);

PAGINAS.projetos3d = async () => {
  const r = await api("projetos3d");
  impressoraConfigurada = r.impressora.configurada;
  tvLigada = !!r.tv;
  const lista = r.projetos.map(projeto).join("");
  const vazia = vazio('Nenhum projeto ainda. Crie um aqui ou peça ao Zé: "cria um suporte de celular em 3D".');
  return `${cabeca("Projetos 3D", formularioAberto ? "" : botao("Novo projeto", "projeto3d-formulario", "", "principal"))}
    ${sub("Peças e artes para imprimir: os arquivos de cada projeto e a prévia na Imersão.")}
    ${formularioAberto ? formulario() : ""}${lista || cartao("", vazia)}
    ${r.impressora.configurada ? "" : `<p class="nota">Para fatiar e imprimir, adicione a impressora em <a href="#dispositivos">Dispositivos</a>.</p>`}${ajustes(r.ajustes, r.raiz)}`;
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
  "projeto3d-fatiar": async (/** @type {HTMLButtonElement} */ b) => {
    try { toast((await ocupado(b, () => api("projetos3d/fatiar", { id: b.dataset.id, arquivo: b.dataset.arquivo }))).aviso, 6000); await abrir(); } catch (erro) { toast(erro.message); }
  },
  "projeto3d-imprimir": (/** @type {HTMLButtonElement} */ b) => confirmar(b, `Imprimir agora? ${b.dataset.resumo}. A mesa precisa estar livre.`, async () => {
    try { toast((await api("projetos3d/imprimir", { id: b.dataset.id, arquivo: b.dataset.arquivo, confirmado: true })).aviso, 5000); await abrir(); } catch (erro) { toast(erro.message); }
  }),
  "projeto3d-trajetos": async (/** @type {HTMLButtonElement} */ b) => {
    const area = /** @type {HTMLElement | null} */ (document.querySelector(`[data-previa="${CSS.escape(`${b.dataset.id}|${b.dataset.arquivo}`)}"]`));
    if (!area) return;
    if (!area.hidden) { area.hidden = true; area.innerHTML = ""; return; }
    try {
      const t = await ocupado(b, () => api("projetos3d/trajetos", { id: b.dataset.id, arquivo: b.dataset.arquivo }));
      const total = t.camadas.length;
      area.innerHTML = `<canvas width="720" height="420" aria-label="Prévia do fatiamento"></canvas>
        <label class="camada-fatia">Camada <input type="range" min="1" max="${total}" value="${total}"><span>${t.total_camadas} de ${t.total_camadas}</span></label>
        <p class="nota"><span style="color:${CORES.parede}">■</span> paredes <span style="color:${CORES.suporte}">■</span> suporte <span style="color:${CORES.ponte}">■</span> pontes</p>`;
      area.hidden = false;
      const tela = /** @type {HTMLCanvasElement} */ (area.querySelector("canvas"));
      const faixa = /** @type {HTMLInputElement} */ (area.querySelector("input"));
      const rotulo = /** @type {HTMLElement} */ (area.querySelector(".camada-fatia span"));
      const redesenhar = () => {
        const ate = Number(faixa.value);
        rotulo.textContent = `${Math.min(t.total_camadas, ate * t.passo)} de ${t.total_camadas}`;
        desenharTrajetos(tela, t, ate);
      };
      faixa.addEventListener("input", redesenhar);
      redesenhar();
    } catch (erro) { toast(erro.message); }
  },
  "projeto3d-ajustes": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { impressora: valor("p3d-impressora"), mesa_mm: [0, 1, 2].map((i) => Number(valor(`p3d-mesa-${i}`))), pipeline_arte: valor("p3d-pipeline") };
    try { toast((await ocupado(b, () => api("projetos3d/ajustes", dados))).aviso); } catch (erro) { toast(erro.message); }
  },
});
