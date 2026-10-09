# Newspaper Publishing Suite Rules

When working on editorial and newspaper layouts within this plugin:
1. Always maintain consistent column widths and column gutters across facing spreads (verso/recto).
2. Adhere to strict vertical grid alignment: headings, body copy, and sidebars must align to baseline increments.
3. Prevent orphan headings at column bottoms and single-line widows at column tops using CSS `break-after: avoid;` and `orphans: 3; widows: 3;`.
4. Ensure headlines span the exact integer count of columns they sit above (`grid-column: span N` or `column-span: all`).
5. Include proper editorial datelines, bylines, jump lines, and photo captions for journalistic authenticity.
