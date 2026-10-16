// --- Sessões: o terminal do agente, com pasta, anexos e explorador ---



let explorador = innerWidth > 1100;

/** @param {boolean} mostrar */
function mostrarExplorador(mostrar) {
  explorador = mostrar;
  document.querySelector('.conversa-topo [data-acao="explorador"]')?.setAttribute("aria-pressed", String(mostrar));
  document.querySelector(".sessao-aberta")?.classList.toggle("sem-explorador", !mostrar);
}

// Até 1100 px os arquivos ocupam o lugar do terminal. Ao estreitar a janela (dividir a tela, por
// exemplo), fecham sozinhos e o terminal continua à vista; o botão Arquivos os abre de novo.
matchMedia("(max-width: 1100px)").addEventListener("change", (e) => { if (e.matches && explorador) mostrarExplorador(false); });
let abertas = new Set();
let modoBusca = "nomes";


const matiz = (t) => [...t].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const inicial = (n) => esc((n.trim()[0] || "?").toUpperCase());
const ha = (iso) => { const s = (Date.now() - new Date(iso).getTime()) / 1000; return s < 60 ? "agora" : s < 3600 ? Math.floor(s / 60) + " min" : s < 86400 ? Math.floor(s / 3600) + " h" : Math.floor(s / 86400) + " d"; };

const pintar = (raiz) => /** @type {NodeListOf<HTMLElement>} */ (raiz.querySelectorAll(".avatar[data-matiz]")).forEach((a) => a.style.setProperty("--matiz", a.dataset.matiz));

PAGINAS.sessoes = async () => `<div class="sessoes">
  <aside class="sessoes-lista"><div class="sessoes-topo"><p class="rotulo">Sessões</p><button type="button" class="mais" data-acao="sessao-nova" aria-label="Nova sessão">+</button></div><div id="lista-sessoes"></div></aside>
  <div class="barra-voltar"><button type="button" class="voltar" data-acao="sessoes-voltar">Sessões</button></div>
  <div id="lado-sessao" class="lado"><div class="nova-sessao">${vazio("Escolha uma sessão ou crie uma no +.")}</div></div></div>`;

// No celular, uma coisa por vez: a lista ou a sessão aberta (com "Sessões" para voltar).
const mostrarLado = (sim) => /** @type {HTMLElement} */ (document.querySelector(".sessoes"))?.classList.toggle("no-lado", sim);

const itemSessao = (s) => `<button type="button" class="item-sessao" data-acao="sessao-abrir" data-id="${s.id}" aria-current="${s.id === sessaoAberta}">
  <span class="avatar ${s.estado === "trabalhando" ? "trabalhando" : ""}" data-matiz="${matiz(s.nome)}">${inicial(s.nome)}</span>
  <strong>${esc(s.nome)}</strong><time>${ha(s.atualizada)}</time><small>${s.estado === "trabalhando" ? "trabalhando…" : esc(s.resumo || s.pasta)}</small></button>`;

async function listaSessoes() {
  const lista = $("lista-sessoes");
  if (!lista) return;
  const sessoes = await api("sessoes");
  lista.innerHTML = sessoes.length ? sessoes.map(itemSessao).join("") : vazio("Nenhuma sessão.");
  pintar(lista);
  $("ponto-sessoes").hidden = !sessoes.some((s) => s.estado === "trabalhando");
}

async function formSessao() {
  mostrarLado(true);
  const pastas = await api("pastas");
  $("lado-sessao").innerHTML = `<div class="nova-sessao">${cartao("Nova sessão", `
    <label>Nome<input id="ns-nome" placeholder="Ligatia — testes" autocomplete="off"></label>
    <div class="segmentos" role="group" aria-label="Onde">${botao("Pasta existente", "ns-onde", 'data-onde="existente" aria-pressed="true"')}${botao("Projeto novo", "ns-onde", 'data-onde="novo" aria-pressed="false"')}</div>
    <div class="segmentos" role="group" aria-label="Agente">${botao("Claude", "ns-motor", 'data-motor="claude" aria-pressed="true"')}${botao("Codex", "ns-motor", 'data-motor="codex" aria-pressed="false"')}</div>
    <label id="ns-campo-pasta">Pasta<input id="ns-pasta" class="mono" list="ns-pastas" placeholder="~/projetos/…" autocomplete="off" spellcheck="false"></label>
    <datalist id="ns-pastas">${pastas.map((p) => `<option value="${esc(p)}">`).join("")}</datalist>
    <label id="ns-campo-projeto" hidden>Nome da pasta<input id="ns-projeto" class="mono" placeholder="minha-loja" autocomplete="off" spellcheck="false"></label>
    <label class="interruptor" id="ns-campo-isolada"><input type="checkbox" id="ns-isolada"> Cópia isolada (só mexe no projeto quando você aprovar)</label>
    <div class="linha">${botao("Criar", "ns-criar", "", "principal")}<span class="resultado" id="ns-resultado"></span></div>`)}</div>`;
}

