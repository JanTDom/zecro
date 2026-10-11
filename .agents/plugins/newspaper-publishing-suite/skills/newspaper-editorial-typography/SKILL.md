---
name: newspaper-editorial-typography
description: >-
  Rules, font pairings, baseline grid alignment, hyphenation and justification algorithms, drop caps, kickers, decks, pull quotes, bylines, and microtypography for newspaper publishing. Use this skill when styling, tuning, or fine-tuning typographic details and hierarchy in editorial projects.
---

# Newspaper Editorial Typography Skill

This skill defines the typographic craft required for legitimate editorial publications.

## Typographic Hierarchy Stack

```text
1. BANNER / HAMMER HEADLINE    (48pt - 96pt Bold/Black Display)
   "GLOBAL SUMMIT REACHES HISTORIC ACCORD"
   
2. KICKER / OVERLINE           (9pt - 11pt Bold Uppercase Sans)
   "CLIMATE ACCORD • GENEVA"
   
3. DECK / SUBHEADLINE          (14pt - 20pt Italic Serif or Medium Sans)
   "Envoys from 140 nations agree on strict emission caps following 72-hour marathon debate."
   
4. BYLINE & DATELINE           (8.5pt - 10pt Sans or Small-Caps Serif)
   "BY ELEANOR VANCE • GENEVA, SWITZERLAND"
   
5. LEAD PARAGRAPH WITH DROP CAP
   [E]NVOYS from around the world signed a binding treaty on Thursday...
   
6. BODY TEXT COLUMNS           (9.5pt - 10.5pt Serif on 12.5pt - 13.5pt Leading)
   Justified text, crisp hyphenation, baseline snapped.
   
7. CROSSHEAD / INTER-TITLE     (11pt - 12pt Bold Sans or Semibold Serif)
   "Sticking Points in Agriculture"
   
8. PULL QUOTE                  (18pt - 24pt Italic Serif with double rules)
   “This agreement marks a decisive turning point for our collective future.”
```

## CSS Implementation for Editorial Typography

```css
:root {
  --font-serif-headline: "Playfair Display", "Georgia", "Times New Roman", serif;
  --font-serif-body: "Merriweather", "Newsreader", "Garamond", serif;
  --font-sans-kicker: "Libre Franklin", "Helvetica Neue", "Arial", sans-serif;
  --font-blackletter: "Chomsky", "UnifrakturCook", "Pirata One", serif;
  --baseline: 18px;
}

/* Drop Cap (Modern CSS) */
.story-lead::first-letter {
  initial-letter: 3 2;
  -webkit-initial-letter: 3 2;
  font-family: var(--font-serif-headline);
  font-weight: 700;
  color: #111;
  margin-right: 0.15em;
}

/* Fallback Drop Cap */
@supports not (initial-letter: 3 2) {
  .story-lead::first-letter {
    float: left;
    font-size: 3.4em;
    line-height: 0.8;
    padding-top: 4px;
    padding-right: 8px;
    padding-bottom: 2px;
    font-family: var(--font-serif-headline);
    font-weight: 700;
  }
}

/* Dateline formatting */
.dateline {
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-family: var(--font-sans-kicker);
  font-size: 0.85em;
}

/* Pull Quote */
.pull-quote {
  font-family: var(--font-serif-headline);
  font-size: 1.35rem;
  font-style: italic;
  line-height: 1.3;
  text-align: center;
  margin: 1.5rem 0;
  padding: 1rem 0;
  border-top: 2px solid #111;
  border-bottom: 1px solid #111;
}
```

## References
- [Baseline Gridsnapping Guide](./references/baseline-grid.md)
- [Hyphenation and Justification](./references/hyphenation-justification.md)
- [Headline Hierarchy & Decks](./references/headline-hierarchy.md)
