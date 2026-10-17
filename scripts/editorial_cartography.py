#!/usr/bin/env python3
"""
Zecro Editorial Data & Press Cartography Engine.

Generates vector SVG graphics styled for print newspapers and snapped to column grids:
- Press Locator Maps (mapki sytuacyjne z punktem zdarzenia, skalówką i różą wiatrów)
- Editorial polling / survey breakdown bar charts
- Column-fitted tabular timetable / schedule modules
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def generate_locator_map_svg(
    title: str = "Miejsce Remontu: Warszawa Zachodnia",
    location_label: str = "Stacja WKD Warszawa Zachodnia",
    width_mm: float = 104.0,  # 2 columns
    height_mm: float = 70.0,
    dpi: float = 72.0 / 25.4,  # SVG user units to mm
) -> str:
    w = width_mm * dpi
    h = height_mm * dpi

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{width_mm}mm" height="{height_mm}mm">
  <defs>
    <style>
      .map-bg {{ fill: #f4f3ef; stroke: #111111; stroke-width: 1.5; }}
      .street-main {{ fill: none; stroke: #d0cec5; stroke-width: 8; stroke-linecap: round; }}
      .rail-track {{ fill: none; stroke: #003366; stroke-width: 3.5; stroke-dasharray: 6 3; }}
      .pin-body {{ fill: #cc0000; stroke: #ffffff; stroke-width: 1.5; }}
      .pin-pulse {{ fill: none; stroke: #cc0000; stroke-width: 1; stroke-opacity: 0.5; }}
      .map-title {{ font-family: 'Barlow', 'Helvetica Neue', Arial, sans-serif; font-size: 11px; font-weight: 800; fill: #111111; text-transform: uppercase; }}
      .map-label {{ font-family: 'Barlow', 'Helvetica Neue', Arial, sans-serif; font-size: 9px; font-weight: 600; fill: #222222; }}
      .scale-text {{ font-family: 'PT Serif', Georgia, serif; font-size: 7.5px; fill: #555555; }}
      .compass {{ fill: #111111; }}
    </style>
  </defs>

  <!-- Background frame -->
  <rect class="map-bg" x="0.75" y="0.75" width="{w - 1.5:.1f}" height="{h - 1.5:.1f}" />

  <!-- Road Network Grid -->
  <path class="street-main" d="M 10,{h * 0.45:.1f} Q {w * 0.5:.1f},{h * 0.35:.1f} {w - 10:.1f},{h * 0.5:.1f}" />
  <path class="street-main" d="M {w * 0.3:.1f},15 L {w * 0.35:.1f},{h - 15:.1f}" />
  <path class="street-main" d="M {w * 0.7:.1f},15 L {w * 0.65:.1f},{h - 15:.1f}" />

  <!-- Railway Line (WKD / PKP) -->
  <path class="rail-track" d="M 5,{h * 0.65:.1f} L {w - 5:.1f},{h * 0.25:.1f}" />

  <!-- Marker Pin -->
  <circle class="pin-pulse" cx="{w * 0.55:.1f}" cy="{h * 0.45:.1f}" r="12" />
  <circle class="pin-body" cx="{w * 0.55:.1f}" cy="{h * 0.45:.1f}" r="5.5" />

  <!-- Callout Box -->
  <rect x="{w * 0.45:.1f}" y="{h * 0.52:.1f}" width="{w * 0.50:.1f}" height="20" fill="#ffffff" stroke="#111111" stroke-width="1" />
  <text class="map-label" x="{w * 0.47:.1f}" y="{h * 0.52 + 13:.1f}">{location_label}</text>

  <!-- Header Banner -->
  <rect x="0.75" y="0.75" width="{w - 1.5:.1f}" height="18" fill="#e2dfd7" stroke="#111111" stroke-width="1" />
  <text class="map-title" x="8" y="13">{title}</text>

  <!-- Scale Bar & Compass -->
  <line x1="10" y1="{h - 8:.1f}" x2="50" y2="{h - 8:.1f}" stroke="#111111" stroke-width="2" />
  <line x1="10" y1="{h - 12:.1f}" x2="10" y2="{h - 8:.1f}" stroke="#111111" stroke-width="1" />
  <line x1="50" y1="{h - 12:.1f}" x2="50" y2="{h - 8:.1f}" stroke="#111111" stroke-width="1" />
  <text class="scale-text" x="12" y="{h - 11:.1f}">250 m</text>

  <g transform="translate({w - 18:.1f}, {h - 18:.1f}) scale(0.6)">
    <polygon class="compass" points="0,-12 4,0 0,-3 -4,0" />
    <polygon points="0,12 4,0 0,-3 -4,0" fill="#999999" />
    <text x="-3" y="-14" font-family="sans-serif" font-size="8" font-weight="bold">N</text>
  </g>
</svg>"""
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Zecro Editorial Cartography & SVG Generator")
    parser.add_argument("--title", default="Lokalizacja Inwestycji", help="Map header title")
    parser.add_argument("--label", default="Warszawa Zachodnia (WKD)", help="Pin point label")
    parser.add_argument("--cols", type=int, choices=[1, 2, 3], default=2, help="Column span width")
    parser.add_argument("--output", type=str, default="output/locator_map.svg", help="Output file path")
    args = parser.parse_args()

    # Column width mapping (50mm for 1 col, 104mm for 2 cols, 158mm for 3 cols)
    width_map = {1: 50.0, 2: 104.0, 3: 158.0}
    w_mm = width_map[args.cols]
    h_mm = 65.0

    svg_content = generate_locator_map_svg(title=args.title, location_label=args.label, width_mm=w_mm, height_mm=h_mm)

    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(svg_content, encoding="utf-8")
    print(f"Generated editorial locator map SVG: {out_p} ({w_mm}x{h_mm} mm)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
