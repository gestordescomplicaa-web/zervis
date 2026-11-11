import { escreverNoTerminal } from "./terminal.js";
import { $, TOKEN, api, botao, esc, toast, valorCampo, vazio } from "../painel.js";
import { compartilhado, carregadas } from "./estado.js";

// Os arquivos da sessão: os anexos (arrastar, colar ou "+") e o explorador da pasta, com busca e
// prévia. Usado pela página de sessões e pelas ações.

// Anexos (arrastar, colar ou "+"): o arquivo sobe para a pasta da sessão e o caminho vai para o
// terminal, onde o agente lê.
export async function anexar(lista) {
  for (const a of lista) {
    if (a.size > 20 * 1024 * 1024) { toast(a.name + ": maior que 20 MB."); continue; }
    const f = a.name ? a : new File([a], "colado-" + Date.now() + "." + (a.type.split("/")[1] || "png"), { type: a.type });
    try { escreverNoTerminal(`"${await subirAnexo(f)}" `); } catch (erro) { toast(erro.message); }
  }
  compartilhado.term?.focus();
}

async function subirAnexo(arquivo) {
  const r = await fetch(`/api/sessao/anexo?id=${encodeURIComponent(compartilhado.sessaoAberta)}&nome=${encodeURIComponent(arquivo.name)}`,
    { method: "POST", headers: { "X-Ze-Token": TOKEN, "Content-Type": "application/octet-stream" }, body: arquivo });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(arquivo.name + ": " + (dados.erro || "falha"));
  return dados.caminho;
}

// explorador
const noArvore = (i) => `<div class="no ${i.pasta ? "pasta" : ""} ${i.ignorado ? "ignorado" : ""}" role="treeitem" data-caminho="${esc(i.caminho)}" ${i.pasta ? 'aria-expanded="false"' : ""}>
  <button type="button" class="linha-no" data-acao="no" data-caminho="${esc(i.caminho)}"><span class="seta">${i.pasta ? "›" : ""}</span><span class="nome-no">${esc(i.nome)}</span>${i.ignorado ? '<span class="sinal" title="ignorado pelo git">⊘</span>' : ""}</button>
  ${i.pasta ? '<div class="filhos" role="group"></div>' : ""}</div>`;

export async function carregarPasta(caminho, recipiente) {
  const { itens } = await api("sessao/arquivos", { id: compartilhado.sessaoAberta, pasta: caminho });
  recipiente.innerHTML = itens.length ? itens.map(noArvore).join("") : vazio("vazia");
  for (const sub of compartilhado.abertas) {
    const no = /** @type {HTMLElement} */ (recipiente.querySelector(`:scope > .no[data-caminho="${CSS.escape(sub)}"]`));
    if (no) await abrirPastaNo(no);
  }
}

export async function abrirPastaNo(no) {
  no.setAttribute("aria-expanded", "true");
  compartilhado.abertas.add(no.dataset.caminho);
  await carregarPasta(no.dataset.caminho, /** @type {HTMLElement} */ (no.querySelector(".filhos")));
}

export async function atualizarArvore() {
  if (!$("arvore")) return;
  if (valorCampo("buscar-arquivos").value.trim()) await buscarArquivos(); else await carregarPasta("", $("arvore"));
}

export async function buscarArquivos() {
  const termo = valorCampo("buscar-arquivos").value.trim();
  if (termo.length < 2) { await carregarPasta("", $("arvore")); return; }
  const { achados } = await api("sessao/buscar", { id: compartilhado.sessaoAberta, termo, modo: compartilhado.modoBusca });
  $("arvore").innerHTML = achados.length
    ? achados.map((a) => `<button type="button" class="achado" data-acao="ver-arquivo" data-caminho="${esc(a.caminho)}"><span class="mono">${esc(a.caminho)}${a.linha ? ":" + a.linha : ""}</span>${a.trecho ? `<small>${esc(a.trecho)}</small>` : ""}</button>`).join("")
    : vazio("Nada encontrado.");
}

export async function verArquivo(caminho) {
  const a = await api("sessao/ver", { id: compartilhado.sessaoAberta, caminho });
  const corpo = a.tipo === "texto" ? `<pre class="codigo">${esc(a.texto)}</pre>` : a.tipo === "imagem" ? `<img class="imagem-previa" src="${a.url}" alt="">` : vazio(a.tipo === "grande" ? "Imagem grande demais." : "Sem prévia.");
  $("previa").innerHTML = `<header><span class="mono">${esc(caminho)}</span>${botao("Mencionar", "mencionar", `data-caminho="${esc(caminho)}"`)}${botao("Fechar", "previa-fechar", "", "discreta")}</header>${corpo}`;
  $("previa").hidden = false;
  $("terminal").hidden = true;
}

export function fecharPrevia() {
  if ($("previa")) { $("previa").hidden = true; $("previa").innerHTML = ""; }
  if ($("terminal")) { $("terminal").hidden = false; compartilhado.term?.focus(); }
}

// Para o núcleo do painel (as ações, a navegação), que chama este módulo depois que ele carrega.
Object.assign(carregadas, { abrirPastaNo, anexar, atualizarArvore, buscarArquivos, carregarPasta, fecharPrevia, verArquivo });
