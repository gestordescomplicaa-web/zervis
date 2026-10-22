// A página Atendimento (ADR 0031), carregada sob demanda pelo painel: usa as funções dele.
// Um cartão por função: WhatsApp (conexão), Atendimento (o que fica ligado), Cérebro (modelo e
// chaves de API), Agente (persona, Publicar), Testar, Com você, Memória e Avisos.

const ESTADO_WHATSAPP = {
  conectado: ["Conectado", "bom"],
  aguardando: ["Aguardando leitura", "alerta"],
  preparando: ["Preparando", "alerta"],
  iniciando: ["Iniciando", "alerta"],
  conectando: ["Conectando", "alerta"],
  desconectado: ["Não conectado", "alerta"],
  desligado: ["Não conectado", "alerta"],
  indisponivel: ["Indisponível", "alerta"],
};
const MUDANDO = ["preparando", "iniciando", "aguardando", "conectando"];
// O estilo só desta página (carregado com ela, fora do peso de abertura do painel).
document.head.insertAdjacentHTML("beforeend", `<style>
.sub-titulo { margin: 18px 0 2px; color: var(--suave); font: 600 11px var(--sans); letter-spacing: .12em; text-transform: uppercase; }
.linha-item .botoes:has(input[type="password"]) { flex-wrap: nowrap; }
.linha-item .botoes input[type="password"] { width: min(240px, 100%); }
@media (max-width: 640px) {
  .linha-item .botoes:has(input[type="password"]) { flex-wrap: wrap; width: 100%; }
  .linha-item .botoes input[type="password"] { flex: 1 1 160px; width: auto; }
}</style>`);
let vigiaAtendimento = null;
let atendimentoVisto = "";
let agenteVisto = null;
let conversaTeste = [];

PAGINAS.atendimento = async () => {
  const a = await api("atendimento");
  vigiarAtendimento(a.whatsapp.estado);
  agenteVisto = a.agente;
  return `${cabeca("Atendimento")}${sub("O agente que atende seus clientes no WhatsApp, separado do Zé.")}
    <div id="cartao-whatsapp">${cartaoWhatsapp(a.whatsapp)}</div>
    ${cartaoFuncionamento(a.agente)}
    ${cartaoCerebro(a.agente.cerebro, a.chaves)}
    ${cartaoAgente(a.agente)}
    ${cartaoTeste()}
    ${cartaoComVoce(a.pausados)}
    ${cartaoMemoria(a.memoria)}
    ${cartao("", `<div class="cabeca"><h2>Avisos</h2></div>
      ${item("Lead quente", "O Zé avisa quando alguém quer comprar.", liga(a.avisos.ligado, "atendimento-avisos", "", "Avisos de lead quente"))}`)}`;
};

const etiquetaDe = (bom, texto) => `<span class="etiqueta ${bom ? "bom" : "alerta"}">${texto}</span>`;

// --- WhatsApp -------------------------------------------------------------------------------------

function cartaoWhatsapp(w) {
  const [rotulo, tom] = ESTADO_WHATSAPP[w.estado] || [w.estado, "alerta"];
  const topo = `<div class="cabeca"><h2>WhatsApp</h2><span class="etiqueta ${tom}">${esc(rotulo)}</span></div>`;
  let corpo;
  if (w.estado === "conectado") {
    corpo = item("", `Número conectado: <span class="mono">+${esc(w.numero)}</span>`, botao("Desconectar", "whatsapp-desconectar", "", "perigo"));
  } else if (w.estado === "aguardando") {
    corpo = `<div class="acesso-qr">${w.qr}<div class="campos"><p>No celular, abra o WhatsApp › Aparelhos conectados › Conectar aparelho e leia o código.</p>
      <p class="nota">O código se renova sozinho.</p></div></div>
      <div class="botoes">${botao("Cancelar", "whatsapp-desconectar", "", "discreta")}</div>`;
  } else if (MUDANDO.includes(w.estado)) {
    corpo = sub(w.estado === "preparando" ? "Preparando a conexão. Na primeira vez leva alguns minutos." : "Um momento.");
  } else if (w.estado === "indisponivel") {
    corpo = `${sub("Conecte um número de WhatsApp para o atendimento.")}
      <details class="detalhes"><summary>Detalhes</summary><p>Requer o Go instalado neste computador (go.dev/dl).</p></details>`;
  } else {
    corpo = `${sub("Conecte um número dedicado ao atendimento.")}
      ${w.falha ? `<p class="aviso">${esc(w.falha)}</p>` : ""}
      <div class="botoes">${botao("Conectar", "whatsapp-conectar", "", "principal")}</div>`;
  }
  return cartao("", topo + corpo);
}

