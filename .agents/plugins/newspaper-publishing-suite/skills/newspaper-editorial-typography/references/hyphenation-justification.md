# Hyphenation & Justification (H&J)

## Modern CSS Rules
```css
p {
  text-align: justify;
  text-justify: inter-word;
  hyphens: auto;
  -webkit-hyphens: auto;
  -ms-hyphens: auto;
  hyphenate-limit-chars: 6 3 2;
  hyphenate-limit-lines: 2;
  hyphenate-limit-last: always;
  hanging-punctuation: first last;
}
```
