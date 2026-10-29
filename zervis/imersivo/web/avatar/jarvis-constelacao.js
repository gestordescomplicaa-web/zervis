// SPDX-License-Identifier: AGPL-3.0-or-later
// The Zé as a constellation of light (approved in the hologram lab on 29/10/2026): points spread
// evenly over the Blender head, joined to their nearest neighbours, with pulses running along the
// links, a rim glow, a scan band, the brief glitches and an "assemble" when he appears.
// It only draws: the expressions, the mouth, the pulse, the glitches and the colour come from the
// same uniforms the chimpanzee logic already drives (jarvis-chimpanze.js), so the face behaves
// exactly as before. The skinned rest pose is baked once; the shape keys keep deforming on the GPU.

const PAPEIS = [
  ["CHIMP2_Holograma", "pele"], ["CHIMP2_Palpebra", "palpebra"], ["Orelhas_anatomicas", "orelha"],
  ["Pescoco_anatomico", "pescoco"], ["CHIMP_Olhos_HUD", "olhos"], ["CHIMP_Dentes", "dentes"], ["CHIMP_Boca_Interna", "boca"],
];
const papel = nome => PAPEIS.find(([prefixo]) => nome.startsWith(prefixo))?.[1] ?? "";
const DENSIDADE = .004;  // Blender metres between points (the head is ~0.2 m tall): ~4 thousand on the skin
const MONTAR_S = 2.2;

// Shared by every layer: shape keys, the assemble flight, the scan band and the neck fade.
const VERTICE = `
  #include <common>
  #include <morphtarget_pars_vertex>
  attribute vec4 aRnd;
  uniform float jvTempo, jvMontar, jvVarredura, jvEnergia, jvFalha, jvFalhaY, jvPx;
  uniform vec3 jvBocaCentro;
  float jvSumir;
  vec3 jvHolo(out vec3 nrm, out float k, out float faixa) {
    vec3 transformed = vec3(position);
    #include <morphtarget_vertex>
    vec3 objectNormal = vec3(normal);
    #include <morphnormal_vertex>
    nrm = objectNormal;
    jvSumir = smoothstep(.535, .575, position.y);  // the neck fades out, as in the Blender render
    float a = clamp(jvMontar * 1.5 - aRnd.y * .5, 0., 1.);
    k = 1. - pow(1. - a, 3.);
    vec3 dir = normalize(vec3(aRnd.z - .5, aRnd.w - .5, fract(aRnd.z * 7.13 + aRnd.w * 3.71) - .5) + 1e-4);
    vec3 inicio = transformed + dir * (.06 + aRnd.w * .16) - vec3(0., .1 + .05 * aRnd.x, 0.);
    vec3 p = mix(inicio, transformed, k);
    faixa = jvVarredura < 0. ? 0. : exp(-pow((position.y - jvVarredura) / .014, 2.));
    return p + nrm * faixa * .0018;
  }`;
// A glitch shifts one horizontal slice sideways for a few frames (the same as the chimpanzee's).
const FALHA = `gl_Position.x += jvFalha * step(abs(gl_Position.y / gl_Position.w - jvFalhaY), .035) * gl_Position.w * .05;`;
const SAIDA = "\n#include <colorspace_fragment>\n";

