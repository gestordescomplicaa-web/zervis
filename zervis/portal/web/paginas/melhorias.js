// A página Autodesenvolvimento (ADR 0025, 0026 e 0028): o estado de manutenção, o diagnóstico do que
// deu errado e a sessão em que o Zé se aprimora, numa cópia isolada, com aprovar ou descartar.
// Carregada sob demanda; só no PC do Zé.

PAGINAS.melhorias = async () => {
  if (!AJUSTES) return `<div class="secao">${cabeca("Autodesenvolvimento")}${sub("Disponível no computador do Zé ou, num servidor, entrando com o código do autenticador.")}</div>`;
  return `<div class="pagina-melhorias">
    <header class="melhorias-topo"><div><h1>Autodesenvolvimento</h1>${sub("Revise e aplique melhorias. Acompanhe a atualização até o reinício.")}</div>
      <span class="espaco"></span><span id="manut"></span>${botao("Último diagnóstico", "diagnostico-ver", "", "discreta")}${botao("Diagnosticar", "diagnosticar", 'id="ze-diagnosticar" disabled', "principal")}</header>
    <section class="diagnostico" id="diagnostico" hidden></section>
    <section class="centralizacao" id="centralizacao" hidden></section>
    <div class="sessoes so-ze no-lado"><div id="lado-sessao" class="lado"></div></div></div>`;
};

let manut = { ligada: false, aguardando: false };
let centralEscolhida = "", estadoCentral = "";

async function acompanharCentral() {
  const vez = navegacao;
  const c = await api("ze/central", {});
  const caixa = $("centralizacao");
  if (!caixa || vez !== navegacao) return c;
  const mudou = estadoCentral === "em_andamento" && c.estado === "concluida";
  if (!!window.unificandoSessoes !== (c.estado === "em_andamento")) cicloAtualizacao++;
  window.unificandoSessoes = c.estado === "em_andamento";
  estadoCentral = c.estado;
  centralEscolhida = c.sessao || centralEscolhida;
  const varias = c.candidatas.length > 1;
  const ocupada = c.estado === "em_andamento";
  // Depois de unificar, a sessão é o estado normal da página, sem um cartão permanente.
  caixa.hidden = !varias && !ocupada && !["erro", "interrompida"].includes(c.estado);
  window.desenharTravaSessoes?.();
  const trava = ocupada || atualizando() || !centralEscolhida || (sessaoAtual?.melhorias && sessaoAtual.estado === "trabalhando");
  const unificar = /** @type {HTMLButtonElement | null} */ (caixa.querySelector('[data-acao="central-unificar"]'));
  if (unificar) unificar.disabled = trava;
  const versao = JSON.stringify([c, atualizando()]);
  if (caixa.dataset.versao === versao) return c;
  caixa.dataset.versao = versao;
  caixa.innerHTML = caixa.hidden ? "" : `<div class="linha"><strong>Sessão central</strong><span class="espaco"></span>
    <span class="etiqueta">${ocupada ? "Unificando" : c.estado === "erro" ? "Pendente" : varias ? "A unificar" : c.estado === "concluida" ? "Unificada" : "Única"}</span></div>
    <p class="nota">${varias ? `${c.candidatas.length} sessões encontradas. Reúna o trabalho na sessão central.` : "A mesma sessão para todas as contas e modelos."}</p>
    ${varias ? `<details><summary>Ver sessões</summary><ul>${c.candidatas.map(s => `<li>${esc(s.motor === "codex" ? "Codex" : "Claude")} · ${esc(s.conta_nome || "Conta em uso")} · ${esc(s.id)}${s.id === c.sessao ? " · Atual" : ""}</li>`).join("")}</ul></details>` : ""}
    ${varias && !c.sessao ? `<label>Sessão central <select id="central-escolhida"><option value="">Selecione uma sessão</option>${c.candidatas.map(s => `<option value="${esc(s.id)}" ${centralEscolhida === s.id ? "selected" : ""}>${esc(s.motor)} · ${esc(s.id)}</option>`).join("")}</select></label>` : ""}
    ${c.aviso ? `<p role="status">${esc(c.aviso)}</p>` : ""}
    ${varias ? botao("Unificar sessões", "central-unificar", trava ? "disabled" : "", "discreta") : ""}`;
  $("central-escolhida")?.addEventListener("change", ev => {
    centralEscolhida = /** @type {HTMLSelectElement} */ (ev.target).value;
    const b = caixa.querySelector("button");
    if (b) b.disabled = !centralEscolhida || ocupada || atualizando();
  });
  if (mudou && c.sessao) {
    toast("Sessões unificadas. Histórico preservado.");
    revisouProtegidos = false;
    sessaoAberta = c.sessao;
    await abrirSessao(c.sessao);
  }
  return c;
}

