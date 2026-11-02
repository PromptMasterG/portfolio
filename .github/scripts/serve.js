// Tiny static server for the built site, mounted under the site's base path so links resolve as they will on Pages.
// Usage as a module: const {serve} = require('./serve'); const {url, close} = await serve('_site', '/portfolio');
const http = require('http');
const fs = require('fs');
const path = require('path');

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.png': 'image/png', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.json': 'application/json',
};

function serve(root, prefix = '/portfolio', port = 0) {
  const base = path.resolve(root);
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://host').pathname);
    let rel = pathname === prefix ? '/' : pathname.startsWith(prefix + '/') ? pathname.slice(prefix.length) : null;
    let file = rel === null ? null : path.join(base, rel);
    if (file && file.startsWith(base) && fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
    if (!file || !file.startsWith(base) || !fs.existsSync(file)) {
      const missing = path.join(base, '404.html');
      res.writeHead(404, { 'content-type': TYPES['.html'] });
      res.end(fs.existsSync(missing) ? fs.readFileSync(missing) : 'Not found');
      return;
    }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => {
    const address = server.address();
    resolve({ url: 'http://127.0.0.1:' + address.port + prefix + '/', origin: 'http://127.0.0.1:' + address.port, close: () => new Promise((r) => server.close(r)) });
  }));
}

module.exports = { serve };

if (require.main === module) {
  const [dir = '_site', prefix = '/portfolio', port = '0'] = process.argv.slice(2);
  serve(dir, prefix, Number(port)).then(({ url }) => console.log('Serving ' + dir + ' at ' + url));
}