function vigiarAtendimento(estado) {
  clearInterval(vigiaAtendimento);
  vigiaAtendimento = null;
  if (!MUDANDO.includes(estado)) return;
  vigiaAtendimento = setInterval(async () => {
    const lugar = $("cartao-whatsapp");
    if (location.hash !== "#atendimento" || !lugar) { clearInterval(vigiaAtendimento); return; }
    try {
      const a = await api("atendimento");
      const html = cartaoWhatsapp(a.whatsapp);
      if (html !== atendimentoVisto) { lugar.innerHTML = html; atendimentoVisto = html; }
      if (!MUDANDO.includes(a.whatsapp.estado)) clearInterval(vigiaAtendimento);
    } catch { /* o Zé reiniciando: tenta na próxima volta */ }
  }, 2000);
}

// --- Atendimento: o que fica ligado --------------------------------------------------------------

function cartaoFuncionamento(g) {
  const estado = !g.ligado ? "Desligado" : g.modo === "todos" ? "Respondendo a todos" : "Em teste";
  const modo = (valor, rotulo) => botao(rotulo, "agente-modo", `data-modo="${valor}" aria-pressed="${g.modo === valor}"`);
  const falta = !g.publicado ? "Publique o agente para ligar." : "";
  return cartao("", `<div class="cabeca"><h2>Atendimento</h2>${etiquetaDe(g.ligado, estado)}</div>
    <div class="itens">
      ${item("Responder no WhatsApp", falta || "O agente responde às mensagens que chegam.", liga(g.ligado, "atendente-ligado", g.publicado || g.ligado ? "" : "disabled", "Responder no WhatsApp"))}
      ${item("Atender ligações", g.ligacoes_falta && !g.ligacoes ? esc(g.ligacoes_falta) : "O agente atende as ligações do WhatsApp por voz.", liga(g.ligacoes, "atendente-ligacoes", g.ligacoes || !g.ligacoes_falta ? "" : "disabled", "Atender ligações"))}
      ${item("Para quem responde", g.modo === "teste" ? "Só os números de teste, para conferir antes de abrir." : "Qualquer conversa privada. Grupos nunca.", `<div class="segmentos" role="group" aria-label="Para quem responde">${modo("teste", "Números de teste")}${modo("todos", "Todos")}</div>`)}
    </div>
    <div class="linha" data-numeros ${g.modo === "teste" ? "" : "hidden"}>
      <label>Números de teste<input id="ag-numeros" class="mono" value="${esc(g.numeros_teste.join(", "))}" placeholder="5511999990000, 5521988880000" autocomplete="off"></label>
      ${botao("Salvar números", "agente-numeros")}
    </div>`);
}

// --- Cérebro: o modelo e as chaves de API --------------------------------------------------------

function cartaoCerebro(c, chaves) {
  const linhaChave = (k) => item(esc(k.nome),
    k.tem ? `Chave guardada ····${esc(k.fim)}` : "Sem chave.",
    k.tem
      ? `${botao("Testar", "chave-testar", `data-motor="${k.motor}"`)}${k.origem === "painel" ? botao("Remover", "chave-remover", `data-motor="${k.motor}"`, "discreta") : ""}`
      : `<input type="password" class="mono" data-chave="${k.motor}" placeholder="Cole a chave" autocomplete="off">${botao("Salvar", "chave-salvar", `data-motor="${k.motor}"`)}`);
  return cartao("", `<div class="cabeca"><h2>Cérebro</h2>${etiquetaDe(c.rapido, c.rapido ? "Rápido nas ligações" : "Assinatura")}</div>
    ${sub("O modelo que responde aos clientes, no texto e nas ligações.")}
    <div class="itens">
      ${item("Modelo", "Assinatura: sem chave, 2 a 5 segundos nas ligações. Chave de API: menos de 1 segundo.", escolha("cerebro-atendente", c.nome, c.opcoes, c.atual, "Modelo do agente"))}
    </div>
    <h3 class="sub-titulo">Chaves de API</h3>
    <div class="itens">${chaves.map(linhaChave).join("")}</div>
    <p class="nota">As chaves são as mesmas da via rápida (Modelos) e ficam só neste computador.</p>`);
}

// --- Agente: a persona ----------------------------------------------------------------------------

