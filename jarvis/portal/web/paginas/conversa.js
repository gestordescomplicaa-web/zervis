// A página Conversa, carregada sob demanda pelo painel: o fio de hoje com o Zé (o que a pessoa
// falou ou escreveu, as respostas e os avisos) e o campo para escrever. É onde fica o que o Zé não
// falou no Silencioso.

PAGINAS.conversa = async () => `<div class="pagina-conversa">
  <header class="conversa-cabeca">${cabeca("Conversa")}${sub("O que você falou com o Zé hoje, as respostas e os avisos.")}</header>
  <div class="fio" id="fio" aria-live="polite"></div>
  <form class="escrever" id="escrever">
    <textarea id="escrever-texto" rows="1" placeholder="Escreva para o Zé" autocomplete="off" aria-label="Mensagem"></textarea>
    <button type="submit" class="acao principal">Enviar</button>
  </form></div>`;

let fioVisto = "";
const horaFio = (q) => q.slice(11, 16);

async function desenharFio() {
  const fio = $("fio");
  if (!fio) return;
  const { itens } = await api("conversa");
  const pensando = ["pensando", "falando"].includes(estadoZe);
  const marca = `${itens.length}|${itens.at(-1)?.quando}|${pensando}`;
  if (marca === fioVisto) return;
  fioVisto = marca;
  const embaixo = fio.scrollHeight - fio.scrollTop - fio.clientHeight < 60;
  fio.innerHTML = itens.length || pensando
    ? itens.map((i) => i.tipo === "aviso"
        ? `<div class="fala aviso"><span>Aviso · ${horaFio(i.quando)}</span><p>${esc(i.texto)}</p></div>`
        : `<div class="fala ${i.tipo}"><p>${esc(i.texto)}</p><span>${horaFio(i.quando)}</span></div>`).join("")
      + (pensando ? '<div class="fala ze pensando"><p>…</p></div>' : "")
    : vazio("Nada por aqui hoje.");
  if (embaixo || !fio.dataset.lido) { fio.scrollTop = fio.scrollHeight; fio.dataset.lido = "1"; }
}

async function prepararConversa() {
  fioVisto = "";
  await desenharFio();
  relogioSessoes = setInterval(() => desenharFio().catch(() => {}), 1500);
  const campo = $("escrever-texto");
  const enviar = async (ev) => {
    ev?.preventDefault();
    const texto = campo.value.trim();
    if (!texto) return;
    const r = await api("conversa/escrever", { texto });
    if (r.aviso === "Enviado.") { campo.value = ""; campo.style.height = ""; } else toast(r.aviso);
    await desenharFio();
  };
  $("escrever").addEventListener("submit", enviar);
  campo.addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey) enviar(ev); });
  campo.addEventListener("input", () => { campo.style.height = ""; campo.style.height = Math.min(campo.scrollHeight, 160) + "px"; });
  campo.focus();
}

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.pagina-conversa { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; height: 100%; min-width: 0; flex: 1 1 auto; max-width: 860px; }
.conversa-cabeca { padding: 18px 20px 10px; }
.conversa-cabeca .sub { margin: 4px 0 0; }
.fio { overflow-y: auto; padding: 8px 20px 16px; display: flex; flex-direction: column; gap: 10px; }
.fala { max-width: 78%; display: grid; gap: 2px; }
.fala p { margin: 0; padding: 9px 13px; border-radius: 14px; white-space: pre-wrap; overflow-wrap: anywhere; }
.fala span { font-size: 11.5px; color: var(--suave); padding: 0 4px; }
.fala.voce { align-self: flex-end; justify-items: end; }
.fala.voce p { background: var(--acento-escuro); border: 1px solid var(--borda-forte); }
.fala.ze { align-self: flex-start; }
.fala.ze p { background: var(--vidro-forte); border: 1px solid var(--borda); }
.fala.pensando p { color: var(--suave); }
.fala.aviso { align-self: center; max-width: 92%; justify-items: center; text-align: center; }
.fala.aviso p { padding: 4px 10px; color: var(--suave); font-size: 13.5px; }
.escrever { display: flex; gap: 10px; align-items: flex-end; padding: 12px 20px 18px; border-top: 1px solid var(--borda); }
.escrever textarea { flex: 1; resize: none; min-height: 44px; max-height: 160px; padding: 11px 13px; border-radius: 12px;
  font: inherit; color: var(--texto); background: var(--fundo-2); border: 1px solid var(--borda-forte); }
` }));
