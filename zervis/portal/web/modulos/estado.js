// O estado que mais de um arquivo do painel muda, num lugar só (painel em módulos ES). Ao lado de
// cada um, o arquivo que o declarava antes.

export const compartilhado = {
  abertas: new Set(), // paginas/sessoes.js
  /** @type {Record<string, any>} */ acessoTela: {}, // modulos/modelos.js
  agentes: [], // modulos/modelos.js
  atualizacaoRecebida: 0, // modulos/navegacao.js
  buscaPendente: null, // painel.js
  cicloAtualizacao: 0, // modulos/navegacao.js
  codigoPreparado: null, // modulos/voz.js
  contasTela: { agentes: [] }, // modulos/modelos.js
  escuta: {}, // modulos/modelos.js
  estadoZe: "inativo", // modulos/imersao.js
  explorador: innerWidth > 1100, // modulos/paineis-sessao.js
  filaEscrita: Promise.resolve(), // painel.js
  filaTerminalWs: [], // painel.js
  loginTela: null, // modulos/modelos.js
  /** @type {Record<string, any>} */ modelo: {}, // modulos/modelos.js
  modoBusca: "nomes", // paginas/sessoes.js
  // Cada troca de página ganha um número. Clicando rápido, a página anterior ainda espera o Zé
  // quando a nova abre: ao voltar, ela não desenha, não mostra erro e não liga relógio.
  navegacao: 0, // painel.js
  passo: 1, // modulos/modelos.js
  prazoTerminalWs: null, // painel.js
  sessaoAberta: null, // painel.js
  sessaoAtual: null, // paginas/sessoes.js
  term: null, // painel.js
  termId: null, // painel.js
  termObservador: null, // painel.js
  // Cancela a leitura do terminal aberto. A leitura espera novidade por até 20 s; sem cancelar,
  // cada troca de aba deixava uma presa, e seis presas esgotam as conexões do navegador.
  /** @type {AbortController | null} */ termParar: null, // painel.js
  termPos: 0, // painel.js
  termWs: null, // painel.js
  termWsPronto: false, // painel.js
  versaoAplicada: 0, // modulos/navegacao.js: quando a página Atualizações mandou atualizar
};

/** As funções das páginas e dos módulos sob demanda que outros arquivos chamam: entram aqui quando
 * eles carregam (o fim de cada um). O núcleo do painel abre leve e chama por aqui.
 * @type {Partial<typeof import("../paginas/conversa.js") & typeof import("../paginas/melhorias.js")
 *   & typeof import("../paginas/sessoes.js") & typeof import("./arquivos-sessao.js")
 *   & typeof import("./conectores-sessao.js")
 *   & typeof import("./modelos.js")
 *   & typeof import("./paineis-sessao.js")
 *   & typeof import("./permissoes-sessao.js")
 *   & typeof import("./terminal.js")>} */
export const carregadas = {};