// Agente e conta da sessão, trocáveis ali mesmo; a faixa avisa quando a conta acabou.
let contasSessao = { agentes: [] };

const contasComLogin = () => contasSessao.agentes.flatMap((ag) =>
  ag.contas.filter((c) => c.logado).map((c) => ({ ...c, motor: ag.id, agente: ag.nome })));

// Menu de escolha próprio do painel (o <select> nativo abre com o tema do sistema, claro no Linux):
// um botão em pílula com o valor atual e uma lista que abre para cima, com grupos e o ✓ no escolhido.




function seletorConta(sessao) {
  const grupos = contasSessao.agentes.map((ag) => ({
    titulo: ag.nome,
    itens: ag.contas.filter((c) => c.logado || c.id === sessao.conta_id).map((c) => ({
      valor: `${ag.id}|${c.id}`, nome: c.nome,
      detalhe: [c.email, c.plano && c.plano[0].toUpperCase() + c.plano.slice(1)].filter(Boolean).join(" · "),
    })),
  })).filter((g) => g.itens.length);
  const rotulo = `${sessao.agente} · ${sessao.conta || "conta em uso"}`;
  return escolha("conta-sessao", rotulo, grupos, `${sessao.motor}|${sessao.conta_id}`, "Agente e conta: a conversa continua na troca");
}

// O modelo da sessão, da lista da conta dela (com a versão); vazio é o padrão da conta.
function seletorModeloSessao(sessao) {
  if (!sessao.modelos?.length) return "";
  const itens = [{ valor: "", nome: "Padrão da conta" }, ...sessao.modelos.map((m) => ({ valor: m.id, nome: m.nome }))];
  const rotulo = sessao.modelos.find((m) => m.id === sessao.modelo)?.nome || "Padrão da conta";
  return escolha("modelo-sessao", rotulo, [{ titulo: "", itens }], sessao.modelo || "", "Modelo: a conversa continua na troca");
}

function faixaLimite(sessao) {
  if (!sessao.limite) return "";
  const outras = contasComLogin().filter((c) => c.id !== sessao.conta_id)
    .sort((a, b) => Number(b.motor === sessao.motor) - Number(a.motor === sessao.motor));
  const botoes = outras.map((c) => botao(`Continuar com ${esc(c.agente)} · ${esc(c.nome)}`, "limite-continuar",
    `data-motor="${esc(c.motor)}" data-conta="${esc(c.id)}"`, "principal")).join("");
  return `<div class="faixa limite" role="alert"><div><strong>Créditos esgotados</strong>
    <span>A conta ${esc(sessao.conta)} do ${esc(sessao.agente)} atingiu o limite de uso. Escolha outra conta para continuar de onde parou.</span></div>
    <div class="botoes">${botoes || '<span class="nota">Nenhuma outra conta com login. Adicione uma em Modelos → Contas.</span>'}</div></div>`;
}

let sessaoAtual = null;

async function trocarSessao(motor, conta, continuar) {
  const id = sessaoAberta;
  const r = await api("sessao/trocar", { id, motor, conta, continuar });
  if (sessaoAberta !== id) return;
  toast(r.aviso);
  await abrirSessao(sessaoAberta);
}

