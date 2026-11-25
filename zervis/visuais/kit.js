// O kit dos visuais do Zé (ADR 0138): slides, números que contam, entradas animadas e controles
// que mexem nos parâmetros. Um controle `data-param="volume"` vira a variável CSS `--volume` (e
// `--volume-n`, de 0 a 1, num deslizante), o texto de `[data-mostra="volume"]` e as contas de
// `[data-calc="volume * preco"]`; o evento `zk:param` avisa o script do próprio visual.
(() => {
  const raiz = document.documentElement;
  /** @type {Record<string, number | string>} */
  const parametros = {};
  const parado = () => document.body.classList.contains("zk-captura") || matchMedia("(prefers-reduced-motion: reduce)").matches;
  const formatar = (v, f) => {
    const n = Number(v);
    const t = typeof v === "number" || (v !== "" && Number.isFinite(n)) ? n.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) : String(v);
    return f ? f.replace("{v}", t) : t;
  };

  function calcular() {
    const nomes = Object.keys(parametros);
    for (const el of document.querySelectorAll("[data-calc]")) {
      try { el.textContent = formatar(Function(...nomes, `"use strict"; return (${el.dataset.calc});`)(...nomes.map((n) => parametros[n])), el.dataset.formato); }
      catch { el.textContent = "—"; }
    }
  }

  function definir(nome, valor, el) {
    const n = Number(valor);
    parametros[nome] = valor !== "" && Number.isFinite(n) ? n : valor;
    raiz.style.setProperty(`--${nome}`, String(valor));
    if (el?.type === "range") {
      const min = Number(el.min || 0), max = Number(el.max || 100);
      raiz.style.setProperty(`--${nome}-n`, String((n - min) / (max - min || 1)));
    }
    for (const s of document.querySelectorAll(`[data-mostra="${nome}"]`)) s.textContent = formatar(parametros[nome], s.dataset.formato);
    calcular();
    document.dispatchEvent(new CustomEvent("zk:param", { detail: { nome, valor: parametros[nome], parametros } }));
  }

  function ligarControles() {
    for (const el of document.querySelectorAll("[data-param]")) {
      const ler = () => definir(el.dataset.param, el.type === "checkbox" ? (el.checked ? 1 : 0) : el.value, el);
      el.addEventListener("input", ler);
      ler();
    }
    for (const grupo of document.querySelectorAll(".zk-alternar[data-param]")) {
      grupo.addEventListener("click", (ev) => {
        const b = ev.target.closest("button[data-valor]");
        if (!b) return;
        for (const o of grupo.querySelectorAll("button")) o.setAttribute("aria-pressed", String(o === b));
        definir(grupo.dataset.param, b.dataset.valor);
      });
      grupo.querySelector('button[aria-pressed="true"]')?.click();
    }
  }

  function contar(el) {
    const fim = Number(el.dataset.contar), f = el.dataset.formato;
    if (parado()) { el.textContent = formatar(fim, f); return; }
    const t0 = performance.now(), duracao = 1100;
    const passo = (t) => {
      const k = Math.min(1, (t - t0) / duracao), e = 1 - (1 - k) ** 3;
      el.textContent = formatar(Math.round(fim * e * 100) / 100, f);
      if (k < 1) requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
  }

  function animar(escopo) {
    escopo.querySelectorAll("[data-contar]").forEach(contar);
    for (const el of escopo.querySelectorAll("[data-entra], .zk-barras, .zk-lista, .zk-tempo")) {
      el.classList.remove("zk-vivo"); void el.offsetWidth; el.classList.add("zk-vivo");
    }
  }

  function slides(deck) {
    const lista = [...deck.querySelectorAll(":scope > .zk-slide")];
    if (!lista.length) return;
    let i = 0;
    const pontos = Object.assign(document.createElement("nav"), { className: "zk-pontos" });
    pontos.innerHTML = lista.map((_, n) => `<button type="button" aria-label="Slide ${n + 1}"></button>`).join("");
    const setas = Object.assign(document.createElement("div"), { className: "zk-setas" });
    setas.innerHTML = '<button type="button" aria-label="Anterior">‹</button><button type="button" aria-label="Próximo">›</button>';
    deck.append(pontos, setas);
    const ir = (n) => {
      lista[i].classList.remove("zk-atual"); pontos.children[i].classList.remove("zk-atual");
      i = (n + lista.length) % lista.length;
      lista[i].classList.add("zk-atual"); pontos.children[i].classList.add("zk-atual");
      animar(lista[i]);
    };
    pontos.addEventListener("click", (ev) => { const b = ev.target.closest("button"); if (b) ir([...pontos.children].indexOf(b)); });
    setas.firstChild.addEventListener("click", () => ir(i - 1));
    setas.lastChild.addEventListener("click", () => ir(i + 1));
    deck.addEventListener("click", (ev) => { if (!ev.target.closest("a, button, input, select, label, .zk-controles, .zk-pontos, .zk-setas")) ir(i + 1); });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowRight" || ev.key === "PageDown") ir(i + 1);
      if (ev.key === "ArrowLeft" || ev.key === "PageUp") ir(i - 1);
    });
    const auto = Number(deck.dataset.auto || 0);
    if (auto > 0 && !parado()) setInterval(() => ir(i + 1), auto * 1000);
    ir(0);
  }

  addEventListener("DOMContentLoaded", () => {
    ligarControles();
    const decks = document.querySelectorAll(".zk-slides");
    decks.forEach(slides);
    if (!decks.length) animar(document);
  });
  window.zk = { parametros, definir };
})();
