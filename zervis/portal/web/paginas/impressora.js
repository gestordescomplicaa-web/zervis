import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { PAGINAS, $, api, botao, cabeca, cartao, esc, ocupado, sub, toast } from "../painel.js";

// A impressora 3D na rede local (ADR 0083, 0085), em Dispositivos (ADR 0089): achar, guardar a
// conexão, ver o estado, a câmera e os últimos avisos. Os projetos continuam em Projetos 3D.

/** @param {number} min */
const duracao = (min) => min >= 60 ? `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")}` : `${min} min`;
/** @param {string} id */
const valor = (id) => /** @type {HTMLInputElement | null} */ ($(id))?.value.trim() || "";

/** @param {any} i */
const impressora = (i) => cartao(`Impressora <span class="etiqueta ${i.configurada ? "bom" : ""}">${i.configurada ? "Configurada" : "Não configurada"}</span>`,
  `${sub("Bambu Lab no modo só LAN, com o modo desenvolvedor ligado.")}
  <div class="campos">
    <label>Endereço IP<input id="p3d-ip" class="mono" value="${esc(i.ip)}" placeholder="192.168.0.20" spellcheck="false"></label>
    <label>Número de série<input id="p3d-serie" class="mono" value="${esc(i.serie)}" spellcheck="false"></label>
    <label>Código de acesso<input id="p3d-codigo" type="password" autocomplete="off" placeholder="${i.configurada ? "Configurado" : "Na tela da impressora"}"></label>
  </div><p class="nota" id="p3d-status">${i.modelo ? esc(`Bambu Lab ${i.modelo}`) : ""}</p>
  ${(i.avisos || []).length ? `<div class="itens">${i.avisos.map((/** @type {any} */ v) => `<div class="linha-item"><div class="texto"><small>${esc(new Date(v.quando * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }))}</small><span title="${esc(v.texto)}">${esc(v.fala)}</span></div></div>`).join("")}</div>` : ""}
  <img id="p3d-foto" class="foto-impressora" alt="Câmera da impressora" hidden>
  <div class="botoes">${botao("Procurar na rede", "impressora3d-procurar", "", "discreta")}${i.configurada ? botao("Testar conexão", "impressora3d-status", "", "discreta") + botao("Ver câmera", "impressora3d-foto", "", "discreta") : ""}${botao("Salvar", "impressora3d-salvar", "", "principal")}</div>`);

PAGINAS.impressora = async () => {
  const i = await api("impressora");
  return `${cabeca("Impressora 3D", '<a class="acao discreta" href="#dispositivos">Dispositivos</a>')}${impressora(i)}`;
};

Object.assign(ACOES, {
  "impressora3d-procurar": async (/** @type {HTMLButtonElement} */ b) => {
    const r = await ocupado(b, () => api("projetos3d/impressora/procurar", {}));
    const [achada] = r.achadas;
    if (!achada) return toast(r.aviso);
    /** @type {HTMLInputElement} */ ($("p3d-ip")).value = achada.ip;
    /** @type {HTMLInputElement} */ ($("p3d-serie")).value = achada.serie;
    toast(`Achei a Bambu Lab ${achada.modelo || ""} em ${achada.ip}. Falta o código de acesso.`.replace("  ", " "), 5000);
  },
  "impressora3d-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { ip: valor("p3d-ip"), serie: valor("p3d-serie"), codigo: valor("p3d-codigo") };
    try { toast((await ocupado(b, () => api("projetos3d/impressora", dados))).aviso); await abrir(); } catch (erro) { toast(erro.message); }
  },
  "impressora3d-foto": async (/** @type {HTMLButtonElement} */ b) => {
    const foto = /** @type {HTMLImageElement | null} */ ($("p3d-foto"));
    try { const r = await ocupado(b, () => api("projetos3d/impressora/foto", {})); if (foto) { foto.src = r.foto; foto.hidden = false; } } catch (erro) { toast(erro.message); }
  },
  "impressora3d-status": async (/** @type {HTMLButtonElement} */ b) => {
    const estado = $("p3d-status");
    try {
      const s = (await ocupado(b, () => api("projetos3d/impressora/status", {}))).status;
      const bandejas = s.bandejas.map((/** @type {any} */ t) => `bandeja ${t.indice + 1}: ${t.marca || t.tipo}`).join(" · ");
      const andamento = s.estado === "imprimindo" ? ` · ${s.percentual}% · faltam ${duracao(s.restante_min)}` : "";
      if (estado) estado.textContent = `Conectada: ${s.estado}${andamento} · bico ${s.bico_c} °C · mesa ${s.mesa_c} °C${bandejas ? ` · ${bandejas}` : ""}`;
    } catch (erro) {
      if (estado) estado.textContent = erro.message;
    }
  },
});
