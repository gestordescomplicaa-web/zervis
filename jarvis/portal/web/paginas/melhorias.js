// As melhorias do Zé (ADR 0026): o que a sessão de auto-desenvolvimento tem pronto, numa cópia
// isolada, para aprovar ou descartar. Carregado sob demanda quando a sessão do Zé abre.

let revisouProtegidos = false, verMudancas = false;

async function desenharMelhorias() {
  const caixa = $("melhorias-ze");
  if (!caixa) return;
  const m = await api("ze/melhorias", {});
  if (!m.copia) { caixa.innerHTML = ""; return; }
  const n = m.commits.length;
  if (!n && !m.sem_commit) { caixa.innerHTML = `<div class="faixa melhorias"><span>Nenhuma melhoria pendente.</span></div>`; return; }
  const resumo = `${n} ${n === 1 ? "melhoria" : "melhorias"} · ${m.arquivos.length} ${m.arquivos.length === 1 ? "arquivo" : "arquivos"}`;
  const protegidos = m.protegidos.length
    ? `<p class="aviso">Mexe na zona protegida: <span class="mono">${m.protegidos.map(esc).join(", ")}</span></p>
       <label class="interruptor"><input type="checkbox" id="revisei" ${revisouProtegidos ? "checked" : ""}> Revisei as mudanças na zona protegida</label>` : "";
  const pode = n && !m.sem_commit && (!m.protegidos.length || revisouProtegidos);
  caixa.innerHTML = `<div class="faixa melhorias"><div class="linha"><strong>Melhorias do Zé</strong><span>${resumo}</span><span class="espaco"></span>
      ${botao(verMudancas ? "Ocultar mudanças" : "Ver mudanças", "melhorias-ver", "", "discreta")}
      ${botao("Descartar", "melhorias-descartar", "", "discreta")}
      ${botao("Aprovar e aplicar", "melhorias-aplicar", pode ? "" : "disabled", "principal")}</div>
    ${m.sem_commit ? '<p class="nota">A cópia tem alterações sem commit: peça para a sessão concluir.</p>' : ""}
    ${protegidos}
    ${verMudancas ? `<pre>${esc(m.commits.join("\n"))}\n\n${esc(m.resumo)}</pre>` : ""}</div>`;
  $("revisei")?.addEventListener("change", (ev) => { revisouProtegidos = ev.target.checked; desenharMelhorias(); });
}

Object.assign(ACOES, {
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
.faixa.melhorias { display: grid; gap: 10px; margin: 0; padding: 10px 20px; border-bottom: 1px solid var(--borda);
  background: rgb(70 217 222 / .06); }
.faixa.melhorias .linha { align-items: center; }
.faixa.melhorias span { color: var(--suave); font-size: 13.5px; }
.faixa.melhorias pre { margin: 0; max-height: 40vh; overflow: auto; padding: 12px; border-radius: 10px;
  background: var(--fundo-2); font: 12px/1.5 var(--mono); white-space: pre-wrap; }
` }));