async function carregarCopia(id) {
  const area = $("copia-sessao");
  if (!area || id !== sessaoAberta) return;
  try {
    const c = await api("sessao/copia", { id });
    if (id !== sessaoAberta || !area.isConnected) return;
    if (!c.copia) { area.hidden = true; return; }
    area.hidden = false;
    const trabalhando = sessaoAtual?.estado === "trabalhando";
    const aplicar = c.commits.length && !c.sem_commit && !trabalhando;
    const descartar = (c.commits.length || c.sem_commit) && !trabalhando;
    area.innerHTML = `<div class="cabeca"><h3>Cópia isolada</h3><span class="etiqueta">${c.sem_commit ? "Sem commit" : c.commits.length ? "Com mudanças" : "Sem mudanças"}</span></div>
      ${c.arquivos.length ? `<details><summary>Arquivos alterados (${c.arquivos.length})</summary><pre>${c.arquivos.map(esc).join("\n")}</pre></details>` : ""}
      ${c.commits.length ? `<details><summary>Commits (${c.commits.length})</summary><pre>${c.commits.map(esc).join("\n")}</pre></details>` : ""}
      <div class="botoes">${botao("Aplicar", "copia-aplicar", aplicar ? "" : "disabled", "principal")}${botao("Descartar", "copia-descartar", descartar ? "" : "disabled", "discreta")}${botao("Atualizar", "copia-atualizar", "", "discreta")}</div>`;
  } catch (erro) {
    if (id !== sessaoAberta || !area.isConnected) return;
    area.hidden = false;
    area.innerHTML = `<p class="resultado erro">${esc(erro.message)}</p>${botao("Atualizar", "copia-atualizar", "", "discreta")}`;
  }
}

async function mudarCopia(acao) {
  const id = sessaoAberta;
  const r = await api(`sessao/copia/${acao}`, { id, confirmado: true });
  toast(r.aviso);
  if (id === sessaoAberta) await carregarCopia(id);
}

async function abrirSessao(id) {
  mostrarLado(true);
  sessaoAberta = id;
  /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll(".item-sessao")).forEach((b) => b.setAttribute("aria-current", String(b.dataset.id === id)));
  const [{ sessao }, ct] = await Promise.all([api("sessao/ler", { id, desde: 1e9 }), api("contas")]);
  if (sessaoAberta !== id || !$("lado-sessao")) return;
  contasSessao = ct;
  sessaoAtual = sessao;
  const lado = $("lado-sessao");
  const trabalhando = sessao.estado === "trabalhando";
  lado.innerHTML = `<div class="sessao-aberta ${explorador ? "" : "sem-explorador"}"><section class="conversa">
    <header class="conversa-topo"><span class="avatar" data-matiz="${matiz(sessao.nome)}">${inicial(sessao.nome)}</span>
      <div class="titulo-sessao"><h2>${esc(sessao.nome)}</h2><small title="${esc(sessao.pasta)}">${esc(sessao.pasta)}${sessao.branch ? " · cópia isolada" : ""}</small></div>
      <div class="ajustes-sessao" id="ajustes-sessao">${seletorConta(sessao)}${seletorModeloSessao(sessao)}</div>
      <span class="etiqueta ${trabalhando ? "bom" : sessao.limite ? "alerta" : ""}" id="estado-sessao" data-estado="${esc(sessao.estado)}">${esc(estadoSessao(sessao))}</span>
      <div class="botoes"><button type="button" class="mais" data-acao="anexar" aria-label="Anexar arquivo" title="Anexar arquivo (ou arraste, ou cole uma imagem)">+</button><input type="file" id="arquivos" multiple hidden>
        ${botao("Interromper", "sessao-interromper", 'id="interromper-trabalho" hidden', "discreta")}${botao("Arquivos", "explorador", `aria-pressed="${explorador}"`)}${botao("Excluir", "sessao-excluir", 'title="Excluir sessão"', "discreta")}</div></header>
    <div id="excluir-sessao"></div>
    <div id="interromper-sessao"></div>
    <div id="limite-sessao" data-limite="${sessao.limite}">${faixaLimite(sessao)}</div>
    ${sessao.interrompida ? `<div id="interrompida-sessao" class="faixa limite" role="alert"><div><strong>Tarefa interrompida</strong>
      <span>${esc(sessao.interrompida)}</span></div><div class="botoes">${botao("Continuar", "interrompida-continuar", "", "principal")}${botao("Dispensar", "interrompida-dispensar", "", "discreta")}</div></div>` : ""}
    <section id="copia-sessao" class="cartao" hidden></section>
    <div id="melhorias-ze"></div>
    <div id="reserva-sessoes" class="faixa limite" role="status" hidden><div><strong>Atualização em andamento</strong>
      <span>Novos comandos bloqueados até a conclusão.</span></div></div>
    <section class="editor-md" id="editor-md" hidden>
      <div class="linha"><label>Arquivo<input id="md-nome" class="mono" placeholder="NOTAS.md" autocomplete="off" spellcheck="false"></label>
        <label class="interruptor"><input type="checkbox" id="md-substituir"> Substituir se existir</label></div>
      <textarea id="md-texto" class="mono" rows="10"></textarea>
      <div class="linha">${botao("Salvar na pasta", "md-salvar", "", "principal")}${botao("Cancelar", "md-fechar", "", "discreta")}</div>
    </section>
    <section class="previa-arquivo" id="previa" hidden></section>
    <div class="terminal-sessao" id="terminal"></div>
    <div class="terminal-fechado" id="terminal-fechado" hidden><strong>Terminal fechado</strong>
      <span>Ao reabrir, a conversa continua de onde parou.</span>${botao("Reabrir", "terminal-reabrir", "", "principal")}</div>
    </section>
    <aside class="explorador" aria-label="Arquivos">
      <header><strong title="${esc(sessao.pasta)}">${esc(sessao.pasta.split("/").pop())}</strong>
        <button type="button" class="icone" data-acao="md-abrir" title="Novo arquivo" aria-label="Novo arquivo">+</button>
        <button type="button" class="icone" data-acao="arvore-recolher" title="Recolher tudo" aria-label="Recolher tudo">⇤</button>
        <button type="button" class="icone" data-acao="arvore-atualizar" title="Atualizar" aria-label="Atualizar">↻</button>
        <button type="button" class="icone" id="fechar-explorador" data-acao="explorador" title="Voltar ao terminal" aria-label="Voltar ao terminal">✕</button></header>
      <input id="buscar-arquivos" type="search" placeholder="Buscar" autocomplete="off" spellcheck="false">
      <div class="seg" role="group" aria-label="Buscar por">${botao("Nome", "busca-modo", 'data-modo="nomes" aria-pressed="true"')}${botao("Conteúdo", "busca-modo", 'data-modo="conteudo" aria-pressed="false"')}</div>
      <div class="arvore" id="arvore" role="tree"></div>
    </aside></div>`;
  pintar(lado);
  abertas = new Set();
  travarAjustes(trabalhando);
  // A faixa de mudanças entra antes do terminal medir a tela: depois, ela o encolheria logo ao
  // abrir, e o agente redesenharia duas vezes (o que embaralha a tela dele).
  if (sessao.melhorias) await carregarPagina("melhorias").then(() => desenharMelhorias()).catch(() => {});
  if (!(sessao.melhorias && window.unificandoSessoes)) await abrirTerminal(id);
  await carregarPasta("", $("arvore"));
  if (sessao.isolada && !sessao.melhorias) await carregarCopia(id);
}

