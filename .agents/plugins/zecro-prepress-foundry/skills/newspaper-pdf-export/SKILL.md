---
name: newspaper-pdf-export
description: >-
  Headless browser and CLI PDF compilation engine for generating high-resolution, print-ready newspaper PDFs (Broadsheet, Tabloid, Berliner, A2, A3, A4) with crop marks, bleeds, exact DPI (300 DPI), and visual inspection snapshots. Use this skill when exporting HTML/CSS layouts or Typst files to publication-ready PDF or high-res image previews.
---

# Newspaper PDF & Print Export Skill

This skill handles precise PDF rendering, print production standards, DPI scaling, and visual validation of newspaper layouts.

## Standard Newspaper Page Sizes

| Name | Dimensions (mm) | Dimensions (pts) | Aspect Ratio | Standard Columns |
|---|---|---|---|---|
| **Broadsheet (Metric)** | 375 × 580 mm | 1063 × 1644 pt | ~1 : 1.55 | 6 columns |
| **Broadsheet (US)** | 15.0 × 22.75 in | 1080 × 1638 pt | ~1 : 1.52 | 6 columns |
| **Berliner** | 315 × 470 mm | 893 × 1332 pt | ~1 : 1.49 | 5 columns |
| **Tabloid / Compact** | 280 × 430 mm | 794 × 1219 pt | ~1 : 1.54 | 4 or 5 columns |
| **A3 Newspaper** | 297 × 420 mm | 842 × 1191 pt | 1 : 1.414 | 4 or 5 columns |
| **A4 Gazette** | 210 × 297 mm | 595 × 842 pt | 1 : 1.414 | 3 columns |

## Generating Print-Ready PDFs

Run the Node export script:
```bash
node scripts/render_pdf.js --input templates/broadsheet/index.html --output output/broadsheet.pdf --format broadsheet
```
Options:
- `--format`: `broadsheet`, `tabloid`, `berliner`, `a3`, `a4`, or custom `--width=375mm --height=580mm`.
- `--scale`: `1.0` (default) or scaled DPI.
- `--screenshot`: Output full-spread high-res PNG image for visual inspection (`--screenshot output/preview.png`).

## Pre-Flight Checklist for Print PDF
1. **Fonts Embedded**: All WebFonts (Google Fonts or local OTF/TTF) loaded before render.
2. **Page Breaks Clean**: No heading separated from its following text (`break-after: avoid;`).
3. **No Overset Text**: All columns balanced without clipping at page bottom.
4. **Contrast & Line Weights**: Column rules at `0.5pt` to `1pt` (`#111` or `#333`), text at `#111` (rich black or pure K-black).
