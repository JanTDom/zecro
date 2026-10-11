---
name: newspaper-prepress-preflight
description: >-
  Professional DTP prepress, PDF/X compliance, color separation, and preflight auditing for newsprint and commercial printing. Use this skill when verifying print-readiness, checking Total Area Coverage (TAC / TIC ink limits < 240%), validating CMYK separations (pure 100% K channel for body text), bleed/trim marks, trapping, image DPI resolution, and PDF/X-1a / PDF/X-4 export rules.
---

# Newspaper Prepress & Preflight Auditor

This skill enforces strict prepress engineering rules required for high-speed coldset and heatset web offset newspaper printing.

## 1. Golden Rules of Newsprint Prepress

1. **Total Area Coverage (TAC / TIC)**:
   - Coldset Newsprint max ink limit: **220% – 240%** (ISOnewspaper26v4 / WAN-IFRA).
   - Exceeding 240% causes ink setoff, smearing, and paper tearing on high-speed web presses.
2. **Text Black vs Rich Black**:
   - **Body text & fine rules**: MUST be **100% K (Black only)** with `overprint: true`. Never use 4-color Rich Black on text below 24pt (misregistration causes blurry rainbow halos).
   - **Large banner headlines (>48pt) & solid background boxes**: Can use Rich Black (e.g., `C30 M30 Y20 K100` $\approx$ 180% TAC) for dense, deep ink coverage.
3. **Image Resolution**:
   - Continuous tone images (Photos): **200 – 300 effective DPI** at 100% scale on page.
   - 1-bit line art (Illustrations / Engravings): **800 – 1200 DPI**.
4. **Bleed & Trim**:
   - Bleed: Standard **3mm (0.125 in)** when elements run off the trim line.
   - Gripper Margin: Traditional broadsheets require an unprinted margin of 10–12mm at paper edges.
5. **PDF/X Standards**:
   - **PDF/X-1a:2001**: Blind exchange, CMYK + spot colors only, all fonts embedded, no transparency.
   - **PDF/X-4:2010**: Modern standard, allows live transparency and ICC-based color management.

## 2. Executing Preflight Verification

Run the Python preflight auditing script:
```bash
python3 scripts/preflight_check.py --pdf output/newspaper.pdf --profile isonewspaper
```
Or check a SceneGraph / IDML package:
```bash
python3 scripts/preflight_check.py --idml output/newspaper.idml --tac-limit 240
```

## References
- [Prepress Newsprint Specifications](./references/newsprint-specs.md)
- [Color Management & Separation Guide](./references/color-separations.md)
