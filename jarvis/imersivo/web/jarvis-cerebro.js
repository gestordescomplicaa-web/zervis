// SPDX-License-Identifier: AGPL-3.0-or-later
// barehands-jarvis: the Zé brain on screen (06/10/2026).
//   1. Decision card — the question waiting for a spoken "yes", with its
//      countdown; pending learning suggestions as a chip in the HUD.
//   2. Brain map — Brain / Work / Focus: a spatial network of memory, projects, agents,
//      automations, plus the timeline of how each piece was learned.
//   3. Efficiency meter — tokens read per answer over the last days, and how
//      much the Zé solved without calling the brain at all.
// Data: GET /jarvis/{decisao,eficiencia,mapa,mapa-abrir}, written by the
// Zé into state/. Tracker page only; read-only (decisions stay by voice).
(function () {
  if (new URLSearchParams(location.search).get("role") === "render") return;

  const CSS = `
  #jv-decisao { position:fixed; top:22px; left:50%; z-index:1001; width:min(560px, 88vw);
    transform:translate(-50%, -14px); opacity:0; pointer-events:none;
    transition:opacity .35s ease, transform .35s ease;
    background:rgba(6,18,22,.78); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px);
    border:1px solid rgba(255,179,71,.45); border-radius:14px; padding:14px 18px 12px;
    box-shadow:0 10px 40px rgba(0,0,0,.45), 0 0 24px rgba(255,179,71,.12);
    font:500 15px/1.45 'SF Mono', Menlo, monospace; color:rgba(235,250,245,.95); }
  #jv-decisao.on { opacity:1; transform:translate(-50%, 0); }
  #jv-decisao .t { display:flex; align-items:center; gap:9px; font-size:11.5px; font-weight:700;
    letter-spacing:.16em; color:rgba(255,179,71,.95); margin-bottom:7px; }
  #jv-decisao .t i { width:8px; height:8px; border-radius:50%; background:rgba(255,179,71,1);
    box-shadow:0 0 10px rgba(255,179,71,.9); animation:jvpulse 1.4s ease-in-out infinite; }
  #jv-decisao .q { white-space:pre-wrap; }
  #jv-decisao .h { margin-top:9px; font-size:12px; color:rgb(var(--jv-borda-rgb) / .8); letter-spacing:.04em; }
  #jv-decisao .bar { margin-top:9px; height:3px; border-radius:2px; background:rgba(255,179,71,.15); overflow:hidden; }
  #jv-decisao .bar i { display:block; height:100%; width:100%; background:rgba(255,179,71,.85);
    transform-origin:left; transition:transform .5s linear; }
  @keyframes jvpulse { 0%,100% { opacity:1 } 50% { opacity:.35 } }

  #hint.hud .jv { display:flex; align-items:center; gap:8px; padding:3px 10px; border-radius:12px;
    border:1px solid rgb(var(--jv-borda-rgb) / .22); cursor:default; }
  #hint.hud .jv.btn { cursor:pointer; transition:background .3s, border-color .3s; }
  #hint.hud .jv.btn:hover { background:rgb(var(--jv-borda-rgb) / .1); border-color:rgb(var(--jv-borda-rgb) / .5); }
  #hint.hud .jv.sug { border-color:rgba(255,179,71,.5); color:rgba(255,200,120,.95); }
  #hint.hud .jv svg { display:block; }
  #hint.hud .jv .down { color:rgba(120,240,170,.95); } #hint.hud .jv .up { color:rgba(255,179,71,.95); }
  #hint.hud .jv small { font-size:10.5px; font-weight:500; opacity:.75; letter-spacing:.03em; }

  `;
  const st = document.createElement("style");
  st.textContent = CSS;
  document.head.appendChild(st);

  const esc = s => String(s ?? "").replace(/[&<>"]/g, x => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[x]);
  const get = async nome => {
    try { return await (await fetch("/jarvis/" + nome, { cache: "no-store" })).json(); }
    catch (e) { return {}; }
  };
  const mil = n => n == null ? "—" : n >= 1000 ? (n / 1000).toFixed(1).replace(".", ",") + " mil" : String(n);

  // ---------- 1. decision card ------------------------------------------------
  const card = document.createElement("div");
  card.id = "jv-decisao";
  card.innerHTML = '<div class="t"><i></i>ESPERANDO VOCÊ</div><div class="q"></div>' +
    '<div class="h"></div><div class="bar"><i></i></div>';
  document.body.appendChild(card);
  let total = 0, decisao = {};

  function mostrarDecisao(d) {
    decisao = d || {};
    const p = decisao.pergunta;
    if (!p || !p.texto) { card.classList.remove("on"); total = 0; return; }
    card.querySelector(".q").textContent = p.texto;
    const exata = /“([^”]+)”|"([^"]+)"/.exec(p.texto);
    card.querySelector(".h").textContent = exata
      ? `Responda por voz com a frase exata: ${exata[1] || exata[2]}`
      : "Responda por voz: sim ou não";
    const bar = card.querySelector(".bar i");
    if (p.expira) {
      const falta = Math.max(0, p.expira - Date.now() / 1000);
      if (!total || falta > total) total = falta;
      bar.style.transform = `scaleX(${total ? falta / total : 0})`;
    } else { total = 0; bar.style.transform = "scaleX(1)"; }
    card.classList.add("on");
  }

  // ---------- 3. efficiency meter + map button + suggestions chip ------------
  let linha = null;
  function garantirLinha() {
    const h = document.getElementById("hint");
    if (!h || !h.classList.contains("hud")) return null;
    if (!linha || !linha.isConnected) {
      linha = document.createElement("div");
      linha.className = "linha"; linha.id = "hud-jv";
      h.appendChild(linha);
      linha.addEventListener("click", ev => {
        if (ev.target.closest(".jv.btn")) abrirMapa(false);
      });
    }
    return linha;
  }

  function sparkline(dias) {
    const pts = dias.map(d => d.media);
    const vals = pts.filter(v => v != null);
    if (vals.length < 2) return "";
    const W = 70, H = 18, max = Math.max(...vals), min = Math.min(...vals), span = max - min || 1;
    let d = "", dots = "";
    pts.forEach((v, i) => {
      if (v == null) return;
      const x = (i / (pts.length - 1)) * (W - 4) + 2, y = H - 2 - ((v - min) / span) * (H - 4);
      d += (d ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
      if (i === pts.length - 1) dots = `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.4" style="fill:var(--jv-acento)"/>`;
    });
    return `<svg width="${W}" height="${H}"><path d="${d}" fill="none" style="stroke:rgb(var(--jv-borda-rgb) / .75)" stroke-width="1.5"/>${dots}</svg>`;
  }

  function mostrarEficiencia(e) {
    const l = garantirLinha();
    if (!l) return;
    let html = "";
    if (e && e.hoje) {
      const h = e.hoje, t = e.tendencia;
      const seta = t == null ? "" : t <= 0 ? `<span class="down">↓ ${-t}%</span>` : `<span class="up">↑ ${t}%</span>`;
      const dica = (e.dias || []).map(d => `${d.dia}: ${d.media == null ? "—" : mil(d.media)} por resposta (${d.respostas} respostas, ${d.locais} sem o cérebro)`).join("\n");
      html += `<span class="jv dev" title="${esc("Tokens lidos por resposta do cérebro\n" + dica)}">TOKENS/RESPOSTA ${sparkline(e.dias || [])}` +
        `${mil(h.media)} ${seta}<small>· ${h.locais} sem cérebro hoje</small></span>`;
    }
    const sug = (decisao.sugestoes || []);
    if (sug.length) {
      const dica = sug.map(s => "• " + s.resumo + (s.origem ? `\n   de: “${s.origem}”` : "")).join("\n");
      html += `<span class="jv sug btn" title="${esc(dica + "\n\nDiga: quais são as sugestões?")}">◆ ${sug.length} ${sug.length === 1 ? "SUGESTÃO" : "SUGESTÕES"}</span>`;
    }
    if (l.innerHTML !== html) l.innerHTML = html;
  }

  // Brain is spatial context; Work is the live inventory; Focus is one object.
  const mapaEl = document.createElement('div');
  mapaEl.id = 'jv-mapa';
  mapaEl.setAttribute('role', 'dialog');
  mapaEl.setAttribute('aria-modal', 'false');
  mapaEl.setAttribute('aria-label', 'Zé — Mapa: Geral, Trabalho e Foco');
  const areas = {
    memoria: {title:'Memória',icon:'◇',x:420,y:250,desc:'O que o Zé sabe sobre você e o ambiente, e as skills que aprendeu.'},
    sessoes: {title:'Sessões',icon:'◎',x:1120,y:440,desc:'Agentes de código trabalhando nos seus projetos.'},
    automacoes: {title:'Automações',icon:'✓',x:420,y:640,desc:'Lembretes e tarefas agendadas.'},
  };
  mapaEl.innerHTML = '<div class="grip"><span class="titulo">◉ MAPA <span class="online">Conectando</span></span><span class="voz">Verificando voz</span><button data-action="window-fit" title="Expandir ou reduzir janela" aria-label="Ajustar janela">↔</button><button data-action="close" aria-label="Recolher mapa">×</button></div>' +
    '<nav class="modos" aria-label="Vistas do mapa"><button data-action="mode:brain"><span class="icone">◉</span><span class="nome">GERAL</span></button><button data-action="mode:work"><span class="icone">◎</span><span class="nome">TRABALHO</span></button><button data-action="mode:focus"><span class="icone">◇</span><span class="nome">FOCO</span></button></nav>' +
    '<main class="principal"><div class="palco"><svg role="group" aria-label="O que o Zé sabe e faz"><g class="mundo"></g></svg>' +
    '<div class="contexto"><h1>O que o Zé sabe e faz</h1><p class="sub">Aponte para conhecer. Pinça para explorar.</p></div>' +
    '</div><section class="vista work" hidden aria-label="Trabalho"></section><section class="vista focus" hidden aria-label="Foco"></section></main>' +
    '<div class="ferramentas" aria-label="Tamanho da vista"><button data-action="motion">Pausar</button><button data-action="zoom-out" aria-label="Reduzir vista">−</button><span class="zoom"></span><button data-action="zoom-in" aria-label="Ampliar vista">+</button><button data-action="fit">Ajustar</button></div>' +
    '<div class="ajuda">Aponte para ler · pinça para puxar · duas mãos ampliam</div><div class="previa" aria-hidden="true"></div>';
  document.body.appendChild(mapaEl);
  const svg = mapaEl.querySelector('.palco>svg'), mundo = svg.querySelector('.mundo');
  const workEl = mapaEl.querySelector('.work'), focusEl = mapaEl.querySelector('.focus'), previa = mapaEl.querySelector('.previa');
  const graph = new window.JarvisGraph(mundo);
  const clamp = (v,a,b)=>Math.max(a,Math.min(b,v));
  const camera = {x:0,y:0,s:1}, pontos = new Map(), maos = new Map();
  let foco={}, focoGrupo=null, focoMarcados=new Set();  // the Foco board (state/foco.json)
  let mapa={}, trabalho={}, presenca={}, aberto=false, fecharEm=0, focoAnterior=null, modo='brain', filtro='sessoes';
  let objetos=new Map(), grupos={}, escolhido=null, hoverEl=null, gesto=null, desenhado='', expandido=null;
  let ultimaVista='brain', peloJarvis=false;
  const leitura={work:1,focus:1};
  let janelaAmpla=false;
  const quando = t => t ? new Date(t*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : '';
  const estados = {working:'Trabalhando',thinking:'Pensando',done:'Concluído',idle:'Em espera',waiting:'Aguardando',
    'waiting-for-input':'Aguardando você',error:'Erro',failed:'Falhou',stopped:'Parado',
    'in-progress':'Em andamento','in-review':'Em revisão',completed:'Concluído',todo:'A fazer',active:'Ativo'};
  const estadoTexto = s=>estados[s] || (s ? String(s) : 'Sem estado informado');
  function atividade() { fecharEm=0; }
  function montarDados() {
    objetos=new Map(); grupos=Object.fromEntries(Object.keys(areas).map(k=>[k,[]]));
    const add=(area,it)=>{const n={...it,area}; objetos.set(n.id,n);grupos[area].push(n);};
    for(const g of mapa.grupos || []) for(const [i,it] of (g.itens||[]).entries()) {
      const area=g.id==='automacoes'?'automacoes':'memoria';
      add(area,{...it,id:it.id||g.id+':'+i,categoria:g.rotulo,meta:it.ativo!=null?(it.ativo?'Automação ativa':'Automação pausada'):it.usos!=null?it.usos+' usos registrados':it.novo?'Aprendido recentemente':g.rotulo});
    }
    for(const it of trabalho.sessoes || []) add('sessoes',{...it,id:'sessao:'+it.id,categoria:'Sessão'+(it.pasta?' · '+it.pasta:''),meta:estadoTexto(it.estado),texto:it.texto||it.rotulo});
  }
  function status() {
    const vivo=presenca.batimento && Date.now()/1000-presenca.batimento<10;
    const online=mapaEl.querySelector('.online'); online.textContent=vivo?'Online':'Sem sinal';online.classList.toggle('vivo',!!vivo);
    const labels={ativo:'Pronto para “Ei Zé”',ouvindo:'Ouvindo',pensando:'Pensando',falando:'Falando',confirmando:'Esperando você',inativo:'Microfone fechado'};
    mapaEl.querySelector('.voz').textContent=vivo?(!presenca.microfone_aberto?'Microfone fechado':labels[presenca.estado]||'Estado indisponível'):'Voz indisponível';
  }
  function subtitulo(id) {
    return grupos[id].length+' '+({memoria:'registros',sessoes:'sessões',automacoes:'itens'}[id]||'itens');
  }
  function desenharGrafo(reset=false) {
    const specs=[{id:'center',title:'Zé',kind:'root',radius:45,color:'root',x:770,y:440,subtitle:'Memória · relações · aprendizado',icon:'root'}],links=[];
    for(const [id,a] of Object.entries(areas)) {
      if(!a.x) continue;
      specs.push({id:'area:'+id,title:a.title,kind:'group',radius:28,color:id,x:a.x,y:a.y,subtitle:subtitulo(id),icon:id});
      links.push({from:'center',to:'area:'+id,color:id,length:Math.hypot(a.x-770,a.y-440)});
      const list=[...grupos[id]], compact=svg.getBoundingClientRect().width<900;
      const picked=list.findIndex(it=>it.id===escolhido);
      if(picked>0&&expandido===id)list.unshift(...list.splice(picked,1));
      const count=expandido===id?Math.min(6,list.length):Math.min(compact?1:3,list.length);
      for(let i=0;i<count;i++) {
        const it=list[i],left=a.x<770, side=left?-1:1, offset=(i-(count-1)/2)*52;
        const x=clamp(a.x+side*(155+(i%2)*20),80,1520),y=clamp(a.y+offset,70,820);
        specs.push({id:it.id,title:it.rotulo,kind:'item',radius:7+Math.min(5,Math.log2(1+(it.usos||0))),color:id,x,y,labelSide:side,subtitle:id==='sessoes'?it.meta:''});
        links.push({from:'area:'+id,to:it.id,color:id,length:Math.hypot(x-a.x,y-a.y)});
      }
    }
    // Exact agent → project relationships, only when both endpoints are visible.
    const visible=new Set(specs.map(n=>n.id));
    graph.setData(specs,links,reset);
    graph.setHighlight(null,escolhido);
    aplicarCamera();
  }
  function aplicarCamera() {
    const r=svg.getBoundingClientRect();
    camera.x=clamp(camera.x,120-1700*camera.s,r.width-120);camera.y=clamp(camera.y,90-950*camera.s,r.height-90);
    mundo.setAttribute('transform',`translate(${camera.x} ${camera.y}) scale(${camera.s})`);
    graph.updateLabels();atualizarZoom();
  }
  function enquadrar() {
    const r=svg.getBoundingClientRect();
    camera.s=clamp(Math.min((r.width-50)/1600,(r.height-140)/900),.16,1.3);
    camera.x=(r.width-1600*camera.s)/2;camera.y=65+(r.height-130-900*camera.s)/2;
    aplicarCamera();
  }
  function ampliar(f,x,y) {
    const r=svg.getBoundingClientRect();x=x??r.width/2;y=y??r.height/2;
    const s=clamp(camera.s*f,.15,3.5),k=s/camera.s;
    camera.x=x-(x-camera.x)*k;camera.y=y-(y-camera.y)*k;camera.s=s;aplicarCamera();
  }
  function atualizarZoom(){
    mapaEl.querySelector('.zoom').textContent=Math.round((modo==='brain'?camera.s:leitura[modo])*100)+'%';
    mapaEl.querySelector('[data-action="motion"]').hidden=modo!=='brain';
    mapaEl.querySelector('.ajuda').textContent=modo==='brain'
      ?'Pinça puxa · duas mãos ampliam · título move a janela'
      :'Pinça arrasta a leitura · duas mãos ampliam · título move a janela';
  }
  function ampliarLeitura(f,y){
    const v=modo==='work'?workEl:focusEl, old=leitura[modo], r=v.getBoundingClientRect();
    const local=clamp((y??(r.top+r.height/2))-r.top,0,r.height);
    const anchor=v.scrollTop+local/old;
    leitura[modo]=clamp(old*f,1,2);
    v.style.zoom=leitura[modo];
    v.scrollTop=anchor-local/leitura[modo];atualizarZoom();
  }
  function zoomVista(f,x,y){
    if(modo==='brain'){const r=svg.getBoundingClientRect();ampliar(f,x==null?undefined:x-r.left,y==null?undefined:y-r.top);}
    else ampliarLeitura(f,y);
  }
  function ajustarVista(){if(modo==='brain')enquadrar();else ampliarLeitura(1/leitura[modo]);}
  function listaWork() {
    const a=areas[filtro],list=grupos[filtro]||[];
    const info=a.desc;
    workEl.innerHTML='<h1>'+esc(a.title)+'</h1><p class="intro">'+esc(info)+'</p><div class="filtros">'+
      Object.keys(areas).map(id=>'<button data-action="area:'+id+'" class="'+(id===filtro?'ativo':'')+'">'+areas[id].title+' <small>'+grupos[id].length+'</small></button>').join('')+'</div><div class="lista">'+
      (list.length?list.map(it=>'<button class="objeto" data-object="'+esc(it.id)+'"><span class="objeto-icon">'+a.icon+'</span><span><strong>'+esc(it.rotulo)+'</strong><small>'+esc(it.categoria||'')+'</small></span><span class="badge">'+esc(it.meta)+'</span><span>›</span></button>').join(''):
      '<div class="vazio">'+({sessoes:'Nenhuma sessão. Crie uma no painel, em Sessões.',automacoes:'Nada agendado. Peça ao Zé: “me lembra amanhã às nove de…”.'}[filtro]||'Nada aqui ainda.')+'</div>')+'</div>';
  }
  function historiaHtml(id=null) {
    const eventos=(mapa.linha_do_tempo||[]).filter(e=>!id||e.item===id);
    const pendentes=id?[]:(decisao.sugestoes||[]);
    return '<div class="history"><h3>Como ele aprendeu</h3>'+pendentes.map(e=>'<div class="evento"><strong>Esperando sua decisão por voz</strong><p>'+esc(e.resumo)+'</p>'+(e.origem?'<q>'+esc(e.origem)+'</q>':'')+'</div>').join('')+
      eventos.map(e=>'<div class="evento"><strong>'+esc(e.rotulo)+'</strong> · '+esc(quando(e.em))+'<p>'+esc(e.resumo)+'</p>'+(e.origem?'<q>'+esc(e.origem)+'</q>':'')+(e.item&&objetos.has(e.item)?'<button data-object="'+esc(e.item)+'">Ver memória</button>':'')+'</div>').join('')+(!eventos.length&&!pendentes.length?'<p class="intro">Nenhum aprendizado registrado para este contexto.</p>':'')+'</div>';
  }
  function focus() {
    const it=objetos.get(escolhido),a=areas[it?.area];
    if(!it) {
      focusEl.innerHTML=quadroFoco();return;  // nothing chosen: the Foco board
    }
    const relacionados=[...objetos.values()].filter(n=>n.id===it.relacao||n.relacao===it.id);
    focusEl.innerHTML='<button data-action="back">← Voltar ao '+(ultimaVista==='work'?'Trabalho':'Geral')+'</button><div class="focus-layout"><article><div class="focus-icone">'+a.icon+'</div><p class="intro">'+esc(it.categoria||a.title)+'</p><h1>'+esc(it.rotulo)+'</h1><div class="focus-meta">'+esc(it.meta||'')+(it.em?' · '+esc(quando(it.em)):'')+'</div><div class="focus-corpo">'+esc(it.texto||it.rotulo)+'</div>'+
      (it.origem?'<blockquote class="focus-origem">Aprendeu com sua correção:<br>“'+esc(it.origem)+'”</blockquote>':'')+
      '<div class="focus-acoes"><button data-action="locate">Ver nas conexões</button><button data-action="node-smaller">Esfera −</button><button data-action="node-larger">Esfera +</button></div>'+
      (it.area==='memoria'?historiaHtml(it.id):'')+'</article><aside class="focus-relacoes"><h3>Relações</h3><button data-action="area:'+it.area+'">'+a.icon+' '+a.title+'</button>'+
      relacionados.map(n=>'<button data-object="'+esc(n.id)+'">'+esc(n.rotulo)+'<small> · '+esc(n.meta)+'</small></button>').join('')+
      '</aside></div>';
  }
  function trocarModo(m) {
    pontos.clear();gesto=null;graph.releaseAll();
    limparHover();atividade();if(m==='focus'&&modo!=='focus')ultimaVista=modo;modo=m;mapaEl.dataset.mode=m;
    mapaEl.querySelector('.palco').hidden=m!=='brain';workEl.hidden=m!=='work';focusEl.hidden=m!=='focus';
    mapaEl.querySelectorAll('.modos button').forEach(b=>{const on=b.dataset.action==='mode:'+m;b.classList.toggle('ativo',on);b.setAttribute('aria-pressed',String(on));});
    mapaEl.querySelectorAll('.navegacao button').forEach(b=>b.classList.toggle('ativo',b.dataset.action==='area:'+(m==='brain'?'brain':filtro)));
    atualizarZoom();
    if(m==='brain') { graph.start();requestAnimationFrame(aplicarCamera); }
    else {graph.close();if(m==='work')listaWork();else focus();}
  }
  function escolher(id) {
    atividade();limparHover();
    if(id==='center') {escolhido=null;ultimaVista=modo;trocarModo('focus');return;}
    if(id.startsWith('area:')) {
      const area=id.slice(5);expandido=expandido===area?null:area;desenharGrafo();
      if(!grupos[area].length){filtro=area;trocarModo('work');}
      else mapaEl.querySelector('.sub').textContent=areas[area].title+': '+grupos[area].length+' itens. Abra um ponto ou veja todos em Trabalho.';
      return;
    }
    if(!objetos.has(id))return;
    escolhido=id;if(modo!=='focus')ultimaVista=modo;trocarModo('focus');focusEl.scrollTop=0;
  }
  function posicionarQuadro() {
    if(janelaAmpla){Object.assign(mapaEl.style,{left:'12px',top:'12px',width:(innerWidth-24)+'px',height:Math.max(280,innerHeight-100)+'px'});return;}
    const ring = window.jarvisStage?.prepareWorkspace();
    const edge = ring ? ring.x + ring.radius + 26 : innerWidth * .32;
    const left = Math.min(Math.max(edge, innerWidth < 750 ? 160 : 240), innerWidth - 290);
    const top = Math.min(64, Math.max(12, innerHeight * .07));
    mapaEl.style.left = left + 'px'; mapaEl.style.top = top + 'px';
    mapaEl.style.width = Math.max(280, innerWidth - left - 20) + 'px';
    mapaEl.style.height = Math.max(280, innerHeight - top - 82) + 'px';
  }
  function abrirMapa(porVoz) {
    if(aberto&&!porVoz){fecharMapa();return;}
    if(!aberto)focoAnterior=document.activeElement;
    aberto=true;fecharEm=porVoz?Date.now()+90000:0;posicionarQuadro();
    mapaEl.style.display='grid';document.body.classList.add('jv-brain-open');
    montarDados();desenharGrafo();trocarModo('brain');fecharEm=porVoz?Date.now()+90000:0;
    requestAnimationFrame(()=>{mapaEl.classList.add('on');enquadrar();});
    mapaEl.querySelector('[data-action="close"]').focus({preventScroll:true});
  }
  function fecharMapa() {
    aberto=false;peloJarvis=false;pontos.clear();gesto=null;graph.close();limparHover();
    mapaEl.classList.remove('on');document.body.classList.remove('jv-brain-open');
    window.jarvisStage?.restoreWorkspace();
    focoAnterior?.focus?.({preventScroll:true});
    setTimeout(()=>{if(!aberto)mapaEl.style.display='none';},280);
  }
  // ---------- the Foco board: what the user started, the "V" to mark it done ----------
  // gdautomacao.ia (08/10/2026): for ADHD, one big card (the current front and its next
  // step), the other active ones smaller, the rest collapsed. Marking the V posts /foco; the
  // Zé applies it, answers aloud and the board refreshes.
  const FOCO_GRUPOS={travadas:'Travadas',pausadas:'Pausadas',ideias:'Ideias'};
  // The open group: the user's choice, or (nothing in progress) the ideas, which are what there is to start.
  const grupoAberto=()=>focoGrupo===''||(foco[focoGrupo]||[]).length?focoGrupo:(!foco.atual&&(foco.ideias||[]).length?'ideias':'');
  function cartaoFoco(f,grande){
    const marcado=focoMarcados.has(f.id)?' marcado':'';
    const passo=f.proximo_passo
      ?'<button class="foco-v'+marcado+'" data-action="foco:passo:'+esc(f.id)+'" aria-label="Marcar como feito: '+esc(f.proximo_passo)+'"><span class="caixa">✓</span><span class="passo"><small>PRÓXIMO PASSO</small>'+esc(f.proximo_passo)+'</span></button>'
      :'<p class="foco-sem-passo">Sem próximo passo. Diga ao Zé qual é.</p>';
    return '<article class="foco-cartao'+(grande?' atual':'')+'">'+(grande?'<p class="foco-rotulo">AGORA</p>':'')+
      '<h2>'+esc(f.titulo)+'</h2>'+(f.projeto&&!f.titulo.toLowerCase().includes(f.projeto.toLowerCase())?'<p class="foco-meta">Projeto '+esc(f.projeto)+'</p>':'')+
      (f.bloqueio?'<p class="foco-trava">Travada: '+esc(f.bloqueio)+'</p>':passo)+
      '<div class="foco-acoes">'+(grande?'<button data-action="foco:concluir:'+esc(f.id)+'">✓ Frente concluída</button><button data-action="foco:pausar:'+esc(f.id)+'">Pausar</button>'
        :'<button data-action="foco:focar:'+esc(f.id)+'">Focar nesta</button><button data-action="foco:concluir:'+esc(f.id)+'">Concluída</button>')+'</div></article>';
  }
  function quadroFoco(){
    const dia=new Date().toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'2-digit'});
    const feitas=foco.concluidas_hoje?' · '+foco.concluidas_hoje+' concluída'+(foco.concluidas_hoje>1?'s':'')+' hoje':'';
    let h='<div class="foco-quadro"><header class="foco-topo"><h1>FOCO</h1><p>'+esc(dia)+feitas+'</p></header>';
    const temIdeias=(foco.ideias||[]).length>0;
    h+=foco.atual?cartaoFoco(foco.atual,true):'<div class="foco-vazio">Nenhuma frente em andamento agora.<br><small>'+
      (temIdeias?'Toque em <b>Virar frente</b> numa ideia abaixo, ou diga: “Ei Zé, comecei …”':'Diga: “Ei Zé, comecei …” e o Zé anota aqui, com o próximo passo.')+'</small></div>';
    if((foco.ativas||[]).length)h+='<div class="foco-outras">'+foco.ativas.map(f=>cartaoFoco(f,false)).join('')+'</div>';
    const grupos=Object.entries(FOCO_GRUPOS).filter(([k])=>(foco[k]||[]).length);
    if(grupos.length){
      h+='<nav class="foco-grupos">'+grupos.map(([k,n])=>'<button data-action="foco-grupo:'+k+'" aria-expanded="'+(grupoAberto()===k)+'">'+n+' ('+foco[k].length+')</button>').join('')+'</nav>';
      const lista=grupoAberto();
      if(lista&&(foco[lista]||[]).length)h+='<div class="foco-lista">'+foco[lista].map(f=>
        '<div class="foco-item"><span>'+esc(f.titulo)+(f.bloqueio?' — '+esc(f.bloqueio):f.proximo_passo?' — '+esc(f.proximo_passo):'')+'</span><button data-action="foco:focar:'+esc(f.id)+'">'+(lista==='ideias'?'Virar frente':'Retomar')+'</button></div>').join('')+'</div>';
    }
    return h+'</div>';
  }
  async function marcarFoco(acaoFoco,id){
    if(acaoFoco==='passo'){focoMarcados.add(id);if(modo==='focus'&&!escolhido)focus();}
    try{await fetch('/foco',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao:acaoFoco,id})});}catch(e){}
    setTimeout(async()=>{foco=await get('foco');focoMarcados.delete(id);if(aberto&&modo==='focus'&&!escolhido)focus();},1300);
  }
  function acao(nome) {
    atividade();
    if(nome.startsWith('foco:')){const [,a,id]=nome.split(':');marcarFoco(a,id);return;}
    if(nome.startsWith('foco-grupo:')){const g=nome.slice(11);focoGrupo=grupoAberto()===g?'':g;focus();return;}
    if(nome.startsWith('mode:')){trocarModo(nome.slice(5));return;}
    if(nome.startsWith('area:')){const id=nome.slice(5);if(id==='brain')trocarModo('brain');else{filtro=id;trocarModo('work');}return;}
    if(nome==='close')fecharMapa();
    else if(nome==='window-fit'){janelaAmpla=!janelaAmpla;posicionarQuadro();}
    else if(nome==='fit')ajustarVista();
    else if(nome==='zoom-in')zoomVista(1.25);
    else if(nome==='zoom-out')zoomVista(1/1.25);
    else if(nome==='motion'){graph.setMotion(!graph.motion);mapaEl.querySelector('[data-action="motion"]').textContent=graph.motion?'Pausar':'Flutuar';}
    else if(nome==='back')trocarModo(ultimaVista);
    else if(nome==='node-larger'||nome==='node-smaller')graph.resize(nome==='node-larger'?1.25:1/1.25,escolhido);
    else if(nome==='locate'){
      expandido=objetos.get(escolhido)?.area;trocarModo('brain');desenharGrafo();
      const list=grupos[expandido]||[],it=list.find(x=>x.id===escolhido);
      // Place a selected item beyond the overview limit into the visible subset.
      if(it&&!graph.nodes.has(it.id)){list.splice(list.indexOf(it),1);list.unshift(it);desenharGrafo();}
      graph.setHighlight(null,escolhido);enquadrar();
    }
  }
  const targets='#jv-mapa [data-action], #jv-mapa [data-node], #jv-mapa [data-object], #hud-jv .btn, #hud-maos .btn, #jv-config [data-config], #jv-config .cer, #jv-teclado-btn, #jv-teclado button, #jv-engrenagem, .panel [data-panel-action]';
  function alvoEm(x,y){return document.elementFromPoint(x,y)?.closest(targets)||null;}
  function ativar(alvo){
    if(!alvo?.isConnected)return;
    // The settings menu (key D): its own buttons, and the rows it hosts keep their clicks.
    if(alvo.matches('[data-panel-action]'))window.jarvisPanels?.action(alvo);
    else if(alvo.closest('#jv-config')){if(alvo.dataset.config)window.jarvisConfig?.acionar(alvo.dataset.config);else if(alvo.matches('#hud-maos .btn'))window.jarvisMaos?.acionar(alvo.dataset.acao);else alvo.click();}
    else if(alvo.matches('#hud-maos .btn'))window.jarvisMaos?.acionar(alvo.dataset.acao);
    else if(alvo.closest('#jv-teclado-btn, #jv-teclado, #jv-engrenagem'))alvo.click();
    else if(alvo.matches('#hud-jv .btn'))abrirMapa(false);
    else if(alvo.dataset.action)acao(alvo.dataset.action);
    else escolher(alvo.dataset.node||alvo.dataset.object);
  }
  let previaHTML='', previaW=0, previaH=0;
  new ResizeObserver(()=>{previaW=previaH=0;}).observe(previa);
  function limparHover(){hoverEl?.classList.remove('apontado');hoverEl=null;graph.setHighlight(null,escolhido);previa.style.display='none';}
  function apontar(x,y){
    const alvo=alvoEm(x,y);
    if(hoverEl!==alvo){limparHover();hoverEl=alvo;alvo?.classList.add('apontado');}
    if(!aberto||!alvo?.dataset.node||pontos.size)return;
    atividade();const id=alvo.dataset.node,it=objetos.get(id),area=id.startsWith('area:')?areas[id.slice(5)]:null;
    graph.setHighlight(id,escolhido);
    const html='<small>'+esc(it?.categoria||(area?'Área da sua rotina':'Seu assistente'))+'</small><strong>'+esc(it?.rotulo||area?.title||'Zé')+'</strong><p>'+esc((it?.texto||area?.desc||mapa.centro?.sub||'').slice(0,600))+'</p>'+
      (it?.origem?'<blockquote>'+esc(it.origem)+'</blockquote>':'')+'<small>'+(area?'Pinça curta expande · segure para puxar':'Pinça curta abre no Focus · segure para puxar')+'</small>';
    // Keep the same DOM while pointing; refreshed data still updates its content.
    if(html!==previaHTML){previa.innerHTML=html;previaHTML=html;previaW=previaH=0;}
    if(previa.style.display!=='block'){previa.style.display='block';previaW=previaH=0;}
    if(!previaW){previaW=previa.offsetWidth;previaH=previa.offsetHeight;}
    let left=x+32;if(left+previaW>innerWidth-12)left=x-previaW-32;
    const frame=mapaEl.getBoundingClientRect();
    previa.style.left=(Math.max(8,left)-frame.left)+'px';
    previa.style.top=(clamp(y-25,8,Math.max(8,innerHeight-previaH-12))-frame.top)+'px';
  }
  function reancorar(){
    const ps=[...pontos.values()].filter(p=>p.area==='map');
    if(ps.length>=2){
      ps.forEach(p=>p.multi=true);const[a,b]=ps,r=svg.getBoundingClientRect(),cx=(a.x+b.x)/2-r.left,cy=(a.y+b.y)/2-r.top;
      const node=a.node&&a.node===b.node?a.node:null;
      if(!node)ps.forEach(p=>{graph.release(p.node);p.node=null;});
      gesto={ids:[a.id,b.id],node,size:graph.sizes.get(node)||1,d:Math.max(30,Math.hypot(a.x-b.x,a.y-b.y)),s:camera.s,wx:(cx-camera.x)/camera.s,wy:(cy-camera.y)/camera.s};
    }else {
      const reading=[...pontos.values()].filter(p=>p.scroll&&p.scroll=== (modo==='work'?workEl:focusEl));
      if(reading.length>=2){const[a,b]=reading;reading.forEach(p=>p.multi=true);
        gesto={ids:[a.id,b.id],reading:true,d:Math.max(30,Math.hypot(a.x-b.x,a.y-b.y)),s:leitura[modo]};
      }else gesto=null;
    }
    for(const p of pontos.values()){
      p.lx=p.x;p.ly=p.y;
      if(p.node){const n=graph.nodes.get(p.node),r=svg.getBoundingClientRect();p.ox=n.x-(p.x-r.left-camera.x)/camera.s;p.oy=n.y-(p.y-r.top-camera.y)/camera.s;}
    }
  }
  function pressionar(id,x,y,mao=false){
    atividade();limparHover();const alvo=alvoEm(x,y),el=document.elementFromPoint(x,y),scroll=el?.closest('.vista, #jv-config .corpo');
    const area=scroll?'scroll':el?.closest('.grip')&&!alvo?'window':el?.closest('.palco')&&!el.closest('.ferramentas')?'map':'control';
    const node=area==='map'?alvo?.dataset.node:null;if(node)graph.hold(node);
    pontos.set(id,{id,x,y,sx:x,sy:y,lx:x,ly:y,alvo,node,area,scroll,mao,movido:false,multi:false,t:performance.now()});reancorar();
  }
  function mover(id,x,y){
    const p=pontos.get(id);if(!p){apontar(x,y);return;}
    // A hand in the air trembles: its tolerance comes from the calibrated profile.
    const d=Math.hypot(x-p.sx,y-p.sy);p.maxd=Math.max(p.maxd||0,d);
    p.x=x;p.y=y;if(d>(p.mao?(window.jarvisMaos?.p?.tremor??16):5))p.movido=true;
    if(gesto&&gesto.ids.includes(id)){
      const[a,b]=gesto.ids.map(i=>pontos.get(i)),r=svg.getBoundingClientRect(),ratio=Math.hypot(a.x-b.x,a.y-b.y)/gesto.d;
      if(gesto.reading)ampliarLeitura(gesto.s*ratio/leitura[modo],(a.y+b.y)/2);
      else if(gesto.node)graph.resize(gesto.size*ratio/(graph.sizes.get(gesto.node)||1),gesto.node);
      else{camera.s=clamp(gesto.s*ratio,.15,3.5);camera.x=(a.x+b.x)/2-r.left-gesto.wx*camera.s;camera.y=(a.y+b.y)/2-r.top-gesto.wy*camera.s;aplicarCamera();}
    }else if(p.movido){
      if(p.area==='window'){
        const r=mapaEl.getBoundingClientRect();
        mapaEl.style.left=clamp(r.left+x-p.lx,8,Math.max(8,innerWidth-r.width-8))+'px';
        mapaEl.style.top=clamp(r.top+y-p.ly,8,Math.max(8,innerHeight-r.height-8))+'px';
      }else if(p.scroll)p.scroll.scrollTop-=(y-p.ly)/(p.scroll===workEl?leitura.work:p.scroll===focusEl?leitura.focus:1);
      else if(p.node){const r=svg.getBoundingClientRect();graph.move(p.node,(x-r.left-camera.x)/camera.s+p.ox,(y-r.top-camera.y)/camera.s+p.oy);}
      else if(p.area==='map'){camera.x+=x-p.lx;camera.y+=y-p.ly;aplicarCamera();}
    }
    if(p.movido||p.multi){p.lx=x;p.ly=y;}
  }
  // The target is locked when the pinch closes: releasing on it, or within the
  // hand's tolerance of it, still opens it.
  function sobreAlvo(p){
    if(!p.alvo)return false;if(alvoEm(p.x,p.y)===p.alvo)return true;if(!p.mao||!p.alvo.isConnected)return false;
    const m=window.jarvisMaos?.p?.tremor??16,r=p.alvo.getBoundingClientRect();
    return p.x>=r.left-m&&p.x<=r.right+m&&p.y>=r.top-m&&p.y<=r.bottom+m;
  }
  function soltar(id,cancelado=false,motivo=''){
    const p=pontos.get(id);if(!p)return;pontos.delete(id);
    if(![...pontos.values()].some(q=>q.node===p.node))graph.release(p.node);reancorar();
    const dur=performance.now()-p.t,abre=!cancelado&&!p.movido&&!p.multi&&(!p.mao||dur<1200)&&sobreAlvo(p);
    if(p.mao)window.jarvisMaos?.registrar({resultado:abre?'abriu':cancelado?(motivo||'perdida'):p.multi?'duas-maos':p.movido?'moveu':!p.alvo?'sem-alvo':dur>=1200?'demorou':'fora-do-alvo',
      viagem:Math.round(p.maxd||0),dur:Math.round(dur),x:Math.round(p.sx),y:Math.round(p.sy),alvo:!!p.alvo});
    if(abre)ativar(p.alvo);
  }
  mapaEl.addEventListener('pointerdown',ev=>{if(ev.button!==0)return;ev.preventDefault();mapaEl.setPointerCapture(ev.pointerId);pressionar('p:'+ev.pointerId,ev.clientX,ev.clientY);});
  mapaEl.addEventListener('pointermove',ev=>mover('p:'+ev.pointerId,ev.clientX,ev.clientY));
  mapaEl.addEventListener('pointerup',ev=>{soltar('p:'+ev.pointerId);if(mapaEl.hasPointerCapture(ev.pointerId))mapaEl.releasePointerCapture(ev.pointerId);});
  for(const type of ['pointercancel','lostpointercapture'])mapaEl.addEventListener(type,ev=>soltar('p:'+ev.pointerId,true));
  mapaEl.addEventListener('pointerleave',()=>{if(!pontos.size)limparHover();});
  mapaEl.addEventListener('focusin',ev=>{
    if(ev.target.matches('[data-node]')){const r=ev.target.querySelector('.hit').getBoundingClientRect();apontar(r.x+r.width/2,r.y+r.height/2);}
  });
  mapaEl.addEventListener('focusout',()=>{if(!pontos.size)limparHover();});
  mapaEl.addEventListener('click',ev=>{if(ev.detail===0)ativar(ev.target.closest(targets));});
  mapaEl.addEventListener('wheel',ev=>{
    if(ev.target.closest('.vista')&&!ev.ctrlKey)return;
    ev.preventDefault();atividade();limparHover();
    zoomVista(Math.exp(-clamp(ev.deltaY*(ev.deltaMode===1?16:1),-300,300)*.002),ev.clientX,ev.clientY);
  },{passive:false});
  document.addEventListener('keydown',ev=>{
    if(!aberto||ev.target.closest?.('input,textarea'))return;
    if(ev.key==='Escape'){ev.preventDefault();if(modo==='focus')trocarModo(ultimaVista);else fecharMapa();}
    else if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-node]')){ev.preventDefault();escolher(ev.target.dataset.node);}

  });
  window.addEventListener('blur',()=>{pontos.clear();maos.clear();gesto=null;graph.releaseAll();limparHover();});
  new ResizeObserver(()=>{if(aberto&&modo==='brain'){desenharGrafo();enquadrar();}}).observe(svg);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)graph.stop();else if(aberto&&modo==='brain')graph.start();});
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function reduzir(){graph.setMotion(!reduced.matches);mapaEl.querySelector('[data-action="motion"]').textContent=graph.motion?'Pausar':'Flutuar';}
  reduced.addEventListener('change',reduzir);reduzir();
  // Ownership includes the release that closes the dialog. No pinch falls through.
  window.jarvisBrainGestures={
    get active(){return aberto;},holding(id){return pontos.has('mao:'+id);},position(id){return maos.get(id);},
    hand({id,x,y,hoverX,hoverY,pinched,wasPinched=false,cancelled=false,motivo=''}){
      const anterior=maos.get(id),dedo=Number.isFinite(hoverX)&&Number.isFinite(hoverY);
      let dx=anterior?.dx||0,dy=anterior?.dy||0;
      if(pinched){if(!anterior?.pinched){const recente=anterior&&performance.now()-anterior.em<250;dx=dedo&&recente?anterior.x-x:0;dy=dedo&&recente?anterior.y-y:0;}x+=dx;y+=dy;}
      else if(anterior?.pinched){x=anterior.x;y=anterior.y;}
      else if(dedo){const recente=anterior&&performance.now()-anterior.em<250;x=recente?anterior.x+(hoverX-anterior.x)*.45:hoverX;y=recente?anterior.y+(hoverY-anterior.y)*.45:hoverY;}
      const alvo=alvoEm(x,y), r=mapaEl.getBoundingClientRect();
      const dentro=(aberto&&x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom)||!!window.jarvisConfig?.contem(x,y)||!!window.jarvisTeclado?.contem(x,y);
      const captura=dentro||(anterior?.dono&&(pinched||anterior.pinched))||
        (!!alvo?.matches('#hud-jv .btn, #hud-maos .btn, #jv-teclado-btn, .panel [data-panel-action]')&&(!pinched||!wasPinched));
      if(!captura){if(!pontos.size)limparHover();return false;}const pid='mao:'+id;
      if(cancelled)soltar(pid,true,motivo);else if(pinched&&!anterior?.pinched)pressionar(pid,x,y,true);else if(pinched)mover(pid,x,y);else if(anterior?.pinched)soltar(pid);else apontar(x,y);
      maos.set(id,{x,y,dx,dy,em:performance.now(),dono:pinched||dentro,pinched:pinched&&!cancelled});return true;
    },
    finishFrame(ids){for(const id of maos.keys())if(!ids.includes(id)){soltar('mao:'+id,true);maos.delete(id);}if(!ids.length&&!pontos.size)limparHover();}
  };
  // gdautomacao.ia: the Zé drives its own screen (jarvis-controle.js), with the
  // same functions and animations a hand or the mouse would trigger.
  const sem = t => String(t ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  const MODOS = { geral: 'brain', cerebro: 'brain', mapa: 'brain', brain: 'brain', trabalho: 'work', work: 'work', foco: 'focus', focus: 'focus' };
  // Opened by the Zé (or by voice): closes by itself 90 s after its last step,
  // like the voice opening. Opened by hand: stays until closed.
  const manter = () => { if (peloJarvis && aberto) fecharEm = Date.now() + 90000; };
  function garantirAberto() { if (!aberto) { abrirMapa(true); peloJarvis = true; } }
  function acharAlvo(alvo) {
    const q = sem(alvo);
    if (!q) return null;
    if (['center', 'centro', 'cerebro', 'ze', 'jarvis'].includes(q)) return { tipo: 'centro', id: 'center', nome: 'Zé' };
    for (const [id, a] of Object.entries(areas)) if (q === id || q === 'area:' + id || q === sem(a.title)) return { tipo: 'area', id, nome: a.title };
    if (objetos.has(alvo)) return { tipo: 'item', id: alvo, nome: objetos.get(alvo).rotulo };
    let parecido = null;
    for (const it of objetos.values()) {
      const n = sem(it.rotulo);
      if (n === q) return { tipo: 'item', id: it.id, nome: it.rotulo };
      if (!parecido && (n.includes(q) || sem(it.texto).includes(q))) parecido = { tipo: 'item', id: it.id, nome: it.rotulo };
    }
    return parecido;
  }
  function centrar(id) {
    const n = graph.nodes.get(id), r = svg.getBoundingClientRect();
    if (!n) return;
    camera.x = r.width / 2 - n.x * camera.s; camera.y = r.height / 2 - n.y * camera.s; aplicarCamera();
  }
  window.jarvisCerebro = {
    abrir() { garantirAberto(); manter(); return { aberto: true }; },
    fechar() { if (aberto) fecharMapa(); return { aberto: false }; },
    modo(m) {
      const alvo = MODOS[sem(m)];
      if (!alvo) throw new Error('modo desconhecido: ' + m + ' (geral, trabalho ou foco)');
      garantirAberto(); trocarModo(alvo); manter(); return { modo: sem(m) };
    },
    focar(alvo) {
      garantirAberto(); montarDados();
      const a = acharAlvo(alvo);
      if (!a) throw new Error('não achei "' + alvo + '" na tela');
      if (a.tipo === 'centro') { expandido = null; trocarModo('brain'); desenharGrafo(); enquadrar(); }
      else if (a.tipo === 'area') {
        if (modo !== 'brain') trocarModo('brain');
        expandido = a.id; desenharGrafo();
        if (!grupos[a.id].length) { filtro = a.id; trocarModo('work'); }
        else setTimeout(() => centrar('area:' + a.id), 60);
      } else escolher(a.id);
      manter(); return a;
    },
    localizar(alvo) {
      garantirAberto(); montarDados();
      const a = acharAlvo(alvo);
      if (!a || a.tipo !== 'item') throw new Error('não achei o item "' + alvo + '"');
      escolhido = a.id; acao('locate'); manter();
      setTimeout(() => centrar(a.id), 60);
      return a;
    },
    zoom(f) { garantirAberto(); zoomVista(clamp(Number(f) || 1.25, .3, 3)); manter(); return { zoom: Math.round((modo==='brain'?camera.s:leitura[modo]) * 100) }; },
    enquadrar() { garantirAberto(); ajustarVista(); manter(); return { zoom: Math.round((modo==='brain'?camera.s:leitura[modo]) * 100) }; },
    mover(dx, dy) { garantirAberto(); camera.x += Number(dx) || 0; camera.y += Number(dy) || 0; aplicarCamera(); manter(); return {}; },
    rolar(px) {
      const v = modo === 'work' ? workEl : modo === 'focus' ? focusEl : null;
      if (!aberto || !v) throw new Error('rolar só funciona no Trabalho ou no Foco');
      v.scrollBy({ top: Number(px) || 300, behavior: 'smooth' }); manter(); return {};
    },
    voltar() { garantirAberto(); trocarModo(ultimaVista); manter(); return { modo: ultimaVista }; },
    // The Foco board itself (not an item's detail): "mostra o meu foco".
    async mostrarFoco() {
      // The board stays until the user closes it (no 90 s auto-close): it is meant to be looked at.
      garantirAberto(); escolhido = null; focoGrupo = null; foco = await get("foco"); trocarModo('focus'); fecharEm = 0;
      return { modo: 'foco', atual: foco.atual?.titulo || null };
    },
    estado() {
      if (!aberto) montarDados();
      const nomeModo = { brain: 'cerebro', work: 'trabalho', focus: 'foco' }[modo];
      const it = escolhido ? objetos.get(escolhido) : null;
      return { aberto, modo: aberto ? nomeModo : null, zoom: aberto ? Math.round((modo==='brain'?camera.s:leitura[modo]) * 100) : null,
        foco: it ? { id: it.id, nome: it.rotulo, area: it.area } : null, area_expandida: expandido,
        areas: Object.fromEntries(Object.entries(areas).map(([id, a]) => [id, { titulo: a.title, total: (grupos[id] || []).length,
          itens: (grupos[id] || []).slice(0, 12).map(x => ({ id: x.id, nome: x.rotulo })) }])) };
    },
  };
  window.jarvisWorkspace = {
    toggle(){abrirMapa(false);}, open(){if(!aberto)abrirMapa(false);}, close(){if(aberto)fecharMapa();},
    get visible(){return aberto;}
  };
  window.addEventListener('resize',()=>{if(aberto)posicionarQuadro();});
  // A new colour theme redraws the graph with the new palette.
  window.addEventListener('jv-tema',()=>{desenhado='';desenhar();});
  function desenhar(){
    if(!aberto||pontos.size)return;
    const key=JSON.stringify([mapa,trabalho,decisao.sugestoes],(k,v)=>k==='ts'?undefined:v);
    if(key===desenhado)return;desenhado=key;montarDados();desenharGrafo();
    if(modo==='work'){const y=workEl.scrollTop;listaWork();workEl.scrollTop=y;}
    else if(modo==='focus'){const y=focusEl.scrollTop;focus();focusEl.scrollTop=y;}
  }

  // ---------- polling -----------------------------------------------------------
  let ultimoPedido = 0;
  function receberFoco(novo){
    // Do not replace a locked target or move the reading position under a hand.
    if(pontos.size||JSON.stringify(novo)===JSON.stringify(foco))return;
    foco=novo;
    if(aberto&&modo==='focus'&&!escolhido){const y=focusEl.scrollTop;focus();focusEl.scrollTop=y;}
  }
  async function rapido() {
    mostrarDecisao(await get("decisao"));
    presenca = await get("presenca"); status();
    const p = await get("mapa-abrir");
    if (p.pedido && p.pedido > ultimoPedido) {
      const novo = ultimoPedido !== 0 || Date.now() / 1000 - p.pedido < 10;
      ultimoPedido = p.pedido;
      if (novo) abrirMapa(true);
    }
    if (aberto && fecharEm && Date.now() > fecharEm) fecharMapa();
    if (aberto && modo === 'focus' && !escolhido && !pontos.size) {  // the board follows the voice too
      const novo = await get("foco");
      receberFoco(novo);
    }
  }
  async function lento() {
    mostrarEficiencia(await get("eficiencia"));
    const dados=await Promise.all([get("mapa"),get("trabalho"),get("foco")]);
    [mapa,trabalho]=dados;receberFoco(dados[2]);
    desenhar();
  }
  rapido(); setInterval(rapido, 700);
  lento(); setInterval(lento, 4000);
  if (new URLSearchParams(location.search).get("mapa") === "1") setTimeout(() => abrirMapa(false), 600);
})();
