---
name: newspaper-indesign-scripting
description: >-
  Adobe InDesign ExtendScript (.jsx) and IDML generation for automating newspaper page layout, multi-column text frame threading, paragraph styles, baseline grids, and master page setup. Use this skill when generating InDesign automation scripts or converting article copy into InDesign templates.
---

# InDesign Newspaper Scripting Skill

This skill provides ExtendScript (JavaScript for InDesign) snippets and automation routines to construct newspaper pages programmatically.

## InDesign Automation Workflow

1. **Document Setup (Broadsheet / Tabloid)**:
   Define page dimensions, margins, and column counts with exact gutters.
2. **Master Page & Folio Setup**:
   Create running headers, date lines, and automatic page numbers on parent pages.
3. **Paragraph Style Sheet Creation**:
   Construct standard styles: `Masthead`, `Headline-Banner`, `Kicker`, `Deck`, `Byline`, `Dateline`, `Body-Justified`, `Caption`.
4. **Text Frame Threading**:
   Automatically link multi-column text frames across stories to allow copy to flow seamlessly.

## ExtendScript Example: Build Newspaper Spread

```javascript
// ExtendScript: Create a 5-Column Newspaper Front Page
var doc = app.documents.add();
with(doc.documentPreferences) {
    pageWidth = "280mm";  // Tabloid width
    pageHeight = "430mm"; // Tabloid height
    facingPages = false;
}

var page = doc.pages.item(0);
with(page.marginPreferences) {
    top = "15mm";
    bottom = "15mm";
    left = "15mm";
    right = "15mm";
    columnCount = 5;
    columnGutter = "4mm";
}

// Add Masthead Text Frame
var mastheadFrame = page.textFrames.add({
    geometricBounds: ["15mm", "15mm", "40mm", "265mm"],
    contents: "THE DAILY CHRONICLE"
});
mastheadFrame.paragraphs.item(0).pointSize = 48;
mastheadFrame.paragraphs.item(0).justification = Justification.CENTER_ALIGN;
```

## References & Scripts
- [ExtendScript & IDML Guide](./references/extendscript-idml-guide.md)
- [Executable InDesign Script](./scripts/build_newspaper_spread.jsx)
