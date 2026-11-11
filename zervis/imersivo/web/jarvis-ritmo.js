// SPDX-License-Identifier: AGPL-3.0-or-later
// A scene in the rhythm of the Zé's voice (11/11/2026). The scenes he writes (jarvis-cenas.js)
// used to run on their own clock (62 ms per letter), starting while he was still thinking, so
// with a lot to show they changed and cleared the board while he was still talking about the
// previous blocks. Now each step waits for his voice to reach the next step's line.
//
// The Zé says the steps' lines in his answer, in order (tela_explicar asks for that). While he
// speaks, GET /orb brings the chunk of speech being played and how far into it he is
// (state/fala.json, written by zervis/rosto/anel.py). A step is reached when that position passes
// the place where its line starts in what he says. Without that (silent mode, a voice that does
// not report its text, no answer within half a minute, a line he never said), it falls back to
// the time spoken so far and, at last, to the reading time.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const R = () => window.jarvisApresentacao?.ritmo ?? 1;   // the tests run it faster
  const espera = ms => new Promise(r => setTimeout(r, ms * R()));
  const SEM_VOZ_MS = 30000;      // no voice by then: the answer is not coming (or is silent)
  const CALADO_MS = 1500;        // this long without speaking: the answer is over
  const MINIMO_MS = 900;         // a step stays at least this long, even if two share a sentence
  const LETRA_MS = 62;           // the reading time, when there is no voice to follow

  // Words with their place in the original text (the offsets the voice reports are in it).
  const normal = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const palavras = texto => [...String(texto || "").matchAll(/[\p{L}\p{N}]+/gu)].map(m => ({ p: normal(m[0]), i: m.index }));
  // The first words that identify a line: numbers are said in words by the voice, so they and
  // the short words are left out.
  const chave = fala => palavras(fala).map(w => w.p).filter(p => p.length >= 3 && !/^\d+$/.test(p)).slice(0, 5);

  // Where the line with this key starts in these words (from index `de`): a window that starts
  // with one of its first two words and holds most of them. -1 when it is not there.
  function achar(ws, key, de = 0) {
    if (key.length < 2) return -1;
    const precisa = Math.max(2, Math.ceil(key.length * .6)), janela = key.length + 3;
    for (let j = de; j < ws.length; j++) {
      if (ws[j].p !== key[0] && ws[j].p !== key[1]) continue;
      const trecho = new Set(ws.slice(j, j + janela).map(w => w.p));
      if (key.filter(k => trecho.has(k)).length >= precisa) return j;
    }
    return -1;
  }

  // Follows the voice for one scene: the chunks said since it started and how far the current one got.
  function ouvir(rodada) {
    const comeco = Date.now() / 1000, t0 = performance.now();
    const pedacos = [];               // {inicio, texto, ate, ws}
    let falando = false, falou = false, ultimaVoz = 0, comTexto = false, fim = false;
    const vivo = () => !fim && window.jarvisApresentacao?.palco?.rodada === rodada;
    (async function seguir() {
      while (vivo()) {
        try {
          const r = await fetch("/orb", { cache: "no-store" });
          const d = r.ok ? await r.json() : {};
          falando = d.state === "speaking";
          if (falando) { falou = true; ultimaVoz = performance.now(); }
          const f = falando ? d.fala : null;
          if (f && f.texto && f.inicio >= comeco - 1) {
            comTexto = true;
            let p = pedacos.at(-1);
            if (!p || p.inicio !== f.inicio) {
              if (p) p.ate = p.texto.length;   // the previous chunk was said to the end
              p = { inicio: f.inicio, texto: f.texto, ate: 0, ws: palavras(f.texto) };
              pedacos.push(p);
            }
            p.ate = Math.max(p.ate, Math.min(f.ate, p.texto.length));
          }
        } catch (_) { /* the Zé restarting: try again */ }
        await new Promise(r => setTimeout(r, 150));
      }
    })();
    return {
      parar() { fim = true; },
      get vivo() { return vivo(); },
      get falando() { return falando; },
      get comTexto() { return comTexto; },
      // no voice yet, long after the scene came: it is not coming
      get semVoz() { return !falou && performance.now() - t0 > SEM_VOZ_MS * R(); },
      // spoke, and has been quiet for a while: the answer is over
      get acabou() { return falou && !falando && performance.now() - ultimaVoz > CALADO_MS * R(); },
      // characters said since the scene came
      get dito() { return pedacos.reduce((n, p) => n + p.ate, 0); },
      pedacos,
    };
  }

  // The steps' waits for a scene: step i holds the board until the voice reaches step i + 1;
  // the last one until the answer is over. `passos` are the scene's steps ({fala}).
  function ritmar(passos, rodada) {
    const voz = ouvir(rodada), chaves = passos.map(p => chave(p.fala));
    const achados = [];               // where each step's line was found: {c: chunk, j: word}
    const antes = i => passos.slice(0, i).reduce((n, p) => n + String(p.fala || "").length, 0);
    // Has the voice reached step i's line?
    function chegou(i) {
      let m = achados[i];
      if (!m) {
        const ant = achados[i - 1];
        for (let c = ant ? ant.c : 0; c < voz.pedacos.length && !m; c++) {
          const j = achar(voz.pedacos[c].ws, chaves[i], ant && c === ant.c ? ant.j + 1 : 0);
          if (j >= 0) m = { c, j };
        }
        if (m) achados[i] = m;
      }
      if (m) {
        const p = voz.pedacos[m.c];
        return m.c < voz.pedacos.length - 1 || p.ate >= p.ws[m.j].i;
      }
      // a line he did not say as written: by the amount he has said since
      return voz.dito >= antes(i) * 1.25 + 60;
    }
    return passos.map((passo, i) => async () => {
      const t0 = performance.now(), proximo = i + 1 < passos.length ? i + 1 : -1;
      const leitura = Math.max(2600, String(passo.fala || "").length * LETRA_MS);
      await espera(MINIMO_MS);
      while (voz.vivo) {
        if (voz.semVoz || (voz.falando && !voz.comTexto && performance.now() - t0 > 2000 * R())) {
          // nothing to follow: the reading time, as before
          await espera(Math.max(0, leitura - (performance.now() - t0) / R()));
          break;
        }
        if (proximo < 0 ? voz.acabou : chegou(proximo)) break;
        if (voz.acabou) { await espera(1800); break; }   // he said it all: the rest, quickly
        await new Promise(r => setTimeout(r, 120));
      }
      if (proximo < 0) voz.parar();
    });
  }

  window.jarvisRitmo = { ritmar, chave, achar, palavras };
})();