function materiais(T, uniformes) {
  const luz = { transparent: true, depthWrite: false, blending: T.CustomBlending, blendSrc: T.OneFactor, blendDst: T.OneFactor };
  const pontos = defines => new T.ShaderMaterial({
    ...luz, uniforms: uniformes, defines,
    vertexShader: VERTICE + `
      attribute float aSel; uniform float jvBoca; varying float vA, vQuente;
      void main() {
        vec3 n; float k, faixa; vec3 p = jvHolo(n, k, faixa);
        vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv; ${FALHA}
        float rim = pow(1. - abs(dot(normalize(normalMatrix * n), normalize(-mv.xyz))), 2.);
        float tw = .6 + .4 * sin(jvTempo * (1.2 + aRnd.x * 2.6) + aRnd.x * 60.);
        float boca = clamp(jvEnergia * 1.4, 0., 1.) * smoothstep(.028, 0., distance(position, jvBocaCentro));
        vQuente = clamp(faixa * .9 + boca, 0., 1.);
        vA = ((.16 + .64 * rim) * tw + faixa * .8 + boca * .45) * (.25 + .75 * k) * jvSumir * aSel;
        #ifdef JV_DENTES
          vA *= smoothstep(.05, .3, jvBoca);  // teeth only with the lips apart
        #endif
        gl_PointSize = aSel * .0193 * jvPx * (.7 + .6 * aRnd.x) * (1. + faixa * 1.4 + boca * .8) / (-mv.z);
        #ifdef JV_HALO
          gl_PointSize *= 3.4; vA *= .11;  // the soft glow around each point (bloom, without a post pass)
        #endif
      }`,
    fragmentShader: `uniform vec3 jvCor; uniform float jvGanho, jvTremor; varying float vA, vQuente;
      void main() {
        float d = length(gl_PointCoord - .5); if (d > .5) discard;
        float a = smoothstep(.5, 0., d); a *= a;
        #ifdef JV_HALO
          a = exp(-d * d * 16.);
        #endif
        vec3 c = mix(jvCor, vec3(1.), vQuente * .75) * a * vA * jvGanho * jvTremor;
        gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));` + SAIDA + "}",
  });
  return {
    pontos: pontos({}),
    dentes: pontos({ JV_DENTES: 1 }),
    halo: pontos({ JV_HALO: 1 }),
    linhas: new T.ShaderMaterial({
      ...luz, uniforms: uniformes,
      vertexShader: VERTICE + `
        varying float vFase, vA;
        void main() {
          vec3 n; float k, faixa; vec3 p = jvHolo(n, k, faixa);
          vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv; ${FALHA}
          float rim = pow(1. - abs(dot(normalize(normalMatrix * n), normalize(-mv.xyz))), 1.6);
          vFase = aRnd.x;
          vA = ((.07 + .36 * rim) + faixa * .5) * k * k * jvSumir;
        }`,
      fragmentShader: `uniform vec3 jvCor; uniform float jvTempo, jvFluxo, jvGanho, jvTremor; varying float vFase, vA;
        void main() {
          float pulso = smoothstep(.9, 1., fract(vFase * 4. - jvTempo * jvFluxo));
          vec3 c = mix(jvCor * .55, vec3(1.), pulso * .8) * vA * (1. + pulso * 3.) * jvGanho * jvTremor;
          gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));` + SAIDA + "}",
    }),
    brilho: base => new T.ShaderMaterial({
      ...luz, uniforms: uniformes,
      vertexShader: VERTICE + `
        varying vec3 vN, vV; varying float vY, vFaixa, vSumir;
        void main() {
          vec3 n; float k, faixa; vec3 p = jvHolo(n, k, faixa);
          vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv; ${FALHA}
          vN = normalMatrix * n; vV = -mv.xyz; vY = position.y; vFaixa = faixa; vSumir = jvSumir;
        }`,
      fragmentShader: `uniform vec3 jvCor; uniform float jvTempo, jvMontar, jvGanho, jvTremor; varying vec3 vN, vV; varying float vY, vFaixa, vSumir;
        void main() {
          float rim = pow(1. - abs(dot(normalize(vN), normalize(vV))), 3.);
          float faixas = pow(.5 + .5 * sin(vY * 3800. - jvTempo * 5.), 10.);
          vec3 c = (jvCor * (rim * .32 + faixas * .035 + ${base}) + vec3(1.) * vFaixa * .2)
            * smoothstep(.7, 1., jvMontar) * vSumir * jvGanho * jvTremor;
          gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));` + SAIDA + "}",
    }),
    // Depth only, a hair behind the surface: the back of the head never shows through the face.
    oclusor: new T.ShaderMaterial({
      uniforms: uniformes, colorWrite: false, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 2,
      vertexShader: VERTICE + `void main() { vec3 n; float k, faixa;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(jvHolo(n, k, faixa), 1.); ${FALHA} }`,
      fragmentShader: "void main() { gl_FragColor = vec4(0.); }",
    }),
  };
}

