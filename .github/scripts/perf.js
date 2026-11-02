// Lighthouse CI against the built site, mobile profile, thresholds from the brief.
//   node .github/scripts/perf.js _site [/portfolio]
// Set CHROME_PATH for a specific browser and LHCI_BIN for a local lhci binary.
// The config is written to a temporary folder at run time, so no local address is committed.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { serve } = require('./serve');

const siteDir = path.resolve(process.argv[2] || '_site');
const prefix = process.argv[3] || '/portfolio';
const PAGES = ['', 'work/samara/', 'work/ai-studio-tool/'];
const MIN = 0.95;

(async () => {
  const { url, close } = await serve(siteDir, prefix);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'lhci-'));
  const config = {
    ci: {
      collect: { url: PAGES.map((p) => url + p), numberOfRuns: 3, settings: { chromeFlags: '--no-sandbox --headless=new' } },
      assert: { assertions: Object.fromEntries(['performance', 'accessibility', 'best-practices', 'seo'].map((c) => ['categories:' + c, ['error', { minScore: MIN }]])) },
      upload: { target: 'filesystem', outputDir: path.join(tmp, 'reports') },
    },
  };
  const configPath = path.join(tmp, 'lighthouserc.json');
  fs.writeFileSync(configPath, JSON.stringify(config));
  const [cmd, ...pre] = process.env.LHCI_BIN ? [process.env.LHCI_BIN] : ['npx', '--yes', '@lhci/cli@0.15.1'];
  const child = spawn(cmd, [...pre, 'autorun', '--config=' + configPath], { stdio: 'inherit', env: process.env, cwd: tmp });
  const code = await new Promise((resolve) => child.on('exit', resolve));
  // Print the median scores that were actually measured.
  const dir = path.join(tmp, 'reports');
  if (fs.existsSync(dir)) {
    const rows = {};
    for (const f of fs.readdirSync(dir).filter((n) => /\.report\.json$/.test(n))) {
      const lhr = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
      const key = lhr.finalUrl.replace(/^https?:\/\/[^/]+/, '');
      if (!rows[key]) {
        for (const cat of Object.values(lhr.categories)) {
          for (const ref of cat.auditRefs) {
            const a = lhr.audits[ref.id];
            if (a.score !== null && a.score < 1 && ref.weight > 0) console.log(`NOTE ${key} [${cat.id}] ${ref.id} scored ${a.score}: ${a.title}${a.displayValue ? ' (' + a.displayValue + ')' : ''}`);
          }
        }
      }
      (rows[key] = rows[key] || []).push(Object.fromEntries(Object.entries(lhr.categories).map(([k, v]) => [k, Math.round(v.score * 100)])));
    }
    for (const [key, runs] of Object.entries(rows)) {
      const med = (k) => runs.map((r) => r[k]).sort((a, b) => a - b)[Math.floor(runs.length / 2)];
      console.log(`MEDIAN ${key}  performance ${med('performance')}  accessibility ${med('accessibility')}  best-practices ${med('best-practices')}  seo ${med('seo')}  (${runs.length} runs)`);
    }
  }
  await close();
  if (process.env.PERF_KEEP) console.log('reports kept in ' + tmp); else fs.rmSync(tmp, { recursive: true, force: true });
  process.exit(code || 0);
})().catch((e) => { console.error(e); process.exit(2); });
