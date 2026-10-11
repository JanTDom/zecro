// ==========================================================================
// TYPST PROFESSIONAL NEWSPAPER TEMPLATE
// A3 Tabloid / Multi-column Editorial Layout
// ==========================================================================

#set page(
  paper: "a3",
  margin: (top: 2cm, bottom: 2cm, left: 1.5cm, right: 1.5cm),
  header: locate(loc => {
    if loc.page() > 1 {
      grid(
        columns: (1fr, 1fr, 1fr),
        align: (left, center, right),
        text(size: 8pt, weight: "bold", font: "Liberation Sans", [THE DAILY CHRONICLE]),
        text(size: 8pt, fill: luma(100), font: "Liberation Sans", [INTERNATIONAL EDITION]),
        text(size: 8pt, font: "Liberation Sans", [PAGE #loc.page()])
      )
      v(2pt)
      line(length: 100%, stroke: 0.5pt + luma(120))
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

// Top Skyline
#align(center)[
  #text(size: 7.5pt, weight: "bold", font: "Liberation Sans", tracking: 0.1em)[
    INSIDE: GLOBAL TECH SUMMIT IN KYOTO (PAGE B1) #h(1cm) OPINION: ARCHITECTURE OF THE NEXT DECADE (PAGE A12)
  ]
  #v(2pt)
  #line(length: 100%, stroke: 0.5pt + luma(80))
]

// Masthead
#align(center)[
  #text(size: 9pt, style: "italic", [“The Voice of Independent Journalism and Truth”]) \
  #v(2pt)
  #text(size: 44pt, weight: "bold", font: "Playfair Display", [The Daily Chronicle]) \
  #v(2pt)
  #line(length: 100%, stroke: 2pt + black)
  #v(-3pt)
  #line(length: 100%, stroke: 0.5pt + black)
]

// Folio Line
#grid(
  columns: (1fr, 1fr, 1fr, 1fr),
  align: (left, center, center, right),
  text(size: 7.5pt, weight: "bold", font: "Liberation Sans", [VOL. CXXXII NO. 42]),
  text(size: 7.5pt, weight: "bold", font: "Liberation Sans", [THURSDAY, OCTOBER 15, 2026]),
  text(size: 7.5pt, weight: "bold", font: "Liberation Sans", [FINAL MORNING EDITION]),
  text(size: 7.5pt, weight: "bold", font: "Liberation Sans", [PRICE $2.50])
)

#v(8pt)

// Lead Banner Story Headline
#block(width: 100%)[
  #text(size: 8.5pt, weight: "bold", fill: rgb("#990000"), font: "Liberation Sans", tracking: 0.08em)[HISTORIC ACCORD • GENEVA DIPLOMACY] \
  #v(2pt)
  #text(size: 26pt, weight: "bold", font: "Playfair Display", [Global Summit Reaches Binding Climate Agreement]) \
  #v(2pt)
  #text(size: 12pt, style: "italic", [Envoys from 140 nations ratify landmark emission caps following intense 72-hour marathon debate in Geneva; \$450 billion transition fund established.])
  #v(4pt)
  #line(length: 100%, stroke: 0.5pt + luma(180))
]

#v(6pt)

// 4-Column Layout
#columns(4, gutter: 14pt)[
  #text(weight: "bold", size: 8pt, font: "Liberation Sans")[BY ELEANOR VANCE] \
  #v(2pt)
  *GENEVA —* In a decisive diplomatic breakthrough that followed three days of continuous deliberation, representatives from 140 sovereign nations ratified a binding international treaty aimed at stabilizing global industrial output and accelerating renewable infrastructure deployment.

  The accord, finalized under the auspices of the International Environmental Council, establishes enforceable decadal targets alongside a dedicated 450-billion-dollar multilateral transition fund.

  #colbreak()

  “We have moved past declarations of intent to actionable, enforceable obligations,” declared lead negotiator Dr. Helena Lindqvist during a crowded morning press briefing.

  Key provisions of the agreement mandate verified carbon accounting for maritime shipping, phased decommission schedules for unabated coal infrastructure, and sovereign green bond standards.

  #colbreak()

  #block(
    fill: rgb("#f4f4f0"),
    inset: 8pt,
    stroke: 0.5pt + black,
    [
      #text(weight: "bold", size: 8pt, font: "Liberation Sans")[KEY PROVISIONS]
      - *\$450B* Transition Facility
      - *2035 Target:* 60% reduction
      - *Maritime Rule:* Zero-emission
      - *Enforcement:* Bilateral panel
    ]
  )

  #colbreak()

  #align(center)[
    #line(length: 80%, stroke: 1pt + black)
    #v(4pt)
    #text(size: 11pt, style: "italic", [“This agreement marks a decisive turning point for our collective future.”])
    #v(4pt)
    #line(length: 80%, stroke: 1pt + black)
  ]
]
