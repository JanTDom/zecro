# Baseline Grid Alignment Guide

In professional typography, all text elements (regardless of font size) must align to a common vertical rhythm.

```css
/* Base vertical rhythm */
body {
  font-size: 10pt;
  line-height: 13.5pt; /* Baseline unit = 13.5pt (18px) */
}

/* Headings take exact multiples of the baseline unit */
h1 {
  font-size: 36pt;
  line-height: 40.5pt; /* Exactly 3 baseline units (3 * 13.5) */
  margin-top: 13.5pt;  /* 1 baseline unit */
  margin-bottom: 13.5pt; /* 1 baseline unit */
}

h2 {
  font-size: 24pt;
  line-height: 27pt;   /* Exactly 2 baseline units (2 * 13.5) */
  margin-top: 13.5pt;
  margin-bottom: 13.5pt;
}
```
