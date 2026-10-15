// --- Imersão no celular: o holograma do Zé reagindo à conversa (a completa é só do PC) ---

const ESTADO_HOLO = { inativo: "Inativo", ativo: "Pronto", ouvindo: "Ouvindo", pensando: "Pensando", falando: "Falando", confirmando: "Esperando o seu sim" };
let estadoZe = "inativo";
const telaHolograma = () => `<div class="holo" data-estado="${estadoZe}">
  <div class="holo-palco"><img src="/imagens/holograma.webp" alt="O Zé" width="780" height="780" decoding="async"></div>
  <p class="holo-estado" id="holo-estado">${ESTADO_HOLO[estadoZe] || ""}</p>
  <div class="holo-botoes"><div class="voz-remota" id="voz-holo"></div><button type="button" class="acao" data-falar aria-pressed="false">Falar</button></div>
</div>`;

// --- Imersão: o modo imersivo de sempre, numa moldura ---

const IMERSIVO = "http://127.0.0.1:8794/stage.html?res=1280x720&fps=auto";
const imersao = $("imersao");
const moldura = $("moldura");
const imersaoLigada = () => !!/** @type {HTMLIFrameElement} */ (moldura.querySelector("iframe"));

function ligarImersao() {
  if (imersaoLigada()) return;
  const q = document.createElement("iframe");
  q.src = IMERSIVO; q.title = "Imersão"; q.allow = "camera; autoplay; fullscreen";
  moldura.replaceChildren(q);
  $("ponto-imersao").hidden = false;
}

function desligarImersao() {
  moldura.innerHTML = `<p class="vazio">Desligada. ${botao("Ligar", "imersao-ligar")}</p>`;
  $("ponto-imersao").hidden = true;
}

// A Imersão só roda à vista: sair dela ou esconder o painel desliga a câmera e o holograma.
document.addEventListener("visibilitychange", () => {
  if (location.hash !== "#imersao" || !NO_PC) return;
  if (document.visibilityState === "hidden") desligarImersao(); else ligarImersao();
});

