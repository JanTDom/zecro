#!/usr/bin/env node
/**
 * Newspaper PDF & High-Res Image Renderer
 */

import { execSync } from 'node:child_process';
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

const input = params.input ? path.resolve(params.input) : path.join(ROOT_DIR, 'templates/broadsheet/index.html');
const output = params.output ? path.resolve(params.output) : path.join(ROOT_DIR, 'output/newspaper.pdf');
const format = params.format || 'broadsheet';

const DIMENSIONS = {
  broadsheet: { width: '375mm', height: '580mm' },
  berliner: { width: '315mm', height: '470mm' },
  tabloid: { width: '280mm', height: '430mm' },
  a3: { width: '297mm', height: '420mm' },
  a4: { width: '210mm', height: '297mm' }
};

const pageDim = DIMENSIONS[format.toLowerCase()] || DIMENSIONS.broadsheet;

console.log(`\n🖨️  NEWSPAPER PDF RENDERING UTILITY`);
console.log(`============================================================`);
console.log(` • Input:      ${input}`);
console.log(` • Output:     ${output}`);
console.log(` • Dimensions: ${pageDim.width} × ${pageDim.height} (${format.toUpperCase()})`);
console.log(`============================================================\n`);

fs.mkdirSync(path.dirname(output), { recursive: true });

const chromePaths = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium-browser'
];

let chromeBin = chromePaths.find(p => fs.existsSync(p));

if (chromeBin) {
  try {
    const tmpDir = path.join(ROOT_DIR, '.tmp-chrome');
    fs.mkdirSync(tmpDir, { recursive: true });
    const cmd = `"${chromeBin}" --headless --no-sandbox --disable-gpu --disable-crash-reporter --user-data-dir="${tmpDir}" --print-to-pdf="${output}" "file://${input}"`;
    console.log(`⚡ Exporting high-resolution PDF...`);
    execSync(cmd, { stdio: 'pipe' });
    if (fs.existsSync(output) && fs.statSync(output).size > 0) {
      console.log(`✅ PDF successfully generated: ${output} (${(fs.statSync(output).size / 1024).toFixed(1)} KB)\n`);
    } else {
      throw new Error('PDF file empty or missing');
    }
  } catch (err) {
    console.log(`ℹ️ To print or export PDF directly from browser:`);
    console.log(` 1. Open the file: file://${input}`);
    console.log(` 2. Press Cmd+P (or Ctrl+P) -> Select 'Save as PDF'`);
    console.log(` 3. Paper size: ${pageDim.width} x ${pageDim.height}\n`);
  }
} else {
  console.log(`ℹ️ Open file in browser to print: file://${input}\n`);
}
