// Accessibility and behaviour checks on the built site.
//   NODE_PATH=<tools>/node_modules node .github/scripts/a11y.js _site [/portfolio]
// Needs playwright-core and @axe-core/playwright. Set CHROME_PATH to use a specific browser.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');
const { AxeBuilder } = require('@axe-core/playwright');
const { serve } = require('./serve');

const siteDir = path.resolve(process.argv[2] || '_site');
const prefix = process.argv[3] || '/portfolio';
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];
const failures = [];
const fail = (msg) => { failures.push(msg); console.log('FAIL  ' + msg); };
const ok = (msg) => console.log('ok    ' + msg);

function listPages(dir, rel = '') {
  return fs.readdirSync(path.join(dir, rel), { withFileTypes: true }).flatMap((e) => {
    const r = path.join(rel, e.name);
    if (e.isDirectory()) return listPages(dir, r);
    return e.name.endsWith('.html') ? [r] : [];
  });
}
const urlFor = (rel) => rel === 'index.html' ? '' : rel.endsWith('/index.html') ? rel.slice(0, -'index.html'.length) : rel;

async function launch() {
  const base = { args: ['--no-sandbox'] };
  if (process.env.CHROME_PATH) return chromium.launch({ ...base, executablePath: process.env.CHROME_PATH });
  try { return await chromium.launch({ ...base, channel: 'chrome' }); } catch (e) { return chromium.launch(base); }
}

