// A página Skills, carregada sob demanda pelo painel: as skills do Zé (criar, editar, ligar,
// excluir) e, só para leitura, as já instaladas no Claude Code e no Codex. O editor é um
// formulário; o SKILL.md (o formato aberto dos agentes) é montado por trás.

PAGINAS.skills = async () => {
  const [s, dosAgentes] = await Promise.all([api("skills"), api("skills/agentes")]);
  const linhas = s.map((k) => item(`${esc(k.nome)}${k.sessoes ? ' <span class="etiqueta">Sessões</span>' : ""}`, esc(k.descricao),
    liga(k.ligada, "skill", `data-nome="${esc(k.nome)}"`, "Ligada") + botao("Editar", "skill-editar", `data-nome="${esc(k.nome)}"`, "discreta") + xis("skill-excluir", `data-nome="${esc(k.nome)}"`, "Excluir"), !k.ligada));
  return `${cabeca("Skills", botao("Nova skill", "skill-nova", "", "principal"))}${sub("Procedimentos do seu jeito: o Zé e as sessões seguem antes de agir.")}
    <section class="cartao" id="editor-skill" hidden></section>
    ${s.length ? `<div class="itens">${linhas.join("")}</div>` : vazio("Nenhuma skill ainda.")}
    ${dosAgentes.length ? cartao("Skills dos agentes", `${sub("Instaladas no Claude Code e no Codex. Valem nas sessões de código daquele agente; gerenciadas no próprio agente.")}
      <div class="itens">${dosAgentes.map((k) => item(`${esc(k.nome)} <span class="etiqueta">${k.agente === "codex" ? "Codex" : "Claude"}</span>`, esc(k.descricao))).join("")}</div>`) : ""}`;
};

const SECOES_SKILL = { jeito: "Do meu jeito", passos: "Passos", pronto: "Pronto quando" };

// "Resumo do dia" -> "resumo-do-dia": o nome da pasta da skill (letras, números e hífen).
const nomeDaSkill = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48);