async function acompanharSessao() {
  if (!sessaoAberta || !$("terminal")) return;
  const id = sessaoAberta;
  const { sessao } = await api("sessao/ler", { id, desde: 1e9 });
  if (sessaoAberta !== id || !$("estado-sessao")) return;
  if (sessaoAtual?.conta_id !== sessao.conta_id || sessaoAtual?.motor !== sessao.motor || sessaoAtual?.modelo !== sessao.modelo) {
    fecharEscolhas();
    $("ajustes-sessao").innerHTML = seletorConta(sessao) + seletorModeloSessao(sessao);
  }
  sessaoAtual = sessao;
  const etiqueta = $("estado-sessao");
  if (etiqueta.dataset.estado === "trabalhando" && sessao.estado !== "trabalhando") {
    atualizarArvore();
    if (sessao.melhorias) window.desenharMelhorias?.();
  }
  etiqueta.dataset.estado = sessao.estado;
  etiqueta.textContent = estadoSessao(sessao);
  etiqueta.classList.toggle("alerta", !!sessao.limite);
  etiqueta.classList.toggle("bom", sessao.estado === "trabalhando");
  travarAjustes(sessao.estado === "trabalhando");
  if (sessao.isolada && !sessao.melhorias && etiqueta.dataset.copiaEstado !== sessao.estado) {
    etiqueta.dataset.copiaEstado = sessao.estado;
    carregarCopia(sessao.id);
  }
  const faixa = $("limite-sessao");
  const versaoLimite = JSON.stringify([sessao.limite, sessao.conta_id, sessao.motor]);
  if (faixa.dataset.limite !== versaoLimite) {
    faixa.dataset.limite = versaoLimite;
    faixa.innerHTML = faixaLimite(sessao);
  }
}

/** @param {number} vez */
async function prepararSessoes(vez) {
  await listaSessoes();
  if (vez !== navegacao) return;
  // A sessão do Zé (Melhorias) não abre aqui: só as que estão na lista.
  if (sessaoAberta && !/** @type {HTMLElement} */ (document.querySelector(`.item-sessao[data-id="${sessaoAberta}"]`))) sessaoAberta = null;
  if (sessaoAberta) await abrirSessao(sessaoAberta).catch(() => { sessaoAberta = null; });
  let volta = 0;
  relogio(vez, async () => {
    try { await acompanharSessao(); if (++volta % 2 === 0) await listaSessoes(); } catch { /* o batimento mostra se o Zé caiu */ }
  });
}

