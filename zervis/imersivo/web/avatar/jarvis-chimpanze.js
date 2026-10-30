// SPDX-License-Identifier: AGPL-3.0-or-later
// Holographic chimpanzee made in Blender by gdautomacao.ia (jarvis-chimpanze.glb; see README.md).
// glTF cannot carry Blender's node shaders or
// geometry-node fur, so the look of that material is rebuilt here: detail from three projections
// (front, profile, back; at the nape the back view replaces the profile so the photographed ear
// does not land on the scalp), rim, scan lines, the sweep band, the neck fade, a firmer nape where
// there is fur, the HUD eyes, the teeth, the anatomical ears and neck, and the combed fur where the
// file's `pelo` attribute marks it. Colours are Blender's blue (anger turns it red), not the theme.
// A real hologram adds light and never darkens: the skin is drawn additively over a depth
// prepass (front surface only, so teeth and the back of the head stay hidden), with screen
// scan lines, flicker, a rolling interference bar and brief signal glitches.
// Speech and emotions (alegria, duvida, raiva, tristeza) drive the file's own shape keys, including the
// variations avatar/expressoes_blender.py adds on top of the untouched base mesh.
// Since 29/10/2026 the default look is the constellation (jarvis-constelacao.js), in the theme colour;
// the Blender-style skin above stays as estilo "classico" until the new look is approved.
import { constelacao, projetor } from "./jarvis-constelacao.js";

const URL_MODELO = new URL("./jarvis-chimpanze.glb", import.meta.url).href;
const VISTAS = ["frente", "perfil", "costas"].map(v => new URL(`./jarvis-chimpanze-${v}.png`, import.meta.url).href);
const CIANO = { r: 0, g: .79, b: 1 }, AZUL = { r: 0, g: .18, b: 1 };  // linear, as in Blender
const ALTURA = 3.15, LARGURA = 3.7, FIOS = 15000;  // fits the ring; ears make it wide
const EMOCOES = {
  alegria: { chaves: { Sorriso_Dentes: 1, Sorriso: .5, Semicerrar: .3, Sobrancelha_Erguida: .3 }, inclinar: 0, baixar: -.04, falhas: 0, brilho: 1.15 },
  duvida: { chaves: { Sobrancelha_Duvida: 1, Olhar_Cima: .3, Olhar_Esq: .45, Semicerrar: .15 }, inclinar: .1, baixar: 0, falhas: 0, brilho: 1 },
  raiva: { chaves: { Sobrancelha_Brava: 1, Semicerrar: .5, Rosnar: 1 }, inclinar: 0, baixar: .07, falhas: 1, brilho: 1.1 },
  tristeza: { chaves: { Sobrancelha_Triste: 1, Boca_Triste: 1, Olhar_Baixo: .5, Semicerrar: .3 }, inclinar: -.05, baixar: .1, falhas: 0, brilho: .72 },
};
export const NOMES_DAS_EMOCOES = Object.keys(EMOCOES);
const TODAS_AS_CHAVES = [...new Set(Object.values(EMOCOES).flatMap(x => Object.keys(x.chaves)))];

// The muzzle front (Blender metres, glTF axes: y up, +z forward): lips from chin to under the nose.
const GLSL_FOCINHO = `
float jvFocinho(vec3 p) {
  return (1. - smoothstep(.045, .06, abs(p.x))) * smoothstep(.595, .605, p.y)
    * (1. - smoothstep(.66, .672, p.y)) * smoothstep(.06, .085, p.z);
}`;
const GLSL_COMUM = GLSL_FOCINHO + `
uniform float jvTempo, jvEnergia, jvVarredura, jvGanho, jvBoca, jvTremor, jvFalha, jvFalhaY; uniform vec3 jvCor, jvFundo;
float jvLinha(float c, float f, float w) { return clamp((abs(fract(c * f) - .5) - (.5 - w)) / w, 0., 1.); }
float jvFaixa(float a, float b, float x) { return clamp((x - a) / (b - a), 0., 1.); }
// Saturating like Blender's emission + bloom: hue kept, only the brightest cores turn white.
// Like Blender's view transform: the brightest light also loses saturation toward white.
vec3 jvLuz(vec3 c) {
  vec3 l = 1. - exp(-c) + max(vec3(0.), c - 2.) * .15;
  float pico = max(l.r, max(l.g, l.b));
  return mix(l, vec3(pico), .55 * smoothstep(.25, 1., pico));
}
// Projector texture in screen space: alternating scan lines and a slow rolling bar.
float jvTela() {
  return (.8 + .2 * step(.5, fract(gl_FragCoord.y * .5))) * jvTremor
    * (1. + .5 * jvFaixa(.97, 1., fract(gl_FragCoord.y / 300. - jvTempo * .3)));
}`;
// A glitch shifts one horizontal slice of the image sideways for a few frames.
const GLSL_FALHA = `
  gl_Position.x += jvFalha * step(abs(gl_Position.y / gl_Position.w - jvFalhaY), .035) * gl_Position.w * .05;`;
