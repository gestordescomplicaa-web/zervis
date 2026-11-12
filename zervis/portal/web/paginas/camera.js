import { ACOES } from "../modulos/acoes.js";
import { abrir } from "../modulos/navegacao.js";
import { PAGINAS, $, api, botao, cabeca, cartao, esc, ocupado, sub, toast, vazio } from "../painel.js";

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
    ${girar(c)}
    <p class="resultado" id="camera-resultado"></p>
    <div class="botoes">${botao("Procurar na rede", "camera-procurar", "", "discreta")}${c.configurada ? botao("Testar conexão", "camera-testar", "", "discreta") : ""}${botao("Salvar", "camera-salvar", "", "principal")}</div>`);
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
  return `${cabeca("Câmera", "")}${formulario(c)}${galeria(c.fotos || [])}`;
};

Object.assign(ACOES, {
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
