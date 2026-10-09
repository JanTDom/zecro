---
name: newspaper-layout-generator
description: >-
  Master workflow for designing, generating, and structuring complete newspaper front pages, inside spreads, section pages (Opinion, Business, Culture, Sports, Classifieds) in broadsheet, tabloid, or Berliner formats using HTML/CSS Paged Media or Typst. Use this skill when asked to create, design, scaffold, or format newspaper layouts from text, articles, or design specifications.
---

# Newspaper Layout Generator Skill

This skill provides end-to-end guidance and tooling for generating authentic, publication-grade newspaper layouts.

## Editorial Layout Anatomy

Every newspaper page is composed of distinct hierarchical modules:

```text
┌───────────────────────────────────────────────────────────────┐
│ SKYLINE / BANNER TEASERS (Top bar for breaking / special)      │
├───────────────────────────────────────────────────────────────┤
│ MASTHEAD / NAMEPLATE (Title, Motto, Date, Vol, Price, Folio)   │
├───────────────────────────────────────┬───────────────────────┤
│ LEAD STORY (Spans 3-4 columns)        │ SIDEBAR STORY         │
│ • Kicker / Overline                   │ • 1-2 Columns         │
│ • Main Headline (Dominant font size)  │ • Compact headline    │
│ • Deck / Subheadline                  │ • Infobox / Chart     │
│ • Dateline & Byline                   │ • Short copy          │
│ • Lead Paragraph with Drop Cap        │                       │
│ • Multi-column body text              ├───────────────────────┤
│ • Editorial Photo + Credit + Caption  │ WEATHER / INDEX / AD  │
├───────────────────────────────────────┴───────────────────────┤
│ SECONDARY STORIES (Spans 2-3 columns each)                    │
│ • Multi-tier headlines • Pull Quotes • Jump lines             │
├───────────────────────────────────────────────────────────────┤
│ FOLIO FOOTER (Page number, Section, Publication name, Date)   │
└───────────────────────────────────────────────────────────────┘
```

## Step-by-Step Generation Workflow

1. **Determine the Format & Grid**:
   - **Broadsheet (A2 / 375x580mm)**: 6-column or 7-column grid. Suited for heavy news density and classic broadsheet authority.
   - **Tabloid / Compact (A3 / 280x430mm)**: 4-column or 5-column grid. Suited for visual punch, large hammer headlines, and modern news.
   - **Berliner (315x470mm)**: 5-column grid. Refined European format balancing elegance and density.
   - **Digital E-Paper / Responsive Gazette**: Modern fluid multi-column with responsive breakpoints.

2. **Run Layout Scaffolding**:
   Use the built-in generator script:
   ```bash
   node scripts/scaffold_newspaper.js --format=broadsheet --title="The Daily Chronicle" --edition="Morning Edition"
   ```

3. **Assemble the Content Structure**:
   - Apply proper semantic HTML tags (`<header class="masthead">`, `<article class="story lead-story">`, `<aside class="sidebar">`, `<figure class="editorial-image">`).
   - Use CSS Grid for modular page zones + CSS Multi-column (`columns: N; column-gap: X; column-rule: 1px solid #ccc;`) for story body copy.
   - Ensure all headlines span their respective columns using `column-span: all` or `grid-column: span N`.

4. **Apply Typographic & Microtypographic Polish**:
   - Set baseline-snapped `line-height`.
   - Enable hyphenation (`hyphens: auto; text-align: justify;`).
   - Add drop caps to lead paragraphs (`initial-letter: 3 2`).
   - Add kickers, bylines, datelines, and captions.

5. **Verify Layout & Render Preview**:
   - Preview in browser via `npm run dev` (`http://localhost:3000`).
   - Export high-resolution PDF via `npm run build:pdf`.
   - Inspect visually with screenshot tools.

## References & Resources
- [Layout Patterns Guide](./references/layout-patterns.md)
- [Copyfitting Formulas](../newspaper-copyfitting-engine/references/copyfitting-formulas.md)
- [HTML/CSS Paged Media Guide](../newspaper-paged-media/references/pagedjs-guide.md)
