// SPDX-License-Identifier: AGPL-3.0-or-later
// Original articulated robot, modeled from zervis-robo-referencia.png. No human scan.
// A separate jaw pivot makes speech mechanical and preserves the face's silhouette.
export function criarRobo(T) {
  const grupo = new T.Group(); grupo.name = "JARVIS_ORCA";
  const cabeca = new T.Group(); cabeca.name = "cabeca"; grupo.add(cabeca);
  const cor = new T.Color("#80edf3");
  const tempo = { value: 0 }, energia = { value: 0 };
  const materiais = [];
  function material(nome, color, metalness, roughness, holo = false) {
    const m = new T.MeshStandardMaterial({ color, metalness, roughness }); m.name = nome;
    if (holo) {
      m.transparent = true; m.opacity = .88;
      m.onBeforeCompile = s => {
        Object.assign(s.uniforms, { jvTempo: tempo, jvEnergia: energia, jvCor: { value: cor } });
        s.vertexShader = 'varying vec3 jvPos;\n' + s.vertexShader;
        s.vertexShader = s.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\njvPos = position;');
        s.fragmentShader = 'uniform float jvTempo; uniform float jvEnergia; uniform vec3 jvCor; varying vec3 jvPos;\n' + s.fragmentShader;
        s.fragmentShader = s.fragmentShader.replace('#include <opaque_fragment>', `
          float rim = pow(1.0 - abs(dot(normalize(normal), normalize(vViewPosition))), 2.8);
          float scan = pow(.5 + .5 * sin(jvPos.y * 220.0 - jvTempo * 1.6), 18.0);
          outgoingLight += jvCor * (rim * .8 + scan * .04 + jvEnergia * .035);
          #include <opaque_fragment>`);
      };
      m.customProgramCacheKey = () => "jarvis-holograma-v2";
    }
    materiais.push(m); return m;
  }
  const casco = material("ceramica_holografica", "#98c1cb", .62, .3, true);
  const lateral = material("titanio_grafite", "#223e4b", .72, .28, true);
  const escuro = material("mecanismos", "#071a22", .65, .32);
  const vidro = material("visor", "#031119", .58, .18);
  const luz = new T.MeshBasicMaterial({ color: cor, toneMapped: false }); luz.name = "luz_ciano";
  const aura = new T.MeshBasicMaterial({color:cor,transparent:true,opacity:.15,depthWrite:false,blending:T.AdditiveBlending,toneMapped:false});
  const branco = new T.MeshBasicMaterial({ color: "#dcffff" }); branco.name = "reflexo";
  materiais.push(luz, branco, aura);
  const por = (geo, mat, nome, pai = cabeca, pos = [0, 0, 0]) => {
    const o = new T.Mesh(geo, mat); o.name = nome; o.position.set(...pos); pai.add(o); return o;
  };
  const tubo = (pontos, raio, mat, nome, pai = cabeca) => por(
    new T.TubeGeometry(new T.CatmullRomCurve3(pontos.map(p => new T.Vector3(...p))),
      Math.max(16, pontos.length * 6), raio, 5, false), mat, nome, pai);
  const anel = (r, esp, mat, nome, pai, pos, rot = [0, 0, 0]) => {
    const o = por(new T.TorusGeometry(r, esp, 8, 64), mat, nome, pai, pos); o.rotation.set(...rot); return o;
  };

  // Smooth loft sections, y up and face toward +z. Panels share a curved surface,
  // with deliberate gaps and different boundaries instead of stacked primitive blobs.
  const secoes = [
    [-1.2, .34, .28, .03], [-1.08, .55, .41, .02], [-.78, .76, .6, 0],
    [-.4, .94, .73, 0], [0, 1.02, .81, 0], [.5, 1.04, .85, 0],
    [.95, .96, .81, -.03], [1.3, .77, .66, -.04], [1.53, .45, .4, -.06], [1.66, .015, .02, -.08],
  ];
  function perfil(y, c) {
    let i = 0;
    while (i < secoes.length - 2 && y > secoes[i + 1][0]) i++;
    const a = secoes[i], b = secoes[i + 1], u = Math.min(1, Math.max(0, (y - a[0]) / (b[0] - a[0])));
    const p = secoes[Math.max(0, i - 1)], q = secoes[Math.min(secoes.length - 1, i + 2)];
    const m0 = (b[c] - p[c]) / (b[0] - p[0]) * (b[0] - a[0]);
    const m1 = (q[c] - a[c]) / (q[0] - a[0]) * (b[0] - a[0]);
    return (2*u**3-3*u*u+1)*a[c]+(u**3-2*u*u+u)*m0+(-2*u**3+3*u*u)*b[c]+(u**3-u*u)*m1;
  }
  function ponto(a, y, offset = 0) {
    return [(perfil(y, 1) + offset) * Math.sin(a), y,
      (perfil(y, 2) + offset) * Math.cos(a) + perfil(y, 3)];
  }
  function superficie(nome, a0, a1, baixo, alto, mat, pai = cabeca, offset = 0) {
    const pos = [], idx = [], nx = 48, ny = 24;
    for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) {
      const a = a0 + (a1-a0)*i/nx, lo = baixo(a), hi = alto(a);
      pos.push(...ponto(a, lo + (hi-lo)*j/ny, offset));
    }
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const n = j*(nx+1)+i; idx.push(n,n+1,n+nx+1,n+1,n+nx+2,n+nx+1);
    }
    const geo = new T.BufferGeometry(); geo.setAttribute("position", new T.Float32BufferAttribute(pos,3));
    geo.setIndex(idx); geo.computeVertexNormals(); return por(geo,mat,nome,pai);
  }
  function borda(nome, a0, a1, y, mat = luz, pai = cabeca, raio = .007) {
    const ps = Array.from({length:49}, (_,i) => { const a=a0+(a1-a0)*i/48; return ponto(a,y(a),.006); });
    return tubo(ps,raio,mat,nome,pai);
  }
  const testa = a => .68 + .12*Math.sin(Math.abs(a)*2.3);
  const bochecha = a => -.1 - .12*Math.cos(a*2);
  superficie("cranio_posterior", 1.29, Math.PI*2-1.29, () => -.76, () => 1.659, lateral);
  superficie("coroa", -1.28, 1.28, testa, () => 1.659, casco);
  superficie("inserto_coroa", -.155, .155, () => .86, () => 1.651, lateral, cabeca, .006);
  borda("arco_sobrancelha",-1.28,1.28,testa);
  superficie("viseira", -1.31, 1.31, bochecha, a=>testa(a)-.023, vidro, cabeca, -.015);
  borda("arco_visor_inferior",-1.27,1.27,bochecha,luz,cabeca,.005);
  superficie("face_superior", -.7, .7, a=>-.53+.1*Math.abs(a), a=>bochecha(a)-.024, casco);
  for (const lado of [-1,1]) {
    const a0=lado<0?-1.28:.72, a1=lado<0?-.72:1.28;
    superficie("placa_malar_"+lado,a0,a1,a=>-.92+.4*(Math.abs(a)-.72),a=>bochecha(a)-.03,casco);
    const ps=Array.from({length:12},(_,i)=>ponto(lado*(.72+.11*i/11),-.2-.67*i/11,.015));
    tubo(ps,.009,luz,"costura_face_"+lado);
    // Helmet side seams follow the crown, leaving a subtle central inset.
    tubo(Array.from({length:20},(_,i)=>ponto(lado*(.35+.05*Math.sin(i/19*Math.PI)),.8+.8*i/19,.008)),
      .006,luz,"costura_coroa_"+lado);
  }
  // The cavity remains still. Only the lower shell and lower lip belong to the jaw.
  superficie("cavidade_boca",-.71,.71,()=>-1.12,()=>-.46,escuro,cabeca,-.08);
  const mandibula = new T.Group(); mandibula.name="mandibula"; mandibula.position.set(0,-.28,-.18); cabeca.add(mandibula);
  const queixo = new T.Group(); queixo.position.set(0,.28,.18); mandibula.add(queixo);
  superficie("queixo_articulado",-.7,.7,()=>-1.185,a=>-.575+.12*Math.abs(a),casco,queixo);
  borda("labio_inferior",-.48,.48,a=>-.586+.12*Math.abs(a),luz,queixo,.009);
  borda("labio_superior",-.49,.49,a=>-.524+.09*Math.abs(a),lateral,cabeca,.013);

  const olhos=[];
  for (const lado of [-1,1]) {
    const olho = new T.Group(); olho.name="olho_"+lado;
    olho.position.set(lado*.43,.29,.793); olho.rotation.y=lado*.22; cabeca.add(olho);
    const aro=anel(.22,.024,lateral,"orbita_"+lado,olho,[0,0,0]); aro.scale.y=.84;
    const iris = new T.Group(); iris.name="iris_"+lado; olho.add(iris);
    por(new T.CircleGeometry(.186,48),escuro,"fundo_iris",iris,[0,0,.006]);
    anel(.142,.012,luz,"iris_luminosa",iris,[0,0,.018]);
    anel(.142,.04,aura,"aura_iris",iris,[0,0,.017]);
    anel(.11,.003,branco,"anel_iris",iris,[0,0,.022]);
    anel(.077,.006,luz,"pupila",iris,[0,0,.025]);
    const pontos=[];
    for (let i=0;i<48;i++) {
      const a=i/48*Math.PI*2;
      pontos.push(.119*Math.cos(a),.119*Math.sin(a),.023,.135*Math.cos(a),.135*Math.sin(a),.023);
    }
    const raios = new T.LineSegments(new T.BufferGeometry().setAttribute("position",new T.Float32BufferAttribute(pontos,3)),
      new T.LineBasicMaterial({color:0x80edf3,transparent:true,opacity:.65})); iris.add(raios);
    por(new T.SphereGeometry(.023,12,8),branco,"brilho_olho",iris,[-.052,.064,.035]);
    olhos.push({olho,iris});
    // Circular temple actuators are oriented along x, not facing the viewer like headphones.
    const ouvido = new T.Group(); ouvido.position.set(lado*1.01,.31,-.08); ouvido.rotation.y=lado*Math.PI/2; cabeca.add(ouvido);
    const disco=por(new T.CylinderGeometry(.38,.38,.13,48),lateral,"atuador",ouvido); disco.rotation.x=Math.PI/2;
    anel(.32,.013,luz,"temporal_luz",ouvido,[0,0,.072]);
    anel(.245,.025,casco,"temporal_metal",ouvido,[0,0,.082]);
    anel(.13,.009,luz,"temporal_centro",ouvido,[0,0,.11]);
    por(new T.CircleGeometry(.115,32),vidro,"temporal_vidro",ouvido,[0,0,.105]);
    for(let i=0;i<3;i++) tubo([[lado*.98,.86+i*.1,-.27],[lado*.9,.9+i*.1,-.48]],.018,escuro,"respiro");
  }
  const pescoco = new T.Group(); pescoco.name="pescoco"; grupo.add(pescoco);
  por(new T.CylinderGeometry(.245,.29,.62,32),escuro,"coluna",pescoco,[0,-1.32,-.17]);
  for(let i=0;i<5;i++) anel(.27,.025,lateral,"vertebra",pescoco,[0,-1.06-i*.11,-.17],[Math.PI/2,0,0]);
  for(const lado of [-1,1]) {
    tubo([[lado*.31,-.99,.09],[lado*.27,-1.3,.2],[lado*.34,-1.61,.14]],.04,casco,"tendao",pescoco);
    tubo([[lado*.19,-1.05,.17],[lado*.16,-1.32,.23],[lado*.21,-1.57,.2]],.01,luz,"fibra",pescoco);
  }
  const colar=por(new T.CylinderGeometry(.46,.52,.12,64),lateral,"colar",pescoco,[0,-1.65,-.12]); colar.scale.z=.8;
  anel(.49,.012,luz,"colar_luz",pescoco,[0,-1.69,-.12],[Math.PI/2,0,0]).scale.y=.8;

  const projecao=new T.Group(); projecao.name="projecao"; grupo.add(projecao);
  anel(.7,.009,luz,"base_projetor",projecao,[0,-1.91,-.12],[Math.PI/2,0,0]);
  const halo = new T.Group(); halo.position.set(0,-.05,-.78); grupo.add(halo);
  const haloMat = new T.MeshBasicMaterial({color:0x75dce9,transparent:true,opacity:.48,toneMapped:false}); materiais.push(haloMat);
  for (let i=0;i<4;i++) {
    const o=por(new T.TorusGeometry(1.98,.009,5,64,Math.PI*.43),haloMat,"halo_"+i,halo);
    o.rotation.z=i*Math.PI/2+.1;
  }
  const marcas=[];
  for(let i=0;i<72;i++) {
    const a=i/72*Math.PI*2,r=2.045,s=i%6===0?.045:.015;
    marcas.push(r*Math.cos(a),r*Math.sin(a),0,(r+s)*Math.cos(a),(r+s)*Math.sin(a),0);
  }
  halo.add(new T.LineSegments(new T.BufferGeometry().setAttribute("position",new T.Float32BufferAttribute(marcas,3)),
    new T.LineBasicMaterial({color:0x75dce9,transparent:true,opacity:.24})));

  let abertura=0;
  return { grupo, cabeca, mandibula, olhos,
    atualizar(t, dt, amplitude, estado, corEstado, reduzir) {
      tempo.value=t; energia.value=amplitude;
      // Attack/release is time based so a slow frame cannot leave the mouth stuck open.
      const alvo=estado==="speaking"?Math.min(1,Math.max(0,(amplitude-.015)*1.35)):0;
      abertura+=(alvo-abertura)*(1-Math.exp(-dt/(alvo>abertura?.045:.075)));
      mandibula.rotation.x=abertura*.24;
      mandibula.position.y=-.28-abertura*.045;
      const piscar = reduzir ? 1 : 1-.94*Math.exp(-((((t%5.4)-4.75)/.09)**2));
      olhos.forEach(({olho,iris})=>{
        olho.scale.y=piscar;
        iris.position.x=reduzir?0:.024*Math.sin(t*.48);
        iris.position.y=reduzir?0:.014*Math.sin(t*.33);
      });
      cabeca.rotation.y=reduzir?-.34:-.34+.07*Math.sin(t*.42);
      cabeca.rotation.x=reduzir?0:.016*Math.sin(t*.66)-abertura*.025+(estado==="listening"?-.025:0);
      grupo.position.y=reduzir?0:.025*Math.sin(t*1.15);
      halo.rotation.z=reduzir?0:t*(estado==="thinking"?.065:.009);
      cor.lerp(corEstado,1-Math.exp(-dt*3)); luz.color.copy(cor).multiplyScalar(1.35); aura.color.copy(cor); haloMat.color.copy(cor);
    },
    get abertura() { return abertura; },
    descartar() {
      const gs=new Set(),ms=new Set(materiais);
      grupo.traverse(o=>{if(o.geometry)gs.add(o.geometry);if(o.material)ms.add(o.material);});
      gs.forEach(g=>g.dispose()); ms.forEach(m=>m.dispose());
    },
  };
}
