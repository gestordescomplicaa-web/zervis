import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { NO_PC, PAGINAS, $, api, botao, cabeca, cartao, esc, ocupado, sub, toast, vazio } from "../painel.js";

const hora = (valor) => new Date(valor * 1000).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
const campo = (id) => /** @type {HTMLInputElement | null} */ ($(id));

function formulario(c) {
  return cartao(`Câmera <span class="etiqueta ${c.estado === "Conectada" ? "bom" : ""}">${esc(c.estado)}</span>`,
    `${sub("Fotos guardadas nesta máquina quando a câmera detecta movimento.")}
    <div class="campos">
      <label>Endereço IP<input id="camera-ip" class="mono" value="${esc(c.ip)}" placeholder="192.168.0.20" spellcheck="false"></label>
      <label>Usuário<input id="camera-usuario" value="${esc(c.usuario || "admin")}" maxlength="64" autocomplete="username"></label>
      <label>Senha do dispositivo<input id="camera-senha" type="password" autocomplete="new-password" placeholder="${c.configurada ? "Configurada" : "Defina no iCSee"}"></label>
      <label>Intervalo entre fotos (s)<input id="camera-intervalo" type="number" min="1" max="86400" value="${c.intervalo_s}" step="1"></label>
    </div>
    <label class="interruptor"><input id="camera-ligada" type="checkbox" ${c.ligado ? "checked" : ""}> Fotos por movimento</label>
    <label class="interruptor"><input id="camera-enviar" type="checkbox" ${c.enviar !== false ? "checked" : ""}> Enviar ao celular</label>
    ${movimento(c)}
    ${girar(c)}
    <p class="resultado" id="camera-resultado"></p>
    <div class="botoes">${botao("Procurar na rede", "camera-procurar", "", "discreta")}${c.configurada ? botao("Testar conexão", "camera-testar", "", "discreta") : ""}${botao("Salvar", "camera-salvar", "", "principal")}</div>`);
}

/** Fotos por movimento por lente: a lente cuja detecção dispara sem ninguém fica de fora. */
function movimento(c) {
  if ((c.lentes || 1) < 2) return "";
  const lentes = Array.from({ length: c.lentes }, (_, i) => i + 1);
  const marcada = (n) => ((c.sem_fotos || []).includes(n) ? "" : "checked");
  return `<p class="rotulo">Lentes com fotos por movimento</p>${lentes.map((n) =>
    `<label class="interruptor"><input class="camera-movimento" data-lente="${n}" type="checkbox" ${marcada(n)}> Lente ${n}</label>`).join("")}`;
}

/** "Girar 180°" por lente: a imagem da lente montada de cabeça para baixo sai de pé. */
function girar(c) {
  const lentes = Array.from({ length: Math.max(1, c.lentes || 1) }, (_, i) => i + 1);
  const marcada = (n) => ((c.girar || []).includes(n) ? "checked" : "");
  if (lentes.length === 1) {
    return `<label class="interruptor"><input class="camera-girar" data-lente="1" type="checkbox" ${marcada(1)}> Girar imagem 180°</label>`;
  }
  return `<p class="rotulo">Girar imagem 180°</p>${lentes.map((n) =>
    `<label class="interruptor"><input class="camera-girar" data-lente="${n}" type="checkbox" ${marcada(n)}> Lente ${n}</label>`).join("")}`;
}

