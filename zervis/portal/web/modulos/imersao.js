import { $, NO_PC, botao } from "../painel.js";
import { compartilhado } from "./estado.js";

// --- Imersão no celular: o holograma do Zé reagindo à conversa (o palco pede tela grande) ---

export const ESTADO_HOLO = { inativo: "Inativo", ativo: "Pronto", ouvindo: "Ouvindo", pensando: "Pensando", falando: "Falando", confirmando: "Esperando o seu sim" };

export const telaHolograma = () => `<div class="holo" data-estado="${compartilhado.estadoZe}">
  <div class="holo-palco"><img src="/imagens/holograma.webp" alt="O Zé" width="780" height="780" decoding="async"></div>
  <p class="holo-estado" id="holo-estado">${ESTADO_HOLO[compartilhado.estadoZe] || ""}</p>
  <div class="holo-botoes"><div class="voz-remota" id="voz-holo"></div><button type="button" class="acao" data-falar aria-pressed="false">Falar</button></div>
</div>`;

// --- Imersão: o modo imersivo de sempre, numa moldura ---

// Do PC, o palco direto, com a câmera e as mãos. De outro aparelho com tela grande (o painel na
// VPS), o palco pelo próprio painel, sem câmera: o Zé e os cards (ADR 0100).
const IMERSIVO = NO_PC
  ? "http://127.0.0.1:8794/stage.html?res=1280x720&fps=auto"
  : "/imersao/stage.html?res=1280x720&fps=auto&camera=0";
export const palcoAqui = () => NO_PC || matchMedia("(min-width: 900px)").matches;
export const imersao = $("imersao");
export const moldura = $("moldura");
export const imersaoLigada = () => !!/** @type {HTMLIFrameElement} */ (moldura.querySelector("iframe"));

// Abrir o programa (ADR 0078): a primeira Imersão leva o pedido da abertura, uma vez só.
let abertura = false;
export const pedirAbertura = () => { abertura = true; };

export function ligarImersao() {
  if (imersaoLigada()) return;
  const q = document.createElement("iframe");
  q.src = IMERSIVO + (abertura ? "&abertura=1" : ""); abertura = false; q.title = "Imersão"; q.allow = "camera; autoplay; fullscreen";
  moldura.replaceChildren(q);
  $("ponto-imersao").hidden = false;
}

export function desligarImersao() {
  moldura.innerHTML = `<p class="vazio">Desligada. ${botao("Ligar", "imersao-ligar")}</p>`;
  $("ponto-imersao").hidden = true;
}

// A Imersão só roda à vista: sair dela ou esconder o painel desliga a câmera e o holograma.
document.addEventListener("visibilitychange", () => {
  if (location.hash !== "#imersao" || !palcoAqui()) return;
  if (document.visibilityState === "hidden") desligarImersao(); else ligarImersao();
});