// O SKILL.md no modelo do Zé vira campos; fora do modelo (seções a mais), null: abre como texto.
function lerSkill(texto) {
  const m = texto.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) return null;
  const campo = (k) => (m[1].match(new RegExp(`^${k}:\\s*(.*)$`, "m")) || [, ""])[1].trim();
  const titulo = (m[2].match(/^#\s+(.*)$/m) || [, ""])[1].trim();
  const corpo = m[2].replace(/^#\s+.*\n+/, "");
  const campos = { nome: campo("name"), titulo, quando: campo("description"), sessoes: /^(sim|true|yes)$/i.test(campo("sessoes")), jeito: "", passos: "", pronto: "" };
  const partes = corpo.split(/^## /m).filter((p) => p.trim());
  for (const parte of partes) {
    const [titulo, ...resto] = parte.split("\n");
    const chave = Object.keys(SECOES_SKILL).find((k) => SECOES_SKILL[k] === titulo.trim());
    if (!chave) return null;
    campos[chave] = resto.map((l) => l.replace(/^\s*(?:[-*]|\d+\.)\s?/, "").trim()).filter(Boolean).join("\n");
  }
  return campos;
}

function montarSkill(c) {
  const lista = (t, numerada) => t.split("\n").map((l) => l.trim()).filter(Boolean).map((l, i) => `${numerada ? `${i + 1}.` : "-"} ${l}`).join("\n");
  return `---\nname: ${c.nome}\ndescription: ${c.quando.replace(/\s+/g, " ").trim()}\n${c.sessoes ? "sessoes: sim\n" : ""}---\n# ${c.titulo || c.nome}\n\n`
    + `## ${SECOES_SKILL.jeito}\n${lista(c.jeito)}\n\n## ${SECOES_SKILL.passos}\n${lista(c.passos, true)}\n\n## ${SECOES_SKILL.pronto}\n${lista(c.pronto)}\n`;
}

let skillEditada = { nome: "", nova: true, texto: false };

function editorSkill(nome, conteudo, nova) {
  const campos = nova ? { nome: "", quando: "", jeito: "", passos: "", pronto: "" } : lerSkill(conteudo);
  skillEditada = { nome, nova, texto: !campos, titulo: campos?.titulo || "" };
  const ed = $("editor-skill");
  ed.hidden = false;
  const corpo = campos
    ? `${nova ? '<label>Nome<input id="sk-titulo" placeholder="Resumo do dia" autocomplete="off"></label>' : ""}
      <label>Quando usar<input id="sk-quando" value="${esc(campos.quando)}" placeholder="Quando eu pedir o resumo do dia" autocomplete="off"></label>
      <label>Do meu jeito<textarea id="sk-jeito" rows="3" placeholder="Uma preferência por linha">${esc(campos.jeito)}</textarea></label>
      <label>Passos<textarea id="sk-passos" rows="4" placeholder="Um passo por linha">${esc(campos.passos)}</textarea></label>
      <label>Pronto quando<textarea id="sk-pronto" rows="2" placeholder="Como saber que terminou">${esc(campos.pronto)}</textarea></label>
      <label class="interruptor"><input type="checkbox" id="sk-sessoes" ${campos.sessoes ? "checked" : ""}> Também nas sessões de código</label>`
    : `${nova ? '<label>Nome<input id="sk-titulo" autocomplete="off"></label>' : ""}<textarea id="sk-texto" class="mono editor-texto" rows="16" spellcheck="false">${esc(conteudo)}</textarea>`;
  ed.innerHTML = `<h2>${nova ? "Nova skill" : esc(nome)}</h2>${corpo}
    <div class="linha">${botao("Salvar", "skill-salvar", "", "principal")}${botao("Fechar", "skill-fechar", "", "discreta")}
      ${campos ? botao("Editar como texto", "skill-texto", "", "discreta") : ""}<span class="resultado" id="sk-resultado"></span></div>`;
  ed.scrollIntoView({ block: "nearest" });
}

function conteudoDoEditor(nome) {
  if (skillEditada.texto) return $("sk-texto").value.replace(/^name: .*$/m, `name: ${nome}`);
  return montarSkill({ nome, titulo: $("sk-titulo")?.value.trim() || skillEditada.titulo, quando: $("sk-quando").value, sessoes: $("sk-sessoes")?.checked, jeito: $("sk-jeito").value, passos: $("sk-passos").value, pronto: $("sk-pronto").value });
}

Object.assign(ACOES, {
  "skill-nova": () => editorSkill("", "", true),
  "skill-editar": async (b) => { const k = await api("skill/ver", { nome: b.dataset.nome }); editorSkill(k.nome, k.conteudo, false); },
  "skill-fechar": () => { $("editor-skill").hidden = true; },
  "skill-texto": () => {
    const nome = skillEditada.nome || nomeDaSkill($("sk-titulo")?.value || "") || "nova-skill";
    const texto = conteudoDoEditor(nome), titulo = $("sk-titulo")?.value || "";
    skillEditada.texto = true;
    $("editor-skill").innerHTML = `<h2>${skillEditada.nova ? "Nova skill" : esc(skillEditada.nome)}</h2>
      ${skillEditada.nova ? `<label>Nome<input id="sk-titulo" value="${esc(titulo)}" autocomplete="off"></label>` : ""}
      <textarea id="sk-texto" class="mono editor-texto" rows="16" spellcheck="false">${esc(texto)}</textarea>
      <div class="linha">${botao("Salvar", "skill-salvar", "", "principal")}${botao("Fechar", "skill-fechar", "", "discreta")}<span class="resultado" id="sk-resultado"></span></div>`;
  },
  "skill-salvar": async (b) => {
    const nome = skillEditada.nome || nomeDaSkill($("sk-titulo")?.value || "");
    if (!nome) return mostrar("sk-resultado", false, "Dê um nome à skill.");
    if (!skillEditada.texto && !$("sk-quando").value.trim()) return mostrar("sk-resultado", false, "Diga quando usar.");
    await ocupado(b, () => api("skill/salvar", { nome, conteudo: conteudoDoEditor(nome) }));
    toast("Skill salva."); await recarregar();
  },
  "skill-excluir": (b) => confirmar(b, "Excluir?", async () => { await api("skill/excluir", { nome: b.dataset.nome }); toast("Excluída."); await recarregar(); }),
});

Object.assign(MUDAR, {
  skill: async (el) => { await api("skill/ligar", { nome: el.dataset.nome, ligada: el.checked }); toast(el.checked ? "Ligada." : "Desligada."); await recarregar(); },
});