const minutos = (s) => (s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`);

/** A conversa ao vivo pela câmera (ADR 0088) e o histórico, com o resumo e as falas. */
function conversa(c) {
  if (!c.configurada) return "";
  const acao = c.em_conversa
    ? botao("Encerrar conversa", "camera-encerrar", "", "discreta")
    : botao("Atender pela câmera", "camera-atender", "", "principal");
  const itens = (c.conversas || []).map((v, i) => `<div class="linha-item">
    <div class="texto"><strong>${esc(hora(v.quando))} · ${esc(minutos(v.duracao || 0))}</strong><small>${esc(v.resumo || v.motivo || "Sem resumo.")}</small></div>
    ${(v.conversa || []).length ? botao("Ver conversa", "camera-ver-conversa", `data-i="${i}"`, "discreta") : ""}
    <div class="falas" data-conversa="${i}" hidden>${(v.conversa || []).map((f) =>
      `<p><b>${f.quem === "cliente" ? "Pessoa" : "Zé"}:</b> ${esc(f.texto)}</p>`).join("")}</div>
  </div>`).join("");
  return cartao(`Conversa <span class="etiqueta ${c.em_conversa ? "bom" : ""}">${c.em_conversa ? "Em conversa" : "Livre"}</span>`,
    `${sub("Fala ao vivo pela câmera. O Zé de lá só conversa e anota recados.")}
    <div class="botoes">${acao}</div>${itens ? `<div class="itens">${itens}</div>` : ""}`);
}

// O vídeo ao vivo (ADR 0101): uma lente ou todas, lado a lado, enquanto a página estiver à vista.
// No PC, a qualidade alta (720p); de outro aparelho, a leve, que pesa menos na rede de fora.
let qualidade = NO_PC ? "alta" : "leve";
/** @type {number[]} as lentes à vista agora */
let vendo = [];

function aoVivo(c) {
  if (!c.configurada) return "";
  const lentes = Array.from({ length: Math.max(1, c.lentes || 1) }, (_, i) => i + 1);
  const todas = lentes.length > 1 ? botao("Todas", "camera-ao-vivo", `data-lentes="${lentes.join(",")}" aria-pressed="false"`, "discreta") : "";
  return cartao("Ao vivo", `${sub("O vídeo de cada lente, enquanto esta página estiver aberta.")}
    <div class="botoes">${lentes.map((n) => botao(`Lente ${n}`, "camera-ao-vivo", `data-lentes="${n}" aria-pressed="false"`, "discreta")).join("")}${todas}
      ${botao(qualidade === "alta" ? "Qualidade alta" : "Qualidade leve", "camera-qualidade", "", "discreta")}
      ${botao("Parar", "camera-parar", "hidden", "discreta")}</div>
    <div class="camera-videos" id="camera-videos"></div>`);
}

function pararVideo() {
  const caixa = $("camera-videos");
  // Tirar a fonte de cada <img> fecha a transmissão, e o Zé encerra a conexão e o ffmpeg dela.
  caixa?.querySelectorAll("img").forEach((v) => v.removeAttribute("src"));
  if (caixa) caixa.replaceChildren();
  vendo = [];
  document.querySelectorAll('[data-acao="camera-ao-vivo"]').forEach((b) => b.setAttribute("aria-pressed", "false"));
  const parar = document.querySelector('[data-acao="camera-parar"]');
  if (parar) /** @type {HTMLElement} */ (parar).hidden = true;
}

/** @param {number[]} lentes */
function verLentes(lentes) {
  const caixa = $("camera-videos");
  if (!caixa) return;
  pararVideo();
  vendo = lentes;
  caixa.classList.toggle("varias", lentes.length > 1);
  for (const lente of lentes) {
    const video = document.createElement("img");
    video.alt = `Vídeo ao vivo da lente ${lente}`;
    video.onerror = () => { if (vendo.includes(lente)) { video.remove(); toast(`Sem vídeo da lente ${lente} agora.`); } };
    video.src = `/fluxo/camera/ao-vivo?lente=${lente}&qualidade=${qualidade}&t=${Date.now()}`;
    caixa.append(video);
  }
  const marcado = lentes.join(",");
  document.querySelectorAll('[data-acao="camera-ao-vivo"]').forEach((b) =>
    b.setAttribute("aria-pressed", String(/** @type {HTMLElement} */ (b).dataset.lentes === marcado)));
  const parar = document.querySelector('[data-acao="camera-parar"]');
  if (parar) /** @type {HTMLElement} */ (parar).hidden = false;
}

// Fora da página Câmera ou com a janela escondida, o vídeo para (e o ffmpeg do Zé com ele).
addEventListener("hashchange", () => { if (location.hash !== "#camera") pararVideo(); });
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") pararVideo(); });

function galeria(fotos) {
  const tirar = `<div class="botoes">${botao("Tirar foto agora", "camera-tirar", "", "discreta")}</div>`;
  if (!fotos.length) return cartao("Fotos", vazio("Nenhuma foto guardada.") + tirar);
  return cartao("Fotos", `${tirar}<div class="itens">${fotos.map((foto) => `<div class="linha-item">
    <div class="texto"><strong>${esc(hora(foto.quando))}</strong><small>${foto.lente ? `Lente ${foto.lente}` : ""}</small></div>
    ${botao("Ver foto", "camera-ver-foto", `data-nome="${esc(foto.nome)}"`, "discreta")}
    <img class="foto-impressora" data-foto="${esc(foto.nome)}" alt="Foto da câmera em ${esc(hora(foto.quando))}" hidden>
  </div>`).join("")}</div>`);
}

PAGINAS.camera = async () => {
  const c = await api("camera");
  return `${cabeca("Câmera", '<a class="acao discreta" href="#dispositivos">Dispositivos</a>')}${formulario(c)}${aoVivo(c)}${conversa(c)}${galeria(c.fotos || [])}`;
};

Object.assign(ACOES, {
  "camera-ao-vivo": (/** @type {HTMLButtonElement} */ b) => verLentes((b.dataset.lentes || "1").split(",").map(Number)),
  "camera-parar": () => pararVideo(),
  "camera-qualidade": (/** @type {HTMLButtonElement} */ b) => {
    qualidade = qualidade === "alta" ? "leve" : "alta";
    b.textContent = qualidade === "alta" ? "Qualidade alta" : "Qualidade leve";
    if (vendo.length) verLentes(vendo);
  },
  "camera-procurar": async (/** @type {HTMLButtonElement} */ b) => {
    const r = await ocupado(b, () => api("camera/procurar", {}));
    const [achada] = r.achadas;
    if (!achada) return toast(r.aviso);
    const ip = campo("camera-ip");
    if (ip) ip.value = achada.ip;
    toast(`Câmera encontrada em ${achada.ip}.`);
  },
  "camera-salvar": async (/** @type {HTMLButtonElement} */ b) => {
    const dados = {
      ip: campo("camera-ip")?.value.trim() || "",
      usuario: campo("camera-usuario")?.value.trim() || "",
      senha: campo("camera-senha")?.value || "",
      intervalo_s: Number(campo("camera-intervalo")?.value || 30),
      ligado: !!campo("camera-ligada")?.checked,
      enviar: !!campo("camera-enviar")?.checked,
      ...(document.querySelector(".camera-movimento") ? {
        sem_fotos: [...document.querySelectorAll(".camera-movimento")]
          .filter((e) => !(/** @type {HTMLInputElement} */ (e).checked))
          .map((e) => Number(/** @type {HTMLElement} */ (e).dataset.lente)),
      } : {}),
      girar: [...document.querySelectorAll(".camera-girar")]
        .filter((e) => /** @type {HTMLInputElement} */ (e).checked)
        .map((e) => Number(/** @type {HTMLElement} */ (e).dataset.lente)),
    };
    try {
      await ocupado(b, () => api("camera/salvar", dados));
      const senha = campo("camera-senha");
      if (senha) senha.value = "";
      toast("Salvo.");
      await abrir();
    } catch (erro) { toast(erro.message); }
  },
  "camera-testar": async (/** @type {HTMLButtonElement} */ b) => {
    try { toast((await ocupado(b, () => api("camera/testar", {}))).aviso); }
    catch (erro) { toast(erro.message); }
  },
  "camera-atender": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      toast((await ocupado(b, () => api("camera/atender", {}))).aviso);
      await abrir();
    } catch (erro) { toast(erro.message); }
  },
  "camera-encerrar": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      toast((await ocupado(b, () => api("camera/encerrar", {}))).aviso);
      await abrir();
    } catch (erro) { toast(erro.message); }
  },
  "camera-ver-conversa": async (/** @type {HTMLButtonElement} */ b) => {
    const falas = /** @type {HTMLElement | null} */ (document.querySelector(`[data-conversa="${CSS.escape(b.dataset.i || "")}"]`));
    if (falas) falas.hidden = !falas.hidden;
  },
  "camera-tirar": async (/** @type {HTMLButtonElement} */ b) => {
    try {
      await ocupado(b, () => api("camera/foto", {}));
      await abrir();
    } catch (erro) { toast(erro.message); }
  },
  "camera-ver-foto": async (/** @type {HTMLButtonElement} */ b) => {
    const imagem = /** @type {HTMLImageElement | null} */ (document.querySelector(`[data-foto="${CSS.escape(b.dataset.nome || "")}"]`));
    if (!imagem) return;
    if (!imagem.hidden) { imagem.hidden = true; imagem.removeAttribute("src"); return; }
    try {
      const resposta = await ocupado(b, () => api("camera/foto", { nome: b.dataset.nome }));
      imagem.src = resposta.foto;
      imagem.hidden = false;
    } catch (erro) { toast(erro.message); }
  },
});

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.camera-videos { display: grid; gap: 10px; margin-top: 10px; }
.camera-videos img { display: block; width: 100%; max-width: 960px; border-radius: 8px; background: var(--fundo-2); }
.camera-videos.varias { grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); }
` }));