// O estado de manutenção no topo da página: Diagnosticar e Aplicar só valem com ele ligado.
window.desenharManutencao = (m) => {
  const caixa = $("manut");
  if (!caixa || !m) return;
  const mudou = m.ligada !== manut.ligada;
  manut = m;
  const estado = m.aguardando ? ["Aguardando sessões", "alerta"] : m.ligada ? ["Ligada", "alerta"] : ["Desligada", ""];
  caixa.innerHTML = `<span>Manutenção</span><span class="etiqueta ${estado[1]}">${estado[0]}</span>
    ${botao(m.ligada ? "Sair da manutenção" : "Entrar em manutenção", "manutencao", `data-ligar="${!m.ligada}"`, "discreta")}`;
  valorCampo("ze-diagnosticar").disabled = !m.ligada;
  if (mudou) desenharMelhorias();
};

/** @param {number} vez */
async function prepararMelhorias(vez) {
  if (!AJUSTES) return;
  window.desenharManutencao((await api("estado")).manutencao);
  const c = await acompanharCentral();
  if (vez !== navegacao) return;
  if (!c.sessao && c.candidatas.length > 1) {
    relogio(vez, () => acompanharMelhorias().catch(() => {}));
    return;
  }
  const { id } = await api("ze/sessao", {});
  if (vez !== navegacao) return;
  sessaoAberta = id;
  await abrirSessao(id);
  relogio(vez, () => acompanharMelhorias().catch(() => {}));
}

async function acompanharMelhorias() {
  const central = await acompanharCentral();
  if (central.estado !== "em_andamento") await acompanharSessao();
}

async function mostrarDiagnostico(texto) {
  const caixa = $("diagnostico");
  caixa.hidden = false;
  caixa.innerHTML = `<pre>${esc(texto || "Nenhum diagnóstico ainda.")}</pre>
    <div class="linha botoes">${botao("Recomeçar diagnóstico", "diagnostico-recomecar", 'title="O próximo diagnóstico conta a partir de agora. O histórico continua na Atividade."', "discreta")}</div>`;
}

let revisouProtegidos = false, verMudancas = false;

async function desenharMelhorias() {
  const caixa = $("melhorias-ze");
  if (!caixa) return;
  const m = await api("ze/melhorias", {});
  if (!m.copia) { caixa.innerHTML = ""; return; }
  const n = m.commits.length;
  if (!n && !m.sem_commit) { caixa.innerHTML = `<div class="faixa melhorias"><span>Nenhuma mudança pendente.</span></div>`; return; }
  const resumo = `${n} ${n === 1 ? "mudança" : "mudanças"} · ${m.arquivos.length} ${m.arquivos.length === 1 ? "arquivo" : "arquivos"}`;
  const protegidos = m.protegidos.length
    ? `<p class="aviso">Mexe na zona protegida: <span class="mono">${m.protegidos.map(esc).join(", ")}</span></p>
       <label class="interruptor"><input type="checkbox" id="revisei" ${revisouProtegidos ? "checked" : ""}> Revisei as mudanças na zona protegida</label>` : "";
  const trabalhando = sessaoAtual?.estado === "trabalhando";
  const pode = !trabalhando && !atualizando() && !window.unificandoSessoes && manut.ligada && n && !m.sem_commit && (!m.protegidos.length || revisouProtegidos);
  caixa.innerHTML = `<div class="faixa melhorias"><div class="linha"><strong>Mudanças do Zé</strong><span>${resumo}</span><span class="espaco"></span>
      ${botao(verMudancas ? "Ocultar mudanças" : "Ver mudanças", "melhorias-ver", "", "discreta")}
      ${botao("Descartar", "melhorias-descartar", atualizando() || window.unificandoSessoes ? "disabled" : "", "discreta")}
      ${botao("Aprovar e aplicar", "melhorias-aplicar", pode ? "" : "disabled", "principal")}</div>
    ${m.sem_commit ? '<p class="nota">A cópia tem alterações sem commit: peça para a sessão concluir.</p>' : ""}
    ${!manut.ligada ? `<div class="linha"><span>Manutenção desligada.</span>${botao("Entrar em manutenção", "manutencao", 'data-ligar="true"', "discreta")}</div>` : ""}
    ${trabalhando ? '<p class="nota">Trabalho em andamento. Aguarde ou interrompa para aplicar.</p>' : ""}
    ${protegidos}
    ${verMudancas ? `<pre>${esc(m.commits.join("\n"))}\n\n${esc(m.resumo)}</pre>` : ""}</div>`;
  $("revisei")?.addEventListener("change", (ev) => { revisouProtegidos = /** @type {HTMLInputElement} */ (ev.target).checked; desenharMelhorias(); });
}