const UNIFORMES_DA_FALHA = "uniform float jvFalha, jvFalhaY;\n";

// Each glTF material gets the same fragment idea as its Blender node tree (kind = material name).
const FRAGMENTOS = {
  // jvPos is in Blender metres with glTF axes: y is Blender Z (up), -z is Blender Y (back).
  CHIMP2_Holograma: `
    float nuca = jvFaixa(-.005, .022, -jvPos.z), perfil = jvPeso.g * (1. - nuca);
    float det = texture2D(jvVista0, jvUv0).r * jvPeso.r + texture2D(jvVista1, jvUv1).r * perfil
              + texture2D(jvVista2, vec2(jvUv2.x * .7 + .15, jvUv2.y)).r * (jvPeso.b + jvPeso.g * nuca);
    // The reference photo's lip wrinkles read as a row of teeth on a hologram: softened.
    float dline = pow(jvFaixa(.22, .70, det), 1.3) * (1. - .7 * jvFocinho(jvPos));
    float rim = pow(1. - abs(dot(normalize(normal), normalize(vViewPosition))), .84);
    float scan = jvLinha(jvPos.y, 260., .10);
    float band = 1. - jvFaixa(0., .012, abs(jvPos.y - jvVarredura));
    float fade = jvFaixa(.535, .566, jvPos.y);
    float s = (dline * 3.2 + rim * 1.9 + scan * .25 + band * 2.5 + .34 + jvEnergia * .4) * fade;
    float al = clamp(dline * .55 + rim * .6 + band * .3 + .34, 0., 1.) * fade;
    al = max(al, jvPelo * jvFaixa(-.015, .01, -jvPos.z));  // the nape with fur is not see-through
    outgoingLight = jvLuz(mix(jvFundo, jvCor, clamp(max(dline, max(rim, band)), 0., 1.)) * s * .4) * al * jvTela();`,
  // Ears and neck: Blender's dark blue with scan-line emission, read here as faint light with a rim.
  CHIMP_Anatomia: `
    float rim = pow(1. - abs(dot(normalize(normal), normalize(vViewPosition))), 1.5);
    float linhas = .19 + .035 * sin(jvPos.y * 2100.);
    outgoingLight = jvLuz(mix(jvFundo, jvCor, .3 + rim * .5) * (linhas * 2.2 + rim * 1.4)) * .5 * jvTela();`,
  // The eyes are opaque, unlike the rest: a dark lens with the lit iris on top. Light added over a
  // bright room vanished (08/10/2026); a solid base keeps their shape on any background.
  CHIMP_Olhos_HUD: `
    #define JV_OPACO
    float v = 1. - jvUv3.y;
    float pupila = 1. - smoothstep(.055, .075, v);
    float iris = smoothstep(.065, .08, v) * (1. - smoothstep(.19, .205, v));
    float anel = smoothstep(.195, .205, v) * (1. - smoothstep(.22, .232, v)), esclera = smoothstep(.225, .24, v);
    float s = (iris * (4. + jvLinha(jvUv3.x, 24., .25) * 6.) + anel * 14. + esclera * .5) * .45 * jvGanho;
    vec3 lente = mix(vec3(.006, .03, .075), vec3(.0), pupila);
    outgoingLight = lente + jvLuz(mix(jvCor, vec3(1.), anel * .7) * s * .42) * (1. - pupila * .9) * jvTela();`,
  // Teeth: pale enamel with dark gaps, opaque like the eyes; hidden by the lips until they part.
  CHIMP_Dentes: `
    #define JV_OPACO
    if (jvBoca < .04) discard;  // only when the lips part (speech, the toothy smile)
    float vao = jvLinha(jvUv3.x, 16., .12), rim = 1. - abs(dot(normalize(normal), normalize(vViewPosition)));
    vec3 esmalte = mix(vec3(.32, .55, .7), vec3(.8, .95, 1.), .5 + .5 * jvCor.g);  // pale, tinted by the light
    outgoingLight = mix(esmalte * (.75 + rim * .25), vec3(.01, .04, .08), vao * .85) * jvTela();`,
  // The inside of the mouth: opaque and dark, so an open mouth never shows the room behind it.
  CHIMP_Boca_Interna: `
    #define JV_OPACO
    outgoingLight = jvFundo * .06 + vec3(.004, .012, .025);`,
};
FRAGMENTOS.CHIMP2_Palpebra = FRAGMENTOS.CHIMP2_Holograma;
// Blender adds suffixes (".001", "_NucaSemTransparencia"); the kind is the stable prefix.
const TIPOS = [
  ["CHIMP2_Holograma", "CHIMP2_Holograma"], ["CHIMP2_Palpebra", "CHIMP2_Palpebra"],
  ["Orelhas_anatomicas", "CHIMP_Anatomia"], ["Pescoco_anatomico", "CHIMP_Anatomia"],
  ["CHIMP_Olhos_HUD", "CHIMP_Olhos_HUD"], ["CHIMP_Dentes", "CHIMP_Dentes"], ["CHIMP_Boca_Interna", "CHIMP_Boca_Interna"],
];
const tipo = nome => TIPOS.find(([prefixo]) => nome.startsWith(prefixo))?.[1] ?? "CHIMP2_Holograma";