let semente = 7;
const aleatorio = () => ((semente = (semente * 16807) % 2147483647) - 1) / 2147483646;

// The skinned rest pose baked into a plain geometry: Points and lines cannot be skinned in three.js.
// The rig is static (the head moves as a whole), so the shape keys stay valid on top of it.
function assada(T, malha) {
  const g0 = malha.geometry, pos0 = g0.attributes.position, nor0 = g0.attributes.normal, n = pos0.count;
  const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), rnd = new Float32Array(n * 4);
  const a = new T.Vector3(), b = new T.Vector3(), nn = new T.Vector3();
  for (let i = 0; i < n; i++) {
    a.fromBufferAttribute(pos0, i); nn.fromBufferAttribute(nor0, i);
    b.copy(a).addScaledVector(nn, .001);
    if (malha.isSkinnedMesh) { malha.applyBoneTransform(i, a); malha.applyBoneTransform(i, b); }
    a.toArray(pos, i * 3); b.sub(a).normalize().toArray(nor, i * 3);
  }
  for (let i = 0; i < rnd.length; i++) rnd[i] = aleatorio();
  const g = new T.BufferGeometry();
  g.setAttribute("position", new T.BufferAttribute(pos, 3));
  g.setAttribute("normal", new T.BufferAttribute(nor, 3));
  g.setAttribute("aRnd", new T.BufferAttribute(rnd, 4));
  g.morphAttributes = g0.morphAttributes; g.morphTargetsRelative = g0.morphTargetsRelative;
  if (g0.index) g.setIndex(g0.index);
  return g;
}

function grade(cel) {
  const m = new Map(), k = (x, y, z) => `${x},${y},${z}`;
  return {
    por(p, i) { const c = k(Math.floor(p.x / cel), Math.floor(p.y / cel), Math.floor(p.z / cel)); (m.get(c) || m.set(c, []).get(c)).push(i); },
    perto(p, f) {
      const cx = Math.floor(p.x / cel), cy = Math.floor(p.y / cel), cz = Math.floor(p.z / cel);
      for (let x = -1; x <= 1; x++) for (let y = -1; y <= 1; y++) for (let z = -1; z <= 1; z++) {
        const l = m.get(k(cx + x, cy + y, cz + z)); if (l) for (const i of l) f(i);
      }
    },
  };
}
// Vertices at least d apart, in a fixed random order: an even, stable constellation.
function escolher(T, pos, d) {
  const n = pos.count, ordem = [...Array(n).keys()];
  for (let i = n - 1; i > 0; i--) { const j = Math.floor(aleatorio() * (i + 1)); [ordem[i], ordem[j]] = [ordem[j], ordem[i]]; }
  const g = grade(d), v = new T.Vector3(), w = new T.Vector3(), fica = [];
  for (const i of ordem) {
    v.fromBufferAttribute(pos, i); let livre = true;
    g.perto(v, j => { if (livre && w.fromBufferAttribute(pos, j).distanceToSquared(v) < d * d) livre = false; });
    if (livre) { g.por(v, i); fica.push(i); }
  }
  return fica;
}
// Each kept point joined to its k nearest kept neighbours within r.
function ligar(T, pos, idx, r, kMax) {
  const g = grade(r), v = new T.Vector3(), w = new T.Vector3(), feitos = new Set(), pares = [];
  for (const i of idx) g.por(v.fromBufferAttribute(pos, i), i);
  for (const i of idx) {
    v.fromBufferAttribute(pos, i); const viz = [];
    g.perto(v, j => { if (j === i) return; const d2 = w.fromBufferAttribute(pos, j).distanceToSquared(v); if (d2 < r * r) viz.push([d2, j]); });
    viz.sort((x, y) => x[0] - y[0]);
    for (const [, j] of viz.slice(0, kMax)) {
      const c = i < j ? i * 65536 + j : j * 65536 + i;
      if (!feitos.has(c)) { feitos.add(c); pares.push(i, j); }
    }
  }
  return pares;
}

