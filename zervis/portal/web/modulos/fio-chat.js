// O desenho do fio do chat (ADR 0136, 0139): um bloco por dia, com a data presa no topo enquanto
// ele passa, e dentro dele só as falas que mudaram.

/** Um bloco por dia, com a data presa no topo enquanto ele passa; dentro, as falas.
 * @param {HTMLElement} fio @param {[string, string, string[][]][]} dias */
export function aplicarDias(fio, dias) {
  const querem = new Set(dias.map(([d]) => d));
  for (const no of [...fio.children]) if (!querem.has(/** @type {HTMLElement} */ (no).dataset.dia || "")) no.remove();
  const atuais = new Map([...fio.children].map((no) => [/** @type {HTMLElement} */ (no).dataset.dia, /** @type {HTMLElement} */ (no)]));
  dias.forEach(([dia, rotulo, partes], posicao) => {
    let bloco = atuais.get(dia);
    if (!bloco) {
      bloco = Object.assign(document.createElement("section"), { className: "dia-conversa" });
      bloco.dataset.dia = dia;
      bloco.innerHTML = `<div class="dia-fio" role="separator"><span></span></div><div class="falas-dia"></div>`;
    }
    const nome = /** @type {HTMLElement} */ (bloco.querySelector(".dia-fio span"));
    if (nome.textContent !== rotulo) nome.textContent = rotulo; // à meia-noite, "Hoje" vira "Ontem"
    if (fio.children[posicao] !== bloco) fio.insertBefore(bloco, fio.children[posicao] || null);
    aplicar(/** @type {HTMLElement} */ (bloco.lastElementChild), partes);
  });
}

/** O desenho de cada fala no fio. @type {WeakMap<Element, string>} */
const desenhos = new WeakMap();
/** Muda só as falas que mudaram, sem mover as outras: um visual redesenhado ou movido recarrega
 * a moldura e a apresentação recomeça (ADR 0138). @param {HTMLElement} fio @param {string[][]} partes */
function aplicar(fio, partes) {
  const querem = new Set(partes.map(([k]) => k));
  for (const no of [...fio.children]) if (!querem.has(/** @type {HTMLElement} */ (no).dataset.chave || "")) no.remove();
  const atuais = new Map([...fio.children].map((no) => [/** @type {HTMLElement} */ (no).dataset.chave, no]));
  partes.forEach(([k, html], posicao) => {
    let no = atuais.get(k);
    if (!no || desenhos.get(no) !== html) {
      const molde = document.createElement("template");
      molde.innerHTML = html.trim();
      const novo = /** @type {HTMLElement} */ (molde.content.firstElementChild);
      novo.dataset.chave = k; desenhos.set(novo, html);
      if (no) no.replaceWith(novo);
      no = novo;
    }
    if (fio.children[posicao] !== no) fio.insertBefore(no, fio.children[posicao] || null);
  });
}

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.fio, .dia-conversa, .falas-dia { display: flex; flex-direction: column; gap: 18px; }
/* A data do dia, presa no topo enquanto ele passa (ADR 0139). */
.dia-fio { position: sticky; top: 8px; z-index: 3; align-self: center; pointer-events: none; }
.dia-fio span { display: block; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 500; color: var(--suave); background: var(--fundo-2); border: 1px solid var(--borda); box-shadow: 0 4px 14px rgb(0 0 0 / .3); }
` }));