// Anexos (arrastar, colar ou "+"): o arquivo sobe para a pasta da sessão e o caminho vai para o
// terminal, onde o agente lê.
async function anexar(lista) {
  for (const a of lista) {
    if (a.size > 20 * 1024 * 1024) { toast(a.name + ": maior que 20 MB."); continue; }
    const f = a.name ? a : new File([a], "colado-" + Date.now() + "." + (a.type.split("/")[1] || "png"), { type: a.type });
    try { escreverNoTerminal(`"${await subirAnexo(f)}" `); } catch (erro) { toast(erro.message); }
  }
  term?.focus();
}

async function subirAnexo(arquivo) {
  const r = await fetch(`/api/sessao/anexo?id=${encodeURIComponent(sessaoAberta)}&nome=${encodeURIComponent(arquivo.name)}`,
    { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: arquivo });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(arquivo.name + ": " + (dados.erro || "falha"));
  return dados.caminho;
}

// explorador
const noArvore = (i) => `<div class="no ${i.pasta ? "pasta" : ""} ${i.ignorado ? "ignorado" : ""}" role="treeitem" data-caminho="${esc(i.caminho)}" ${i.pasta ? 'aria-expanded="false"' : ""}>
  <button type="button" class="linha-no" data-acao="no" data-caminho="${esc(i.caminho)}"><span class="seta">${i.pasta ? "›" : ""}</span><span class="nome-no">${esc(i.nome)}</span>${i.ignorado ? '<span class="sinal" title="ignorado pelo git">⊘</span>' : ""}</button>
  ${i.pasta ? '<div class="filhos" role="group"></div>' : ""}</div>`;

async function carregarPasta(caminho, recipiente) {
  const { itens } = await api("sessao/arquivos", { id: sessaoAberta, pasta: caminho });
  recipiente.innerHTML = itens.length ? itens.map(noArvore).join("") : vazio("vazia");
  for (const sub of abertas) {
    const no = /** @type {HTMLElement} */ (recipiente.querySelector(`:scope > .no[data-caminho="${CSS.escape(sub)}"]`));
    if (no) await abrirPastaNo(no);
  }
}

async function abrirPastaNo(no) {
  no.setAttribute("aria-expanded", "true");
  abertas.add(no.dataset.caminho);
  await carregarPasta(no.dataset.caminho, /** @type {HTMLElement} */ (no.querySelector(".filhos")));
}

async function atualizarArvore() {
  if (!$("arvore")) return;
  if (valorCampo("buscar-arquivos").value.trim()) await buscarArquivos(); else await carregarPasta("", $("arvore"));
}

async function buscarArquivos() {
  const termo = valorCampo("buscar-arquivos").value.trim();
  if (termo.length < 2) { await carregarPasta("", $("arvore")); return; }
  const { achados } = await api("sessao/buscar", { id: sessaoAberta, termo, modo: modoBusca });
  $("arvore").innerHTML = achados.length
    ? achados.map((a) => `<button type="button" class="achado" data-acao="ver-arquivo" data-caminho="${esc(a.caminho)}"><span class="mono">${esc(a.caminho)}${a.linha ? ":" + a.linha : ""}</span>${a.trecho ? `<small>${esc(a.trecho)}</small>` : ""}</button>`).join("")
    : vazio("Nada encontrado.");
}

async function verArquivo(caminho) {
  const a = await api("sessao/ver", { id: sessaoAberta, caminho });
  const corpo = a.tipo === "texto" ? `<pre class="codigo">${esc(a.texto)}</pre>` : a.tipo === "imagem" ? `<img class="imagem-previa" src="${a.url}" alt="">` : vazio(a.tipo === "grande" ? "Imagem grande demais." : "Sem prévia.");
  $("previa").innerHTML = `<header><span class="mono">${esc(caminho)}</span>${botao("Mencionar", "mencionar", `data-caminho="${esc(caminho)}"`)}${botao("Fechar", "previa-fechar", "", "discreta")}</header>${corpo}`;
  $("previa").hidden = false;
  $("terminal").hidden = true;
}

function fecharPrevia() {
  if ($("previa")) { $("previa").hidden = true; $("previa").innerHTML = ""; }
  if ($("terminal")) { $("terminal").hidden = false; term?.focus(); }
}