// Builds the constellation next to each mesh of the head (same parent, same transform) and hides the
// meshes; returns what the chimpanzee update loop calls each frame.
export function constelacao(T, cabeca, uniformes, densidade = DENSIDADE) {
  Object.assign(uniformes, {
    jvMontar: { value: 0 }, jvFluxo: { value: .3 }, jvPx: { value: 840 }, jvBocaCentro: { value: new T.Vector3() },
  });
  const M = materiais(T, uniformes), geometrias = [], brilhos = [M.brilho(".006"), M.brilho(".30")];
  const malhas = []; cabeca.traverse(o => { if (o.isMesh && papel(o.material.name)) malhas.push(o); });
  cabeca.updateMatrixWorld(true);
  let pontos = 0, ligacoes = 0;
  for (const m of malhas) {
    const tipo = papel(m.material.name), g = assada(T, m); geometrias.push(g);
    const junta = (obj, ordem) => {
      obj.morphTargetInfluences = m.morphTargetInfluences; obj.morphTargetDictionary = m.morphTargetDictionary;
      obj.position.copy(m.position); obj.quaternion.copy(m.quaternion); obj.scale.copy(m.scale);
      obj.frustumCulled = false; obj.renderOrder = ordem; obj.name = `${m.name}_${tipo}`; m.parent.add(obj); return obj;
    };
    m.visible = false;
    if (tipo === "boca") { junta(new T.Mesh(g, M.oclusor), -1); continue; }
    if (tipo === "olhos") { junta(new T.Mesh(g, brilhos[1]), 6); continue; }
    const pos = g.attributes.position, idx = escolher(T, pos, tipo === "pele" ? densidade : densidade * .85);
    const sel = new Float32Array(pos.count); for (const i of idx) sel[i] = 1;
    g.setAttribute("aSel", new T.BufferAttribute(sel, 1));
    pontos += idx.length;
    if (tipo === "dentes") { junta(new T.Points(g, M.dentes), 2); continue; }
    junta(new T.Mesh(g, M.oclusor), -1);
    junta(new T.Mesh(g, brilhos[0]), 3);
    const pares = ligar(T, pos, idx, densidade * 2.1, 3), gl = new T.BufferGeometry();
    for (const [k, a] of Object.entries(g.attributes)) gl.setAttribute(k, a);
    gl.morphAttributes = g.morphAttributes; gl.morphTargetsRelative = g.morphTargetsRelative; gl.setIndex(pares);
    geometrias.push(gl); ligacoes += pares.length / 2;
    junta(new T.LineSegments(gl, M.linhas), 4);
    junta(new T.Points(g, M.pontos), 5);
    if (tipo !== "pescoco") junta(new T.Points(g, M.halo), 2);
    if (tipo === "pele") {  // the mouth glows with the voice: centre of what Boca_Aberta moves most
      const alvo = g.morphAttributes.position?.[m.morphTargetDictionary?.Boca_Aberta];
      if (alvo) {
        let max = 0; const mag = new Float32Array(alvo.count);
        for (let i = 0; i < alvo.count; i++) { mag[i] = Math.hypot(alvo.getX(i), alvo.getY(i), alvo.getZ(i)); max = Math.max(max, mag[i]); }
        const c = new T.Vector3(), v = new T.Vector3(); let n = 0;
        mag.forEach((l, i) => { if (l > max * .55) { c.add(v.fromBufferAttribute(pos, i)); n++; } });
        uniformes.jvBocaCentro.value.copy(c.divideScalar(Math.max(n, 1)));
      }
    }
  }
  let inicio = null;
  return {
    pontos, ligacoes,
    // estado: the ring state; links pulse faster while he thinks or listens.
    atualizar(t, dt, estado, reduzir) {
      inicio ??= t;
      uniformes.jvMontar.value = reduzir ? 1 : Math.min(1, (t - inicio) / MONTAR_S);
      const fluxo = estado === "thinking" ? 1.6 : estado === "speaking" ? .9 : estado === "listening" ? .55 : .25;
      uniformes.jvFluxo.value += (fluxo - uniformes.jvFluxo.value) * (1 - Math.exp(-dt * 3));
    },
    montar() { inicio = null; },
    tela(px) { uniformes.jvPx.value = px; },
    descartar() {
      geometrias.forEach(g => g.dispose());
      [M.pontos, M.dentes, M.halo, M.linhas, M.oclusor, ...brilhos].forEach(m => m.dispose());
    },
  };
}