Object.assign(ACOES, {
  "central-unificar": (b) => confirmar(b, "Unificar as sessões e preservar as origens como histórico?", async () => {
    const r = await api("ze/unificar", { confirmado: true, sessao: centralEscolhida });
    revisouProtegidos = false;
    toast(r.aviso);
    await acompanharCentral();
  }),
  manutencao: async (b) => {
    const r = await ocupado(b, () => api("ze/manutencao", { ligar: b.dataset.ligar === "true" }));
    toast(r.aviso);
    const e = await api("estado");
    document.body.classList.toggle("manutencao", e.manutencao.ligada); window.desenharManutencao(e.manutencao);
  },
  diagnosticar: async (b) => {
    const r = await ocupado(b, () => api("ze/diagnosticar", {}));
    await mostrarDiagnostico(r.relatorio); toast(r.aviso);
  },
  "diagnostico-ver": async () => {
    const caixa = $("diagnostico");
    if (!caixa.hidden) { caixa.hidden = true; return; }
    await mostrarDiagnostico((await api("ze/diagnostico", {})).relatorio);
  },
  "diagnostico-recomecar": (b) => confirmar(b, "Recomeçar o diagnóstico a partir de agora?", async () => {
    const r = await api("ze/diagnostico/recomecar", {}); toast(r.aviso);
    $("diagnostico").hidden = true;
  }),
  "melhorias-ver": async () => { verMudancas = !verMudancas; await desenharMelhorias(); },
  "melhorias-descartar": (b) => confirmar(b, "Descartar as melhorias da cópia? Isto não se desfaz.", async () => {
    const r = await api("ze/descartar", {}); toast(r.aviso); await desenharMelhorias();
  }),
  "melhorias-aplicar": async (b) => {
    const r = await ocupado(b, () => api("ze/aplicar", { revisei: revisouProtegidos }));
    toast(r.aviso); revisouProtegidos = false;
    desenharAtualizacao((await api("estado")).atualizacao ?? null);
    await desenharMelhorias();
  },
});

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.pagina-melhorias { display: grid; grid-template-rows: auto auto auto minmax(0, 1fr); height: 100%; min-width: 0; flex: 1 1 auto; }
.centralizacao { padding: 10px 20px; border-bottom: 1px solid var(--borda); }
.melhorias-topo { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 18px 20px 12px; border-bottom: 1px solid var(--borda); }
.melhorias-topo .sub { margin: 4px 0 0; }
#manut { display: flex; gap: 8px; align-items: center; color: var(--suave); }
#manut > span:first-child { font-size: 13.5px; }
.diagnostico { padding: 0 20px 12px; border-bottom: 1px solid var(--borda); }
.diagnostico .linha { justify-content: flex-end; margin-top: 10px; }
.diagnostico pre { margin: 12px 0 0; max-height: 34vh; overflow: auto; padding: 12px; border-radius: 10px;
  background: var(--fundo-2); font: 12px/1.5 var(--mono); white-space: pre-wrap; }
.sessoes.so-ze { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); }
/* Linhas fixas: o diagnóstico oculto sai da grade, e a sessão caía na linha da altura do conteúdo. */
.pagina-melhorias > .melhorias-topo { grid-row: 1; }
.pagina-melhorias > .diagnostico { grid-row: 2; }
.pagina-melhorias > .centralizacao { grid-row: 3; }
.pagina-melhorias > .sessoes { grid-row: 4; }
.faixa.melhorias { display: grid; gap: 10px; margin: 0; padding: 10px 20px; border-bottom: 1px solid var(--borda);
  background: rgb(70 217 222 / .06); }
.faixa.melhorias .linha { align-items: center; }
.faixa.melhorias span { color: var(--suave); font-size: 13.5px; }
.faixa.melhorias pre { margin: 0; max-height: 40vh; overflow: auto; padding: 12px; border-radius: 10px;
  background: var(--fundo-2); font: 12px/1.5 var(--mono); white-space: pre-wrap; }
` }));
