---
name: newspaper-infographics
description: >-
  Editorial SVG infographics, financial market tickers, weather forecast boxes, locator maps, timelines, and fact boxes styled specifically for print and digital newspapers. Use this skill when creating visual editorial widgets, data charts, or decorative print accents.
---

# Newspaper Infographics & Editorial Widgets

Authentic newspaper design relies on clean, high-contrast editorial data graphics with classic news styling (stippling, hatched fills, clean linework, tabular figures).

## Essential Newspaper Infographic Types

1. **Weather Forecast Ear Box**:
   - Placed in top left or right of the masthead.
   - 3 to 5 day forecast with clean SVG weather icons (Sun, Rain, Cloud, Wind) and High/Low temperatures.
2. **Financial Market Summary Bar**:
   - Stock indices (DJIA, S&P 500, NASDAQ, FTSE 100, WTI Crude, Gold, EUR/USD).
   - Directional delta arrows ($\blacktriangle$ / $\blacktriangledown$) and percentage changes.
3. **Editorial Locator Map**:
   - Minimalist vector map highlighting key cities, borders, conflict/treaty zones with inset locator globe.
4. **Key Facts / Sidebar Box**:
   - Tinted background (`#f4f4f2`), thin 1px black border or thick top bar, bulleted summary facts.
5. **Editorial Timeline**:
   - Vertical or horizontal milestone track with clean dates and short bold descriptions.

## Clean SVG Weather Box Example

```html
<div class="weather-ear-box">
  <div class="weather-title">TODAY'S WEATHER</div>
  <div class="weather-forecast">
    <div class="forecast-day">
      <span class="day-label">THU</span>
      <svg class="weather-icon" viewBox="0 0 24 24" width="24" height="24">
        <circle cx="12" cy="12" r="5" fill="none" stroke="#111" stroke-width="2"/>
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1l2.1-2.1M17 7l2.1-2.1" stroke="#111" stroke-width="2"/>
      </svg>
      <span class="temp-hi">22°</span> / <span class="temp-lo">14°</span>
    </div>
  </div>
</div>
```

## References & Templates
- [Weather Box Template](./templates/weather-box.svg)
- [Stock Ticker Component](./templates/stock-ticker.html)
- [Editorial Chart Component](./templates/editorial-chart.html)
