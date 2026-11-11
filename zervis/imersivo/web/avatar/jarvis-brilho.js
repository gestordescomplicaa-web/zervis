// SPDX-License-Identifier: AGPL-3.0-or-later
// The glow around the hologram, as in the hologram lab (11/11/2026): the scene is drawn into a
// multisampled half-float target, its bright parts are blurred over five levels (the same
// UnrealBloomPass recipe the lab used: strength .6, radius .25, threshold .18) and added back, and
// the result is encoded to sRGB, as the lab's OutputPass did.
// three's UnrealBloomPass writes alpha 1 everywhere, which would cover the camera behind the Zé;
// here the scene keeps its own alpha and the glow gets the alpha of its light, so it sits on the
// camera image as light (the canvas is premultiplied).

const NIVEIS = [3, 5, 7, 9, 11];             // the blur kernel radius per level, half size each time
const PESOS = [1, .8, .6, .4, .2];
// A few pixels of the scene can come out as NaN or infinity (degenerate normals in the model); a
// blur would spread them over the whole picture, so every read of the scene goes through this.
const LIMPA = `vec4 limpa(vec4 c) { bvec4 ruim = bvec4(isnan(c.x) || isinf(c.x), isnan(c.y) || isinf(c.y), isnan(c.z) || isinf(c.z), isnan(c.w) || isinf(c.w));
  return clamp(mix(c, vec4(0.), vec4(ruim)), 0., 64.); }
`;
const VERTICE = "varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }";

export function criarBrilho(T, renderer, { forca = .6, raio = .25, limiar = .18, amostras = 4 } = {}) {
  const alvo = (w, h, extra = {}) => new T.WebGLRenderTarget(w, h, { type: T.HalfFloatType, depthBuffer: false, ...extra });
  const cenaRT = alvo(1, 1, { depthBuffer: true, samples: amostras });
  const claro = alvo(1, 1);
  const niveis = NIVEIS.map(() => ({ h: alvo(1, 1), v: alvo(1, 1) }));
  const quad = new T.Mesh(new T.PlaneGeometry(2, 2));
  quad.frustumCulled = false;
  const camera = new T.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const passo = (fragmentShader, uniforms, defines = {}) => new T.ShaderMaterial({
    uniforms, defines, vertexShader: VERTICE, fragmentShader, depthTest: false, depthWrite: false, blending: T.NoBlending,
  });
  // the bright parts only (luminance above the threshold, a soft step)
  const filtro = passo(LIMPA + `uniform sampler2D tCena; uniform float uLimiar; varying vec2 vUv;
    void main() { vec4 c = limpa(texture2D(tCena, vUv)); float l = dot(c.rgb, vec3(.2126, .7152, .0722));
      gl_FragColor = vec4(c.rgb * smoothstep(uLimiar, uLimiar + .01, l), 1.); }`,
  { tCena: { value: cenaRT.texture }, uLimiar: { value: limiar } });
  // a separable gaussian, one material per kernel size
  const borrar = NIVEIS.map(k => passo(`uniform sampler2D tFonte; uniform vec2 uPasso; varying vec2 vUv;
    float g(float x) { return .39894 * exp(-.5 * x * x / float(RAIO * RAIO)) / float(RAIO); }
    void main() { float soma = g(0.); vec3 c = texture2D(tFonte, vUv).rgb * soma;
      for (int i = 1; i < RAIO; i++) { float p = g(float(i)); vec2 d = uPasso * float(i);
        c += (texture2D(tFonte, vUv + d).rgb + texture2D(tFonte, vUv - d).rgb) * p; soma += 2. * p; }
      gl_FragColor = vec4(c / soma, 1.); }`,
  { tFonte: { value: null }, uPasso: { value: new T.Vector2() } }, { RAIO: k }));
  const fator = PESOS.map(f => f + (1.2 - 2 * f) * raio);   // UnrealBloomPass: mix(f, 1.2 - f, radius)
  const junta = passo(LIMPA + `uniform sampler2D tCena, b0, b1, b2, b3, b4; uniform float uForca, f[5]; varying vec2 vUv;
    vec3 srgb(vec3 c) { c = clamp(c, 0., 1.); return mix(c * 12.92, 1.055 * pow(c, vec3(1. / 2.4)) - .055, step(.0031308, c)); }
    void main() {
      vec4 cena = limpa(texture2D(tCena, vUv));
      vec3 luz = uForca * (f[0] * texture2D(b0, vUv).rgb + f[1] * texture2D(b1, vUv).rgb + f[2] * texture2D(b2, vUv).rgb
        + f[3] * texture2D(b3, vUv).rgb + f[4] * texture2D(b4, vUv).rgb);
      luz = max(luz - .001, 0.);                // the glow's faint tail ends inside the canvas, not at its edge
      vec3 cor = srgb(cena.rgb + luz);          // what the lab showed on black
      // the light fades out before the canvas edge, so no straight cut shows over the camera
      vec2 borda = min(vUv, 1. - vUv);
      float dentro = smoothstep(0., .1, min(borda.x, borda.y));
      gl_FragColor = vec4(cor, clamp(max(cena.a, max(cor.r, max(cor.g, cor.b))), 0., 1.)) * dentro; }`,
  { tCena: { value: cenaRT.texture }, uForca: { value: forca }, f: { value: fator },
    ...Object.fromEntries(niveis.map((n, i) => [`b${i}`, { value: n.v.texture }])) });
  const passar = (material, destino) => {
    quad.material = material; renderer.setRenderTarget(destino); renderer.render(quad, camera);
  };
  return {
    tamanho(w) {
      cenaRT.setSize(w, w);
      let lado = Math.max(1, Math.round(w / 2));
      claro.setSize(lado, lado);
      for (const n of niveis) { n.h.setSize(lado, lado); n.v.setSize(lado, lado); lado = Math.max(1, Math.round(lado / 2)); }
    },
    desenhar(cena, camera3d) {
      renderer.setRenderTarget(cenaRT); renderer.clear(); renderer.render(cena, camera3d);
      passar(filtro, claro);
      let fonte = claro.texture;
      niveis.forEach((n, i) => {
        const m = borrar[i], px = 1 / n.h.width;
        m.uniforms.tFonte.value = fonte; m.uniforms.uPasso.value.set(px, 0); passar(m, n.h);
        m.uniforms.tFonte.value = n.h.texture; m.uniforms.uPasso.value.set(0, px); passar(m, n.v);
        fonte = n.v.texture;
      });
      passar(junta, null);
    },
    descartar() {
      for (const r of [cenaRT, claro, ...niveis.flatMap(n => [n.h, n.v])]) r.dispose();
      for (const m of [filtro, ...borrar, junta]) m.dispose();
      quad.geometry.dispose();
    },
  };
}
