# Typst Newspaper Publishing Architecture

## Column Flow Control
- `#columns(N, gutter: Xpt)[ ... ]` creates an N-column container.
- `#colbreak()` forces content to advance to the next column.
- `#pagebreak()` advances to the next page.
- Wrap full-width articles in `#place()` or exit `#columns` to place full-page span headlines.
