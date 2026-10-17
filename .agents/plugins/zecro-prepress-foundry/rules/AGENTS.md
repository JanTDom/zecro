# Zecro Prepress Foundry Rules

When exporting, converting, inspecting, and preflighting print documents within this plugin:
1. **Total Area Coverage (TAC) Limit**: TAC must never exceed 240% on newsprint stock (ISO 12647-3). Any separation exceeding 240% must be flagged as a critical failure.
2. **Pure 100% K Overprint**: All body text, column rules, hairline borders, and captions set in 100% K black must have `overprint: true`. White knockout around small black text is a blocker defect.
3. **Trapping and Bleeds**: Enforce minimum 0.15mm trapping on color junctions. Facing spreads require 3mm outer bleeds and 0mm inner spine bleeds.
4. **Resolution Bounds**: Ensure all bitmap images have at least 180–200 effective PPI at their 100% physical reproduction frame size.
5. **PDF/X Standards**: Production outputs must validate against PDF/X-1a or PDF/X-4 specifications with embedded fonts, CMYK color spaces, and correct trim/bleed boxes.
