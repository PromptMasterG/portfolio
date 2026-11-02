/* Optional enhancements. The site works without them. */
(() => {
  const d = document, r = d.documentElement, $ = (s, c = d) => [...c.querySelectorAll(s)];
  const run = f => { try { return f(); } catch (e) {} };
  const store = (k, v) => run(() => v === undefined ? localStorage.getItem(k) : localStorage.setItem(k, v));
  r.classList.replace('no-js', 'js');

  run(() => {
  const tb = $('#theme-toggle')[0], mq = matchMedia('(prefers-color-scheme: dark)');
  const dark = () => (r.dataset.theme || (mq.matches ? 'dark' : 'light')) === 'dark';
  const paint = () => tb && tb.setAttribute('aria-pressed', dark());
  if (store('theme')) r.dataset.theme = store('theme');
  paint();
  if (tb) tb.onclick = () => { const t = dark() ? 'light' : 'dark'; r.dataset.theme = t; store('theme', t); paint(); };
  });

  run(() => {
  const btns = $('[data-lens-btn]');
  const lens = (v, anim) => {
    r.dataset.lens = v;
    btns.forEach(b => b.setAttribute('aria-pressed', b.dataset.lensBtn === v));
    const k = v === 'creator' ? 'rc' : 're';
    const apply = () => {
      $('[data-sort]').forEach(c => [...c.children].sort((a, b) => a.dataset[k] - b.dataset[k]).forEach(x => c.append(x)));
      $('[data-fit]').forEach(x => x.classList.toggle('fit', x.dataset.fit.split(' ').includes(v)));
    };
    anim && d.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches ? d.startViewTransition(apply) : apply();
    if (anim) { const u = new URL(location); u.searchParams.set('for', v); history.replaceState(null, '', u); }
  };
  btns.forEach(b => b.onclick = () => lens(b.dataset.lensBtn, 1));
  if (btns.length) lens(new URLSearchParams(location.search).get('for') === 'creator' ? 'creator' : 'engineer');
  });

  run(() => {
  const zoom = $('a.zoom');
  if (zoom.length && d.createElement('dialog').showModal) {
    const dl = d.createElement('dialog');
    dl.className = 'lb';
    dl.setAttribute('aria-label', 'Larger view');
    dl.innerHTML = '<button type="button" class="lb-x">Close</button><img alt=""><p></p>';
    d.body.append(dl);
    const im = $('img', dl)[0], cap = $('p', dl)[0];
    zoom.forEach(a => a.onclick = e => {
      if (e.metaKey || e.ctrlKey) return;
      e.preventDefault();
      const s = $('img', a)[0];
      im.src = s.src; im.alt = s.alt;
      cap.textContent = a.closest('figure').textContent.trim();
      dl.showModal();
    });
    dl.onclick = e => { if (e.target === dl || e.target.className === 'lb-x') dl.close(); };
  }
  });

  const el = (t, a, p) => { const e = d.createElementNS('http://www.w3.org/2000/svg', t); for (const k in a) e.setAttribute(k, a[k]); if (p) p.append(e); return e; };
  const wrap = t => t.split(' ').reduce((o, w) => { const c = o.pop(); return (c + ' ' + w).trim().length > 15 && c ? [...o, c, w] : [...o, (c + ' ' + w).trim()]; }, ['']);
  let dn = 0;
  $('code.language-mermaid').forEach(box => run(() => {
    const n = {}, e = [], W = 112, G = 22, V = 40, pos = {};
    const re = /(\w+)(?:\[\(?([^\]\)]*)\)?\]|\(\[?([^\)\]]*)\]?\)|\{([^}]*)\})?|(-->|---|-\.->|==>)(?:\|([^|]*)\|)?/g;
    for (const l of box.textContent.split('\n')) {
      if (/^\s*(flowchart|graph|%%)/.test(l)) continue;
      let p, ar, lb;
      for (const m of l.matchAll(re)) {
        if (m[5]) { ar = 1; lb = m[6] || ''; continue; }
        const t = m[2] ?? m[3] ?? m[4];
        if (t !== undefined) n[m[1]] = t.trim(); else n[m[1]] = n[m[1]] || m[1];
        if (p && ar) e.push([p, m[1], lb]);
        p = m[1]; ar = 0;
      }
    }
    const ids = Object.keys(n), rk = {}, rows = [];
    ids.forEach(i => rk[i] = 0);
    ids.forEach(() => e.forEach(([a, b]) => { if (rk[b] <= rk[a] && rk[a] < ids.length) rk[b] = rk[a] + 1; }));
    ids.forEach(i => (rows[rk[i]] = rows[rk[i]] || []).push(i));
    rows.forEach((row, y) => {
      const avg = i => { const ps = e.filter(x => x[1] === i).map(x => rows[y - 1].indexOf(x[0])); return ps.length ? Math.min(...ps) : 0; };
      if (y) row.sort((a, b) => avg(a) - avg(b));
    });
    const wide = Math.max(...rows.map(x => x.length)) * (W + G) - G;
    const hs = rows.map(row => Math.max(...row.map(i => wrap(n[i]).length * 15 + 16)));
    const svg = el('svg', { class: 'dg', role: 'img', viewBox: `0 0 ${wide + 12} ${hs.reduce((s, h) => s + h + V, 12) - V}`, width: wide + 12, 'aria-label': 'Diagram. ' + e.map(x => n[x[0]] + ' leads to ' + n[x[1]]).join('. ') + '.' });
    const mid = 'dga' + ++dn, mk = el('marker', { id: mid, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto' }, el('defs', {}, svg));
    el('path', { d: 'M0 0L8 4L0 8z', class: 'dg-a' }, mk);
    let top = 6;
    rows.forEach((row, y) => {
      const x0 = 6 + (wide - (row.length * (W + G) - G)) / 2;
      row.forEach((i, c) => pos[i] = { x: x0 + c * (W + G) + W / 2, t: top, b: top + hs[y] });
      top += hs[y] + V;
    });
    e.forEach(([a, b, lb]) => {
      const A = pos[a], B = pos[b], k = (B.t - A.b) / 2;
      el('path', { class: 'dg-e', d: `M${A.x} ${A.b}C${A.x} ${A.b + k} ${B.x} ${B.t - k} ${B.x} ${B.t}`, 'marker-end': 'url(#' + mid + ')' }, svg);
      if (lb) el('text', { class: 'dg-l', x: (A.x + B.x) / 2, y: (A.b + B.t) / 2, 'text-anchor': 'middle' }, svg).textContent = lb;
    });
    ids.forEach(i => {
      const P = pos[i], ls = wrap(n[i]), h = P.b - P.t, t = el('text', { class: 'dg-t', 'text-anchor': 'middle' });
      el('rect', { class: 'dg-n', x: P.x - W / 2, y: P.t, width: W, height: h, rx: 6 }, svg);
      svg.append(t);
      ls.forEach((s, j) => el('tspan', { x: P.x, y: P.t + h / 2 + (j - (ls.length - 1) / 2) * 15 + 4 }, t).textContent = s);
    });
    const fig = d.createElement('figure');
    fig.className = 'diagram';
    fig.append(svg);
    box.parentNode.replaceWith(fig);
  }));
})();
