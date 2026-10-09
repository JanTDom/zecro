---
name: newspaper-typst-engine
description: >-
  Typst-based high-performance newspaper publishing engine. Use this skill when generating vector-sharp, print-ready PDF newspapers, broadsheets, tabloids, or gazettes using Typst markup, multi-column flows, and modular layouts.
---

# Typst Newspaper Engine Skill

Typst compiles complex multi-page, multi-column documents to PDF in milliseconds with perfect typography, hyphenation, and vector graphics.

## Typst Newspaper Core Concepts

```typst
// Define Newspaper Page Setup
#set page(
  paper: "a3",
  flipped: false,
  margin: (top: 2cm, bottom: 2cm, left: 1.5cm, right: 1.5cm),
  header: locate(loc => {
    if loc.page() > 1 {
      grid(
        columns: (1fr, 1fr, 1fr),
        align: (left, center, right),
        text(size: 8pt, weight: "bold", "THE DAILY CHRONICLE"),
        text(size: 8pt, fill: luma(100), "INTERNATIONAL EDITION"),
        text(size: 8pt, [PAGE #loc.page()])
      )
      line(length: 100%, stroke: 0.5pt + luma(150))
    }
  })
)

#set text(
  font: "Linux Libertine",
  size: 9.5pt,
  lang: "en",
  hyphenate: true
)
#set par(justify: true, leading: 0.55em)
```

## Multi-Column and Headline Spanning in Typst

```typst
// Masthead
#align(center)[
  #text(size: 10pt, tracking: 2pt, weight: "bold", [ESTABLISHED 1894 • VOL. CXXXII NO. 42])
  #v(2pt)
  #text(size: 42pt, font: "UnifrakturMaguntia", weight: "bold", [The Daily Chronicle])
  #v(2pt)
  #line(length: 100%, stroke: 2pt + black)
  #line(length: 100%, stroke: 0.5pt + black)
]

// Lead Banner Story spanning full width
#block(width: 100%)[
  #text(size: 9pt, weight: "bold", fill: rgb("#990000"), [BREAKING DIPLOMACY]) \
  #text(size: 28pt, weight: "bold", font: "Playfair Display", [Historic Treaty Signed in Geneva]) \
  #text(size: 13pt, style: "italic", [One hundred and forty nations commit to binding emission quotas.])
]

#v(8pt)

// 4-Column Body Layout
#columns(4, gutter: 14pt)[
  *GENEVA —* In a landmark session concluding at dawn, delegates ratified the comprehensive treaty.
  
  #lorem(180)
  
  #colbreak()
  
  #figure(
    image("summit.jpg", width: 100%),
    caption: [Delegates celebrating following ratification.]
  )
  
  #lorem(140)
]
```

## References & Templates
- [Typst Newspaper Guide](./references/typst-newspaper-guide.md)
- [Complete Typst Template](./templates/newspaper.typ)
