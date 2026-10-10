// SPDX-License-Identifier: AGPL-3.0-or-later
// The Zé: the holographic chimpanzee inside the original interactive ring.
// Speech comes from the real ring waveform. No extra microphone or audio connection.
(() => {
  if (new URLSearchParams(location.search).get("role") === "render") return;
  const CHAVE = "jv-visual";
  const EMOCOES = ["alegria", "duvida", "raiva", "tristeza"];  // avatar/jarvis-chimpanze.js: NOMES_DAS_EMOCOES
  const FORCAR = new URLSearchParams(location.search).get("avatar") === "forcar";
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)");
  let ativo = true;
  try { ativo = localStorage.getItem(CHAVE) !== "anel"; } catch (_) {}
  const vivos = new Map(), pendentes = new Map(), falharam = new WeakSet();
  // An emotion asked here (controller action, tests) wins over the one in /orb until it expires.
  let sentida = { nome: "", ate: 0 };
  let bibliotecas;
  const carregar = () => (bibliotecas ||= Promise.all([import("three"), import("three/addons/loaders/GLTFLoader.js"), import("./avatar/jarvis-chimpanze.js")]));
  const css = document.createElement("style");
  css.textContent = `
    .ringcard.jv-avatar > canvas:first-child, .ringcard.jv-preparando > canvas:first-child { opacity:0; }
    /* While the 3D loads, the flat ring with its old name stays hidden: just the name, breathing. */
    .ringcard.jv-preparando::after { content:"ZÉ"; position:absolute; left:50%; top:50%;
      transform:translate(-50%,-50%); pointer-events:none; color:#a6ecf6; letter-spacing:.42em;
      font:600 22px ui-monospace,'SF Mono',monospace; text-shadow:0 0 14px rgb(80 200 255 / .8),0 1px 7px #001019;
      animation:jv-preparando 1.4s ease-in-out infinite; }
    @keyframes jv-preparando { 0%,100% { opacity:.3 } 50% { opacity:1 } }
    @media (prefers-reduced-motion: reduce) { .ringcard.jv-preparando::after { animation:none; opacity:.8 } }
    .ringcard > canvas.jv-avatar-cena { position:absolute; inset:0; width:100%; height:100%; pointer-events:none;
      filter:drop-shadow(0 0 2px rgb(var(--jv-brilho, 100 225 240) / .45)) drop-shadow(0 0 9px rgb(var(--jv-brilho, 100 225 240) / .3)); }
    .ringcard > .jv-avatar-identidade { position:absolute; bottom:0; left:0; right:0; pointer-events:none;
      text-align:center; color:#d6f6fa; text-shadow:0 1px 7px #001019,0 0 12px #001019;
      font:600 12px ui-monospace,'SF Mono',monospace; letter-spacing:.32em; }
    .jv-avatar-identidade small { display:block; margin-top:7px; color:#99c9ce;
      font-size:8px; font-weight:500; letter-spacing:.22em; }
  `;
  document.head.appendChild(css);

  async function montar(el, pedido) {
    const [T, { GLTFLoader }, { criarChimpanze }] = await carregar();
    if (pedido.cancelado || !ativo || !el.isConnected) return null;
    const canvas = document.createElement("canvas"); canvas.className="jv-avatar-cena";
    canvas.setAttribute("aria-hidden","true"); el.appendChild(canvas);
    let renderer, robo, raf = 0;
    const etiqueta = document.createElement("div"); etiqueta.className="jv-avatar-identidade";
    etiqueta.innerHTML='ZÉ<small>PRONTO</small>'; etiqueta.setAttribute("aria-hidden","true");
    const estadoEl=etiqueta.querySelector("small");
    const limpar = () => {
      cancelAnimationFrame(raf); robo?.descartar(); renderer?.dispose(); renderer?.forceContextLoss();
      canvas.remove(); etiqueta.remove(); el.classList.remove("jv-avatar");
    };
    try {
      renderer = new T.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:"low-power"});
      const gl=renderer.getContext(),info=gl.getExtension("WEBGL_debug_renderer_info");
      const placa=info?String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)):"";
      const software=/swiftshader|llvmpipe|software/i.test(placa);
      if (!FORCAR && software) throw new Error("WebGL por software; anel mantido");
      // Forced software rendering (the tests) draws less so the other browser tests keep their CPU.
      const intervalo=software?100:32,lado=software?280:840;
      renderer.setClearColor(0x000000,0); renderer.outputColorSpace=T.SRGBColorSpace;
      renderer.toneMapping=T.ACESFilmicToneMapping; renderer.toneMappingExposure=1.35;
      const cena=new T.Scene();
      const camera=new T.PerspectiveCamera(32,1,.1,30); camera.position.set(0,.12,8.15); camera.lookAt(0,-.12,0);
      cena.add(new T.HemisphereLight(0xc5f5ff,0x0d2534,2.2));
      for(const [color,intensity,pos] of [[0xe0f8ff,4.5,[-3,5,4]],[0x3acadd,3,[4,2,-2]],[0x779bc8,.8,[2,-1,3]]]) {
        const light=new T.DirectionalLight(color,intensity); light.position.set(...pos); cena.add(light);
      }
      robo=await criarChimpanze(T,GLTFLoader);
      if (pedido.cancelado || !ativo || !el.isConnected) { limpar(); return null; }
      // The hand's spin (stage.html "spin mode") turns the Zé inside the scene, never the flat card.
      const giro=new T.Group(); giro.add(robo.grupo); cena.add(giro);
      // Feathered backdrop keeps the face legible against the real camera.
      const fundo=new T.Mesh(new T.PlaneGeometry(4.7,4.7),new T.ShaderMaterial({
        transparent:true,depthWrite:false,
        vertexShader:'varying vec2 vU; void main(){vU=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
        fragmentShader:'varying vec2 vU; void main(){float d=length((vU-.5)*2.);gl_FragColor=vec4(.006,.026,.043,(1.-smoothstep(.4,1.,d))*.68);}',
      })); fundo.position.set(0,-.07,-1.05); fundo.renderOrder=-2; cena.add(fundo);
      const ctl={el,canvas,quadros:0,vivo:true,robo,renderer,placa,estado:"idle",voltas:0,ultimoRy:0,proximaTontura:0};
      let ultimo=0, inicio=performance.now(), cor=new T.Color("#80edf3"), ultimoEstado="",ultimoBrilho="";
      const rotulos={idle:"PRONTO",listening:"OUVINDO",thinking:"PENSANDO",speaking:"FALANDO",inactive:"EM REPOUSO",maintenance:"MANUTENÇÃO"};
      const olhar=()=>{
        if(!ctl.vivo) return;
        raf=requestAnimationFrame(olhar);
        const agora=performance.now();
        if(document.hidden || !el.isConnected) { ultimo=agora; return; }
        if(agora-ultimo<intervalo) return;
        const dt=Math.min(.12,(agora-ultimo)/1000 || .033); ultimo=agora;
        // Cap fill rate: the hand tracker needs the same integrated GPU.
        const w=Math.min(lado,Math.max(280,Math.round((canvas.clientWidth||440)*Math.min(devicePixelRatio||1,1.5))));
        if(canvas.width!==w) renderer.setSize(w,w,false);
        const r=window.jarvisRing||{},estado=r.data?.state||"idle";
        // The ring's visual decay can outlast a syllable. Silence in the actual PCM
        // must close the jaw promptly, even when frames are slow or speech is interrupted.
        const comVoz=Array.isArray(r.data?.wave)&&r.data.wave.some(v=>Number.isFinite(v)&&Math.abs(v)>.004);
        const amplitude=estado==="speaking"&&comVoz&&Number.isFinite(r.amp)?Math.sqrt(Math.max(0,Math.min(1,r.amp))):0;
        const rgb=r.MOODT?.[r.data?.mood]||r.COLS?.[estado]||[128,237,243];
        cor.setRGB(rgb[0]/255,rgb[1]/255,rgb[2]/255,T.SRGBColorSpace);
        // The glow around the hologram (Blender's bloom) follows the theme too.
        const brilho=rgb.slice(0,3).map(Math.round).join(" ");
        if(brilho!==ultimoBrilho){canvas.style.setProperty("--jv-brilho",brilho);ultimoBrilho=brilho;}
        const sentimento=agora<sentida.ate?sentida.nome:(r.data?.expressao||"");
        robo.atualizar((agora-inicio)/1000,dt,amplitude,estado,cor,reduzir.matches,sentimento);
        const item=window.jarvisItemDe?.(el);
        if(item){
          if(item.girando){  // "dê uma voltinha": a full turn, eased, ending facing front
            const g=item.girando,p=Math.min(1,(agora-g.ini)/g.dur),f=p<.5?4*p*p*p:1-(-2*p+2)**3/2;
            item.ry=g.de+(g.ate-g.de)*f;item.rvy=0;if(p>=1)item.girando=null;
          }
          // Spun round and round by hand: about two and a half turns within a few seconds and
          // he gets dizzy, says so (through the JARVIS) and needs a while before it happens again.
          if(item.grabbedBy.length&&item.mode==="rotate")ctl.voltas+=Math.abs((item.ry||0)-ctl.ultimoRy);
          ctl.ultimoRy=item.ry||0;ctl.voltas*=Math.exp(-dt/3);
          if(ctl.voltas>2.5*2*Math.PI&&agora>ctl.proximaTontura){
            ctl.voltas=0;ctl.proximaTontura=agora+20000;robo.tontear(3.5);window.jarvisControle?.evento?.("tonto");
          }
          giro.rotation.x=item.rx||0;giro.rotation.y=item.ry||0;ctl.giro=giro.rotation.y;
        }
        if(estado!==ultimoEstado){estadoEl.textContent=rotulos[estado]||"PRONTO";ultimoEstado=estado;}
        ctl.estado=estado; renderer.render(cena,camera); ctl.quadros++;
      };
      ctl.parar=()=>{if(!ctl.vivo)return;ctl.vivo=false;fundo.geometry.dispose();fundo.material.dispose();limpar();};
      canvas.addEventListener("webglcontextlost",e=>{
        // forceContextLoss during intentional disposal is delivered asynchronously;
        // it must not remove a newer scene mounted on the same ring.
        if(!ctl.vivo)return;
        e.preventDefault();ctl.parar();if(vivos.get(el)===ctl)vivos.delete(el);falharam.add(el);
      },{once:true});
      el.appendChild(etiqueta);el.classList.add("jv-avatar");raf=requestAnimationFrame(olhar);
      return ctl;
    } catch(e) { limpar();throw e; }
  }

  // Tokens prevent a late async load from hiding the ring or leaking a WebGL context.
  function vestir(el) {
    if(!ativo||vivos.has(el)||pendentes.has(el)||falharam.has(el))return;
    const pedido={cancelado:false};pendentes.set(el,pedido);el.classList.add("jv-preparando");
    montar(el,pedido).then(ctl=>{
      if(!ctl)return;
      if(pedido.cancelado||!ativo||!el.isConnected)ctl.parar();else vivos.set(el,ctl);
    }).catch(e=>{falharam.add(el);console.info("Avatar: "+e.message);}).finally(()=>{
      if(pendentes.get(el)===pedido)pendentes.delete(el);
      if(!pendentes.has(el))el.classList.remove("jv-preparando");  // the hologram or, on failure, the ring
      if(ativo&&!pedido.cancelado&&!falharam.has(el)&&el.isConnected&&!vivos.has(el))vestir(el);
    });
  }
  function aplicar() {
    for(const [el,p] of pendentes)if(!ativo||!el.isConnected){p.cancelado=true;pendentes.delete(el);el.classList.remove("jv-preparando");}
    for(const [el,c] of vivos)if(!ativo||!el.isConnected){c.parar();vivos.delete(el);}
    if(ativo)document.querySelectorAll(".ringcard").forEach(vestir);
  }
  new MutationObserver(aplicar).observe(document.body,{childList:true,subtree:true});
  // Start fetching three.js and the model as the page opens, before the ring even exists.
  if(ativo)carregar().catch(()=>{});
  setTimeout(aplicar,0);
  window.jarvisAvatar={
    get ativo(){return ativo;},
    get montados(){return vivos.size;},
    get quadros(){let n=0;vivos.forEach(c=>n+=c.quadros);return n;},
    diagnostico(){return [...vivos.values()].map(c=>({
      modelo:c.robo.modelo,estado:c.estado,giro:c.giro||0,tonto:c.robo.tonto,girando:!!window.jarvisItemDe?.(c.el)?.girando,boca:c.robo.abertura,
      bocaAberta:c.robo.chave("Boca_Aberta"),piscar:c.robo.chave("Piscar"),expressoes:c.robo.expressoes,
      emocao:c.robo.emocao,sorriso:c.robo.chave("Sorriso_Dentes"),rosnar:c.robo.chave("Rosnar"),duvida:c.robo.chave("Sobrancelha_Duvida"),tristeza:c.robo.chave("Boca_Triste"),pulso:c.robo.pulso,olharCima:c.robo.chave("Olhar_Cima"),
      gpu:c.placa,triangulos:c.renderer.info.render.triangles,chamadas:c.renderer.info.render.calls,
    }));},
    // nome: alegria, duvida, raiva, tristeza or neutro; segundos: how long it holds (default 6).
    sentir(nome,segundos=6){
      const n=String(nome||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
      if(n&&n!=="neutro"&&!EMOCOES.includes(n))throw new Error("expressão: "+EMOCOES.join(", ")+" ou neutro");
      sentida={nome:n==="neutro"?"":n,ate:performance.now()+Math.max(.5,Number(segundos)||6)*1000};
      return{expressao:n||"neutro"};
    },
    // A full spin of the Zé (voltas turns), the "dê uma voltinha" command.
    girar(voltas=1){
      const n=Math.max(1,Math.min(3,Math.round(Number(voltas)||1)));let feito=false;
      vivos.forEach(c=>{const it=window.jarvisItemDe?.(c.el);if(!it)return;
        const de=it.ry||0,frente=Math.round(de/(2*Math.PI))*2*Math.PI;
        it.girando={de,ate:frente+2*Math.PI*n,ini:performance.now(),dur:1500*n**.7};feito=true;});
      if(!feito)throw new Error("o Zé não está na tela (visual: anel)");
      return{voltas:n};
    },
    usar(sim){ativo=!!sim;try{localStorage.setItem(CHAVE,ativo?"avatar":"anel");}catch(_){}
      if(ativo)document.querySelectorAll(".ringcard").forEach(el=>falharam.delete(el));
      aplicar();window.dispatchEvent(new Event("jv-visual"));return{visual:ativo?"avatar":"anel"};},
  };
})();