async function axePass(browser, url, label, opts) {
  const ctx = await browser.newContext(opts.context);
  const page = await ctx.newPage();
  const external = [], errors = [];
  page.on('request', (r) => { if (!r.url().startsWith(url.split('/').slice(0, 3).join('/')) && !r.url().startsWith('data:')) external.push(r.url()); });
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(url, { waitUntil: 'networkidle' });
  if (opts.scroll) {
    await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 80)); } });
    await page.waitForTimeout(900);
    await page.evaluate(() => window.scrollTo(0, 0));
  }
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  for (const v of results.violations) {
    fail(`${label}: axe ${v.id} (${v.impact}): ${v.help} -> ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
  }
  if (!results.violations.length) ok(`${label}: axe clean (${results.passes.length} rules passed)`);
  if (external.length) fail(`${label}: third-party requests: ${[...new Set(external)].join(', ')}`);
  if (errors.length) fail(`${label}: console errors: ${errors.join(' | ')}`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 0) fail(`${label}: horizontal scroll of ${overflow}px`);
  await ctx.close();
}

async function behaviour(browser, origin) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: 'light', reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  const home = origin + prefix + '/';

  // Skip link: first Tab lands on it, Enter moves focus into main.
  await page.goto(home, { waitUntil: 'networkidle' });
  await page.keyboard.press('Tab');
  const first = await page.evaluate(() => document.activeElement.textContent.trim());
  first === 'Skip to content' ? ok('skip link is the first tab stop') : fail('first tab stop is "' + first + '"');
  await page.keyboard.press('Enter');
  (await page.evaluate(() => document.activeElement.id)) === 'main' ? ok('skip link moves focus to main') : fail('skip link does not move focus to main');

  // Theme toggle by keyboard.
  const before = await page.evaluate(() => document.documentElement.dataset.theme || 'auto');
  await page.focus('#theme-toggle');
  await page.keyboard.press('Enter');
  const after = await page.evaluate(() => [document.documentElement.dataset.theme, document.querySelector('#theme-toggle').getAttribute('aria-pressed')]);
  after[0] === 'dark' && after[1] === 'true' ? ok(`theme toggle works by keyboard (${before} -> dark)`) : fail('theme toggle did not switch: ' + after);
  await page.keyboard.press('Space');
  (await page.evaluate(() => document.documentElement.dataset.theme)) === 'light' ? ok('theme toggle switches back with Space') : fail('theme toggle did not switch back');

  // Lens toggle: reorders real nodes, updates pressed state and the address.
  await page.focus('[data-lens-btn="creator"]');
  await page.keyboard.press('Enter');
  const lens = await page.evaluate(() => ({
    pressed: document.querySelector('[data-lens-btn="creator"]').getAttribute('aria-pressed'),
    other: document.querySelector('[data-lens-btn="engineer"]').getAttribute('aria-pressed'),
    firstCard: document.querySelector('.rows li h3').textContent.trim(),
    firstProof: document.querySelector('.proof-list li .stat').textContent.trim(),
    url: location.search,
  }));
  lens.pressed === 'true' && lens.other === 'false' && lens.url === '?for=creator' && lens.firstCard === 'AI Studio Tool'
    ? ok('lens toggle reorders cards and proof for creators by keyboard (' + lens.firstCard + ', ' + lens.firstProof + ')')
    : fail('lens toggle misbehaved: ' + JSON.stringify(lens));
  await page.goto(home + '?for=creator', { waitUntil: 'networkidle' });
  (await page.evaluate(() => document.querySelector('.rows li h3').textContent.trim())) === 'AI Studio Tool'
    ? ok('?for=creator is honoured on load') : fail('?for=creator not honoured on load');

  // Lightbox: Enter opens, Escape closes, focus returns to the link.
  await page.goto(origin + prefix + '/work/samara/', { waitUntil: 'networkidle' });
  const link = page.locator('a.zoom').first();
  await link.focus();
  await page.keyboard.press('Enter');
  (await page.evaluate(() => !!document.querySelector('dialog.lb[open]'))) ? ok('lightbox opens from the keyboard') : fail('lightbox did not open');
  const named = await page.evaluate(() => document.querySelector('dialog.lb img').alt.length > 10);
  named ? ok('lightbox image keeps its alt text') : fail('lightbox image lost its alt text');
  await page.keyboard.press('Escape');
  (await page.evaluate(() => !document.querySelector('dialog.lb[open]'))) ? ok('Escape closes the lightbox') : fail('Escape did not close the lightbox');
  const back = await page.evaluate(() => document.activeElement.classList.contains('zoom'));
  back ? ok('focus returns to the screenshot link') : fail('focus did not return to the screenshot link');

  // Diagram renders to an accessible image on a case study.
  const dg = await page.evaluate(() => { const s = document.querySelector('svg.dg'); return s && { role: s.getAttribute('role'), label: s.getAttribute('aria-label').length, nodes: s.querySelectorAll('rect').length, pre: !!document.querySelector('code.language-mermaid') }; });
  dg && dg.role === 'img' && dg.label > 40 && dg.nodes >= 6 && !dg.pre ? ok('diagram renders with an accessible name (' + dg.nodes + ' nodes)') : fail('diagram did not render: ' + JSON.stringify(dg));
  await ctx.close();

  // Without JavaScript the page still carries its content and the fallback links.
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const p2 = await noJs.newPage();
  await p2.goto(home, { waitUntil: 'load' });
  const lensHidden = await p2.evaluate(() => getComputedStyle(document.querySelector('.lens')).display === 'none');
  const hasLinks = await p2.evaluate(() => !!document.querySelector('a[href$="/for/ai-engineer/"]') && !!document.querySelector('a[href$="/for/ai-content-creator/"]'));
  lensHidden && hasLinks ? ok('without JavaScript the lens is hidden and the role pages are linked') : fail('no-JavaScript fallback is wrong');
  await noJs.close();
}

(async () => {
  const { origin, close } = await serve(siteDir, prefix);
  const browser = await launch();
  const pages = listPages(siteDir).sort();
  for (const rel of pages) {
    const url = origin + prefix + '/' + urlFor(rel);
    for (const scheme of ['light', 'dark']) {
      await axePass(browser, url, `${rel} [${scheme}, desktop]`, { context: { viewport: { width: 1280, height: 800 }, colorScheme: scheme, reducedMotion: 'reduce' } });
    }
    await axePass(browser, url, `${rel} [light, phone]`, { context: { viewport: { width: 390, height: 844 }, colorScheme: 'light', reducedMotion: 'reduce', isMobile: true, hasTouch: true } });
  }
  for (const rel of ['index.html', 'work/samara/index.html']) {
    await axePass(browser, origin + prefix + '/' + urlFor(rel), `${rel} [dark, motion on, scrolled]`, { scroll: true, context: { viewport: { width: 1280, height: 800 }, colorScheme: 'dark', reducedMotion: 'no-preference' } });
  }
  await behaviour(browser, origin);
  await browser.close();
  await close();
  console.log(failures.length ? `\n${failures.length} accessibility or behaviour problem(s).` : '\nAccessibility and behaviour checks passed.');
  process.exit(failures.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
