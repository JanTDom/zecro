#!/usr/bin/env node
/**
 * Newspaper Layout Scaffolding Utility
 * Generates ready-to-edit newspaper editions with customized masthead, sections, and grids.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

const argv = process.argv.slice(2);
const params = {};

for (let i = 0; i < argv.length; i++) {
  const arg = argv[i];
  if (arg.startsWith('--')) {
    if (arg.includes('=')) {
      const [k, v] = arg.replace(/^--/, '').split('=');
      params[k] = v;
    } else {
      const k = arg.replace(/^--/, '');
      const nextArg = argv[i + 1];
      if (nextArg && !nextArg.startsWith('--')) {
        params[k] = nextArg;
        i++;
      } else {
        params[k] = true;
      }
    }
  }
}

const format = params.format || 'broadsheet';
const title = params.title || 'The Daily Chronicle';
const motto = params.motto || 'The Voice of Independent Journalism';
const edition = params.edition || 'Final Morning Edition';
const date = params.date || 'Thursday, October 15, 2026';
const price = params.price || '$2.50';
const outputDir = params.out ? path.resolve(params.out) : path.join(ROOT_DIR, 'editions', `${format}-${Date.now()}`);

console.log(`\n📰 Scaffolding New Newspaper Edition:`);
console.log(` • Title:   ${title}`);
console.log(` • Format:  ${format.toUpperCase()}`);
console.log(` • Edition: ${edition}`);
console.log(` • Output:  ${outputDir}\n`);

fs.mkdirSync(outputDir, { recursive: true });

const templateSource = path.join(ROOT_DIR, 'templates', format);
if (fs.existsSync(templateSource)) {
  const files = fs.readdirSync(templateSource);
  for (const file of files) {
    let content = fs.readFileSync(path.join(templateSource, file), 'utf8');
    content = content.replace(/THE DAILY CHRONICLE/g, title.toUpperCase())
                     .replace(/The Daily Chronicle/g, title)
                     .replace(/The Voice of Independent Journalism/g, motto)
                     .replace(/Morning Edition/g, edition)
                     .replace(/Thursday, October 15, 2026/g, date)
                     .replace(/\$2\.50/g, price);
    fs.writeFileSync(path.join(outputDir, file), content, 'utf8');
  }
  console.log(`✅ Successfully scaffolded edition at: ${outputDir}`);
  console.log(`👉 To preview: open ${path.join(outputDir, 'index.html')} in browser or run 'npm run dev'`);
} else {
  console.error(`❌ Template format '${format}' not found in templates/ directory.`);
  process.exit(1);
}
