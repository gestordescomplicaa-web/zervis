import { ACOES } from "../modulos/acoes.js";
import { PAGINAS, $, api, botao, cabeca, cartao, esc, mostrar, ocupado, sub } from "../painel.js";

// O Modo TV (ADR 0084), em Dispositivos (ADR 0089): o que o Zé mostra na TV da casa, pelo
// navegador dela.

/** @param {any} t */
const cartaoTV = (t) => cartao(`Modo TV <span class="etiqueta ${t.aberta ? "bom" : ""}">${t.aberta ? "Aberto na TV" : t.ligado ? "Ligado" : "Desligado"}</span>`,
  `${sub("Mostra na TV da casa o que o Zé apresenta, como as peças 3D.")}
  <div class="campos">
    <label class="interruptor"><input type="checkbox" id="tv-ligado" ${t.ligado ? "checked" : ""}> Ligado</label>
    <label>IP da TV<input id="tv-ip" class="mono" value="${esc(t.ip_tv)}" placeholder="192.168.0.20" spellcheck="false"></label>
  </div>
  ${t.endereco ? `<p class="sub">Página inicial do navegador da TV:</p><p class="mono quebra">${esc(t.endereco)}</p>` : ""}
  <div class="linha">${botao("Salvar", "tv-salvar", "", "principal")}${botao("Procurar na rede", "tv-procurar", "", "discreta")}${t.ligado ? botao("Abrir na TV", "tv-abrir") + botao("Fechar", "tv-fechar", "", "discreta") : ""}</div>
  <p class="resultado" id="resultado-tv"></p>`);

PAGINAS.tv = async () => {
  const t = await api("tv");
  return `${cabeca("TV", '<a class="acao discreta" href="#dispositivos">Dispositivos</a>')}<div id="cartao-tv">${cartaoTV(t)}</div>`;
};

/** @param {any} r */
function redesenharTV(r) {
  const lugar = $("cartao-tv");
  if (lugar) lugar.innerHTML = cartaoTV(r);
  if (r.aviso) mostrar("resultado-tv", true, r.aviso);
}

Object.assign(ACOES, {
  "tv-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = { ligado: /** @type {HTMLInputElement} */ ($("tv-ligado")).checked, ip_tv: /** @type {HTMLInputElement} */ ($("tv-ip")).value };
    try { redesenharTV(await ocupado(b, () => api("tv", dados))); } catch (erro) { mostrar("resultado-tv", false, erro.message); }
  },
  "tv-procurar": async (/** @type {HTMLButtonElement} */ b) => {
    const r = await ocupado(b, () => api("tv/procurar", {}));
    const [achada] = r.achadas;
    if (!achada) return mostrar("resultado-tv", false, r.aviso);
    /** @type {HTMLInputElement} */ ($("tv-ip")).value = achada.ip;
    mostrar("resultado-tv", true, `${achada.nome}: ${achada.ip}. Salve para usar.`);
  },
  "tv-abrir": async (/** @type {HTMLButtonElement} */ b) => {
    try { redesenharTV(await ocupado(b, () => api("tv/abrir", {}))); } catch (erro) { mostrar("resultado-tv", false, erro.message); }
  },
  "tv-fechar": async (/** @type {HTMLButtonElement} */ b) => { redesenharTV(await ocupado(b, () => api("tv/fechar", {}))); },
});
