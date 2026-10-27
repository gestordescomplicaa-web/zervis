// A página Atualizações, carregada sob demanda: procurar, escolher o canal e atualizar o Zé
// (zervis/versoes.py). Atualizar roda fora do Zé e o reinicia; o painel recarrega sozinho quando
// ele volta (o batimento vê o processo novo) e mostra o resultado aqui.

const CANAIS = [
  ["versoes", "Versões publicadas", "Mais seguro: só o que foi lançado como versão."],
  ["desenvolvimento", "Desenvolvimento", "Tudo o que entra no código, assim que entra."],
];
/** @type {Record<string, string>} */
const TITULO_RESULTADO = { ok: "Atualizado", nada: "Já estava em dia", voltou: "Versão anterior restaurada", falhou: "Não atualizou" };
let procurouAoAbrir = false;

PAGINAS.atualizacoes = async () => {
  const a = await api("atualizacoes");
  const u = a.ultima || {};
  const r = a.resultado || {};
  if (!u.procurado && !procurouAoAbrir) { // a primeira vez: procura sem esperar o clique
    procurouAoAbrir = true;
    api("atualizacoes/procurar", {}).then(() => { if (location.hash === "#atualizacoes") abrir(); }).catch(() => {});
  }
  if (r.rodando) relogio(navegacao, () => api("atualizacoes").then((n) => { if (!n.resultado?.rodando) abrir(); }).catch(() => {}));
  const canal = cartao("", `<div class="cabeca"><h2>Canal</h2></div>
    ${sub("De onde vêm as atualizações.")}
    <div class="modos-fala" role="radiogroup" aria-label="Canal">${CANAIS.map(([v, n, d]) => `<button type="button" role="radio" class="modo" data-acao="atualizacoes-canal" data-canal="${v}" aria-checked="${v === a.canal}" ${AJUSTES ? "" : "disabled"}><strong>${n}</strong><small>${d}</small></button>`).join("")}</div>`);
  const novidades = (u.novidades || []).map((t) => `<li>${esc(t)}</li>`).join("");
  const situacao = !u.procurado
    ? `<p class="vazio">Procurando…</p>`
    : `${sub(esc(u.texto))}
      ${novidades ? `<h3 class="subtitulo">O que muda</h3><ul class="novidades">${novidades}</ul>${u.mais ? `<p class="sub">E mais ${u.mais}.</p>` : ""}` : ""}
      <p class="sub">Instalada: ${esc(u.instalada)} · procurado ${quando(new Date(u.procurado * 1000).toISOString())}</p>
      ${u.disponivel ? (AJUSTES
        ? `<div class="linha">${botao("Atualizar agora", "atualizacoes-aplicar", "", "principal")}</div><p class="resultado" id="resultado-atualizacao"></p>`
        : `<p class="sub">Para atualizar, use o computador do Zé ou entre com o código do autenticador.</p>`) : ""}`;
  const estado = r.rodando
    ? cartao("", `<div class="cabeca"><h2>Atualizando…</h2><span class="etiqueta bom">Em andamento</span></div>${sub("O Zé reinicia e volta em alguns segundos. Se a versão nova não subir, ele volta sozinho para a anterior.")}`)
    : r.estado ? cartao("", `<div class="cabeca"><h2>Última atualização</h2><span class="etiqueta ${r.estado === "ok" || r.estado === "nada" ? "bom" : "alerta"}">${TITULO_RESULTADO[r.estado] || ""}</span></div>
        ${sub(`${esc(r.texto)} ${r.fim ? quando(new Date(r.fim * 1000).toISOString()) : ""}`)}
        ${r.registro ? `<details class="detalhes"><summary>Detalhes</summary><pre class="mono quebra">${esc(r.registro)}</pre></details>` : ""}`) : "";
  return `${cabeca("Atualizações", botao("Procurar agora", "atualizacoes-procurar"))}${sub("O Zé procura uma vez por dia e só avisa. Instalar é com você.")}
    ${r.rodando ? estado : ""}${cartao("", `<div class="cabeca"><h2>Versão</h2>${u.disponivel ? '<span class="etiqueta bom">Atualização disponível</span>' : ""}</div>${situacao}`)}${r.rodando ? "" : estado}${canal}`;
};

Object.assign(ACOES, {
  "atualizacoes-procurar": async (b) => { await ocupado(b, () => api("atualizacoes/procurar", {})); await abrir(); },
  "atualizacoes-canal": async (b) => {
    if (b.getAttribute("aria-checked") === "true") return;
    await ocupado(b, () => api("atualizacoes/canal", { canal: b.dataset.canal }));
    await abrir();
  },
  "atualizacoes-aplicar": (b) => confirmar(b, "Atualizar e reiniciar o Zé?", async () => {
    try {
      const r = await api("atualizacoes/aplicar", {});
      versaoAplicada = Date.now(); // a queda que vem é o reinício: sem a faixa de "Reconectando"
      toast(r.aviso, 6000);
      await abrir();
    } catch (erro) {
      await abrir();
      mostrar("resultado-atualizacao", false, erro.message);
    }
  }),
});