function cartaoAgente(g) {
  const publicacao = !g.publicado ? "Não publicado" : g.pendente ? "Alterações não publicadas" : "Publicado";
  const extra = g.outros_arquivos ? `<p class="nota">Mais ${g.outros_arquivos} ${g.outros_arquivos === 1 ? "arquivo" : "arquivos"} de conhecimento na pasta do agente.</p>` : "";
  return cartao("", `<div class="cabeca"><h2>Agente</h2>${etiquetaDe(g.publicado && !g.pendente, publicacao)}</div>
    ${sub("Quem o agente é e o que ele sabe. As mudanças valem para os clientes depois de Publicar.")}
    ${g.erro ? `<p class="aviso">${esc(g.erro)}</p>` : ""}
    <div class="campos">
      <div class="linha"><label>Nome<input id="ag-nome" value="${esc(g.nome)}" autocomplete="off"></label>
        <label>Empresa<input id="ag-empresa" value="${esc(g.empresa)}" autocomplete="off"></label></div>
      <label>Como atender<textarea id="ag-persona" rows="4" placeholder="Simpática e direta. Trata o cliente pelo nome. Nunca promete desconto.">${esc(g.persona)}</textarea></label>
      <label>O que sabe<textarea id="ag-conhecimento" rows="8" placeholder="Serviços, preços, horários, endereço, perguntas frequentes.">${esc(g.conhecimento)}</textarea></label>
      ${extra}
      <label>Quando passar para você<textarea id="ag-passar" rows="2" placeholder="${esc(g.passar_padrao)}">${esc(g.passar)}</textarea></label>
    </div>
    <div class="botoes">${botao("Publicar", "agente-publicar", "", "principal")}${botao("Salvar rascunho", "agente-salvar")}${botao("Abrir sessão", "agente-sessao")}<span class="resultado" id="ag-resultado"></span></div>
    <div class="itens" id="ag-testes" hidden></div>
    <details class="detalhes"><summary>Detalhes</summary><p>Pasta do agente: <span class="mono quebra">${esc(g.pasta)}</span></p>
      <p>Publicar roda os testes de conversa da pasta antes de valer para os clientes. "Abrir sessão" cria uma sessão de código nessa pasta.</p></details>`);
}

const camposPersona = () => ({ nome: valorCampo("ag-nome").value, empresa: valorCampo("ag-empresa").value, persona: valorCampo("ag-persona").value,
  conhecimento: valorCampo("ag-conhecimento").value, passar: valorCampo("ag-passar").value });

async function salvar(ajustes, b = null) {
  try {
    const r = await ocupado(b, () => api("atendente/salvar", ajustes));
    toast(r.aviso);
  } catch (erro) { toast(erro.message); }
  await recarregar();
}

// --- Testar, Com você, Memória ----------------------------------------------------------------------

function cartaoTeste() {
  return cartao("", `<div class="cabeca"><h2>Testar</h2></div>
    ${sub("Converse com o rascunho do agente como se fosse um cliente. Nada é enviado.")}
    <div class="itens" id="teste-conversa">${linhasTeste()}</div>
    <div class="linha"><input id="teste-texto" placeholder="Oi, quanto custa?" autocomplete="off">${botao("Enviar", "agente-testar", "", "principal")}${botao("Limpar", "agente-limpar", "", "discreta")}</div>`);
}

const linhasTeste = () => conversaTeste.map((t) => item(t.quem === "agente" ? esc(agenteVisto?.nome || "Agente") : "Cliente", esc(t.texto) + (t.passar ? `<br><span class="etiqueta alerta">Passou para você: ${esc(t.passar)}</span>` : ""))).join("") || vazio("Nenhuma mensagem.");

function cartaoComVoce(pausados) {
  const linhas = pausados.map((c) => item(esc(c.nome || "+" + c.telefone), esc(c.motivo), botao("Devolver", "agente-devolver", `data-telefone="${esc(c.telefone)}"`))).join("");
  return cartao("", `<div class="cabeca"><h2>Com você</h2></div>
    ${sub("Conversas que o agente passou para você. Ele não responde até você devolver.")}
    ${linhas || vazio("Nenhuma conversa.")}`);
}

function cartaoMemoria(m) {
  const resumo = m.contatos ? `${m.contatos} ${m.contatos === 1 ? "contato" : "contatos"}, ${m.mensagens} ${m.mensagens === 1 ? "mensagem" : "mensagens"}` : "Nenhuma conversa guardada.";
  return cartao("", `<div class="cabeca"><h2>Memória</h2></div>
    ${sub(`Cada contato tem a própria conversa, a mesma no texto e nas ligações. O agente usa as últimas ${m.lembra} mensagens.`)}
    ${item("Conversas guardadas", resumo, m.contatos ? botao("Apagar memória", "memoria-apagar", "", "perigo") : "")}
    <details class="detalhes"><summary>Detalhes</summary><p>Fica só neste computador, na pasta de dados do Zé (atendente/conversas), separada da memória do Zé. O que o agente sabe sobre a empresa vem da persona e do conhecimento, não das conversas.</p></details>`);
}

// --- ações ------------------------------------------------------------------------------------

ESCOLHAS["cerebro-atendente"] = (valor) => salvar({ cerebro: valor });

