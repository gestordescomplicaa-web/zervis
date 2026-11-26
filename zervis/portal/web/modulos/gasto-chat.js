// O gasto de cada resposta do chat (pedido de 27/10/2026: entender como o Zé gasta os tokens), por
// parte: a via rápida, o cérebro e a pesquisa; e o do dia, com o que rodou em segundo plano.
import { esc } from "../painel.js";

const ROTULOS_DO_GASTO = { rapida: "Respostas rápidas", completo: "Cérebro", pesquisa: "Pesquisa na internet" };
/** 840, "14,2 mil", "1,3 mi". */
const tokens = (n) => n < 1000 ? String(n) : n < 1e6 ? `${(n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: n < 1e4 ? 1 : 0 })} mil` : `${(n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
const lidos = (p) => (p.entrada || 0) + (p.cache_lido || 0) + (p.cache_criado || 0);
const somaPartes = (partes) => partes.reduce((t, p) => ({ lidos: t.lidos + lidos(p), cache: t.cache + (p.cache_lido || 0), saida: t.saida + (p.saida || 0) }), { lidos: 0, cache: 0, saida: 0 });
// O que pesa de verdade é o novo: o lido do cache custa uma fração e não esgota a conta igual.
const resumo = (t) => `${tokens(t.lidos - t.cache)} novos + ${tokens(t.cache)} do cache · ${tokens(t.saida)} gerados`;

/** A linha do gasto de uma resposta e, ao abrir, cada parte. */
export function gastoDaResposta(g) {
  if (!g?.partes?.length) return "";
  const t = somaPartes(g.partes);
  const partes = g.partes.map((p) => `<li><b>${esc(ROTULOS_DO_GASTO[p.rotulo] || p.rotulo)}</b>${p.modelo ? ` · ${esc(p.modelo)}` : ""}<br>${tokens(lidos(p))} lidos (${tokens(p.cache_lido || 0)} em cache${p.cache_criado ? `, ${tokens(p.cache_criado)} gravados no cache` : ""}) · ${tokens(p.saida || 0)} gerados</li>`).join("");
  const ferramentas = g.ferramentas?.length ? `<li><b>Ferramentas</b><br>${esc(g.ferramentas.join(", "))}</li>` : "";
  return `<details class="gasto"><summary>${resumo(t)}</summary><ul>${partes}${ferramentas}</ul></details>`;
}

/** O dia: as respostas com gasto, as resolvidas sem modelo e o segundo plano. */
export function consumoDoDia(itens, consumo) {
  const gastos = itens.filter((i) => i.gasto?.partes?.length).map((i) => somaPartes(i.gasto.partes));
  const t = gastos.reduce((a, g) => ({ lidos: a.lidos + g.lidos, cache: a.cache + g.cache, saida: a.saida + g.saida }), { lidos: 0, cache: 0, saida: 0 });
  const partes = [];
  if (gastos.length) {
    const novos = t.lidos - t.cache + t.saida;
    partes.push(`Hoje: ${gastos.length} ${gastos.length === 1 ? "resposta" : "respostas"} · ${resumo(t)} · média de ${tokens(Math.round(novos / gastos.length))} novos por resposta`);
  }
  if (consumo?.locais) partes.push(`${consumo.locais} sem modelo`);
  const f = consumo?.fundo;
  if (f && consumo.fundo_vezes) partes.push(`segundo plano: ${tokens(lidos(f) + (f.saida || 0))} tokens em ${consumo.fundo_vezes} ${consumo.fundo_vezes === 1 ? "tarefa" : "tarefas"}`);
  return partes.join(" · ");
}

document.head.appendChild(Object.assign(document.createElement("style"), { textContent: `
.gasto { font-size: 11.5px; color: var(--suave); padding: 0 4px; font-variant-numeric: tabular-nums; }
.gasto summary { cursor: pointer; list-style: none; width: fit-content; }
.gasto summary::-webkit-details-marker { display: none; }
.gasto summary::after { content: " ▾"; opacity: .7; }
.gasto[open] summary::after { content: " ▴"; }
.gasto ul { margin: 6px 0 2px; padding: 8px 10px; list-style: none; display: grid; gap: 6px; border: 1px solid var(--borda); border-radius: 10px; background: var(--fundo-2); }
.gasto b { color: var(--texto); font-weight: 600; }
` }));
