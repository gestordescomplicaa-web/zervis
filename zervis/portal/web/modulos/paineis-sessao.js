import { compartilhado, carregadas } from "./estado.js";
// Os painéis da sessão: os arquivos à vista ou não, e as larguras ajustáveis. A lista e os arquivos
// têm uma alça na borda para arrastar (ou setas do teclado; duplo clique volta ao padrão). A largura
// fica guardada neste navegador. Carregado com a página de sessões.


/** @param {boolean} mostrar */
export function mostrarExplorador(mostrar) {
  compartilhado.explorador = mostrar;
  document.querySelector('.conversa-topo [data-acao="explorador"]')?.setAttribute("aria-pressed", String(mostrar));
  document.querySelector(".sessao-aberta")?.classList.toggle("sem-explorador", !mostrar);
}

// Até 1100 px os arquivos ocupam o lugar do terminal. Ao estreitar a janela (dividir a tela, por
// exemplo), fecham sozinhos e o terminal continua à vista; o botão Arquivos os abre de novo.
matchMedia("(max-width: 1100px)").addEventListener("change", (e) => { if (e.matches && compartilhado.explorador) mostrarExplorador(false); });

const PAINEIS = {
  lista: { variavel: "--largura-lista", caixa: ".sessoes", lado: "esquerda", min: 200, max: 480 },
  explorador: { variavel: "--largura-explorador", caixa: ".sessao-aberta", lado: "direita", min: 220, max: 560 },
};
const ESPACO_TERMINAL = 420; // o terminal nunca fica mais estreito que isto por causa de uma alça

/** @param {"lista" | "explorador"} nome */
export function larguraSalva(nome) {
  let px = 0;
  try { px = Number(localStorage.getItem(`zervis.largura.${nome}`)) || 0; } catch { /* sem armazenamento */ }
  const p = PAINEIS[nome];
  return px ? `${p.variavel}: ${Math.min(p.max, Math.max(p.min, px))}px` : "";
}

/** @param {"lista" | "explorador"} nome @param {string} rotulo */
export const divisor = (nome, rotulo) => `<div class="divisor" data-divisor="${nome}" role="separator" aria-orientation="vertical"
  aria-label="${rotulo}" tabindex="0" title="Arraste para ajustar a largura"></div>`;

/** @param {HTMLElement} alca @param {number | null} px  null volta ao padrão */
function ajustarLargura(alca, px) {
  const p = PAINEIS[/** @type {"lista" | "explorador"} */ (alca.dataset.divisor)];
  const caixa = /** @type {HTMLElement | null} */ (p && alca.closest(p.caixa));
  if (!caixa) return;
  const chave = `zervis.largura.${alca.dataset.divisor}`;
  if (px === null) {
    caixa.style.removeProperty(p.variavel);
    try { localStorage.removeItem(chave); } catch { /* sem armazenamento */ }
    return;
  }
  // O que o painel pode crescer é a sobra do terminal acima do mínimo (sem terminal à vista, só o máximo).
  const terminal = document.querySelector(".conversa")?.getBoundingClientRect().width || Infinity;
  const limite = Math.min(p.max, larguraAtual(alca) + terminal - ESPACO_TERMINAL);
  const final = Math.round(Math.max(p.min, Math.min(limite, px)));
  caixa.style.setProperty(p.variavel, `${final}px`);
  try { localStorage.setItem(chave, String(final)); } catch { /* sem armazenamento: vale só agora */ }
}

/** @param {HTMLElement} alca */
function larguraAtual(alca) {
  const p = PAINEIS[/** @type {"lista" | "explorador"} */ (alca.dataset.divisor)];
  const vizinho = /** @type {HTMLElement | null} */ (p.lado === "esquerda" ? alca.previousElementSibling : alca.nextElementSibling);
  return vizinho?.getBoundingClientRect().width || p.min;
}

document.addEventListener("pointerdown", (ev) => {
  const alca = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (ev.target).closest?.(".divisor"));
  if (!alca || ev.button !== 0) return;
  ev.preventDefault();
  const p = PAINEIS[/** @type {"lista" | "explorador"} */ (alca.dataset.divisor)];
  const inicio = ev.clientX, largura = larguraAtual(alca), sinal = p.lado === "esquerda" ? 1 : -1;
  alca.setPointerCapture(ev.pointerId);
  document.body.classList.add("redimensionando");
  const mover = (/** @type {PointerEvent} */ e) => ajustarLargura(alca, largura + sinal * (e.clientX - inicio));
  const soltar = () => {
    document.body.classList.remove("redimensionando");
    alca.removeEventListener("pointermove", mover);
    alca.removeEventListener("pointerup", soltar);
    alca.removeEventListener("pointercancel", soltar);
  };
  alca.addEventListener("pointermove", mover);
  alca.addEventListener("pointerup", soltar);
  alca.addEventListener("pointercancel", soltar);
});
document.addEventListener("dblclick", (ev) => {
  const alca = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (ev.target).closest?.(".divisor"));
  if (alca) ajustarLargura(alca, null);
});
document.addEventListener("keydown", (ev) => {
  const alca = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (ev.target).closest?.(".divisor"));
  if (!alca || (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight")) return;
  ev.preventDefault();
  const sinal = PAINEIS[/** @type {"lista" | "explorador"} */ (alca.dataset.divisor)].lado === "esquerda" ? 1 : -1;
  ajustarLargura(alca, larguraAtual(alca) + sinal * (ev.key === "ArrowRight" ? 16 : -16));
});

// Para o núcleo do painel (as ações, a navegação), que chama este módulo depois que ele carrega.
Object.assign(carregadas, { mostrarExplorador });
