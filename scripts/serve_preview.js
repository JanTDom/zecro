#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const PORT = process.env.PORT || 3000;

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.typ': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8'
};

const server = http.createServer((req, res) => {
  let reqPath = decodeURIComponent(req.url.split('?')[0]);
  
  if (reqPath === '/' || reqPath === '/index.html') {
    // Generate an interactive portal listing all newspaper templates and tools
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Newspaper Layout Suite — Editorial Workbench</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,400&family=Libre+Franklin:wght@400;600;800&family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f8f6f0;
      --paper: #ffffff;
      --ink: #111111;
      --border: #222222;
      --accent: #990000;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--ink);
      font-family: 'Newsreader', serif;
      padding: 40px 20px;
      line-height: 1.5;
    }
    .container {
      max-width: 1100px;
      margin: 0 auto;
      background: var(--paper);
      border: 2px solid var(--border);
      padding: 40px 50px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.06);
    }
    header {
      text-align: center;
      border-bottom: 3px double var(--border);
      padding-bottom: 25px;
      margin-bottom: 30px;
    }
    .motto {
      font-family: 'Libre Franklin', sans-serif;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.25em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 8px;
    }
    h1 {
      font-family: 'Playfair Display', serif;
      font-size: 48px;
      font-weight: 900;
      letter-spacing: -0.5px;
      margin-bottom: 10px;
    }
    .subtitle {
      font-style: italic;
      font-size: 19px;
      color: #444;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 30px;
      margin-top: 30px;
    }
    .card {
      border: 1px solid var(--border);
      padding: 25px;
      background: #fafaf8;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .card:hover {
      transform: translateY(-3px);
      box-shadow: 0 6px 16px rgba(0,0,0,0.08);
    }
    .badge {
      align-self: flex-start;
      font-family: 'Libre Franklin', sans-serif;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      padding: 3px 8px;
      background: var(--ink);
      color: #fff;
      margin-bottom: 15px;
    }
    .card h2 {
      font-family: 'Playfair Display', serif;
      font-size: 24px;
      margin-bottom: 12px;
    }
    .card p {
      font-size: 15px;
      color: #333;
      margin-bottom: 20px;
    }
    .btn {
      display: inline-block;
      text-align: center;
      padding: 10px 18px;
      background: var(--border);
      color: #fff;
      text-decoration: none;
      font-family: 'Libre Franklin', sans-serif;
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      transition: background 0.15s;
    }
    .btn:hover {
      background: var(--accent);
    }
    .meta-bar {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #ccc;
      display: flex;
      justify-content: space-between;
      font-family: 'Libre Franklin', sans-serif;
      font-size: 12px;
      color: #666;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="motto">Professional Editorial Architecture & Publishing</div>
      <h1>The Editorial Workbench</h1>
      <div class="subtitle">Select a format to preview or inspect layout mechanics</div>
    </header>

    <div class="grid">
      <div class="card">
        <div>
          <span class="badge">Classic Broadsheet</span>
          <h2>Broadsheet 6-Column</h2>
          <p>Full-size classic 375×580mm layout. Skyline banner, masthead, ear boxes, 3-column lead article, secondary reports, and financial sidebar.</p>
        </div>
        <a href="/templates/broadsheet/" class="btn">View Broadsheet Layout →</a>
      </div>

      <div class="card">
        <div>
          <span class="badge" style="background:#990000;">Modern Tabloid</span>
          <h2>Tabloid / Compact</h2>
          <p>Punchy 280×430mm 4-column layout. Dominant hammer headline, photo placement, deck teasers, and opinion columns.</p>
        </div>
        <a href="/templates/tabloid/" class="btn">View Tabloid Layout →</a>
      </div>

      <div class="card">
        <div>
          <span class="badge" style="background:#004488;">European Berliner</span>
          <h2>Berliner Spread</h2>
          <p>Refined 315×470mm 5-column layout. Balanced proportions, elegant serif typography, culture features, and pull quotes.</p>
        </div>
        <a href="/templates/berliner/" class="btn">View Berliner Layout →</a>
      </div>
    </div>

    <div class="meta-bar">
      <span>Antigravity Newspaper Publishing Suite</span>
      <span>Node.js / CSS Paged Media / Typst / InDesign ExtendScript</span>
    </div>
  </div>
</body>
</html>`);
    return;
  }

  let filePath = path.join(ROOT_DIR, reqPath);
  
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }

  if (!fs.existsSync(filePath)) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('404 Not Found: ' + reqPath);
    return;
  }

  const ext = path.extname(filePath);
  const mimeType = MIME_TYPES[ext] || 'application/octet-stream';

  fs.readFile(filePath, (err, content) => {
    if (err) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('Error loading file: ' + err.message);
    } else {
      res.writeHead(200, { 'Content-Type': mimeType });
      res.end(content);
    }
  });
});

server.listen(PORT, () => {
  console.log(`📰 Newspaper Layout Preview Server running at http://localhost:${PORT}`);
});
