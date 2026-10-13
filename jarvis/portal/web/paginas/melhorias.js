// A página Autodesenvolvimento (ADR 0025, 0026 e 0028): o estado de manutenção, o diagnóstico do que
// deu errado e a sessão em que o Zé se aprimora, numa cópia isolada, com aprovar ou descartar.
// Carregada sob demanda; só no PC do Zé.

PAGINAS.melhorias = async () => {
  if (!NO_PC) return `<div class="secao">${cabeca("Autodesenvolvimento")}${sub("Disponível só no computador do Zé.")}</div>`;
  return `<div class="pagina-melhorias">
    <header class="melhorias-topo"><div><h1>Autodesenvolvimento</h1>${sub("O Zé se aprimora numa cópia isolada. Nada entra sem a sua aprovação.")}</div>
      <span class="espaco"></span><span id="manut"></span>${botao("Último diagnóstico", "diagnostico-ver", "", "discreta")}${botao("Diagnosticar", "diagnosticar", 'id="ze-diagnosticar" disabled', "principal")}</header>
    <section class="diagnostico" id="diagnostico" hidden></section>
    <div class="sessoes so-ze no-lado"><div id="lado-sessao" class="lado"></div></div></div>`;
};

let manut = { ligada: false, aguardando: false };

// O estado de manutenção no topo da página: Diagnosticar e Aplicar só valem com ele ligado.
window.desenharManutencao = (m) => {
  const caixa = $("manut");
  if (!caixa || !m) return;
  const mudou = m.ligada !== manut.ligada;
  manut = m;
  const estado = m.aguardando ? ["Aguardando sessões", "alerta"] : m.ligada ? ["Ligada", "alerta"] : ["Desligada", ""];
  caixa.innerHTML = `<span>Manutenção</span><span class="etiqueta ${estado[1]}">${estado[0]}</span>
    ${botao(m.ligada ? "Sair da manutenção" : "Entrar em manutenção", "manutencao", `data-ligar="${!m.ligada}"`, "discreta")}`;
  $("ze-diagnosticar").disabled = !m.ligada;
  if (mudou) desenharMelhorias();
};

async function prepararMelhorias() {
  if (!NO_PC) return;
  window.desenharManutencao((await api("estado")).manutencao);
  const { id } = await api("ze/sessao", {});
  sessaoAberta = id;
  await abrirSessao(id);
  relogioSessoes = setInterval(() => acompanharSessao().catch(() => {}), 1500);
}

async function mostrarDiagnostico(texto) {
  const caixa = $("diagnostico");
  caixa.hidden = false;
  caixa.innerHTML = `<pre>${esc(texto || "Nenhum diagnóstico ainda.")}</pre>`;
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
  const pode = manut.ligada && n && !m.sem_commit && (!m.protegidos.length || revisouProtegidos);
  caixa.innerHTML = `<div class="faixa melhorias"><div class="linha"><strong>Mudanças do Zé</strong><span>${resumo}</span><span class="espaco"></span>
      ${botao(verMudancas ? "Ocultar mudanças" : "Ver mudanças", "melhorias-ver", "", "discreta")}
      ${botao("Descartar", "melhorias-descartar", "", "discreta")}
      ${botao("Aprovar e aplicar", "melhorias-aplicar", pode ? "" : "disabled", "principal")}</div>
    ${m.sem_commit ? '<p class="nota">A cópia tem alterações sem commit: peça para a sessão concluir.</p>' : ""}
    ${protegidos}
    ${verMudancas ? `<pre>${esc(m.commits.join("\n"))}\n\n${esc(m.resumo)}</pre>` : ""}</div>`;
  $("revisei")?.addEventListener("change", (ev) => { revisouProtegidos = ev.target.checked; desenharMelhorias(); });
}

Object.assign(ACOES, {
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
  "melhorias-ver": async () => { verMudancas = !verMudancas; await desenharMelhorias(); },
  "melhorias-descartar": (b) => confirmar(b, "Descartar as melhorias da cópia? Isto não se desfaz.", async () => {
    const r = await api("ze/descartar", {}); toast(r.aviso); await desenharMelhorias();
  }),
  "melhorias-aplicar": async (b) => {
    const r = await ocupado(b, () => api("ze/aplicar", { revisei: revisouProtegidos }));
    toast(r.aviso); revisouProtegidos = false;
  },
});

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.pagina-melhorias { display: grid; grid-template-rows: auto auto minmax(0, 1fr); height: 100%; min-width: 0; flex: 1 1 auto; }
.melhorias-topo { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 18px 20px 12px; border-bottom: 1px solid var(--borda); }
.melhorias-topo .sub { margin: 4px 0 0; }
#manut { display: flex; gap: 8px; align-items: center; color: var(--suave); }
#manut > span:first-child { font-size: 13.5px; }
.diagnostico { padding: 0 20px 12px; border-bottom: 1px solid var(--borda); }
.diagnostico pre { margin: 12px 0 0; max-height: 34vh; overflow: auto; padding: 12px; border-radius: 10px;
  background: var(--fundo-2); font: 12px/1.5 var(--mono); white-space: pre-wrap; }
.sessoes.so-ze { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); }
.faixa.melhorias { display: grid; gap: 10px; margin: 0; padding: 10px 20px; border-bottom: 1px solid var(--borda);
  background: rgb(70 217 222 / .06); }
.faixa.melhorias .linha { align-items: center; }
.faixa.melhorias span { color: var(--suave); font-size: 13.5px; }
.faixa.melhorias pre { margin: 0; max-height: 40vh; overflow: auto; padding: 12px; border-radius: 10px;
  background: var(--fundo-2); font: 12px/1.5 var(--mono); white-space: pre-wrap; }
` }));