Object.assign(MUDAR, {
  "atendente-ligado": (el) => salvar({ ligado: el.checked }),
  "atendente-ligacoes": (el) => salvar({ ligacoes: el.checked }),
  "atendimento-avisos": async (el) => {
    const r = await api("mensagens/whatsapp", { ligar: el.checked });
    toast(r.aviso);
    await recarregar();
  },
});

Object.assign(ACOES, {
  "agente-modo": (b) => {
    if (b.getAttribute("aria-pressed") === "true") return;
    if (b.dataset.modo === "todos") confirmar(b, "Responder a todos os contatos?", () => salvar({ modo: "todos" }));
    else salvar({ modo: "teste" }, b);
  },
  "agente-numeros": (b) => salvar({ numeros_teste: valorCampo("ag-numeros").value }, b),
  "agente-salvar": async (b) => {
    try { await ocupado(b, () => api("atendente/salvar", camposPersona())); toast("Rascunho salvo."); }
    catch (erro) { $("ag-resultado").textContent = erro.message; return; }
    await recarregar();
  },
  "agente-publicar": async (b) => {
    let r;
    try {
      await api("atendente/salvar", camposPersona());
      $("ag-resultado").textContent = "Rodando os testes de conversa…";
      r = await ocupado(b, () => api("atendente/publicar", {}));
    } catch (erro) { $("ag-resultado").textContent = erro.message; return; }
    toast(r.aviso);
    if (r.publicado) { await recarregar(); return; }
    $("ag-resultado").textContent = r.aviso;
    const lista = $("ag-testes");
    lista.hidden = false;
    lista.innerHTML = r.resultados.map((t) => item(esc(t.nome), t.ok ? "Passou." : esc(t.falha) + (t.resposta ? `<br><small>${esc(t.resposta)}</small>` : ""), `<span class="etiqueta ${t.ok ? "bom" : "alerta"}">${t.ok ? "Passou" : "Falhou"}</span>`)).join("");
  },
  "agente-sessao": async (b) => {
    try {
      await api("atendente/salvar", camposPersona());
      const s = await ocupado(b, () => api("atendente/sessao", {}));
      sessaoAberta = s.id;
      location.hash = "#sessoes";
    } catch (erro) { $("ag-resultado").textContent = erro.message; }
  },
  "chave-salvar": async (b) => {
    const campo = /** @type {HTMLInputElement} */ (document.querySelector(`[data-chave="${b.dataset.motor}"]`));
    try {
      const r = await ocupado(b, () => api("atendente/chave", { motor: b.dataset.motor, chave: campo.value }));
      toast(r.aviso);
    } catch (erro) { toast(erro.message); return; }
    await recarregar();
  },
  "chave-testar": async (b) => {
    try {
      const r = await ocupado(b, () => api("atendente/chave", { motor: b.dataset.motor }));
      toast(r.aviso);
    } catch (erro) { toast(erro.message); }
  },
  "chave-remover": (b) => confirmar(b, "Remover a chave?", async () => {
    const r = await api("atendente/chave/apagar", { motor: b.dataset.motor });
    toast(r.aviso);
    await recarregar();
  }),
  "memoria-apagar": (b) => confirmar(b, "Apagar as conversas de todos os contatos?", async () => {
    const r = await api("atendente/esquecer", { confirmado: true });
    toast(r.aviso);
    await recarregar();
  }),
  "agente-testar": async (b) => {
    const campo = valorCampo("teste-texto");
    const texto = campo.value.trim();
    if (!texto) return;
    const historico = conversaTeste.slice();
    conversaTeste.push({ quem: "cliente", texto });
    campo.value = "";
    $("teste-conversa").innerHTML = linhasTeste();
    try {
      const r = await ocupado(b, () => api("atendente/testar", { texto, historico }));
      conversaTeste.push({ quem: "agente", texto: r.resposta, passar: r.passar });
    } catch (erro) { toast(erro.message); }
    $("teste-conversa").innerHTML = linhasTeste();
  },
  "agente-limpar": () => { conversaTeste = []; $("teste-conversa").innerHTML = linhasTeste(); },
  "agente-devolver": async (b) => {
    const r = await ocupado(b, () => api("atendente/devolver", { telefone: b.dataset.telefone }));
    toast(r.aviso);
    await recarregar();
  },
  "whatsapp-conectar": async (b) => {
    const r = await ocupado(b, () => api("whatsapp/conectar", {}));
    toast(r.aviso);
    await recarregar();
  },
  "whatsapp-desconectar": (b) => confirmar(b, "Desconectar o WhatsApp?", async () => {
    const r = await api("whatsapp/desconectar", { confirmado: true });
    toast(r.aviso);
    await recarregar();
  }),
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && /** @type {HTMLElement} */ (ev.target).id === "teste-texto") { ev.preventDefault(); /** @type {HTMLElement} */ (document.querySelector('[data-acao="agente-testar"]'))?.click(); }
});
