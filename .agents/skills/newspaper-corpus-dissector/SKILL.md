---
name: newspaper-corpus-dissector
description: >-
  Reverse-engineering newspaper grids, detecting column counts, measuring gutter widths, extracting font size histograms, and segmenting editorial layout zones from PDF archives and scanned newspaper pages. Use this skill when analyzing a newspaper's historical corpus to derive its formal TitleDNA grammar automatically.
---

# Newspaper Corpus Dissector Skill

This skill provides algorithms and procedures to reverse-engineer a newspaper's visual DNA from historical page archives.

## 1. The Grid Reverse-Engineering Algorithm

1. **Bounding Box Projection**:
   - Extract bounding boxes of all text and image elements on the page.
   - Project vertical edges ($x$-coordinates) onto a 1D horizontal histogram.
2. **Column & Gutter Detection**:
   - Peaks in gap distances reveal **column gutters** (typically 3.5mm – 5.5mm).
   - The number of repeating continuous text valleys gives the **column count** ($N \in \{4, 5, 6, 7, 8\}$).
3. **Baseline Leading Calculation**:
   - Compute vertical distance ($\Delta y$) between consecutive text baselines across all body blocks.
   - The greatest common divisor (GCD) yields the **baseline grid increment** (e.g. $13.5\text{ pt} \approx 4.76\text{ mm}$).
4. **Typographic Scale Hierarchy Extraction**:
   - Cluster font sizes ($pt$) into standard functional tiers:
     - Tier 1 ($>40\text{ pt}$): Primary / Hammer Headlines
     - Tier 2 ($24–36\text{ pt}$): Secondary Headlines
     - Tier 3 ($14–20\text{ pt}$): Decks / Subheads
     - Tier 4 ($11–13\text{ pt}$): Leads
     - Tier 5 ($8.5–10.5\text{ pt}$): Body text
     - Tier 6 ($7–8\text{ pt}$): Captions & Bylines

## 2. Automatic TitleDNA Calibration

The extracted parameters are mapped directly into the formal [`title_dna.schema.json`](file:///Users/macbookpro/PROJEKTY/LAYOUT/contracts/title_dna.schema.json) specification to initialize a new project automatically.

## References
- [Corpus Ingestion API](../../../backend/app/api/corpus.py)
- [Directory Importer](../../../scripts/import_corpus.py)
