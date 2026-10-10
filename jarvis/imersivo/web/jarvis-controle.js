// SPDX-License-Identifier: AGPL-3.0-or-later
// gdautomacao.ia: the JARVIS on its own screen. The jarvisd writes a list of
// actions to state/tela-comando.json (tools tela_agir / tela_ver); this page runs
// them in order, with the same animations a hand would trigger, and answers in
// state/tela-estado.json with what happened and what is on screen. The state is
// also refreshed every few seconds, so "what is open?" needs no round trip.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const sem = t => String(t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const espera = ms => new Promise(r => setTimeout(r, ms));
  const PASSO_MS = 450;   // between visual steps, so each animation can be seen
  const RAPIDAS = new Set(["tema", "brilho", "menu", "teclado", "buscar", "visual", "expressao", "girar", "aguardar"]);
  const C = () => {
    if (!window.jarvisCerebro) throw new Error("o cérebro da tela ainda não carregou");
    return window.jarvisCerebro;
  };

  const S = () => {
    if (!window.jarvisStage?.nucleo) throw new Error("o Núcleo ainda não carregou");
    return window.jarvisStage;
  };
  const ACOES = {
    // The Núcleo: the ring and its orbs (the manifest). abrir takes an orb or any item by
    // its spoken name, optionally inside one orb (orbe); buscar lists matches; fechar
    // takes an orb, an open item, or "tudo".
    nucleo: a => sem(a.valor ?? a.alvo) === "fechar" ? S().fecharNucleo() : S().abrirNucleo(),
    abrir: a => S().abrir(a.alvo ?? a.valor, a.orbe),
    buscar: a => S().buscar(a.alvo ?? a.valor, a.orbe),
    fechar: a => S().fechar(a.alvo ?? a.valor),
    foco: () => C().mostrarFoco(),
    abrir_mapa: () => C().abrir(),
    fechar_mapa: () => C().fechar(),
    abrir_cerebro: () => C().abrir(),   // old names, kept for commands in flight
    fechar_cerebro: () => C().fechar(),
    modo: a => C().modo(a.valor ?? a.alvo),
    focar: a => C().focar(a.alvo ?? a.valor),
    localizar: a => C().localizar(a.alvo ?? a.valor),
    zoom: a => C().zoom(a.valor),
    enquadrar: () => C().enquadrar(),
    mover: a => { const [x, y] = String(a.valor ?? "0,0").split(",").map(Number); return C().mover(x, y); },
    rolar: a => C().rolar(a.valor),
    voltar: () => C().voltar(),
    aguardar: async a => { await espera(Math.min(10000, Math.max(0, Number(a.valor) || 1000))); },
    visual: a => {
      if (!window.jarvisAvatar) throw new Error("avatar indisponível");
      const v = sem(a.valor ?? a.alvo);
      if (v !== "avatar" && v !== "anel") throw new Error("visual: avatar ou anel");
      return window.jarvisAvatar.usar(v === "avatar");
    },
    // The avatar's face: alegria, duvida, raiva, tristeza or neutro, for segundos (default 6).
    girar: a => {
      if (!window.jarvisAvatar) throw new Error("avatar indisponível");
      return window.jarvisAvatar.girar(a.valor ?? a.voltas ?? 1);
    },
    expressao: a => {
      if (!window.jarvisAvatar) throw new Error("avatar indisponível");
      return window.jarvisAvatar.sentir(a.valor ?? a.alvo, a.segundos);
    },
    teclado: a => {
      if (!window.jarvisTeclado) throw new Error("teclado indisponível");
      sem(a.valor ?? a.alvo) === "fechar" ? window.jarvisTeclado.fechar() : window.jarvisTeclado.abrir();
      return { teclado: window.jarvisTeclado.aberto };
    },
    menu: a => {
      if (!window.jarvisConfig) throw new Error("menu indisponível");
      sem(a.valor ?? a.alvo) === "fechar" ? window.jarvisConfig.fechar() : window.jarvisConfig.abrir();
      return { aberto: window.jarvisConfig.aberto };
    },
    tema: a => {
      const t = sem(a.alvo ?? a.valor), T = window.jarvisTema;
      if (!T?.lista.some(x => x.id === t)) throw new Error("tema desconhecido: " + t + " (" + (T?.lista.map(x => x.id).join(", ") || "") + ")");
      T.usar(t); return { tema: t };
    },
    brilho: a => {
      const n = Math.round(Number(a.valor));
      if (!(n >= 0 && n <= 3)) throw new Error("brilho de 0 (desligado) a 3 (forte)");
      window.jarvisMaos.mudarBrilho(n); return { brilho: window.jarvisMaos.brilho };
    },
    calibrar_maos: () => { window.jarvisMaos.calibrar(); return { calibrando: window.jarvisMaos.calibrando }; },
    maos_padrao: async () => { await window.jarvisMaos.padrao(); return { calibracao: "padrao" }; },
  };

  function estado() {
    const M = window.jarvisMaos, e = M?.estado?.();
    return {
      janela_visivel: document.visibilityState === "visible",
      nucleo: window.jarvisStage?.nucleo?.() ?? null,
      cerebro: window.jarvisCerebro?.estado() ?? null,
      menu_configuracoes: { aberto: !!window.jarvisConfig?.aberto },
      teclado: { aberto: !!window.jarvisTeclado?.aberto },
      visual: window.jarvisAvatar ? (window.jarvisAvatar.ativo ? "avatar" : "anel") : "anel",
      tema: { atual: window.jarvisTema?.nome ?? null, opcoes: window.jarvisTema?.lista.map(t => t.id) ?? [] },
      brilho_camera: M?.brilho ?? null,
      maos: e ? { calibracao: e.origem, calibrando: M.calibrando, quadros_por_segundo: Math.round(e.qps), luz: e.luz } : null,
      maos_em_uso: !!M?.emUso,
    };
  }
  // The last start/answer rides along every post, so the periodic state can never
  // overwrite an answer before the JARVIS has read it.
  let ultimaResposta = {};
  async function enviar(extra = {}) {
    ultimaResposta = { ...ultimaResposta, ...extra };
    try {
      await fetch("/tela/estado", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...ultimaResposta, estado: estado() }) });
    } catch (e) {}
  }
  async function executar(cmd) {
    const resultados = [];
    await enviar({ recebido: cmd.id });
    for (const a of Array.isArray(cmd.acoes) ? cmd.acoes : []) {
      // Never move the screen under a pinch: wait (up to 6 s) for the hand to rest.
      for (let t = 0; window.jarvisMaos?.emUso && t < 6000; t += 200) await espera(200);
      try {
        const f = ACOES[a?.acao];
        if (!f) throw new Error("ação desconhecida: " + a?.acao);
        const r = await f(a);
        resultados.push({ acao: a.acao, ok: true, ...(r && typeof r === "object" ? r : {}) });
        await espera(RAPIDAS.has(a.acao) ? 120 : PASSO_MS);
      } catch (e) {
        resultados.push({ acao: a?.acao, ok: false, erro: String(e?.message || e) });
      }
    }
    await enviar({ resposta: cmd.id, resultados });
  }

  // Commands arrive by polling; an id runs once, and a command older than 30 s
  // (a reload, a stopped page) is never replayed.
  let ultimo = null, ocupado = false;
  async function ouvir() {
    if (ocupado) return;
    try {
      const cmd = await (await fetch("/jarvis/tela-comando", { cache: "no-store" })).json();
      if (!cmd.id || cmd.id === ultimo) return;
      ultimo = cmd.id;
      if (Date.now() / 1000 - Number(cmd.ts || 0) > 30) return;
      ocupado = true;
      await executar(cmd);
    } catch (e) {} finally { ocupado = false; }
  }
  // Something that happened on the page for the JARVIS to react to (the Zé got dizzy): rides
  // along every state post, the jarvisd speaks it once by its id.
  const evento = tipo => enviar({ evento: { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), tipo, ts: Date.now() / 1000 } });
  window.jarvisControle = { executar, estado, evento, ACOES: Object.keys(ACOES) };
  setInterval(ouvir, 150);
  setInterval(() => { if (!ocupado) enviar(); }, 5000);
  setTimeout(enviar, 1500);
})();
