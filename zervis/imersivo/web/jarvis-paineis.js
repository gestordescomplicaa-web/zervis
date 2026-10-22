// SPDX-License-Identifier: AGPL-3.0-or-later
// One set of controls for every folder/note, including future manifest orbs.
(function () {
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const item=el=>window.jarvisItemDe?.(el?.closest('.panel'));
  function constrain(c){
    const w=c.el.offsetWidth*c.scale,h=c.el.offsetHeight*c.scale;
    c.x=clamp(c.x,w/2+12,innerWidth-w/2-12);
    c.y=clamp(c.y,h/2+12,innerHeight-h/2-12);
  }
  function scale(c,value){
    c.scale=clamp(value,.85,2);
    // Reflow the frame at large sizes: close/zoom stay on screen, text grows.
    c.el.style.width=Math.min(c.type==='browser'?560:845,(innerWidth-24)/c.scale)+'px';
    c.el.style.height=Math.min(c.type==='browser'?720:756,(innerHeight-24)/c.scale)+'px';
    constrain(c);scroll(c,0);
  }
  function scroll(c,dy){
    c.sTarget=null;
    c.scrollY=clamp((c.scrollY||0)+dy,0,Math.max(0,c.body.offsetHeight-c.body.parentElement.clientHeight+40));
    c.body.style.transform=`translateY(${-c.scrollY}px)`;
  }
  function prepare(c){c.anim=null;c.inS=1;c.rx=c.ry=c.rz=0;c.el.style.opacity="";}
  function action(button){
    const c=item(button);if(!c||c.grabbedBy.length||c.anim?.k==='out')return;
    prepare(c);const a=button.dataset.panelAction;
    if(a==='close')window.jarvisPanelActions.close(c);
    else scale(c,a==='fit'?1:c.scale*(a==='larger'?1.2:1/1.2));
  }
  function attach(c){
    const bar=c.el.querySelector('.bar');
    const controls=document.createElement('div');controls.className='panel-tools';
    controls.innerHTML='<button data-panel-action="smaller" aria-label="Reduzir aba">−</button>'+
      '<button data-panel-action="fit" aria-label="Ajustar aba">Ajustar</button>'+
      '<button data-panel-action="larger" aria-label="Ampliar aba">+</button>'+
      '<button data-panel-action="close" aria-label="Fechar aba">×</button>';
    bar.append(controls);bar.title='Segure o título para mover · duas mãos ampliam';
    const hint=document.createElement('small');hint.className='panel-hint';
    hint.textContent='Título move · conteúdo rola · duas mãos ampliam';bar.append(hint);
    c.el.setAttribute('aria-label',c.def.title||'Notas');
    scale(c,1);
    // Offset new panes so their title bars remain distinguishable.
    const count=[...document.querySelectorAll('.panel')].filter(el=>el!==c.el&&window.jarvisItemDe?.(el)?.anim?.k!=='out').length;
    c.x-=Math.min(count,5)*44;c.y+=Math.min(count,5)*36;constrain(c);
  }
  let drag=null;
  document.addEventListener('pointerdown',ev=>{
    const c=item(ev.target);if(!c||c.grabbedBy.length||ev.button!==0||!ev.target.closest('.bar')||ev.target.closest('button'))return;
    ev.preventDefault();c.flying=false;prepare(c);c.el.parentElement.append(c.el);
    drag={c,id:ev.pointerId,x:ev.clientX,y:ev.clientY};c.el.setPointerCapture(ev.pointerId);
  });
  document.addEventListener('pointermove',ev=>{
    if(!drag||drag.id!==ev.pointerId)return;
    if(drag.c.grabbedBy.length){release(ev);return;}
    drag.c.x+=ev.clientX-drag.x;drag.c.y+=ev.clientY-drag.y;
    drag.x=ev.clientX;drag.y=ev.clientY;constrain(drag.c);
  });
  function release(ev){if(drag&&drag.id===ev.pointerId){const c=drag.c;drag=null;if(c.el.hasPointerCapture(ev.pointerId))c.el.releasePointerCapture(ev.pointerId);}}
  for(const type of ['pointerup','pointercancel','lostpointercapture'])document.addEventListener(type,release);
  window.addEventListener('blur',()=>{drag=null;});
  document.addEventListener('click',ev=>{
    const b=ev.target.closest('[data-panel-action]');if(b){action(b);return;}
    const row=ev.target.closest('.brow'),c=item(row);
    if(c){const r=row.getBoundingClientRect();window.jarvisPanelActions.row(c,{x:r.left+r.width/2,y:r.top+r.height/2});}
  });
  document.addEventListener('keydown',ev=>{
    if(!ev.target.matches('.brow')||!['Enter',' '].includes(ev.key))return;
    ev.preventDefault();ev.target.click();
  });
  document.addEventListener('wheel',ev=>{
    const c=item(ev.target);if(!c||c.grabbedBy.length||c.anim?.k==='out')return;
    ev.preventDefault();const dy=ev.deltaY*(ev.deltaMode===1?16:ev.deltaMode===2?innerHeight:1);
    if(ev.ctrlKey)scale(c,c.scale*Math.exp(-clamp(dy,-300,300)*.002));
    else scroll(c,dy/c.scale);
  },{passive:false});
  window.addEventListener('resize',()=>document.querySelectorAll('.panel').forEach(el=>{const c=item(el);if(c)scale(c,c.scale);}));
  window.jarvisPanels={attach,action,scale,scroll,constrain,prepare};
})();
