import { $, TOKEN, esc, toast } from "../painel.js";
import { icone } from "./casca.js";

// Anexos (ADR 0137): imagens, PDF e texto, até 5 por mensagem e 20 MB cada (o "+", colar ou
// arrastar). Sobem para a pasta de anexos do Zé; o cérebro lê só esses arquivos, pela ferramenta
// anexo_ler. A trava de verdade é a do servidor (zervis/memoria/anexos.py).
export const ACEITOS = "image/png,image/jpeg,image/webp,image/gif,application/pdf,.txt,.md,.csv,.json";
const MAX_ANEXOS = 5, MAX_BYTES = 20 * 1024 * 1024;
/** @typedef {{ nome: string, tipo: string, tamanho: number, miniatura?: string }} Anexo */
/** Os anexos escolhidos e ainda não enviados. @type {{ arquivo: File, url: string }[]} */
let pendentes = [];
/** "840 KB", "1,2 MB". @param {number} n */
const tamanho = (n) => n < 1e6 ? `${Math.max(1, Math.round(n / 1000))} KB` : `${(n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
/** "PDF", "Texto", "Imagem". @param {string} nome @param {string} tipo */
const especie = (nome, tipo) => tipo.startsWith("image/") ? "Imagem" : tipo === "application/pdf" || /\.pdf$/i.test(nome) ? "PDF" : "Texto";
/** Um anexo dentro de uma fala: a miniatura da imagem, ou o arquivo com nome e tamanho. @param {Anexo} a */
const anexoNaFala = (a) => a.miniatura
  ? `<img class="miniatura" src="${esc(a.miniatura)}" alt="${esc(a.nome)}" title="${esc(a.nome)}">`
  : `<span class="arquivo-fala">${icone("file-text")}<span><b>${esc(a.nome)}</b><small>${especie(a.nome, a.tipo)} · ${tamanho(a.tamanho)}</small></span></span>`;
export const anexosNaFala = (/** @type {Anexo[] | undefined} */ lista) => lista?.length ? `<div class="anexos-fala">${lista.map(anexoNaFala).join("")}</div>` : "";

/** Os anexos no campo, com o botão de tirar. */
function desenharPendentes() {
  const caixa = $("anexos-escrever");
  if (!caixa) return;
  caixa.hidden = !pendentes.length;
  caixa.innerHTML = pendentes.map(({ arquivo, url }, i) => `<div class="anexo-chip${url ? " imagem" : ""}">${url
    ? `<img src="${esc(url)}" alt="">`
    : `<span class="icone-arquivo">${icone("file-text")}</span><span class="nome-anexo"><b>${esc(arquivo.name)}</b><small>${especie(arquivo.name, arquivo.type)} · ${tamanho(arquivo.size)}</small></span>`}
    <button type="button" class="tirar" data-tirar="${i}" aria-label="Tirar ${esc(arquivo.name)}">${icone("x")}</button></div>`).join("");
}

/** Junta arquivos aos anexos (o "+", colar ou arrastar). @param {Iterable<File>} lista */
export function anexarNoChat(lista) {
  for (const bruto of lista) {
    if (pendentes.length >= MAX_ANEXOS) { toast(`No máximo ${MAX_ANEXOS} anexos por mensagem.`); break; }
    if (bruto.size > MAX_BYTES) { toast(`${bruto.name}: maior que 20 MB.`); continue; }
    const arquivo = bruto.name ? bruto : new File([bruto], `colado-${Date.now()}.${bruto.type.split("/")[1] || "png"}`, { type: bruto.type });
    if (!ACEITOS.split(",").some((t) => t.startsWith(".") ? arquivo.name.toLowerCase().endsWith(t) : arquivo.type === t)) { toast(`${arquivo.name}: tipo não aceito.`); continue; }
    pendentes.push({ arquivo, url: arquivo.type.startsWith("image/") ? URL.createObjectURL(arquivo) : "" });
  }
  desenharPendentes();
}

/** Sobe um anexo; volta o nome guardado. @param {File} arquivo @returns {Promise<string>} */
export async function subirAnexo(arquivo) {
  const r = await fetch(`/api/conversa/anexo?nome=${encodeURIComponent(arquivo.name)}`,
    { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: arquivo });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`${arquivo.name}: ${dados.erro || "não enviado"}`);
  return dados.anexo;
}

/** O "+" do campo e o seletor de arquivos (escondido). */
export const botaoAnexar = () => `<button type="button" class="redondo" id="anexar" aria-label="Anexar imagem ou arquivo" title="Anexar imagem ou arquivo">${icone("plus")}</button>
      <input type="file" id="anexar-arquivo" multiple hidden accept="${ACEITOS}">`;

/** Onde os anexos esperam o envio, dentro do campo. */
export const caixaAnexos = () => '<div class="anexos-escrever" id="anexos-escrever" hidden></div>';

/** Os anexos que vão com a mensagem; o campo fica sem eles. */
export function tirarPendentes() {
  const indo = pendentes;
  pendentes = [];
  desenharPendentes();
  return indo;
}

/** O envio falhou: os anexos voltam ao campo, se nada novo entrou. @param {{ arquivo: File, url: string }[]} lista */
export function devolverPendentes(lista) {
  if (pendentes.length) return;
  pendentes = lista;
  desenharPendentes();
}

/** O "+", tirar, colar e arrastar para o chat. @param {HTMLTextAreaElement} campo */
export function ligarAnexos(campo) {
  const arquivo = /** @type {HTMLInputElement} */ ($("anexar-arquivo"));
  $("anexar").addEventListener("click", () => arquivo.click());
  arquivo.addEventListener("change", () => { anexarNoChat(arquivo.files || []); arquivo.value = ""; });
  $("anexos-escrever").addEventListener("click", (ev) => {
    const b = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (ev.target).closest("[data-tirar]"));
    if (!b) return;
    const [fora] = pendentes.splice(Number(b.dataset.tirar), 1);
    if (fora?.url) URL.revokeObjectURL(fora.url);
    desenharPendentes();
  });
  campo.addEventListener("paste", (ev) => {
    const arquivos = [...(ev.clipboardData?.files || [])];
    if (arquivos.length) { ev.preventDefault(); anexarNoChat(arquivos); }
  });
  const area = /** @type {HTMLElement | null} */ (document.querySelector(".coluna-chat"));
  area?.addEventListener("dragover", (ev) => { if (ev.dataTransfer?.types.includes("Files")) { ev.preventDefault(); area.classList.add("soltando"); } });
  area?.addEventListener("dragleave", (ev) => { if (!area.contains(/** @type {Node | null} */ (ev.relatedTarget))) area.classList.remove("soltando"); });
  area?.addEventListener("drop", (ev) => { ev.preventDefault(); area.classList.remove("soltando"); anexarNoChat(ev.dataTransfer?.files || []); campo.focus(); });
}

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.anexos-escrever { display: flex; flex-wrap: wrap; gap: 8px; padding: 6px 0 4px; }
.anexo-chip { position: relative; display: flex; align-items: center; gap: 10px; height: 56px; padding: 0 30px 0 8px; max-width: 240px; border-radius: 12px; background: var(--fundo-2); border: 1px solid var(--borda-forte); }
.anexo-chip.imagem { width: 56px; padding: 0; overflow: hidden; }
.anexo-chip.imagem img { width: 100%; height: 100%; object-fit: cover; }
.icone-arquivo { display: grid; place-items: center; width: 38px; height: 38px; flex: none; border-radius: 9px; background: var(--acento-suave); color: var(--acento); }
.icone-arquivo svg { width: 18px; height: 18px; }
.nome-anexo { display: grid; min-width: 0; }
.nome-anexo b, .arquivo-fala b { font-weight: 500; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nome-anexo small, .arquivo-fala small { font-size: 11.5px; color: var(--suave); }
.tirar { position: absolute; top: 4px; right: 4px; display: grid; place-items: center; width: 20px; height: 20px; padding: 0; border-radius: 50%; border: 0; cursor: pointer; color: var(--texto); background: rgb(7 11 15 / .75); }
.tirar svg { width: 12px; height: 12px; }
.anexos-fala { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 6px; justify-content: flex-end; margin-bottom: 2px; }
.fala.ze .anexos-fala { justify-content: flex-start; }
.anexos-fala .miniatura { width: 160px; height: 120px; object-fit: cover; border-radius: 12px; border: 1px solid var(--borda-forte); }
.arquivo-fala { display: flex; align-items: center; gap: 10px; padding: 8px 14px 8px 8px; max-width: 280px; border-radius: 12px; background: var(--vidro-forte); border: 1px solid var(--borda-forte); }
.arquivo-fala > svg { width: 34px; height: 34px; padding: 8px; flex: none; border-radius: 9px; background: var(--acento-suave); color: var(--acento); }
.arquivo-fala > span { display: grid; min-width: 0; }
.coluna-chat.soltando { outline: 2px dashed var(--acento); outline-offset: -10px; border-radius: 16px; }
` }));
