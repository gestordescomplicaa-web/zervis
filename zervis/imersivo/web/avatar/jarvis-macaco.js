// SPDX-License-Identifier: AGPL-3.0-or-later
// The Zé as a holographic monkey (approved in the hologram lab on 11/11/2026): a chimpanzee bust
// drawn as light, a dark volume with a crisp lit contour ("C" in the lab), two points of light for
// eyes, on the projector of the constellation look (jarvis-constelacao.js).
// The model (jarvis-macaco.glb) is "Monkey / Australopithecus stone bust" by gamnok (CC BY 4.0,
// see README.md and THIRD_PARTY.md), prepared in Blender by avatar/macaco_blender.py: lips split on
// the carved crease, a dark mouth inside, a chimpanzee dentition (32 teeth, U-shaped arcade, blunt
// canines) and the shape keys jawOpen, alegria, tristeza, raiva and duvida.
// Same interface as jarvis-chimpanze.js: the avatar (../jarvis-avatar.js) feeds the ring's real
// speech wave, the Zé's state and his emotion; the channels it reports (Boca_Aberta, Piscar,
// Sorriso_Dentes, Rosnar, Sobrancelha_Duvida, Boca_Triste, Olhar_Cima) are this model's
// equivalents of the chimpanzee's shape keys.
import { projetor } from "./jarvis-constelacao.js";

const URL_MODELO = new URL("./jarvis-macaco.glb", import.meta.url).href;
const ALTURA = 3.55;                       // the bust in the ring: chest on the projector
const EMOCOES = {
  alegria: { baixar: -.05, inclinar: 0, brilho: 1.2, falhas: 0 },
  duvida: { baixar: 0, inclinar: .12, brilho: 1, falhas: 0 },
  raiva: { baixar: .1, inclinar: 0, brilho: .85, falhas: 1, cor: [1, .23, .15] },
  tristeza: { baixar: .16, inclinar: -.04, brilho: .8, falhas: 0, cor: [.43, .62, 1] },
};
export const NOMES_DAS_EMOCOES = Object.keys(EMOCOES);
const CANAIS = ["Boca_Aberta", "Piscar", "Sorriso_Dentes", "Rosnar", "Sobrancelha_Duvida", "Boca_Triste", "Olhar_Cima"];

// The C finish: a depth pass first (only the nearest surface glows), a fresnel contour, and the
// back faces pushed out a little as a lit outline. The shape keys run in the vertex shader.
const VERT = `
  #include <common>
  #include <morphtarget_pars_vertex>
  uniform float uExpande;
  varying vec3 vN; varying vec3 vV; varying vec3 vP; varying vec3 vL;
  void main() {
    vec3 transformed = vec3(position);
    #include <morphtarget_vertex>
    transformed += normal * uExpande;
    vec4 mundo = modelMatrix * vec4(transformed, 1.);
    vL = position; vP = mundo.xyz; vN = normalize(mat3(modelMatrix) * normal); vV = normalize(cameraPosition - mundo.xyz);
    gl_Position = projectionMatrix * viewMatrix * mundo;
  }`;
const COMUM = `
  uniform float jvTempo, jvBrilho, jvAbre; uniform vec3 jvCor;
  varying vec3 vN; varying vec3 vV; varying vec3 vP; varying vec3 vL;
  float ruido(float x) { return fract(sin(x * 91.17) * 43758.5); }
  float varredura(float y) {
    float linhas = smoothstep(.75, 1., sin(y * 170. - jvTempo * 3.));
    float faixa = smoothstep(.07, 0., abs(fract(y * .45 - jvTempo * .11) - .5));
    return linhas * .3 + faixa * .7;
  }
  float cintila() { return .94 + .06 * ruido(floor(jvTempo * 24.)); }
  float pe() { return smoothstep(-.52, -.3, vL.y); }     // the chest fades into the projector's light
  float fres(float k) { return pow(1. - abs(dot(normalize(vN), normalize(vV))), k); }`;