// The projector under the Zé and the rings around him (the lab's scene, sized to the avatar: the head
// is ALTURA = 3.15 units tall, centred a little below 0). It stays still while the head sways and
// spins; the rings turn faster with the links (jvFluxo).
export function projetor(T, uniformes) {
  const luz = { transparent: true, depthWrite: false, blending: T.CustomBlending, blendSrc: T.OneFactor, blendDst: T.OneFactor };
  const grupo = new T.Group(); grupo.name = "projetor";
  const materiais = [], geometrias = [];
  const anel = (r1, r2, { dash = 1, fill = 1, speed = 0, alpha = .5 } = {}) => {
    const m = new T.ShaderMaterial({
      ...luz, side: T.DoubleSide,
      uniforms: { ...uniformes, uDash: { value: dash }, uFill: { value: fill }, uSpeed: { value: speed }, uAlpha: { value: alpha } },
      vertexShader: "varying vec3 vP; void main() { vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }",
      fragmentShader: `uniform vec3 jvCor; uniform float jvTempo, jvFluxo, jvGanho, uDash, uFill, uSpeed, uAlpha; varying vec3 vP;
        void main() { float a = atan(vP.y, vP.x) / 6.2831853 + .5;
          float on = step(fract(a * uDash + jvTempo * uSpeed * (.6 + jvFluxo)), uFill);
          vec3 c = jvCor * on * uAlpha * jvGanho; gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));` + SAIDA + "}",
    });
    const g = new T.RingGeometry(r1, r2, 192, 1); materiais.push(m); geometrias.push(g);
    return new T.Mesh(g, m);
  };
  const BASE = -2.05;
  const chao = new T.Group(); chao.rotation.x = -Math.PI / 2; chao.position.y = BASE; grupo.add(chao);
  chao.add(anel(.95, .962, { alpha: .55 }), anel(1.13, 1.18, { dash: 48, fill: .55, speed: .02, alpha: .4 }),
    anel(1.32, 1.34, { dash: 3, fill: .7, speed: -.03, alpha: .45 }), anel(1.58, 1.67, { dash: 120, fill: .18, speed: .008, alpha: .3 }),
    anel(1.95, 1.958, { dash: 6, fill: .08, speed: .05, alpha: .55 }));
  const disco = new T.Mesh(new T.CircleGeometry(.95, 96), new T.ShaderMaterial({
    ...luz, uniforms: uniformes,
    vertexShader: "varying vec2 vP; void main() { vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }",
    fragmentShader: `uniform vec3 jvCor; uniform float jvEnergia, jvGanho; varying vec2 vP;
      void main() { float r = length(vP) / .95; vec3 c = jvCor * (.1 + .25 * jvEnergia) * pow(1. - r, 1.5) * jvGanho;
        gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));` + SAIDA + "}",
  }));
  chao.add(disco); materiais.push(disco.material); geometrias.push(disco.geometry);
  // The light beam from the projector up through the head.
  const feixe = new T.Mesh(new T.CylinderGeometry(1.73, .95, 3.9, 96, 1, true), new T.ShaderMaterial({
    ...luz, side: T.DoubleSide, uniforms: uniformes,
    vertexShader: `varying vec2 vUv; varying vec3 vN, vV; void main() { vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.);
      vN = normalMatrix * normal; vV = -mv.xyz; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform vec3 jvCor; uniform float jvTempo, jvEnergia, jvGanho; varying vec2 vUv; varying vec3 vN, vV;
      void main() { float borda = pow(1. - abs(dot(normalize(vN), normalize(vV))), 1.4);
        float risco = .55 + .45 * sin(vUv.x * 6.2831853 * 36. + jvTempo * .6) * sin(vUv.x * 6.2831853 * 7. - jvTempo * .3);
        vec3 c = jvCor * pow(1. - vUv.y, 1.8) * (.15 + borda) * risco * (.03 + .04 * jvEnergia) * jvGanho;
        gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));` + SAIDA + "}",
  }));
  feixe.position.y = BASE + 1.95; grupo.add(feixe); materiais.push(feixe.material); geometrias.push(feixe.geometry);
  // Motes rising in the beam.
  const N = 320, sem = new Float32Array(N * 4);
  for (let i = 0; i < sem.length; i++) sem[i] = aleatorio();
  const gm = new T.BufferGeometry();
  gm.setAttribute("position", new T.BufferAttribute(new Float32Array(N * 3), 3));
  gm.setAttribute("aS", new T.BufferAttribute(sem, 4));
  const motes = new T.Points(gm, new T.ShaderMaterial({
    ...luz, uniforms: uniformes,
    vertexShader: `attribute vec4 aS; uniform float jvTempo, jvEnergia, jvPx; varying float vA;
      void main() { float y = fract(aS.y + jvTempo * (.03 + .05 * aS.z) * (.6 + jvEnergia));
        float r = (.95 + .7 * y) * sqrt(aS.x), an = aS.w * 6.2831853 + jvTempo * .08 * (aS.z - .5);
        vec4 mv = modelViewMatrix * vec4(cos(an) * r, ${BASE.toFixed(2)} + y * 3.9, sin(an) * r, 1.); gl_Position = projectionMatrix * mv;
        vA = smoothstep(0., .1, y) * (1. - y) * (.4 + .6 * aS.z); gl_PointSize = (2. + 3. * aS.x) * jvPx * .0008 / (-mv.z) * 11.7; }`,
    fragmentShader: `uniform vec3 jvCor; uniform float jvGanho; varying float vA;
      void main() { float d = length(gl_PointCoord - .5); if (d > .5) discard;
        vec3 c = jvCor * smoothstep(.5, 0., d) * vA * .7 * jvGanho; gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));` + SAIDA + "}",
  }));
  motes.frustumCulled = false; grupo.add(motes); materiais.push(motes.material); geometrias.push(gm);
  // Rings orbiting the head.
  const orbita = new T.Group(); orbita.position.y = -.05; grupo.add(orbita);
  const o1 = anel(2.08, 2.095, { dash: 4, fill: .62, speed: .04, alpha: .4 }), o2 = anel(2.33, 2.355, { dash: 90, fill: .25, speed: -.015, alpha: .28 });
  const o3 = anel(2.5, 2.507, { dash: 2, fill: .15, speed: .07, alpha: .5 });
  o1.rotation.x = o2.rotation.x = Math.PI / 2 - .22; o3.rotation.set(Math.PI / 2 - .5, .35, 0);
  orbita.add(o1, o2, o3);
  return {
    grupo,
    atualizar(dt, reduzir) {
      if (reduzir) return;
      const f = uniformes.jvFluxo?.value ?? .3;
      orbita.rotation.y += dt * .15 * (.6 + f); o3.rotation.z += dt * .25 * (.6 + f);
      orbita.scale.setScalar(1 + (uniformes.jvEnergia?.value ?? 0) * .03);
    },
    descartar() { geometrias.forEach(g => g.dispose()); materiais.forEach(m => m.dispose()); },
  };
}
