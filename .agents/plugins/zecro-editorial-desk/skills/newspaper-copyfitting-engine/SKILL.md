---
name: newspaper-copyfitting-engine
description: >-
  Copyfitting calculation and text optimization engine for newspapers. Use this skill when you need to calculate word counts, character counts, column inches, adjust font size or tracking to fill newspaper space precisely, eliminate widows/orphans, or split long articles with jump lines.
---

# Newspaper Copyfitting Engine

In print journalism, **copyfitting** is the art and science of matching a writer's text volume exactly to the allocated page geometry (column inches and picas) without leaving awkward gaps ("holes") or overflowing columns.

## Copyfitting Principles

1. **Column-Inch Metric**:
   - 1 Column-Inch = 1 column wide × 1 inch (72 points / 6 picas) deep.
   - At standard 10pt/12pt body text, 1 column-inch holds approximately **32 to 38 words** (or ~220 characters).
2. **Character Count (CPP - Characters Per Pica)**:
   - Average CPP for standard serif body type (10pt) = 2.4 to 2.8 CPP.
   - A 12-pica wide column (2 inches / ~50mm) holds ~30 to 34 characters per line.
3. **Copy Adjustment Strategies**:
   - **Text is Too Long (Overset)**:
     - Reduce body type size slightly (e.g., from 10pt to 9.5pt).
     - Tighten tracking slightly (e.g., `-0.01em` to `-0.02em` or `-10` tracking).
     - Tighten leading (e.g., from `13pt` to `12.2pt`).
     - Split story and add jump line: *"Continued on Page B4"*.
     - Sub-edit: cut secondary clauses and adjectives.
   - **Text is Too Short (Underset / Hole)**:
     - Increase headline deck lines from 1 line to 2-3 lines.
     - Add a pull quote in a framed box.
     - Add a sidebar or "Key Facts / At a Glance" box.
     - Increase image height or add a secondary photo with caption.

## Executing the Copyfit Calculator

Run the Python copyfitting tool:
```bash
python3 scripts/copyfit.py --words 450 --columns 3 --height-in 6.5 --font-size 10 --leading 13
```
Or analyze a text file:
```bash
python3 scripts/copyfit.py --file path/to/article.txt --columns 2 --width-mm 60 --height-mm 180
```

## References
- [Copyfitting Formulas & Tables](./references/copyfitting-formulas.md)