function holograma(T, nome, uniformes) {
  const m = new T.MeshStandardMaterial({ color: 0x000000, metalness: 0, roughness: 1 });
  m.name = nome;
  // Light is added (alpha too, so faint parts stay see-through over the camera). The skin and
  // the lids test against their own depth prepass; the eyes and the cavity write depth.
  // Eyes and teeth are opaque: they cover what is behind them, so they keep their shape over a
  // bright room. Everything else adds light.
  const olhos = nome === "CHIMP_Olhos_HUD" || nome === "CHIMP_Dentes" || nome === "CHIMP_Boca_Interna";
  if (!olhos) Object.assign(m, { blending: T.CustomBlending, blendSrc: T.OneFactor, blendDst: T.OneFactor });
  const pele = nome.startsWith("CHIMP2_") || nome === "CHIMP_Anatomia";  // these have the prepass
  m.transparent = pele;
  m.depthWrite = !m.transparent;
  m.depthFunc = T.LessEqualDepth;
  m.side = nome === "CHIMP_Dentes" || nome === "CHIMP_Boca_Interna" ? T.DoubleSide : T.FrontSide;
  m.onBeforeCompile = s => {
    Object.assign(s.uniforms, uniformes);
    s.vertexShader = `attribute vec2 jv_uv0, jv_uv1, jv_uv2, jv_uv3; attribute vec4 color_1; attribute float _pelo;
      varying vec3 jvPos, jvPeso; varying vec2 jvUv0, jvUv1, jvUv2, jvUv3; varying float jvPelo;\n` + UNIFORMES_DA_FALHA + s.vertexShader.replace(
      "#include <morphtarget_vertex>", `#include <morphtarget_vertex>
      jvPos = transformed; jvPeso = color_1.rgb; jvPelo = _pelo; jvUv0 = jv_uv0; jvUv1 = jv_uv1; jvUv2 = jv_uv2; jvUv3 = jv_uv3;`)
      .replace("#include <project_vertex>", "#include <project_vertex>" + GLSL_FALHA);
    s.fragmentShader = `uniform sampler2D jvVista0, jvVista1, jvVista2;
      varying vec3 jvPos, jvPeso; varying vec2 jvUv0, jvUv1, jvUv2, jvUv3; varying float jvPelo;` + GLSL_COMUM + "\n"
      + s.fragmentShader.replace("#include <opaque_fragment>", FRAGMENTOS[nome]
        + "\ndiffuseColor.a = max(outgoingLight.r, max(outgoingLight.g, outgoingLight.b));"
        + "\n#ifdef JV_OPACO\ndiffuseColor.a = 1.;\n#endif\n#include <opaque_fragment>");
  };
  m.toneMapped = false;
  m.customProgramCacheKey = () => "jarvis-chimpanze-v7-" + nome;
  return m;
}

// The prepass writes depth (so the additive skin shows only its front) and lays a smoked-glass
// shade behind the light: over a bright room the head still reads, and the camera still shows
// faintly through it. Same skin, morphs, neck fade and glitch as the light pass.
const SOMBRA = .85;
function profundidade(T, uniformes) {
  // DoubleSide: through a gap in the lips one sees the inside of the head, shaded too, not the room.
  const m = new T.MeshBasicMaterial({ color: 0x000000, transparent: true, depthWrite: true, side: T.DoubleSide });
  m.onBeforeCompile = s => {
    Object.assign(s.uniforms, uniformes);
    s.vertexShader = UNIFORMES_DA_FALHA + "varying vec3 jvP;\n" + s.vertexShader
      .replace("#include <morphtarget_vertex>", "#include <morphtarget_vertex>\njvP = transformed;")
      .replace("#include <project_vertex>", "#include <project_vertex>" + GLSL_FALHA);
    // The muzzle is nearly solid, so nothing inside the closed mouth shows through the lips.
    s.fragmentShader = "varying vec3 jvP;\n" + GLSL_FOCINHO + "\n" + s.fragmentShader.replace("#include <opaque_fragment>",
      `#include <opaque_fragment>\ngl_FragColor = vec4(0., 0., 0., mix(${SOMBRA} * clamp((jvP.y - .535) / .031, 0., 1.), .97, jvFocinho(jvP)));`);
  };
  m.customProgramCacheKey = () => "jarvis-chimpanze-sombra-v2";
  return m;
}

