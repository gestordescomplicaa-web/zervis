import { camposPerfil } from "../modulos/modelos.js";
import { ACOES } from "../modulos/acoes.js";
import { PAGINAS, TOKEN, $, api, botao, cabeca, cartao, esc, mostrar, ocupado, sub } from "../painel.js";

// Página perfil, carregada sob demanda. O cartão Abertura (ADR 0078): o que o Zé mostra e toca
// ao abrir o programa.
/** @param {any} a */
const cartaoAbertura = (a) => cartao("Abertura", `${sub("Música e resumo do dia na Imersão, ao abrir o Zérvis.")}
  <div class="campos">
    <label class="interruptor"><input type="checkbox" id="ab-ligada" ${a.ligada ? "checked" : ""}> Mostrar ao abrir o programa</label>
    <label>Cidade do clima<input id="ab-cidade" value="${esc(a.cidade)}" maxlength="80" placeholder="${esc(a.cidade_do_fuso || "Cidade")}" autocomplete="address-level2"></label>
  </div>
  <p class="sub">Música: ${a.musica ? "arquivo próprio" : "som padrão"}</p>
  <div class="linha">${botao("Salvar", "abertura-salvar", "", "principal")}${botao(a.musica ? "Trocar música" : "Enviar música", "abertura-musica")}${a.musica ? botao("Remover música", "abertura-remover", "", "discreta") : ""}
    <input type="file" id="ab-arquivo" accept="audio/mpeg,audio/ogg,audio/wav,audio/mp4,.mp3,.ogg,.wav,.m4a" hidden></div>
  <p class="resultado" id="resultado-abertura"></p>`);

/** O Modo TV (ADR 0084): o que o Zé mostra na TV da casa, pelo navegador dela. @param {any} t */
const cartaoTV = (t) => cartao(`Modo TV <span class="etiqueta ${t.aberta ? "bom" : ""}">${t.aberta ? "Aberto na TV" : t.ligado ? "Ligado" : "Desligado"}</span>`,
  `${sub("Mostra na TV da casa o que o Zé apresenta, como as peças 3D.")}
  <div class="campos">
    <label class="interruptor"><input type="checkbox" id="tv-ligado" ${t.ligado ? "checked" : ""}> Ligado</label>
    <label>IP da TV<input id="tv-ip" class="mono" value="${esc(t.ip_tv)}" placeholder="192.168.0.20" spellcheck="false"></label>
  </div>
  ${t.endereco ? `<p class="sub">Página inicial do navegador da TV:</p><p class="mono quebra">${esc(t.endereco)}</p>` : ""}
  <div class="linha">${botao("Salvar", "tv-salvar", "", "principal")}${botao("Procurar na rede", "tv-procurar", "", "discreta")}${t.ligado ? botao("Abrir na TV", "tv-abrir") + botao("Fechar", "tv-fechar", "", "discreta") : ""}</div>
  <p class="resultado" id="resultado-tv"></p>`);

PAGINAS.perfil = async function() {
    const [cfg, abertura, tv] = await Promise.all([api("configuracao"), api("abertura"), api("tv")]);
    return `${cabeca("Perfil")}${sub("Usado pelo Zé em todas as conversas.")}
      ${cartao("", `${camposPerfil(cfg)}<div class="linha">${botao("Salvar", "perfil-salvar", "", "principal")}</div><p class="resultado" id="resultado-perfil"></p>`)}
      <div id="cartao-abertura">${cartaoAbertura(abertura)}</div>
      <div id="cartao-tv">${cartaoTV(tv)}</div>`;
  };

/** @param {any} r */
function redesenharTV(r) {
  const lugar = $("cartao-tv");
  if (lugar) lugar.innerHTML = cartaoTV(r);
  if (r.aviso) mostrar("resultado-tv", true, r.aviso);
}

/** @param {any} r */
function redesenhar(r) {
  const lugar = $("cartao-abertura");
  if (lugar) lugar.innerHTML = cartaoAbertura(r);
  mostrar("resultado-abertura", true, r.aviso);
}

Object.assign(ACOES, {
  "abertura-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const ligada = /** @type {HTMLInputElement} */ ($("ab-ligada")).checked;
    const cidade = /** @type {HTMLInputElement} */ ($("ab-cidade")).value;
    redesenhar(await ocupado(b, () => api("abertura", { ligada, cidade })));
  },
  "abertura-musica": () => $("ab-arquivo")?.click(),
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
  "abertura-remover": async (/** @type {HTMLButtonElement} */ b) => {
    redesenhar(await ocupado(b, () => api("abertura/musica/remover", {})));
  },
});

document.addEventListener("change", async (e) => {
  const campo = /** @type {HTMLInputElement} */ (e.target);
  if (campo.id !== "ab-arquivo" || !campo.files?.length) return;
  try {
    const r = await fetch("/api/abertura/musica", { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: campo.files[0] });
    const dados = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(dados.erro || "Falha ao enviar.");
    redesenhar(dados);
  } catch (erro) {
    mostrar("resultado-abertura", false, erro.message);
  }
});
