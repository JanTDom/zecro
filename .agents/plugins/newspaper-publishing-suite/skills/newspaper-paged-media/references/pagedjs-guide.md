# Paged.js Complete Reference for Newspapers

## Named Strings for Dynamic Headers
Use CSS `string-set` to dynamically pull the current section or article title into running headers:

```css
.section-title {
  string-set: section-title content();
}

@page {
  @top-left {
    content: string(section-title);
  }
}
```

## Handling Cross-Column Figures and Pull Quotes
In newspaper layout, images often span 2 out of 4 columns, or float within a column:
```css
/* 2-Column Spanning Image in a CSS Grid Container */
.grid-container {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  column-gap: 15px;
  row-gap: 20px;
}

.hero-image {
  grid-column: span 3;
}

.hero-story {
  grid-column: span 2;
}
```
