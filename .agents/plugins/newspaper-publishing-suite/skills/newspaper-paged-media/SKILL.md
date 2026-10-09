---
name: newspaper-paged-media
description: >-
  CSS Paged Media, Paged.js, and multi-column CSS techniques for automated newspaper pagination, running headers/footers, folio numbers, spread handling (verso/recto), column balancing, and print styles. Use this skill when coding CSS for multi-page newspaper printing or browser-based publication engines.
---

# CSS Paged Media & Paged.js Skill

This skill documents how to structure and style multi-page newspaper publications using modern CSS Multi-Column specifications and CSS Paged Media Module Level 3 (supported natively or enhanced via Paged.js).

## Core CSS Multi-Column Syntax

```css
/* Column container for stories */
.story-body {
  column-count: 3;
  column-gap: 1.25rem;
  column-rule: 1px solid #d0d0d0;
  text-align: justify;
  text-justify: inter-word;
  hyphens: auto;
  -webkit-hyphens: auto;
  line-height: 1.35;
  orphans: 3;
  widows: 3;
}

/* Span across all columns in a multi-column container */
.story-headline {
  column-span: all;
  margin-bottom: 0.75rem;
}

/* Prevent unwanted breaks inside figures or infoboxes */
.editorial-figure,
.sidebar-box,
.pull-quote {
  break-inside: avoid;
  page-break-inside: avoid;
}

/* Ensure headings never get orphaned at column bottoms */
h1, h2, h3, h4, h5, .deck, .kicker {
  break-after: avoid;
  page-break-after: avoid;
}
```

## CSS Paged Media (`@page`) Rules

```css
@page {
  size: 375mm 580mm; /* Broadsheet */
  margin: 15mm 15mm 15mm 15mm;
  @top-left {
    content: "THE DAILY CHRONICLE";
    font-family: "Libre Franklin", sans-serif;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  @top-right {
    content: "SECTION A • PAGE " counter(page);
    font-family: "Libre Franklin", sans-serif;
    font-size: 8pt;
    font-weight: 600;
  }
  @bottom-center {
    content: "CONFIDENTIAL & COPYRIGHT © 2026";
    font-size: 7pt;
    color: #666;
  }
}

/* Verso (Left) & Recto (Right) Page Specifics */
@page :left {
  margin-left: 18mm;
  margin-right: 12mm;
  @top-left {
    content: "PAGE " counter(page) " • " string(section-title);
  }
  @top-right {
    content: "THE DAILY CHRONICLE";
  }
}

@page :right {
  margin-left: 12mm;
  margin-right: 18mm;
  @top-left {
    content: "THE DAILY CHRONICLE";
  }
  @top-right {
    content: string(section-title) " • PAGE " counter(page);
  }
}
```

## Paged.js Integration

Include Paged.js polyfill script for full W3C Paged Media support in modern browsers:
```html
<script src="https://unpkg.com/pagedjs/dist/paged.polyfill.js"></script>
```

## References
- [Paged.js Deep Dive Guide](./references/pagedjs-guide.md)
- [CSS Multi-Column Specification](./references/css-multicolumn.md)
