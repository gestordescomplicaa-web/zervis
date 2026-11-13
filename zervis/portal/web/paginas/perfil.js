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

PAGINAS.perfil = async function() {
    const [cfg, abertura] = await Promise.all([api("configuracao"), api("abertura")]);
    return `${cabeca("Perfil")}${sub("Usado pelo Zé em todas as conversas.")}
      ${cartao("", `${camposPerfil(cfg)}<div class="linha">${botao("Salvar", "perfil-salvar", "", "principal")}</div><p class="resultado" id="resultado-perfil"></p>`)}
      <div id="cartao-abertura">${cartaoAbertura(abertura)}</div>`;
  };

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