export async function criarMacaco(T, GLTFLoader) {
  const gltf = await new GLTFLoader().loadAsync(URL_MODELO);
  const malhas = {};
  gltf.scene.traverse(o => { if (o.isMesh) malhas[o.name] = o; });
  const uniformes = {
    jvCor: { value: new T.Color("#80edf3") }, jvTempo: { value: 0 }, jvFluxo: { value: 0 }, jvGanho: { value: 1 },
    jvEnergia: { value: 0 }, jvBrilho: { value: 1 }, jvAbre: { value: 0 }, jvPisca: { value: 1 }, jvOlhar: { value: 0 },
    jvTela: { value: 840 }, jvPx: { value: 840 },
  };
  const materiais = [];
  const material = (frag, extra = {}) => {
    const m = new T.ShaderMaterial({
      uniforms: { ...uniformes, uExpande: { value: 0 } }, vertexShader: VERT, fragmentShader: COMUM + frag,
      transparent: true, depthWrite: false, blending: T.AdditiveBlending, depthFunc: T.LessEqualDepth, ...extra,
    });
    materiais.push(m); return m;
  };
  const solido = (cor, extra = {}) => material(`void main(){ gl_FragColor = vec4(${cor}, 1.); }`,
    { transparent: false, depthWrite: true, blending: T.NormalBlending, depthFunc: T.LessDepth, ...extra });

  const grupo = new T.Group(), corpo = new T.Group(); grupo.add(corpo);
  const comChaves = [], daBoca = [];
  const copia = (fonte, mat, ordem) => {
    const m = new T.Mesh(fonte.geometry, mat);
    m.morphTargetInfluences = fonte.morphTargetInfluences ? fonte.morphTargetInfluences.slice() : undefined;
    m.morphTargetDictionary = fonte.morphTargetDictionary;
    m.renderOrder = ordem; corpo.add(m); if (m.morphTargetDictionary) comChaves.push(m); return m;
  };
  // the skin: depth, contour, lit outline
  copia(malhas.busto, solido("vec3(0.)", { colorWrite: false }), 0);
  copia(malhas.busto, material(`void main(){
    float c = (.012 + fres(4.5) * 2. + varredura(vP.y / ${ALTURA.toFixed(2)}) * .04) * cintila() * jvBrilho * pe();
    gl_FragColor = vec4(jvCor * c, 1.); }`), 2);
  const contorno = material(`void main(){ gl_FragColor = vec4(jvCor * .8 * cintila() * jvBrilho * pe(), 1.); }`, { side: T.BackSide });
  contorno.uniforms.uExpande.value = .004;
  copia(malhas.busto, contorno, 1);
  // the mouth: the dark inside and the teeth exist only while it is open (nothing behind the
  // closed seam of the lips, where their light would leak)
  daBoca.push(copia(malhas.boca, solido("vec3(0.)"), -1));
  for (const nome of ["dentes_cima", "dentes_baixo"]) {
    const fonte = malhas[nome]; if (!fonte) continue;
    daBoca.push(copia(fonte, solido("vec3(0.)"), -1));
    daBoca.push(copia(fonte, material(`void main(){
      vec3 dente = mix(jvCor, vec3(1.), .45);
      gl_FragColor = vec4(dente * (.32 + fres(1.6) * .55) * jvBrilho * jvAbre, 1.); }`), 3));
  }
  // the eyes: two points of light that blink and look up when he thinks
  const olhosGeo = new T.BufferGeometry();
  olhosGeo.setAttribute("position", new T.Float32BufferAttribute([-.052, .292, .232, .052, .292, .232], 3));
  const olhosMat = new T.ShaderMaterial({
    uniforms: uniformes, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
    vertexShader: `uniform float jvTela, jvOlhar; void main(){ vec3 p = position + vec3(0., .012 * jvOlhar, 0.);
      vec4 v = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * v; gl_PointSize = .38 * jvTela / -v.z; }`,
    fragmentShader: `uniform vec3 jvCor; uniform float jvBrilho, jvPisca; void main(){ vec2 q = gl_PointCoord - .5; q.y /= max(.08, jvPisca);
      float a = smoothstep(.5, .0, length(q)); gl_FragColor = vec4(mix(jvCor, vec3(1.), .65) * a * a * 1.6 * jvBrilho, 1.); }`,
  });
  materiais.push(olhosMat);
  const olhos = new T.Points(olhosGeo, olhosMat); olhos.renderOrder = 5; corpo.add(olhos);
  corpo.scale.setScalar(ALTURA);
  corpo.position.y = -.12;
  const cenario = projetor(T, uniformes);

  let abertura = 0, piscar = 0, olharCima = 0, pulso = 1, fasePulso = 0, agoraT = 0, tontoInicio = -1, tontoAte = -1, tonto = 0;
  let falha = 0, proximaFalha = 4, fimDaFalha = 0, inclinar = 0, baixar = 0, emocao = "", forca = 0;
  const peso = Object.fromEntries(NOMES_DAS_EMOCOES.map(n => [n, 0]));
  const cor = uniformes.jvCor.value, alvoCor = new T.Color(), tinta = new T.Color(), enjoo = new T.Color(.45, 1, .5);
  const canal = () => ({
    Boca_Aberta: abertura * .85, Piscar: piscar, Sorriso_Dentes: peso.alegria, Rosnar: peso.raiva,
    Sobrancelha_Duvida: Math.max(peso.duvida, olharCima > .2 ? .45 : 0), Boca_Triste: peso.tristeza, Olhar_Cima: olharCima,
  });
  return {
    grupo, modelo: "macaco", estilo: "holograma", expressoes: CANAIS, fios: 0, pontos: 0, ligacoes: 0,
    cenario: cenario.grupo,
    tela(px) { uniformes.jvTela.value = px; uniformes.jvPx.value = px; },
    get falha() { return falha; },
    montar() {},
    get emocao() { return forca > .5 ? emocao : ""; },
    atualizar(t, dt, amplitude, estado, corEstado, reduzir, sentimento = "") {
      agoraT = t;
      uniformes.jvTempo.value = t; uniformes.jvEnergia.value = amplitude;
      tonto = reduzir || t > tontoAte ? 0 : Math.min(1, (tontoAte - t) / 1, (t - tontoInicio) / .3);
      // an emotion fades in and out; a change first fades the old one, then brings the new
      const pedida = EMOCOES[sentimento] ? sentimento : "";
      if (pedida !== emocao && forca < .05) emocao = pedida;
      forca += ((pedida && pedida === emocao ? 1 : 0) - forca) * (1 - Math.exp(-dt / .25));
      for (const n of NOMES_DAS_EMOCOES) peso[n] = n === emocao ? forca : 0;
      // the mouth follows the ring's real speech wave; attack and release are time based
      const alvo = estado === "speaking" ? Math.min(1, Math.max(0, (amplitude - .015) * 1.35)) : 0;
      abertura += (alvo - abertura) * (1 - Math.exp(-dt / (alvo > abertura ? .045 : .075)));
      const pensando = estado === "thinking";
      olharCima += ((pensando ? .55 : 0) - olharCima) * (1 - Math.exp(-dt / .25));
      piscar = reduzir ? 0 : Math.exp(-((((t % 5.4) - 4.75) / .09) ** 2));
      const abre = Math.min(.85, abertura * .85 + peso.alegria * .12);
      const chaves = { jawOpen: abre, alegria: peso.alegria, tristeza: peso.tristeza, raiva: peso.raiva,
        duvida: Math.max(peso.duvida, pensando ? .3 * olharCima / .55 : 0) };
      for (const m of comChaves) for (const [n, i] of Object.entries(m.morphTargetDictionary)) m.morphTargetInfluences[i] = chaves[n] ?? 0;
      for (const m of daBoca) m.visible = abre > .015;
      uniformes.jvAbre.value = Math.min(1, Math.max(0, (abre - .02) / .12));
      uniformes.jvPisca.value = 1 - piscar; uniformes.jvOlhar.value = olharCima;
      // the pulse: thinking beats, listening breathes, at rest steady
      fasePulso = (fasePulso + dt * (pensando ? 1.3 : .45)) % 1;
      const fundura = pensando ? .25 : estado === "listening" ? .08 : 0;
      pulso = reduzir ? 1 : 1 + fundura * Math.sin(fasePulso * 2 * Math.PI);
      uniformes.jvGanho.value = pensando ? 1.4 : estado === "listening" ? 1.3 : 1;
      // signal glitches: rare at rest, frequent in anger
      if (!reduzir && t > proximaFalha) {
        fimDaFalha = t + .09 + Math.random() * .08; falha = (Math.random() < .5 ? -1 : 1) * (.5 + Math.random() * .5);
        proximaFalha = t + ((peso.raiva > .5) || tonto > .3 ? .5 + Math.random() : 6 + Math.random() * 6);
      }
      if (t > fimDaFalha) falha = 0;
      // the head: a slow drift, a nod with anger, down with sadness, a tilt in doubt, dizzy wobble
      let inc = 0, bai = 0, brilho = 1;
      for (const n of NOMES_DAS_EMOCOES) { inc += EMOCOES[n].inclinar * peso[n]; bai += EMOCOES[n].baixar * peso[n]; brilho += (EMOCOES[n].brilho - 1) * peso[n]; }
      inclinar += (inc + (pensando ? .06 : 0) - inclinar) * (1 - Math.exp(-dt / .3));
      baixar += (bai - baixar) * (1 - Math.exp(-dt / .3));
      grupo.rotation.y = reduzir ? 0 : .14 * Math.sin(t * .31);
      grupo.rotation.z = inclinar + tonto * .16 * Math.sin(t * 6);
      grupo.rotation.x = baixar + tonto * .07 * Math.sin(t * 4.3) + (reduzir ? 0 : .02 * Math.sin(t * .66) + abertura * .02 - (estado === "listening" ? .03 : 0));
      grupo.position.y = reduzir ? 0 : .025 * Math.sin(t * (peso.alegria > .5 ? 2.3 : peso.tristeza > .5 ? .6 : 1.15));
      // the theme's colour; anger pulls to red, sadness to blue, dizziness a little green
      alvoCor.copy(corEstado || alvoCor);
      for (const n of ["raiva", "tristeza"]) if (peso[n] > 0) alvoCor.lerp(tinta.setRGB(...EMOCOES[n].cor), (n === "raiva" ? .85 : .65) * peso[n]);
      if (tonto) alvoCor.lerp(enjoo, .35 * tonto);
      cor.lerp(alvoCor, 1 - Math.exp(-dt * 3));
      uniformes.jvBrilho.value = brilho * pulso * (estado === "inactive" ? .6 : 1) + abertura * .1;
      cenario.atualizar(dt, reduzir);
    },
    get abertura() { return abertura; },
    get pulso() { return pulso; },
    get tonto() { return tonto; },
    tontear(segundos = 3.5) { tontoInicio = agoraT; tontoAte = agoraT + segundos; },
    chave(nome) { return canal()[nome] ?? null; },
    descartar() {
      cenario.descartar();
      const gs = new Set();
      grupo.traverse(o => { if (o.geometry) gs.add(o.geometry); });
      gs.forEach(g => g.dispose()); materiais.forEach(m => m.dispose());
    },
  };
}
