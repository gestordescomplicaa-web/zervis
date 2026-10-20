// SPDX-License-Identifier: AGPL-3.0-or-later
// Local, dependency-free SVG graph. Springs encode only relationships supplied
// by Zé; the simulation never invents semantic links or calls a model.
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const el = (tag, attrs = {}) => {
    const element = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
    return element;
  };
  const COLORS = { root: '#8ff0e4', memoria: '#b5efdf', sessoes: '#bee9dc',
    automacoes: '#a7eddc', novo: '#efbe7c' };
  // barehands-jarvis: not node colours; jarvis-tema.js swaps all of these.
  const TONS = { meta: '#a8d8cf', fundo: '#0c1c2b', base: '#071115' };
  const ICONS = {
    root: 'M12 4c-3-3-7 0-6 3-4 0-4 6-1 7-1 4 3 7 7 5V4m0 0c3-3 7 0 6 3 4 0 4 6 1 7 1 4-3 7-7 5M8 8l4 2m4-2-4 2m-5 5 5-2m5 2-5-2',
    memoria: 'M4 4h6c2 0 2 2 2 2s0-2 2-2h6v15h-6c-2 0-2 2-2 2s0-2-2-2H4ZM12 6v15',
    sessoes: 'M4 8h16v12H4ZM12 8V4m-2 0h4M8 12v3m8-3v3m-8 2h8M1 12v5m22-5v5',
    automacoes: 'M5 12l5 5L20 6',
  };


  class JarvisGraph {
    constructor(world) {
      this.world = world; this.nodes = new Map(); this.edges = [];
      this.sizes = new Map(); this.size = 1.15; this.hovered = null; this.selected = null;
      this.motion = !matchMedia('(prefers-reduced-motion: reduce)').matches;
      this.visible = false; this.raf = 0; this.last = 0; this.tick = 0;
      this.observer = new ResizeObserver(() => this.updateLabels());
      this.observer.observe(world.ownerSVGElement);
    }
    setData(specs, links, reset = false) {
      this.stop();
      const old = reset ? new Map() : this.nodes;
      this.nodes = new Map(specs.map((s, i) => {
        const prior = old.get(s.id);
        return [s.id, { ...s, x: prior?.x ?? s.x, y: prior?.y ?? s.y,
          ax: prior?.ax ?? s.x, ay: prior?.ay ?? s.y, vx: 0, vy: 0, pin: false,
          r: s.radius * this.size * (this.sizes.get(s.id) || 1), phase: i * 2.39996 }];
      }));
      this.edges = links.filter(l => this.nodes.has(l.from) && this.nodes.has(l.to)).map(l => ({ ...l,
        a: this.nodes.get(l.from), b: this.nodes.get(l.to) }));
      this.world.replaceChildren();
      const defs = el('defs');
      for (const [name, color] of Object.entries(COLORS)) {
        const grad = el('radialGradient', { id: `jvg-${name}`, cx: '32%', cy: '25%', r: '78%' });
        for (const [offset, fill, opacity] of [['0%', '#ffffff', '.96'], ['16%', color, '.92'], ['48%', color, '.45'], ['100%', TONS.base, '1']]) {
          grad.append(el('stop', { offset, 'stop-color': fill, 'stop-opacity': opacity }));
        }
        defs.append(grad);
      }
      this.world.append(defs);
      const lines = el('g', { class: 'ligacoes', 'pointer-events': 'none' });
      for (const link of this.edges) {
        link.el = el('path', { fill: 'none', class: 'ligacao', stroke: COLORS[link.color] || COLORS.root,
          'stroke-width': link.origin ? .8 : 1.1, 'stroke-opacity': link.origin ? .18 : .38,
          ...(link.origin ? { 'stroke-dasharray': '3 5' } : {}) });
        lines.append(link.el);
      }
      this.world.append(lines);
      for (const n of this.nodes.values()) {
        const color = COLORS[n.color] || COLORS.root;
        n.el = el('g', { class: `no esfera ${n.kind || 'item'}`, 'data-node': n.id,
          style: 'color:' + color, role: 'button', tabindex: '0', 'aria-label': n.ariaLabel || n.title, 'aria-pressed': 'false' });
        n.halo = el('circle', { class: 'halo', fill: color, opacity: '.06', 'pointer-events': 'none' });
        n.hit = el('circle', { class: 'hit', fill: 'transparent', 'pointer-events': 'all' });
        n.ball = el('circle', { class: 'bola', fill: TONS.fundo, stroke: color,
          'stroke-opacity': '.85', 'stroke-width': '1.1', 'pointer-events': 'none' });
        n.ring = el('circle', { class: 'anel', fill: 'none', stroke: color, 'stroke-opacity': '.24', 'stroke-width': '.7', 'pointer-events': 'none' });
        n.label = el('text', { class: 'rotulo', 'text-anchor': 'middle', fill: color, 'pointer-events': 'none',
          'font-size': n.kind === 'root' ? 23 : n.kind === 'group' ? 18 : 13 });
        n.label.textContent = n.title.length > 27 ? n.title.slice(0, 26) + '…' : n.title;
        n.icon = el('path', { class: 'node-icon', d: ICONS[n.icon || n.color] || ICONS.root,
          fill: 'none', stroke: color, 'stroke-width': '1.6', 'stroke-linecap': 'round',
          'stroke-linejoin': 'round', 'pointer-events': 'none' });
        n.meta = el('text', { class: 'node-meta', fill: TONS.meta, 'pointer-events': 'none' });
        n.meta.textContent = n.subtitle || '';
        n.el.append(n.halo, n.hit, n.ball, n.ring, n.icon, n.label, n.meta);
        this.world.append(n.el); this.radius(n);
      }
      // Deterministic settling avoids a pile of overlapping points on first open.
      if (reset || !old.size) for (let i = 0; i < 65; i++) this.step(1, false);
      this.paint(); this.highlight(); this.updateLabels();
      if (this.visible) this.start();
    }
    radius(n) {
      n.r = n.radius * this.size * (this.sizes.get(n.id) || 1);
      n.ball.setAttribute('r', n.r); n.halo.setAttribute('r', n.r * 2.1);
      n.icon.setAttribute('transform', `translate(${-n.r * .48} ${-n.r * .48}) scale(${n.r * .04})`);
      n.icon.style.display = n.kind === 'item' ? 'none' : '';
      n.ring.setAttribute('r', n.r + 5); n.hit.setAttribute('r', Math.max(n.r + 11, 23));
      n.label.setAttribute('y', n.r + (n.kind === 'root' ? 30 : 24));
    }
    bounds() {
      const list = [...this.nodes.values()];
      if (!list.length) return { x: 0, y: 0, w: 1600, h: 900 };
      const x = Math.min(...list.map(n => n.x - n.r - 180));
      const y = Math.min(...list.map(n => n.y - n.r - 70));
      return { x, y, w: Math.max(...list.map(n => n.x + n.r + 180)) - x,
        h: Math.max(...list.map(n => n.y + n.r + 95)) - y };
    }
    updateLabels() {
      const scale = Math.max(.08, Math.abs(this.world.getScreenCTM()?.a || 1));
      for (const n of this.nodes.values()) {
        const hub = n.kind !== 'item', side = n.labelSide || (n.ax < 750 ? -1 : 1);
        const compact = scale < .25;
        const size = hub ? (n.kind === 'root' ? 17 : 15) : 12;
        const fs = clamp((compact ? hub ? 12 : 11 : size) / scale, 10, 100);
        const maxTitle = scale < .48 && !hub ? 17 : 27;
        n.label.textContent = n.title.length > maxTitle ? n.title.slice(0, maxTitle - 1) + '…' : n.title;
        n.label.setAttribute('font-size', fs);
        n.label.setAttribute('font-weight', hub ? 550 : 400);
        n.label.setAttribute('text-anchor', hub ? 'middle' : side < 0 ? 'end' : 'start');
        n.label.setAttribute('x', hub ? 0 : side * (n.r + 12 / scale));
        n.label.setAttribute('y', hub ? n.r + (compact ? 16 : 23) / scale : 4 / scale);
        n.meta.setAttribute('font-size', clamp((compact ? 9 : 11) / scale, 9, 80));
        n.meta.setAttribute('text-anchor', hub ? 'middle' : side < 0 ? 'end' : 'start');
        n.meta.setAttribute('x', hub ? 0 : side * (n.r + 12 / scale));
        n.meta.setAttribute('y', hub ? n.r + (compact ? 30 : 42) / scale : 22 / scale);
        n.meta.style.display = n.subtitle ? '' : 'none';
        n.hit.setAttribute('r', Math.max(n.r + 8, Math.min(200, 28 / scale)));

      }
    }
    resize(factor, id = null) {
      if (id) this.sizes.set(id, clamp((this.sizes.get(id) || 1) * factor, .6, 3.5));
      else this.size = clamp(this.size * factor, .65, 2.4);
      for (const n of this.nodes.values()) this.radius(n);
      this.updateLabels(); this.paint();
      return id ? this.sizes.get(id) : this.size;
    }
    setHighlight(hovered, selected = this.selected) {
      if (hovered === this.hovered && selected === this.selected) return;
      this.hovered = hovered; this.selected = selected; this.highlight();
    }
    highlight() {
      const id = this.hovered || this.selected, near = new Set(id ? [id] : []);
      for (const link of this.edges) if (link.from === id || link.to === id) {
        near.add(link.from); near.add(link.to);
      }
      for (const n of this.nodes.values()) {
        n.el.classList.toggle('apontado', n.id === this.hovered);
        n.el.classList.toggle('selecionado', n.id === this.selected);
        n.el.classList.toggle('afastado', !!id && !near.has(n.id));
        n.el.setAttribute('aria-pressed', String(n.id === this.selected));
      }
      for (const link of this.edges) {
        const active = link.from === id || link.to === id;
        link.el.setAttribute('stroke-opacity', id ? active ? .95 : .10 : link.origin ? .18 : .38);
        link.el.setAttribute('stroke-width', active ? 2.3 : link.origin ? .8 : 1.1);
      }
    }
    hold(id) { const n = this.nodes.get(id); if (n) { n.pin = true; n.vx = 0; n.vy = 0; } }
    move(id, x, y) {
      const n = this.nodes.get(id); if (!n) return;
      n.x = clamp(x, 40, 1560); n.y = clamp(y, 40, 860);
      n.ax = n.x; n.ay = n.y; n.pin = true; n.vx = 0; n.vy = 0; this.paint();
    }
    release(id) { const n = this.nodes.get(id); if (n) n.pin = false; }
    releaseAll() { for (const n of this.nodes.values()) n.pin = false; }
    step(dt, floating = true) {
      const list = [...this.nodes.values()];
      for (const n of list) {
        const strength = n.kind === 'root' ? .035 : n.kind === 'group' ? .012 : .007;
        const drift = floating ? 4 : 0;
        n.vx += (n.ax + Math.sin(this.tick * .012 + n.phase) * drift - n.x) * strength * dt;
        n.vy += (n.ay + Math.cos(this.tick * .009 + n.phase) * drift - n.y) * strength * dt;
      }
      for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
        const a = list[i], b = list[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        if (Math.abs(dx) + Math.abs(dy) < .001) { dx = .1; dy = .1; }
        const d = Math.hypot(dx, dy), gap = a.r + b.r + 36;
        const f = Math.min(8, 220 / Math.max(d * d, 1) + Math.max(0, gap - d) * .065) * dt;
        const fx = dx / d * f, fy = dy / d * f;
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
      }
      for (const l of this.edges) {
        if (l.origin) continue; // Semantic cross-links must not collapse the two clusters.
        const dx = l.b.x - l.a.x, dy = l.b.y - l.a.y, d = Math.hypot(dx, dy) || 1;
        const rest = Math.max(l.length || 115, l.a.r + l.b.r + 45);
        const f = (d - rest) * .009 * dt, fx = dx / d * f, fy = dy / d * f;
        l.a.vx += fx; l.a.vy += fy; l.b.vx -= fx; l.b.vy -= fy;
      }
      for (const n of list) {
        if (n.pin || n.id === this.hovered) { n.vx = 0; n.vy = 0; continue; }
        n.vx = clamp(n.vx * .78, -7, 7); n.vy = clamp(n.vy * .78, -7, 7);
        n.x = clamp(n.x + n.vx * dt, n.r + 25, 1575 - n.r);
        n.y = clamp(n.y + n.vy * dt, n.r + 25, 855 - n.r);
      }
    }
    paint() {
      for (const n of this.nodes.values()) n.el.setAttribute('transform', `translate(${n.x.toFixed(2)} ${n.y.toFixed(2)})`);
      for (const l of this.edges) {
        const dx = l.b.x - l.a.x, bend = dx * .5;
        l.el.setAttribute('d', `M${l.a.x} ${l.a.y} C${l.a.x + bend} ${l.a.y} ${l.b.x - bend} ${l.b.y} ${l.b.x} ${l.b.y}`);
      }
    }
    start() {
      this.visible = true;
      if (this.raf || !this.motion || document.hidden) return;
      this.world.dataset.motion = 'running'; this.last = 0;
      const frame = now => {
        this.raf = 0;
        if (!this.visible || !this.motion || document.hidden) return;
        if (!this.last || now - this.last >= 32) {
          const dt = this.last ? clamp((now - this.last) / 33.33, .2, 2) : 1;
          this.last = now; this.tick += dt; this.step(dt); this.paint();
        }
        this.raf = requestAnimationFrame(frame);
      };
      this.raf = requestAnimationFrame(frame);
    }
    stop() {
      if (this.raf) cancelAnimationFrame(this.raf);
      this.raf = 0; this.world.dataset.motion = 'paused';
    }
    close() { this.visible = false; this.stop(); this.releaseAll(); }
    setMotion(enabled) { this.motion = enabled; if (enabled && this.visible) this.start(); else this.stop(); }
  }
  window.JarvisGraph = JarvisGraph;
  JarvisGraph.CORES = COLORS; JarvisGraph.TONS = TONS;
})();
