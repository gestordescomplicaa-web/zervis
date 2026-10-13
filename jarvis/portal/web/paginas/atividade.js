// A página Atividade (ADR 0025), carregada sob demanda pelo painel: usa as funções dele.

// --- Atividade: o que o Zé fez e onde tropeçou (ADR 0025), e o registro técnico ---

const TIPOS_ATIVIDADE = { execucao: "Execução", negada: "Negada", falha: "Falha", nao_entendi: "Não entendeu", correcao: "Correção", pedido: "Pedido" };
const FILTROS_ATIVIDADE = { tudo: null, execucoes: ["execucao", "negada"], problemas: ["falha", "nao_entendi", "correcao", "negada"], pedidos: ["pedido"] };
let abaAtividade = "sinais", filtroAtividade = "problemas", nivelRegistro = "avisos";
const horaEvento = (t) => new Date(t * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

PAGINAS.atividade = async () => {
  const abas = `<div class="segmentos" role="group" aria-label="Atividade">${botao("Execuções e sinais", "atividade-aba", `data-aba="sinais" aria-pressed="${abaAtividade === "sinais"}"`)}${botao("Registro técnico", "atividade-aba", `data-aba="registro" aria-pressed="${abaAtividade === "registro"}"`)}</div>`;
  const topo = `${cabeca("Atividade")}${sub("O que o Zé executou e onde teve problemas. Fica só neste computador.")}${abas}`;
  if (abaAtividade === "registro") {
    const r = await api("atividade/registro", { nivel: nivelRegistro });
    const niveis = [["erros", "Erros"], ["avisos", "Avisos"], ["tudo", "Tudo"]].map(([v, n]) => botao(n, "registro-nivel", `data-nivel="${v}" aria-pressed="${v === nivelRegistro}"`)).join("");
    return `${topo}${cartao("", `<div class="linha"><div class="segmentos">${niveis}</div><span class="espaco"></span>${botao("Copiar diagnóstico", "registro-copiar")}</div>
      ${r.aviso ? `<p class="aviso">${esc(r.aviso)}</p>` : `<pre class="registro" id="registro">${esc(r.linhas.join("\n")) || "Nada registrado."}</pre>`}`)}`;
  }
  const { itens, resumo } = await api("atividade");
  const tipos = FILTROS_ATIVIDADE[filtroAtividade];
  const lista = itens.filter((i) => !tipos || tipos.includes(i.tipo));
  const contagem = Object.entries(TIPOS_ATIVIDADE).map(([t, n]) => `<span class="contagem" data-tipo="${t}"><strong>${resumo[t] || 0}</strong> ${n}</span>`).join("");
  const filtros = [["problemas", "Problemas"], ["execucoes", "Execuções"], ["pedidos", "Pedidos"], ["tudo", "Tudo"]].map(([v, n]) => botao(n, "atividade-filtro", `data-filtro="${v}" aria-pressed="${v === filtroAtividade}"`)).join("");
  const linha = (i) => {
    const meta = [TIPOS_ATIVIDADE[i.tipo], i.origem, i.autorizacao, i.motivo, i.erro].filter(Boolean).map(esc).join(" · ");
    const extra = { entrada: i.entrada, resultado: i.resultado, resposta: i.resposta, fala: i.fala, duracao_ms: i.duracao_ms };
    const tem = Object.values(extra).some((v) => v !== undefined && v !== "");
    return `<details class="evento" data-tipo="${i.tipo}"><summary><time>${horaEvento(i.quando)}</time><span class="marcador"></span><span class="titulo-evento">${esc(i.titulo)}</span><small>${meta}</small></summary>${tem ? `<pre>${esc(JSON.stringify(extra, null, 2))}</pre>` : ""}</details>`;
  };
  return `${topo}<p class="nota">Últimos 7 dias</p><div class="contagens">${contagem}</div>
    <div class="segmentos">${filtros}</div>
    ${cartao("", lista.length ? lista.map(linha).join("") : vazio(filtroAtividade === "problemas" ? "Nenhum problema registrado." : "Nada registrado ainda."))}`;
};

Object.assign(ACOES, {
  "atividade-aba": async (b) => { abaAtividade = b.dataset.aba; await recarregar(); },
  "atividade-filtro": async (b) => { filtroAtividade = b.dataset.filtro; await recarregar(); },
  "registro-nivel": async (b) => { nivelRegistro = b.dataset.nivel; await recarregar(); },
  "registro-copiar": async () => {
    const texto = `Zérvis · ${navigator.userAgent}\n\n${$("registro")?.textContent || ""}`;
    await navigator.clipboard.writeText(texto); toast("Diagnóstico copiado.");
  },
});

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
/* --- Atividade --- */
.contagens { display: flex; flex-wrap: wrap; gap: 8px; }
.contagem { padding: 6px 12px; border-radius: 10px; border: 1px solid var(--borda); color: var(--suave); font-size: 13px; }
.contagem strong { color: var(--texto); font-variant-numeric: tabular-nums; }
.evento { border-top: 1px solid var(--borda); }
.evento:first-child { border-top: 0; }
.evento summary { display: grid; grid-template-columns: auto 10px minmax(0, 1fr); align-items: center; gap: 2px 10px;
  padding: 10px 2px; cursor: pointer; list-style: none; }
.evento summary::-webkit-details-marker { display: none; }
.evento time { color: var(--suave); font: 12px var(--mono); }
.evento .marcador { width: 8px; height: 8px; border-radius: 50%; background: var(--acento); }
.evento[data-tipo="falha"] .marcador, .evento[data-tipo="negada"] .marcador { background: var(--erro); }
.evento[data-tipo="nao_entendi"] .marcador, .evento[data-tipo="correcao"] .marcador { background: var(--alerta); }
.evento[data-tipo="pedido"] .marcador { background: var(--suave); }
.titulo-evento { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.evento small { grid-column: 3; color: var(--suave); font-size: 12.5px; overflow-wrap: anywhere; }
.evento pre, .registro { margin: 0 0 12px; padding: 12px; border-radius: 10px; background: var(--fundo-2); overflow: auto;
  font: 12px/1.5 var(--mono); color: var(--texto); white-space: pre-wrap; overflow-wrap: anywhere; }
.registro { max-height: 60vh; }
` }));
