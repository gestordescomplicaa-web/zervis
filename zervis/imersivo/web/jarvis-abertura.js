// SPDX-License-Identifier: AGPL-3.0-or-later
// The opening (ADR 0078): opening the Zérvis program lands here with ?abertura=1. The music
// plays, the name lights up, and the Zé presents the day: one holographic panel per block of the
// panorama he writes (GET /abertura: greeting, weather with the day's curve, agenda on a line of
// the day, focus, code sessions, WhatsApp, Instagram with its views, headlines), each one spoken
// in his own voice (POST /abertura/falar asks for that block's line;
// the text is always the one the Zé wrote). The music ducks while he speaks. Esc skips it.
// Also: the Zé's "apresentar dia" action (jarvis-controle.js), without the music.
(() => {
  const busca = new URLSearchParams(location.search);
  if (busca.get("role") === "render") return;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  let ritmo = 1;  // the browser tests run it faster (jarvisAbertura.ritmo)
  const espera = ms => new Promise(r => setTimeout(r, ms * ritmo));
  const P = () => window.jarvisApresentacao.palco;
  let musica = null, rodada = 0, rodando = false, relogio = 0, feitos = 0;
  const falados = [];  // the steps whose line was asked for (the tests read it)

  // ---- the music: the file of whoever uses the Zé, or a short synthesized swell ----
  // Web Audio, not an <audio>: a media element shows up as a player (MPRIS), and the Zé pauses
  // every player while he speaks ("pausar mídia"), so the music stalled under his voice.
  let ac = null, ganho = null;
  async function tocar() {
    try {
      const r = await fetch("/abertura/musica", { cache: "no-store" });
      if (r.ok) {
        ac ||= new AudioContext();
        if (ac.state !== "running") await ac.resume();
        const sinal = await ac.decodeAudioData(await r.arrayBuffer());
        ganho = ac.createGain(); ganho.gain.value = .9; ganho.connect(ac.destination);
        const fonte = ac.createBufferSource(); fonte.buffer = sinal; fonte.connect(ganho); fonte.start();
        musica = fonte;
        return "arquivo";
      }
    } catch (_) { musica = null; }
    const tom = P().tom;
    [110, 165, 220, 330].forEach((f, i) => tom(f, 2.6, .03, "sine", f * 2, i * .4));
    tom(880, .9, .025, "triangle", 1760, 1.8);
    return "sintetizada";
  }
  function volume(alvo, ms = 500) {
    if (!musica || !ganho || !ac) return;
    const g = ganho.gain, agora = ac.currentTime;
    g.cancelScheduledValues(agora); g.setValueAtTime(g.value, agora); g.linearRampToValueAtTime(alvo, agora + ms / 1000);
    if (alvo === 0) { const m = musica; setTimeout(() => { try { m.stop(); } catch (_) { /* already over */ } }, ms + 50); }
  }
  function calar() {
    try { musica?.stop(); } catch (_) { /* already over */ }
    musica = null;
  }

  // ---- the opening tells the Zé it began (-1) or was skipped (-2): no step, no line ----
  let montado = "";
  function sinal(passo) {
    if (!montado) return;
    fetch("/abertura/falar", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ montado, passo }) }).catch(() => {});
  }

  // ---- the Zé's voice: ask for the line, then follow /orb while he speaks ----
  async function estado() {
    try { const r = await fetch("/orb", { cache: "no-store" }); return r.ok ? (await r.json()).state : ""; } catch (_) { return ""; }
  }
  // One subject at a time: the line is asked for first; its panel comes with the
  // voice (or after a short head start, if it is slow), and the next one waits for the end.
  async function falar(montado, passo, texto, id, mostrar) {
    falados.push(passo);
    try {
      await fetch("/abertura/falar", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ montado, passo }) });
    } catch (_) { /* no voice: the panel still shows */ }
    let comecou = false, mostrado = false;
    for (const t0 = performance.now(); id === rodada && performance.now() - t0 < 12000 * ritmo;) {
      if (await estado() === "speaking") { comecou = true; break; }
      if (!mostrado && performance.now() - t0 > 2500 * ritmo) { mostrado = true; mostrar(); }
      await espera(150);
    }
    if (!mostrado) mostrar();
    if (!comecou) { await espera(Math.max(3000, texto.length * 70)); return; }
    volume(.18);
    // Done after 600 ms in a row without speaking: the voice pauses between sentences.
    for (let calado = 0, t0 = performance.now(); id === rodada && calado < 4 && performance.now() - t0 < 60000;) {
      calado = await estado() === "speaking" ? 0 : calado + 1;
      await espera(150);
    }
    volume(.45);
    await espera(400);
  }

  // ---- the opening title, over the music ----
  function vinheta(dia) {
    const v = document.createElement("div");
    v.id = "jv-abertura-vinheta"; v.setAttribute("aria-hidden", "true");
    const oi = (dia.blocos || [])[0] || {};
    v.innerHTML = `<div class="anel"></div><h1>ZÉRVIS</h1><p>${esc(oi.data || new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" }))}</p>`;
    document.body.appendChild(v);
    return v;
  }

  // ---- one panel per block, in two rows to the right of the Zé (three columns, four with seven) ----
  // No caption under the panels (11/11/2026): the Zé says it, and the room is for the panels.
  const lugar = (i, total) => {
    const colunas = Math.max(3, Math.ceil(total / 2)), passo = .786 / colunas;
    return { x: .215 + (i % colunas) * passo, y: i < colunas ? .05 : .48, w: passo - .017, h: .38 };
  };
  const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
  // The day's temperature, hour by hour, with a dot on now.
  function curva(horas) {
    if (horas.length < 2) return "";
    const min = Math.min(...horas), max = Math.max(...horas), y = t => 92 - (t - min) / Math.max(1, max - min) * 80;
    const x = i => i / (horas.length - 1) * 100, agora = Math.min(horas.length - 1, new Date().getHours());
    const pontos = horas.map((t, i) => `${x(i).toFixed(1)},${y(t).toFixed(1)}`).join(" ");
    return `<div class="jv-ab-curva"><div class="traco"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points="${pontos}"/></svg>
      <i style="left:${x(agora)}%;top:${y(horas[agora])}%"></i></div><span>0h</span><span>12h</span><span>23h</span></div>`;
  }
  // The day from 6h to midnight: a mark for each item and one for now.
  function linhaDoDia(itens) {
    const lugar = hhmm => { const [h, m] = String(hhmm).split(":").map(Number); return Math.max(0, Math.min(100, ((h + m / 60) - 6) / 18 * 100)); };
    const agora = new Date(), marcas = (itens || []).map(i => `<i class="${i.tipo === "automacao" ? "auto" : ""}" style="left:${lugar(i.hora)}%"></i>`);
    return `<div class="jv-ab-dia">${marcas.join("")}<b style="left:${lugar(`${agora.getHours()}:${agora.getMinutes()}`)}%"></b><span>6h</span><span>12h</span><span>18h</span><span>24h</span></div>`;
  }
  const lista = itens => `<ul class="jv-ab-lista">${itens.join("")}</ul>`;
  const mais = (b, mostrados) => b.total > mostrados ? `<p class="jv-ab-mais">+${b.total - mostrados}</p>` : "";
  const ICONES = { interrompida: ["alerta", "◐"], limite: ["alerta", "◷"], erro: ["critico", "✕"], trabalhando: ["bom", "●"] };
  const PAINEIS = {
    relogio: b => ({ nome: "AGORA", titulo: "Hoje", corpo: `<b class="jv-ab-hora" data-relogio>--:--</b>
      <p class="jv-ab-data">${esc(b.data)}</p><p class="jv-ab-oi">${esc(b.saudacao)}</p>` }),
    clima: b => ({ nome: "CLIMA", titulo: b.cidade, fonte: "OPEN-METEO", corpo: `<div class="jv-ab-clima">
      <b>${esc(b.temperatura)}°</b><span>${esc(b.ceu)}</span></div><dl class="jv-linhas">
      <dt>Máxima</dt><dd>${esc(b.maxima)}°</dd><dt>Mínima</dt><dd>${esc(b.minima)}°</dd><dt>Chuva</dt><dd>${esc(b.chuva)}%</dd></dl>`
      + curva(b.horas || []) }),
    hoje: b => ({ nome: "AGENDA", titulo: "Hoje", corpo: linhaDoDia(b.itens) + lista(b.itens.map((i, n) => `<li style="animation-delay:${.3 + n * .12}s">
      <time>${esc(i.hora)}</time><span class="jv-st ${i.tipo === "automacao" ? "" : "bom"}" data-ico="${i.tipo === "automacao" ? "⟳" : "◆"}">${i.tipo === "automacao" ? "AUTOMAÇÃO" : "COMPROMISSO"}</span>
      <span class="txt">${esc(i.titulo)}</span></li>`)) + mais(b, b.itens.length) }),
    sessoes: b => ({ nome: "OFICINA", titulo: "Sessões de código", corpo: lista(b.itens.map((i, n) => {
      const [cls, ico] = ICONES[i.chave] || ["", "·"];
      return `<li style="animation-delay:${.3 + n * .12}s"><span class="txt">${esc(i.nome)}</span><span class="jv-st ${cls}" data-ico="${ico}">${esc(i.situacao.toUpperCase())}</span></li>`;
    })) + mais(b, b.itens.length) }),
    whatsapp: b => ({ nome: "WHATSAPP", titulo: "Sem resposta", corpo: `<div class="jv-heroi"><span>CONVERSAS</span><b>${esc(b.total)}</b></div>`
      + lista(b.itens.map((i, n) => `<li style="animation-delay:${.3 + n * .12}s"><span class="txt">${esc(i.nome)}</span><time>${esc(i.ha)}</time></li>`)) }),
    // the current front, its next step and the fronts by state, as bars
    foco: b => ({ nome: "FOCO", titulo: "Foco", corpo: `<p class="jv-ab-frente">${esc(b.atual || "Nenhuma frente ativa")}</p>`
      + (b.proximo_passo ? `<p class="jv-ab-passo"><span>PRÓXIMO PASSO</span>${esc(b.proximo_passo)}</p>` : "") + '<div class="jv-ab-barras"></div>',
    depois: reg => setTimeout(() => {
      const g = reg.el.querySelector(".jv-ab-barras"), itens = [["Ativas", b.ativas], ["Travadas", b.travadas], ["Pausadas", b.pausadas],
        ["Feitas na semana", b.feitas_semana]].filter(([, v]) => v > 0).map(([nome, valor]) => ({ nome, valor }));
      if (g && reg.el.isConnected && itens.length) P().barras(g, itens);
    }, 420) }),
    // the followers, the week's posts and the views of the latest ones, as columns
    instagram: b => ({ nome: "INSTAGRAM", titulo: "@" + b.usuario, fonte: "META", corpo: `<div class="jv-herois">
      <div class="jv-heroi"><span>SEGUIDORES</span><b>${esc(compacto.format(b.seguidores || 0))}</b></div>
      <div class="jv-heroi"><span>NA SEMANA</span><b>${esc(b.semana || 0)}</b><small>publicações</small></div></div>
      <span class="jv-h-legenda">VISUALIZAÇÕES POR PUBLICAÇÃO</span><div class="jv-grafico"></div>`
      + (b.destaque ? `<p class="jv-ab-destaque"><span class="txt">${esc(b.destaque.legenda || "(sem legenda)")}</span><b>${esc(b.destaque.valor)}</b></p>` : ""),
    depois: reg => setTimeout(() => {
      const g = reg.el.querySelector(".jv-grafico");
      if (g && reg.el.isConnected && (b.grafico || []).length) P().colunas(g, b.grafico);
    }, 420) }),
    noticias: b => ({ nome: "BRASIL", titulo: "Manchetes", fonte: "RSS", corpo: lista(b.itens.map((i, n) => `<li class="jv-ab-noticia" style="animation-delay:${.3 + n * .12}s">
      <span class="txt">${esc(i.titulo)}</span><small>${esc(i.fonte)}</small></li>`)) }),
  };
  function marcarHora() {
    const agora = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    document.querySelectorAll("[data-relogio]").forEach(el => { el.textContent = agora; });
  }

  function passos(dia, id) {
    const blocos = Array.isArray(dia.blocos) ? dia.blocos : [];
    const total = blocos.filter(b => PAINEIS[b.tipo]).length;
    let i = 0;
    return blocos.map((b, passo) => {
      const fazer = PAINEIS[b.tipo], fala = String(b.fala || "");
      const id_ = "abertura-" + b.tipo, ordem = fazer ? ++i : 0, onde = fazer ? lugar(ordem - 1, total) : null;
      const mostrar = () => {
        if (id !== rodada || !fazer) return;
        const { nome, depois, ...painel } = fazer(b);
        const reg = P().painel(id_, { ...onde, fonte: "AO VIVO", ...painel, cod: `${String(ordem).padStart(2, "0")} · ${nome}`, classe: "jv-ab" });
        depois?.(reg); P().focar(id_);
      };
      // The script runner only waits: the panel comes with the voice.
      return { fala: "", aguardar: async () => {
        await (dia.montado ? falar(dia.montado, passo, fala, id, mostrar) : (mostrar(), espera(Math.max(3000, fala.length * 70))));
        if (id === rodada) feitos++;
      } };
    });
  }

  async function panorama() {
    for (let n = 0; n < 30; n++) {
      try {
        const r = await fetch("/abertura", { cache: "no-store" });
        const d = r.ok ? await r.json() : {};
        if (Array.isArray(d.blocos) && d.blocos.length) return d;
      } catch (_) { /* the Zé is still starting */ }
      await espera(200);
    }
    // Without the Zé: the clock and the greeting from this machine, no voice.
    const agora = new Date(), h = agora.getHours();
    return { blocos: [{ tipo: "relogio", saudacao: h >= 5 && h < 12 ? "Bom dia" : h >= 12 && h < 18 ? "Boa tarde" : "Boa noite",
      data: agora.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" }), fala: "" }] };
  }

  // Opening the program starts the Zé: his first panorama comes before the weather, the
  // Instagram and the headlines (completo: false). The name stays up over the music until the
  // full one arrives, or a while passes (no network: the day goes without them).
  async function completar(dia, id) {
    for (const t0 = performance.now(); dia.completo === false && id === rodada && performance.now() - t0 < 12000 * ritmo;) {
      await espera(300);
      try {
        const r = await fetch("/abertura", { cache: "no-store" });
        const d = r.ok ? await r.json() : {};
        if (Array.isArray(d.blocos) && d.blocos.length) dia = d;
      } catch (_) { /* keep the one in hand */ }
    }
    return dia;
  }

  async function iniciar({ musica: comMusica = true, automatica = false } = {}) {
    for (let n = 0; n < 100 && !(window.jarvisStage && window.jarvisApresentacao); n++) await new Promise(r => setTimeout(r, 100));
    if (!window.jarvisApresentacao) return { abertura: false, erro: "apresentação indisponível" };
    encerrar();
    const id = ++rodada; rodando = true; falados.length = 0; feitos = 0;
    let dia = await panorama();
    if (id !== rodada) return { abertura: false };
    if (automatica && dia.ligada === false) { rodando = false; return { abertura: false, desligada: true }; }
    montado = dia.montado || "";
    sinal(-1);  // the Zé holds his notices until the opening is over
    const som = comMusica ? await tocar() : "sem";
    const v = vinheta(dia);
    const [, completo] = await Promise.all([espera(2600), completar(dia, id)]);
    if (id !== rodada) return { abertura: false };  // skipped: encerrar() took the title away
    dia = completo; montado = dia.montado || montado;
    v.classList.add("saindo"); setTimeout(() => v.remove(), 900 * ritmo);
    clearInterval(relogio); marcarHora(); relogio = setInterval(marcarHora, 1000);
    P().comecar();
    const pronto = P().roteiro(P().rodada, passos(dia, id));
    (async () => {  // when the script is over: the music fades and the opening is done
      while (id === rodada && window.jarvisApresentacao.apresentando && feitos < (dia.blocos || []).length) await espera(300);
      await espera(1500);
      if (id === rodada) { volume(0, 2500); rodando = false; }
    })();
    return { abertura: true, musica: som, blocos: (dia.blocos || []).map(b => b.tipo), ...pronto };
  }

  function encerrar() {
    if (rodando) sinal(-2);  // skipped: the notices may come now
    rodada++; clearInterval(relogio);
    calar();
    document.getElementById("jv-abertura-vinheta")?.remove();
    if (rodando && window.jarvisApresentacao?.apresentando) window.jarvisApresentacao.encerrar();
    rodando = false;
    return { abertura: false };
  }

  addEventListener("keydown", e => {
    if (e.key === "Escape" && rodando) encerrar();
  });
  window.jarvisAbertura = {
    iniciar, encerrar,
    get rodando() { return rodando; },
    get falados() { return [...falados]; },
    get ritmo() { return ritmo; }, set ritmo(v) { ritmo = Math.max(.01, Number(v) || 1); },
  };
  // Opening the program: once, then the address forgets it (a reload does not repeat it).
  if (busca.get("abertura") === "1") {
    busca.delete("abertura");
    history.replaceState(null, "", location.pathname + (busca.size ? "?" + busca : "") + location.hash);
    addEventListener("load", () => iniciar({ automatica: true }).catch(() => {}), { once: true });
  }
})();