// Combed fur like the geometry-node "Pelo": strands flow down and back over the surface.
function pelo(T, malha, uniformes) {
  const pos = malha.geometry.attributes.position, nrm = malha.geometry.attributes.normal;
  const idx = malha.geometry.index, v = new T.Vector3(), n = new T.Vector3();
  const P = [], N = [];
  for (let i = 0; i < pos.count; i++) {
    malha.getVertexPosition(i, v); v.applyMatrix4(malha.matrixWorld); P.push(v.toArray());
    n.fromBufferAttribute(nrm, i).transformDirection(malha.matrixWorld); N.push(n.toArray());
  }
  // Where Blender grows fur: the `pelo` attribute (exported as _pelo by expressoes_blender.py).
  const marcado = malha.geometry.attributes._pelo;
  if (!marcado) throw new Error("o chimpanzé veio sem o atributo _pelo");
  // Triangles weighted by area and fur mask; then a fixed-seed random draw keeps the look stable.
  const tris = [], pesos = [], pa = new T.Vector3(), pb = new T.Vector3(), pc = new T.Vector3();
  let total = 0;
  for (let k = 0; k < idx.count; k += 3) {
    const a = idx.getX(k), b = idx.getX(k + 1), c = idx.getX(k + 2);
    const mask = (marcado.getX(a) + marcado.getX(b) + marcado.getX(c)) / 3;
    if (mask < .5) continue;
    pa.fromArray(P[a]); pb.fromArray(P[b]).sub(pa); pc.fromArray(P[c]).sub(pa);
    total += pb.cross(pc).length() / 2; tris.push([a, b, c]); pesos.push(total);
  }
  let semente = 7;
  const rnd = () => ((semente = (semente * 16807) % 2147483647) - 1) / 2147483646;
  const vert = new Float32Array(FIOS * 6), ponta = new Float32Array(FIOS * 2), fluxo = new T.Vector3(0, -.85, -.42);
  const p = new T.Vector3(), nn = new T.Vector3(), d = new T.Vector3(), tmp = new T.Vector3();
  for (let f = 0; f < FIOS && tris.length; f++) {
    const alvo = rnd() * total;
    let lo = 0, hi = pesos.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (pesos[m] < alvo) lo = m + 1; else hi = m; }
    const [a, b, c] = tris[lo];
    let u = rnd(), w = rnd(); if (u + w > 1) { u = 1 - u; w = 1 - w; }
    p.fromArray(P[a]).multiplyScalar(1 - u - w).addScaledVector(tmp.fromArray(P[b]), u).addScaledVector(tmp.fromArray(P[c]), w);
    nn.fromArray(N[a]).multiplyScalar(1 - u - w).addScaledVector(tmp.fromArray(N[b]), u).addScaledVector(tmp.fromArray(N[c]), w).normalize();
    d.copy(fluxo).addScaledVector(nn, -fluxo.dot(nn)).normalize().addScaledVector(nn, .22)
      .add(tmp.set(rnd() - .5, rnd() - .5, rnd() - .5).multiplyScalar(.28)).normalize();
    p.toArray(vert, f * 6); p.addScaledVector(d, .012 + rnd() * .022).toArray(vert, f * 6 + 3);
    ponta[f * 2 + 1] = 1;
  }
  const geo = new T.BufferGeometry();
  geo.setAttribute("position", new T.BufferAttribute(vert, 3));
  geo.setAttribute("ponta", new T.BufferAttribute(ponta, 1));
  const mat = new T.ShaderMaterial({
    // Pure addition of light, alpha included: over the camera a faint strand must stay faint, not dark.
    uniforms: uniformes, transparent: true, depthWrite: false,
    blending: T.CustomBlending, blendSrc: T.OneFactor, blendDst: T.OneFactor,
    vertexShader: UNIFORMES_DA_FALHA + `attribute float ponta; varying float vPonta; varying vec3 vPos;
      void main() { vPonta = ponta; vPos = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.);` + GLSL_FALHA + "}",
    fragmentShader: GLSL_COMUM + `
      varying float vPonta; varying vec3 vPos;
      void main() {
        float ruido = .5 + .5 * sin(dot(vPos, vec3(431., 517., 389.))) * sin(dot(vPos, vec3(-233., 611., 157.)));
        float var = mix(.4, 1.4, jvFaixa(.35, .65, ruido)), fade = jvFaixa(.47, .60, vPos.y);
        vec3 c = jvLuz(mix(jvFundo, jvCor, var * .7) * var * 2.6 * fade * .065);
        c *= (1. - vPonta * .75) * jvTela();
        gl_FragColor = vec4(c, max(c.r, max(c.g, c.b)));
      }`,
  });
  const fios = new T.LineSegments(geo, mat); fios.name = "pelo"; fios.frustumCulled = false;
  return fios;
}

