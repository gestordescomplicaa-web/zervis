// SPDX-License-Identifier: AGPL-3.0-or-later
// gdautomacao.ia: colour themes. "original" is the original teal, untouched;
// roxo, marinho, esmeralda and grafite are darker tones that hold on LIGHT rooms.
// CSS lives in jarvis-tema.css;
// this file switches the body class and recolours what CSS cannot reach: the
// ring (canvas) and the brain graph (SVG attributes). Remembered per window.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  // Each theme: ring colours per state (canvas) and graph colours (SVG). The CSS
  // palettes live in jarvis-tema.css; "original" leaves everything untouched.
  const grafo = (c, meta, fundo, base) => ({ cores: { root: c[0], memoria: c[1],
    sessoes: c[3], automacoes: c[4] }, tons: { meta, fundo, base } });
  const TEMAS = {
    original: { rotulo: "ORIGINAL", nome: "Original", ring: null, grafo: null },
    roxo: { rotulo: "ROXO", nome: "Roxo",
      ring: { idle: [109, 40, 217], listening: [79, 70, 229], thinking: [139, 92, 246], speaking: [109, 40, 217] },
      grafo: grafo(["#a78bfa", "#c4b5fd", "#b9a6fb", "#c7b8ff", "#b4a0fb"], "#cbbff2", "#1e0b47", "#0c0420") },
    marinho: { rotulo: "MARINHO", nome: "Marinho",
      ring: { idle: [37, 99, 235], listening: [56, 120, 245], thinking: [96, 150, 250], speaking: [37, 99, 235] },
      grafo: grafo(["#7aa7ff", "#a9c8ff", "#93b6ff", "#b4cdff", "#8fb2fb"], "#b6c8ec", "#0a1a44", "#040a1e") },
    esmeralda: { rotulo: "ESMERALDA", nome: "Esmeralda",
      ring: { idle: [16, 160, 104], listening: [20, 140, 140], thinking: [52, 200, 140], speaking: [16, 160, 104] },
      grafo: grafo(["#5fd6a0", "#9ff0c6", "#86e3b4", "#a9f0cc", "#7ddcae"], "#aed8c0", "#06301f", "#02140d") },
    grafite: { rotulo: "GRAFITE", nome: "Grafite",
      ring: { idle: [120, 128, 145], listening: [140, 150, 170], thinking: [175, 182, 196], speaking: [120, 128, 145] },
      grafo: grafo(["#d6dae2", "#eceef2", "#c8cdd6", "#e2e5ea", "#cfd3db"], "#bcc2cc", "#1c1e23", "#0b0c0e") },
  };
  const ORDEM = Object.keys(TEMAS);
  const ler = () => { try { return localStorage.getItem("jv-tema"); } catch (e) { return null; } };
  let nome = TEMAS[ler()] ? ler() : "original";
  let ringOriginal = null, grafoOriginal = null;

  function pintarRing() {
    const R = window.jarvisRing;
    if (!R) return false;   // the stage module runs after this script; retried below
    ringOriginal ||= JSON.parse(JSON.stringify(R.COLS));
    Object.assign(R.COLS, TEMAS[nome].ring || ringOriginal);
    return true;
  }
  function pintarGrafo() {
    const G = window.JarvisGraph;
    if (!G?.CORES) return;
    grafoOriginal ||= { cores: { ...G.CORES }, tons: { ...G.TONS } };
    const t = TEMAS[nome].grafo || grafoOriginal;
    Object.assign(G.CORES, t.cores); Object.assign(G.TONS, t.tons);
  }
  function usar(novo) {
    if (!TEMAS[novo]) return;
    nome = novo;
    try { localStorage.setItem("jv-tema", nome); } catch (e) {}
    for (const t of ORDEM) document.body.classList.toggle("tema-" + t, t === nome && t !== "original");
    document.body.classList.toggle("tema-ativo", nome !== "original");
    pintarRing(); pintarGrafo();
    window.dispatchEvent(new Event("jv-tema"));
  }
  window.jarvisTema = {
    get nome() { return nome; }, get rotulo() { return TEMAS[nome].rotulo; },
    usar, alternar() { usar(ORDEM[(ORDEM.indexOf(nome) + 1) % ORDEM.length]); },
    lista: ORDEM.map(id => ({ id, nome: TEMAS[id].nome })),
  };
  usar(nome);
  // The ring lives in the stage module, which runs after the classic scripts.
  const espera = setInterval(() => { if (pintarRing()) clearInterval(espera); }, 300);
})();
