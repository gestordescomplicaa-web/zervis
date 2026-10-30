// SPDX-License-Identifier: AGPL-3.0-or-later
// Real 3D holograms the Zé builds on request (ADR 0048): he describes the object as pieces
// (sphere, box, cylinder, cone, torus, ring, helix, tube, line, particles), each with a place,
// a size, a colour, a label and a motion (spin, pulse, float, orbit), and "filhos" that ride on
// their parent (the Moon on the Earth). This file turns that recipe into a three.js object; the
// board shows it in a Barehands model card (stage.html), so the pinch lock turns it on every
// axis and two hands scale it, exactly like a .glb from the Acervo.
//
// The recipe comes from a language model: everything is clamped and counted here, and nothing
// in it is ever run as code.
(() => {
  const FORMAS = ["esfera", "cubo", "caixa", "cilindro", "cone", "piramide", "toro", "anel", "capsula",
    "helice", "tubo", "linha", "ligacao", "particulas"];
  const ANIMS = ["girar", "pulsar", "flutuar", "orbitar"];
  const CORES = { azul: "#4aa3ff", vermelho: "#ff5a4f", verde: "#4fdc8a", amarelo: "#ffd84a", laranja: "#ff9d3c",
    roxo: "#a77bff", rosa: "#ff7ac8", branco: "#f4fbff", ciano: "#5ff2e6", dourado: "#ffc955", cinza: "#9aa8b2",
    marrom: "#b07a4f", preto: "#3a4450", prata: "#cfd8df", turquesa: "#3fe0c5", anil: "#5b6bff" };
  const MAX_PECAS = 80, MAX_PONTOS = 40, MAX_PARTICULAS = 3000;
  const num = (v, d, a, b) => { const n = Number(v); return Number.isFinite(n) ? Math.max(a, Math.min(b, n)) : d; };
  const vec = (v, d, a, b) => Array.isArray(v) ? [0, 1, 2].map(i => num(v[i] ?? v[0], d, a, b)) : Number.isFinite(Number(v)) ? [0, 1, 2].map(() => num(v, d, a, b)) : [d, d, d];
  const cor = v => { const s = String(v ?? "").trim().toLowerCase(); return /^#[0-9a-f]{6}$/.test(s) ? s : /^#[0-9a-f]{3}$/.test(s) ? "#" + [...s.slice(1)].map(c => c + c).join("") : CORES[s] || ""; };
  const texto = (v, n) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, n);

  // ---- the recipe, cleaned ----
  function limpar(receita) {
    if (!receita || typeof receita !== "object") return null;
    let total = 0;
    const peca = (p, fundo) => {
      if (!p || typeof p !== "object" || total >= MAX_PECAS) return null;
      const forma = FORMAS.includes(p.forma) ? p.forma : null;
      if (!forma) return null;
      total++;
      const o = p.orbita && typeof p.orbita === "object" ? p.orbita : null;
      // a bond between two points ("de" and "ate"): the cylinder turns itself, no angle to work out
      const brutos = forma === "ligacao" && p.de && p.ate ? [p.de, p.ate] : Array.isArray(p.pontos) ? p.pontos : [];
      const pontos = brutos.slice(0, MAX_PONTOS).map(q => vec(q, 0, -20, 20));
      const r = {
        forma, nome: texto(p.nome, 30), rotulo: texto(p.rotulo, 26), cor: cor(p.cor),
        pos: vec(p.pos, 0, -20, 20), tam: vec(p.tam ?? p.tamanho, 1, .01, 20), rot: vec(p.rot, 0, -360, 360),
        anim: ANIMS.includes(p.anim) ? p.anim : "", velocidade: num(p.velocidade, 1, -10, 10),
        orbita: o ? { raio: num(o.raio, 2, 0, 30), velocidade: num(o.velocidade, 1, -10, 10), inclinacao: num(o.inclinacao, 0, -90, 90),
          fase: num(o.fase, Math.random() * 360, -360, 360), trilha: o.trilha !== false } : null,
        voltas: num(p.voltas, 3, .25, 12), espessura: num(p.espessura, .12, .01, 1),
        quantidade: Math.round(num(p.quantidade, 400, 10, MAX_PARTICULAS)), pontos,
      };
      if (r.anim === "orbitar" && !r.orbita) r.orbita = { raio: 2, velocidade: r.velocidade, inclinacao: 0, fase: Math.random() * 360, trilha: true };
      if ((forma === "tubo" || forma === "linha" || forma === "ligacao") && pontos.length < 2) return null;
      r.filhos = fundo < 2 ? (Array.isArray(p.filhos) ? p.filhos : []).map(f => peca(f, fundo + 1)).filter(Boolean) : [];
      return r;
    };
    const pecas = (Array.isArray(receita.pecas) ? receita.pecas : []).map(p => peca(p, 0)).filter(Boolean);
    if (!pecas.length) return null;
    return { titulo: texto(receita.titulo, 48), estilo: receita.estilo === "solido" ? "solido" : "holograma", pecas };
  }

  // ---- building it ----
  function rotulo(T, txt) {
    const cv = document.createElement("canvas"), ctx = cv.getContext("2d"), px = 44;
    ctx.font = `600 ${px}px "Chakra Petch", system-ui, sans-serif`;
    const w = Math.ceil(ctx.measureText(txt).width) + 36;
    cv.width = w; cv.height = px + 26;
    ctx.font = `600 ${px}px "Chakra Petch", system-ui, sans-serif`; ctx.textBaseline = "middle";
    ctx.fillStyle = "rgba(2,20,18,.55)"; ctx.fillRect(0, 0, w, cv.height);
    ctx.strokeStyle = "rgba(143,240,228,.7)"; ctx.lineWidth = 2; ctx.strokeRect(1, 1, w - 2, cv.height - 2);
    ctx.fillStyle = "#ecfffa"; ctx.shadowColor = "#8ff0e4"; ctx.shadowBlur = 10; ctx.fillText(txt, 18, cv.height / 2 + 2);
    const tex = new T.CanvasTexture(cv); tex.colorSpace = T.SRGBColorSpace;
    const s = new T.Sprite(new T.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false }));
    s.userData.aspecto = w / cv.height; s.renderOrder = 10;
    return s;
  }
  function geometria(T, p) {
    switch (p.forma) {
      case "esfera": return new T.SphereGeometry(.5, 40, 24);
      case "cubo": case "caixa": return new T.BoxGeometry(1, 1, 1, 2, 2, 2);
      case "cilindro": return new T.CylinderGeometry(.5, .5, 1, 40, 1);
      case "cone": return new T.ConeGeometry(.5, 1, 40);
      case "piramide": return new T.ConeGeometry(.6, 1, 4);
      case "toro": return new T.TorusGeometry(.5, Math.min(.45, p.espessura * 1.5), 20, 64);
      case "anel": { const g = new T.RingGeometry(.5 - Math.min(.45, p.espessura), .5, 96); g.rotateX(-Math.PI / 2); return g; }
      case "capsula": return new T.CapsuleGeometry(.3, .5, 8, 20);
      case "helice": {
        const curva = new T.Curve(); curva.getPoint = (t, alvo = new T.Vector3()) =>
          alvo.set(Math.cos(t * Math.PI * 2 * p.voltas) * .5, t - .5, Math.sin(t * Math.PI * 2 * p.voltas) * .5);
        return new T.TubeGeometry(curva, Math.round(40 * p.voltas), p.espessura * .25, 10, false);
      }
      case "tubo": return new T.TubeGeometry(new T.CatmullRomCurve3(p.pontos.map(q => new T.Vector3(...q))), p.pontos.length * 16, p.espessura * .5, 10, false);
      default: return null;
    }
  }
  function material(T, p) {
    const c = new T.Color(p.cor || "#8ff0e4");
    return new T.MeshStandardMaterial({ color: c, emissive: c.clone().multiplyScalar(.28), roughness: .45, metalness: .15,
      side: p.forma === "anel" ? T.DoubleSide : T.FrontSide });
  }
  function construir(T, receita) {
    const raiz = new T.Group(), animados = [], rotulos = [];
    const monta = (p, pai) => {
      let alvo = pai;
      if (p.orbita) {   // the piece rides a pivot at its parent's centre
        const pivo = new T.Group(); pivo.rotation.x = p.orbita.inclinacao * Math.PI / 180; pai.add(pivo);
        const giro = new T.Group(); giro.rotation.y = p.orbita.fase * Math.PI / 180; pivo.add(giro);
        animados.push({ tipo: "orbita", g: giro, v: p.orbita.velocidade, base: giro.rotation.y });
        if (p.orbita.trilha && p.orbita.raio > 0) {
          const pts = []; for (let i = 0; i <= 128; i++) { const a = i / 128 * Math.PI * 2; pts.push(new T.Vector3(Math.cos(a) * p.orbita.raio, 0, Math.sin(a) * p.orbita.raio)); }
          const c = new T.Color(p.cor || "#8ff0e4");
          pivo.add(new T.Line(new T.BufferGeometry().setFromPoints(pts),
            new T.LineBasicMaterial({ color: c, transparent: true, opacity: .35, blending: T.AdditiveBlending, depthWrite: false })));
        }
        const no = new T.Group(); no.position.set(p.orbita.raio, 0, 0); giro.add(no); alvo = no;
      }
      const casca = new T.Group();   // place, turn and motion of this piece; its children ride on it
      casca.position.set(...p.pos); casca.rotation.set(...p.rot.map(g => g * Math.PI / 180)); alvo.add(casca);
      let obj;
      if (p.forma === "particulas") {
        const n = p.quantidade, pos = new Float32Array(n * 3);
        for (let i = 0; i < n; i++) { const r = Math.cbrt(Math.random()) * .5, a = Math.random() * Math.PI * 2, b = Math.acos(Math.random() * 2 - 1);
          pos.set([r * Math.sin(b) * Math.cos(a), r * Math.cos(b), r * Math.sin(b) * Math.sin(a)], i * 3); }
        const g = new T.BufferGeometry(); g.setAttribute("position", new T.BufferAttribute(pos, 3));
        obj = new T.Points(g, new T.PointsMaterial({ color: new T.Color(p.cor || "#bffff2"), size: .025, transparent: true, opacity: .9,
          blending: T.AdditiveBlending, depthWrite: false }));
      } else if (p.forma === "linha") {
        obj = new T.Line(new T.BufferGeometry().setFromPoints(p.pontos.map(q => new T.Vector3(...q))),
          new T.LineBasicMaterial({ color: new T.Color(p.cor || "#bffff2"), transparent: true, opacity: .85, blending: T.AdditiveBlending, depthWrite: false }));
      } else if (p.forma === "ligacao") {
        const a = new T.Vector3(...p.pontos[0]), b = new T.Vector3(...p.pontos[1]), d = b.clone().sub(a), L = d.length() || .001;
        obj = new T.Mesh(new T.CylinderGeometry(1, 1, 1, 24), material(T, p));
        obj.position.copy(a).add(b).multiplyScalar(.5);
        obj.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), d.normalize());
        obj.scale.set(p.espessura * .5, L, p.espessura * .5);
        if (p.cor) obj.userData.cor = p.cor;
      } else {
        obj = new T.Mesh(geometria(T, p), material(T, p));
        if (p.cor) obj.userData.cor = p.cor;   // the hologram glass keeps the piece's colour (stage.html)
      }
      // tubes and lines are drawn in the recipe's own units; the rest is a unit shape sized by tam
      if (!["tubo", "linha", "ligacao"].includes(p.forma)) obj.scale.set(...p.tam);
      obj.name = p.nome || p.forma;
      casca.add(obj);
      if (p.anim && p.anim !== "orbitar") animados.push({ tipo: p.anim, o: obj, v: p.velocidade, s: obj.scale.clone(), y: obj.position.y, fase: Math.random() * 6 });
      if (p.rotulo) rotulos.push({ txt: p.rotulo, pai: casca, alto: ["tubo", "linha", "ligacao"].includes(p.forma) ? .3 : p.tam[1] * .5 });
      for (const f of p.filhos) monta(f, casca);
    };
    for (const p of receita.pecas) monta(p, raiz);
    // labels last, sized to the whole object so they read the same on any scale
    raiz.updateMatrixWorld(true);
    const caixa = new T.Box3(); raiz.traverse(n => { if (n.isMesh) caixa.expandByObject(n); });   // solids only
    const tamanho = (caixa.isEmpty() ? new T.Box3().setFromObject(raiz) : caixa).getSize(new T.Vector3()).length() || 1;
    for (const r of rotulos) {
      const s = rotulo(T, r.txt), h = Math.max(tamanho * .032, .16);
      s.scale.set(h * s.userData.aspecto, h, 1); s.position.set(0, r.alto + h * .9, 0); r.pai.add(s);
    }
    const animar = t => {
      for (const a of animados) {
        if (a.tipo === "orbita") a.g.rotation.y = a.base + t * a.v * Math.PI * 2 / 8;   // speed 1 = a turn every 8 s
        else if (a.tipo === "girar") a.o.rotation.y = t * a.v * Math.PI * 2 / 6;
        else if (a.tipo === "pulsar") a.o.scale.copy(a.s).multiplyScalar(1 + .08 * Math.sin(t * a.v * 3 + a.fase));
        else if (a.tipo === "flutuar") a.o.position.y = a.y + .08 * Math.sin(t * a.v * 1.6 + a.fase);
      }
    };
    animar(0);
    return { obj: raiz, animar };
  }

  window.jarvisHolograma = { limpar, construir, rotulo, FORMAS, ANIMS, cores: Object.keys(CORES) };
})();