export async function criarChimpanze(T, GLTFLoader, { estilo = "constelacao" } = {}) {
  const classico = estilo === "classico";
  const carregarVista = url => new T.TextureLoader().loadAsync(url).then(t => {
    t.flipY = false; t.colorSpace = T.NoColorSpace; return t;  // glTF UV convention, raw detail data
  });
  const [gltf, ...vistas] = await Promise.all([new GLTFLoader().loadAsync(URL_MODELO), ...(classico ? VISTAS.map(carregarVista) : [])]);
  const grupo = new T.Group(); grupo.name = "JARVIS_CHIMPANZE";
  const cabeca = gltf.scene; grupo.add(cabeca);
  const cor = new T.Color(CIANO.r, CIANO.g, CIANO.b), fundo = new T.Color(AZUL.r, AZUL.g, AZUL.b);
  const uniformes = {
    jvTempo: { value: 0 }, jvEnergia: { value: 0 }, jvBoca: { value: 0 }, jvVarredura: { value: .6 }, jvGanho: { value: 1 },
    jvTremor: { value: 1 }, jvFalha: { value: 0 }, jvFalhaY: { value: 0 },
    jvCor: { value: cor }, jvFundo: { value: fundo },
    jvVista0: { value: vistas[0] }, jvVista1: { value: vistas[1] }, jvVista2: { value: vistas[2] },
  };
  const rostos = [], materiais = new Map(), antigos = new Set();
  const ordem = nome => (nome.startsWith("CHIMP2_") || nome === "CHIMP_Anatomia" ? 3 : nome === "CHIMP_Dentes" ? 2 : 0);
  let pele = null;
  cabeca.traverse(o => {
    if (!o.isMesh) return;
    o.frustumCulled = false;  // skinned and morphed: the rest-pose bounds are not enough
    if (o.morphTargetDictionary) rostos.push(o);
    antigos.add(o.material);
    // three.js declares uv..uv3 itself; aliases keep the four Blender UV maps under our names.
    ["uv", "uv1", "uv2", "uv3"].forEach((n, i) => o.geometry.setAttribute("jv_uv" + i, o.geometry.attributes[n]));
    const nome = tipo(o.material.name);
    if (nome === "CHIMP2_Holograma") pele = o;
    if (!classico) return;  // the constellation reads the original material names, then hides the meshes
    if (!materiais.has(nome)) materiais.set(nome, holograma(T, nome, uniformes));
    o.material = materiais.get(nome);
    o.renderOrder = ordem(nome);
  });
  if (!rostos.length || !pele) throw new Error("o chimpanzé veio sem shape keys ou sem a pele");
  const visual = classico ? null : constelacao(T, cabeca, uniformes);
  const cenario = classico ? null : projetor(T, uniformes);  // the avatar adds it outside the spin
  antigos.forEach(m => { for (const v of Object.values(m)) if (v?.isTexture) v.dispose(); m.dispose(); });
  const fundoDaPele = classico ? profundidade(T, uniformes) : null;
  for (const o of classico ? [...rostos] : []) {
    if (!o.material.name.startsWith("CHIMP2_") && o.material.name !== "CHIMP_Anatomia") continue;
    const d = new T.SkinnedMesh(o.geometry, fundoDaPele);
    d.name = o.name + "_profundidade"; d.frustumCulled = false; d.renderOrder = -1;
    d.position.copy(o.position); d.quaternion.copy(o.quaternion); d.scale.copy(o.scale);
    d.morphTargetInfluences = o.morphTargetInfluences; d.morphTargetDictionary = o.morphTargetDictionary;
    o.parent.add(d); d.bind(o.skeleton, o.bindMatrix);
  }

  // precise=true applies the skin: the rig moves the head away from the raw geometry bounds.
  cabeca.updateMatrixWorld(true);
  const fios = classico ? pelo(T, pele, uniformes) : null;
  if (fios) { fios.renderOrder = 4; cabeca.add(fios); }
  if (classico) {
    // A dark backing just behind the lips: through an open mouth or its corners one sees the inside
    // of a mouth, never the room. Placed from the skinned lip line, like the fur.
    const posPele = pele.geometry.attributes.position, labio = new T.Vector3(), v = new T.Vector3();
    let frenteLabio = -Infinity;
    for (let i = 0; i < posPele.count; i++) {
      if (Math.abs(posPele.getY(i) - .639) > .003 || Math.abs(posPele.getX(i)) > .006) continue;
      pele.getVertexPosition(i, v).applyMatrix4(pele.matrixWorld);
      if (v.z > frenteLabio) { frenteLabio = v.z; labio.copy(v); }
    }
    // A soft ellipse the size of the mouth, faded when seen from the side (through the cheeks).
    const fundoBoca = new T.Mesh(new T.PlaneGeometry(.1, .07), new T.ShaderMaterial({
      transparent: true, depthWrite: false,
      vertexShader: `varying vec2 vU; varying float vFrente;
        void main() { vU = uv; vec4 mv = modelViewMatrix * vec4(position, 1.);
          vFrente = abs(dot(normalize(normalMatrix * vec3(0., 0., 1.)), normalize(-mv.xyz)));
          gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec2 vU; varying float vFrente;
        void main() { float d = length((vU - .5) * 2.);
          gl_FragColor = vec4(.004, .012, .025, (1. - smoothstep(.7, 1., d)) * smoothstep(.55, .85, vFrente)); }`,
    }));
    fundoBoca.name = "fundo_da_boca"; fundoBoca.renderOrder = 1;
    fundoBoca.position.set(labio.x, labio.y - .01, labio.z - .03);
    if (Number.isFinite(frenteLabio)) cabeca.add(fundoBoca);
  }
  const caixa = new T.Box3().setFromObject(cabeca, true), tamanho = caixa.getSize(new T.Vector3());
  const escala = Math.min(ALTURA / tamanho.y, LARGURA / tamanho.x);
  cabeca.scale.setScalar(escala);
  cabeca.position.copy(caixa.getCenter(new T.Vector3()).multiplyScalar(-escala));
  cabeca.position.y -= .1;

  // The constellation goes without it: the person asked to take the turning circle away (29/10/2026).
  const halo = new T.Group(); halo.position.set(0, -.05, -.9); halo.visible = classico; grupo.add(halo);
  const haloMat = new T.MeshBasicMaterial({ color: 0x75dce9, transparent: true, opacity: .42, toneMapped: false });
  for (let i = 0; i < 4; i++) {
    const o = new T.Mesh(new T.TorusGeometry(1.98, .009, 5, 64, Math.PI * .43), haloMat);
    o.rotation.z = i * Math.PI / 2 + .1; halo.add(o);
  }
  const marcas = [];
  for (let i = 0; i < 72; i++) {
    const a = i / 72 * Math.PI * 2, r = 2.045, s = i % 6 === 0 ? .045 : .015;
    marcas.push(r * Math.cos(a), r * Math.sin(a), 0, (r + s) * Math.cos(a), (r + s) * Math.sin(a), 0);
  }
  const marcasMat = new T.LineBasicMaterial({ color: 0x75dce9, transparent: true, opacity: .22 });
  halo.add(new T.LineSegments(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(marcas, 3)), marcasMat));

  const nomes = Object.keys(rostos[0].morphTargetDictionary);
  const atual = Object.fromEntries(nomes.map(n => [n, 0]));
  const definir = (nome, valor, dt, tau = .12) => {
    if (!(nome in atual)) return;
    atual[nome] += (valor - atual[nome]) * (dt === null ? 1 : 1 - Math.exp(-dt / tau));
  };
  let pulso = 1, pulsoFundo = 0, fasePulso = 0, ritmoPulso = 1;
  let agoraT = 0, tontoInicio = -1, tontoAte = -1, tonto = 0;
  let abertura = 0, fase = 0, emocao = "", peso = 0, proximaFalha = 3, fimDaFalha = 0, inclinar = 0, baixar = 0;
  const brilhoBase = new T.Color(), fundoAlvo = new T.Color();
  return {
    grupo, modelo: "chimpanze", estilo: classico ? "classico" : "constelacao", expressoes: nomes,
    fios: classico ? FIOS : 0, pontos: visual?.pontos ?? 0, ligacoes: visual?.ligacoes ?? 0,
    // The drawing-buffer height: the constellation sizes its points in pixels from it.
    tela(px) { visual?.tela(px); },
    cenario: cenario?.grupo ?? null,
    get falha() { return uniformes.jvFalha.value; },
    montar() { visual?.montar(); },
    get emocao() { return peso > .5 ? emocao : ""; },
    atualizar(t, dt, amplitude, estado, corEstado, reduzir, sentimento = "") {
      uniformes.jvTempo.value = t; uniformes.jvEnergia.value = amplitude; agoraT = t;
      visual?.atualizar(t, dt, estado, reduzir); cenario?.atualizar(dt, reduzir);
      // Dizzy (spun too much by hand): fades in fast, out over the last second.
      tonto = reduzir || t > tontoAte ? 0 : Math.min(1, (tontoAte - t) / 1, (t - tontoInicio) / .3);
      // An emotion fades in and out; a change of emotion first fades the old one.
      const pedida = EMOCOES[sentimento] ? sentimento : "";
      if (pedida !== emocao && peso < .05) emocao = pedida;
      peso += ((pedida && pedida === emocao ? 1 : 0) - peso) * (1 - Math.exp(-dt / .25));
      const E = EMOCOES[emocao], e = E ? peso : 0;
      // Blender: the sweep runs 0.53 → 0.85 m every four seconds, three times faster when thinking.
      fase = (fase + dt / 4 * (estado === "thinking" ? 3 : 1)) % 1;
      uniformes.jvVarredura.value = reduzir ? -1 : .53 + fase * .32;
      uniformes.jvGanho.value = estado === "thinking" ? 1 + .8 * (.5 + .5 * Math.sin(t * 22)) : estado === "listening" ? 1.3 : 1;
      // Pulse: thinking (waiting for the brain) beats about 1.3 times a second; listening (waiting
      // for the user) breathes slowly. The depth eases in and out with the state.
      const [batida, fundura] = estado === "thinking" ? [1.3, .3] : estado === "listening" ? [.45, .1] : [0, 0];
      if (batida) ritmoPulso = batida;
      pulsoFundo += (fundura - pulsoFundo) * (1 - Math.exp(-dt / .3));
      fasePulso = (fasePulso + dt * ritmoPulso) % 1;
      pulso = reduzir ? 1 : 1 + pulsoFundo * (Math.sin(fasePulso * 2 * Math.PI) * .5 + .5) * 2 - pulsoFundo * .6;
      uniformes.jvTremor.value = pulso * (reduzir ? 1 : .94 + .04 * Math.sin(t * 61) * Math.sin(t * 17.3) + .02 * Math.sin(t * 3.1));
      // Signal glitches: rare at rest, frequent in anger; never with reduced motion.
      if (!reduzir && t > proximaFalha) {
        fimDaFalha = t + .09 + Math.random() * .08; uniformes.jvFalhaY.value = Math.random() * 1.4 - .7;
        uniformes.jvFalha.value = (Math.random() < .5 ? -1 : 1) * (.5 + Math.random() * .5);
        proximaFalha = t + ((E?.falhas && e > .5) || tonto > .3 ? .5 + Math.random() : 5 + Math.random() * 6);
      }
      if (t > fimDaFalha) uniformes.jvFalha.value = 0;
      // Attack/release is time based so a slow frame cannot leave the mouth stuck open.
      const alvo = estado === "speaking" ? Math.min(1, Math.max(0, (amplitude - .015) * 1.35)) : 0;
      abertura += (alvo - abertura) * (1 - Math.exp(-dt / (alvo > abertura ? .045 : .075)));
      atual.Boca_Aberta = abertura * .85;
      const piscar = reduzir ? 0 : Math.exp(-((((t % 5.4) - 4.75) / .09) ** 2));
      // Listening: attentive. Thinking: the pensive face, eyes up and to the side, one brow a little
      // raised, lips pressed.
      const pensando = estado === "thinking";
      const doEstado = {
        Arregalar: estado === "listening" ? .35 : 0,
        Sobrancelha_Erguida: estado === "listening" ? .3 : 0,
        Semicerrar: pensando ? .35 : estado === "inactive" ? .6 : 0,
        Olhar_Cima: pensando ? .55 : 0,
        Olhar_Esq: pensando ? .35 : 0,
        Sobrancelha_Duvida: pensando ? .45 : 0,
        Boca_Triste: pensando ? .15 : 0,
      };
      const chaves = new Set([...Object.keys(doEstado), ...TODAS_AS_CHAVES]);  // all of them, so the old ones fade
      for (const k of chaves) definir(k, Math.max(doEstado[k] ?? 0, (E?.chaves[k] ?? 0) * e), dt, k === "Olhar_Cima" ? .25 : .12);
      definir("Piscar", piscar, null);
      const olhar = reduzir || pensando ? 0 : .35 * Math.sin(t * .48) * (1 - e * (E?.chaves.Olhar_Esq ? 1 : 0));
      definir("Olhar_Esq", Math.max(0, olhar, (E?.chaves.Olhar_Esq ?? 0) * e, doEstado.Olhar_Esq), dt, .2);
      definir("Olhar_Dir", Math.max(0, -olhar), dt, .2);
      if (tonto > 0) {  // eyes rolling round, lids heavy
        const c = Math.cos(t * 9), sn = Math.sin(t * 9), k = .8 * tonto;
        atual.Olhar_Esq = Math.max(0, c) * k; atual.Olhar_Dir = Math.max(0, -c) * k;
        if ("Olhar_Cima" in atual) atual.Olhar_Cima = Math.max(0, sn) * k;
        if ("Olhar_Baixo" in atual) atual.Olhar_Baixo = Math.max(0, -sn) * k;
        atual.Semicerrar = Math.max(atual.Semicerrar ?? 0, .3 * tonto);
      }
      for (const r of rostos) for (const n of nomes) r.morphTargetInfluences[r.morphTargetDictionary[n]] = atual[n];
      uniformes.jvBoca.value = Math.max(abertura, atual.Sorriso_Dentes ?? 0);  // lips apart: teeth exist
      // A slow drift around the front view; the volume reads from the rim and the fur.
      inclinar += ((E?.inclinar ?? 0) * e + (pensando ? .07 : 0) - inclinar) * (1 - Math.exp(-dt / .3));
      baixar += ((E?.baixar ?? 0) * e - baixar) * (1 - Math.exp(-dt / .3));
      grupo.rotation.y = reduzir ? 0 : .14 * Math.sin(t * .31);  // facing, as in the render
      grupo.rotation.z = inclinar + tonto * .16 * Math.sin(t * 6);  // the wobble of a dizzy head
      grupo.rotation.x = baixar + tonto * .07 * Math.sin(t * 4.3) + (reduzir ? 0 : .02 * Math.sin(t * .66) - abertura * .03 + (estado === "listening" ? -.03 : 0));
      const ritmo = emocao === "alegria" ? 2.3 : emocao === "tristeza" ? .6 : 1.15;  // sadness breathes slowly
      grupo.position.y = reduzir ? 0 : .025 * Math.sin(t * ritmo) * (1 + e * (emocao === "alegria" ? 1 : 0));
      halo.rotation.z = reduzir ? 0 : t * (estado === "thinking" ? .065 : .009);
      // Blender's own colours (build_chimpanze_holograma.py: CIANO and AZUL), not the ring's theme:
      // the head must look like the Blender render. Anger pulls it toward red, joy brightens it,
      // sadness dims it toward the deep blue.
      // The constellation follows the ring's theme colour instead (approved in the lab, 29/10/2026).
      brilhoBase.copy(!classico && corEstado ? corEstado : CIANO);
      if (emocao === "raiva") brilhoBase.lerp(new T.Color(1, .22, .08), .7 * e);
      if (emocao === "tristeza") brilhoBase.lerp(AZUL, .4 * e);
      if (tonto) brilhoBase.lerp(new T.Color(.45, 1, .5), .35 * tonto);  // a little seasick green
      brilhoBase.multiplyScalar(1 + ((E?.brilho ?? 1) - 1) * e);
      cor.lerp(brilhoBase, 1 - Math.exp(-dt * 3));
      fundoAlvo.copy(AZUL);
      if (emocao === "raiva") fundoAlvo.lerp(new T.Color(.6, .05, .02), .7 * e);
      fundo.lerp(fundoAlvo, 1 - Math.exp(-dt * 3));
      haloMat.color.copy(cor); marcasMat.color.copy(cor);
    },
    get abertura() { return abertura; },
    get pulso() { return pulso; },
    get tonto() { return tonto; },
    tontear(segundos = 3.5) { tontoInicio = agoraT; tontoAte = agoraT + segundos; },
    chave(nome) { return atual[nome] ?? null; },
    descartar() {
      const gs = new Set(), ms = new Set([...materiais.values(), haloMat, marcasMat, ...(fios ? [fios.material] : [])]);
      visual?.descartar(); cenario?.descartar();
      grupo.traverse(o => { if (o.geometry) gs.add(o.geometry); });
      gs.forEach(g => g.dispose()); ms.forEach(m => m.dispose()); vistas.forEach(v => v.dispose());
    },
  };
}
