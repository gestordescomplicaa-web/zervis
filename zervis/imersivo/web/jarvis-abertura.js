// SPDX-License-Identifier: AGPL-3.0-or-later
// The opening (ADR 0078): opening the Zérvis program lands here with ?abertura=1. The music
// plays, the name lights up, and the Zé presents the day: one holographic panel per block of the
// panorama he writes (GET /abertura: greeting, weather, agenda, code sessions, WhatsApp,
// headlines), each one spoken in his own voice (POST /abertura/falar asks for that block's line;
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
  async function tocar() {
    try {
      const r = await fetch("/abertura/musica", { cache: "no-store" });
      if (r.ok) {
        musica = new Audio(URL.createObjectURL(await r.blob()));
        musica.volume = 0.9;
        await musica.play();
        return "arquivo";
      }
    } catch (_) { musica = null; }
    const tom = P().tom;
    [110, 165, 220, 330].forEach((f, i) => tom(f, 2.6, .03, "sine", f * 2, i * .4));
    tom(880, .9, .025, "triangle", 1760, 1.8);
    return "sintetizada";
  }
  function volume(alvo, ms = 500) {
    const m = musica; if (!m) return;
    const de = m.volume, t0 = performance.now();
    (function passo() {
      const k = Math.min(1, (performance.now() - t0) / ms);
      m.volume = Math.max(0, Math.min(1, de + (alvo - de) * k));
      if (k < 1 && m === musica) requestAnimationFrame(passo);
      else if (alvo === 0 && k >= 1) m.pause();
    })();
  }

  // ---- the Zé's voice: ask for the line, then follow /orb until he stops speaking ----
  async function estado() {
    try { const r = await fetch("/orb", { cache: "no-store" }); return r.ok ? (await r.json()).state : ""; } catch (_) { return ""; }
  }
  async function falar(montado, passo, texto, id) {
    falados.push(passo);
    try {
      await fetch("/abertura/falar", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ montado, passo }) });
    } catch (_) { /* no voice: the caption still shows */ }
    let comecou = false;
    for (const t0 = performance.now(); id === rodada && performance.now() - t0 < 6000 * ritmo;) {
      if (await estado() === "speaking") { comecou = true; break; }
      await espera(150);
    }
    if (!comecou) { await espera(Math.max(2200, texto.length * 55)); return; }
    volume(.22);
    // Done after 600 ms in a row without speaking: the voice pauses between sentences.
    for (let calado = 0, t0 = performance.now(); id === rodada && calado < 4 && performance.now() - t0 < 60000;) {
      calado = await estado() === "speaking" ? 0 : calado + 1;
      await espera(150);
    }
    volume(.5);
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

  // ---- one panel per block, three columns by two rows to the right of the Zé ----
  const lugar = i => ({ x: .215 + (i % 3) * .262, y: i < 3 ? .06 : .45, w: .245, h: .33 });  // the caption sits below
  const lista = itens => `<ul class="jv-ab-lista">${itens.join("")}</ul>`;
  const mais = (b, mostrados) => b.total > mostrados ? `<p class="jv-ab-mais">+${b.total - mostrados}</p>` : "";
  const ICONES = { interrompida: ["alerta", "◐"], limite: ["alerta", "◷"], erro: ["critico", "✕"], trabalhando: ["bom", "●"] };
  const PAINEIS = {
    relogio: b => ({ cod: "01 · AGORA", titulo: "Hoje", corpo: `<b class="jv-ab-hora" data-relogio>--:--</b>
      <p class="jv-ab-data">${esc(b.data)}</p><p class="jv-ab-oi">${esc(b.saudacao)}</p>` }),
    clima: b => ({ cod: "02 · CLIMA", titulo: b.cidade, fonte: "OPEN-METEO", corpo: `<div class="jv-ab-clima">
      <b>${esc(b.temperatura)}°</b><span>${esc(b.ceu)}</span></div><dl class="jv-linhas">
      <dt>Máxima</dt><dd>${esc(b.maxima)}°</dd><dt>Mínima</dt><dd>${esc(b.minima)}°</dd><dt>Chuva</dt><dd>${esc(b.chuva)}%</dd></dl>` }),
    hoje: b => ({ cod: "03 · AGENDA", titulo: "Hoje", corpo: lista(b.itens.map((i, n) => `<li style="animation-delay:${.3 + n * .12}s">
      <time>${esc(i.hora)}</time><span class="jv-st ${i.tipo === "automacao" ? "" : "bom"}" data-ico="${i.tipo === "automacao" ? "⟳" : "◆"}">${i.tipo === "automacao" ? "AUTOMAÇÃO" : "COMPROMISSO"}</span>
      <span class="txt">${esc(i.titulo)}</span></li>`)) + mais(b, b.itens.length) }),
    sessoes: b => ({ cod: "04 · OFICINA", titulo: "Sessões de código", corpo: lista(b.itens.map((i, n) => {
      const [cls, ico] = ICONES[i.chave] || ["", "·"];
      return `<li style="animation-delay:${.3 + n * .12}s"><span class="txt">${esc(i.nome)}</span><span class="jv-st ${cls}" data-ico="${ico}">${esc(i.situacao.toUpperCase())}</span></li>`;
    })) + mais(b, b.itens.length) }),
    whatsapp: b => ({ cod: "05 · WHATSAPP", titulo: "Sem resposta", corpo: `<div class="jv-heroi"><span>CONVERSAS</span><b>${esc(b.total)}</b></div>`
      + lista(b.itens.map((i, n) => `<li style="animation-delay:${.3 + n * .12}s"><span class="txt">${esc(i.nome)}</span><time>${esc(i.ha)}</time></li>`)) }),
    noticias: b => ({ cod: "06 · BRASIL", titulo: "Manchetes", fonte: "RSS", corpo: lista(b.itens.map((i, n) => `<li class="jv-ab-noticia" style="animation-delay:${.3 + n * .12}s">
      <span class="txt">${esc(i.titulo)}</span><small>${esc(i.fonte)}</small></li>`)) }),
  };
  function marcarHora() {
    const agora = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    document.querySelectorAll("[data-relogio]").forEach(el => { el.textContent = agora; });
  }

  function passos(dia, id) {
    const blocos = Array.isArray(dia.blocos) ? dia.blocos : [];
    let i = 0;
    return blocos.map((b, passo) => {
      const fazer = PAINEIS[b.tipo];
      const p = { fala: String(b.fala || ""), aguardar: async () => {
        await (dia.montado ? falar(dia.montado, passo, String(b.fala || ""), id) : espera(2600));
        if (id === rodada) feitos++;
      } };
      if (fazer) {
        const onde = lugar(i++), id_ = "abertura-" + b.tipo;
        p.mostrar = [() => P().painel(id_, { ...onde, fonte: "AO VIVO", ...fazer(b), classe: "jv-ab" })];
        p.foco = id_;
      }
      return p;
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

  async function iniciar({ musica: comMusica = true, automatica = false } = {}) {
    for (let n = 0; n < 100 && !(window.jarvisStage && window.jarvisApresentacao); n++) await new Promise(r => setTimeout(r, 100));
    if (!window.jarvisApresentacao) return { abertura: false, erro: "apresentação indisponível" };
    encerrar();
    const id = ++rodada; rodando = true; falados.length = 0; feitos = 0;
    const dia = await panorama();
    if (id !== rodada) return { abertura: false };
    if (automatica && dia.ligada === false) { rodando = false; return { abertura: false, desligada: true }; }
    const som = comMusica ? await tocar() : "sem";
    const v = vinheta(dia);
    await espera(2600);
    v.classList.add("saindo"); setTimeout(() => v.remove(), 900 * ritmo);
    if (id !== rodada) return { abertura: false };
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
    rodada++; clearInterval(relogio);
    if (musica) { musica.pause(); musica = null; }
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
