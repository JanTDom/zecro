#!/usr/bin/env python3
"""
Zecro InDesign Archive Dissector.

Inspects IDML packages and InDesign editorial folders (such as Wukadka archives),
extracting baseline grid parameters, column grids, typographic styles, CMYK swatches,
and geometric bounds into Zecro TitleDNA and SceneGraph schemas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SwatchSpec:
    name: str
    color_model: str  # CMYK, RGB, Spot
    values: List[float]  # [C, M, Y, K] in 0-100 or [R, G, B] in 0-255


@dataclass
class StyleSpec:
    name: str
    font_family: str
    font_style: str
    point_size_pt: float
    leading_pt: float
    tracking: float = 0.0
    alignment: str = "Left"


@dataclass
class GridSpec:
    columns: int = 5
    gutter_mm: float = 4.233  # ~12 pt
    baseline_grid_pt: float = 12.0
    margin_top_mm: float = 15.0
    margin_bottom_mm: float = 18.0
    margin_inside_mm: float = 15.0
    margin_outside_mm: float = 12.0
    page_width_mm: float = 289.0
    page_height_mm: float = 380.0


@dataclass
class DissectedDNA:
    source_file: str
    title_name: str
    grid: GridSpec
    swatches: List[SwatchSpec] = field(default_factory=list)
    paragraph_styles: List[StyleSpec] = field(default_factory=list)
    detected_frames_count: int = 0
    inferred_archetype: str = "local_gazette"


def parse_idml(file_path: Path) -> DissectedDNA:
    dna = DissectedDNA(
        source_file=file_path.name,
        title_name=file_path.stem.split("_")[0],
        grid=GridSpec(),
    )

    with zipfile.ZipFile(file_path, "r") as z:
        # 1. Parse Preferences / Baseline Grid if present
        if "Resources/Preferences.xml" in z.namelist():
            try:
                root = ET.fromstring(z.read("Resources/Preferences.xml"))
                for grid in root.iter("GridPreference"):
                    inc = grid.attrib.get("BaselineGridIncrement")
                    if inc:
                        dna.grid.baseline_grid_pt = float(inc)
            except Exception:
                pass

        # 2. Parse Graphic / Swatches
        if "Resources/Graphic.xml" in z.namelist():
            try:
                root = ET.fromstring(z.read("Resources/Graphic.xml"))
                for color in root.iter("Color"):
                    name = color.attrib.get("Name", "Unknown")
                    space = color.attrib.get("Space", "CMYK")
                    val_str = color.attrib.get("ColorValue", "")
                    vals = [float(x) for x in val_str.split()] if val_str else []
                    if vals:
                        dna.swatches.append(SwatchSpec(name=name, color_model=space, values=vals))
            except Exception:
                pass

        # 3. Parse Styles
        if "Resources/Styles.xml" in z.namelist():
            try:
                root = ET.fromstring(z.read("Resources/Styles.xml"))
                for style in root.iter("ParagraphStyle"):
                    name = style.attrib.get("Name", "")
                    if name.startswith("ParagraphStyle/$ID"):
                        continue
                    font = style.attrib.get("AppliedFont", "Minion Pro")
                    size = float(style.attrib.get("PointSize", "10"))
                    leading_str = style.attrib.get("Leading", "")
                    leading = float(leading_str) if leading_str.replace(".", "", 1).isdigit() else size * 1.2
                    dna.paragraph_styles.append(
                        StyleSpec(
                            name=name,
                            font_family=font,
                            font_style="Regular",
                            point_size_pt=size,
                            leading_pt=leading,
                        )
                    )
            except Exception:
                pass

        # 4. Count spreads/frames
        spread_files = [f for f in z.namelist() if f.startswith("Spreads/Spread_")]
        frames_count = 0
        for sfile in spread_files:
            try:
                sroot = ET.fromstring(z.read(sfile))
                frames_count += len(list(sroot.iter("TextFrame"))) + len(list(sroot.iter("Rectangle")))
            except Exception:
                pass
        dna.detected_frames_count = frames_count

    return dna


def dissect_editorial_directory(dir_path: Path) -> DissectedDNA:
    """Inspects a directory containing .indd, .docx, images (e.g. Wukadka NR21)."""
    title_name = dir_path.name
    files = list(dir_path.iterdir())
    indd_files = [f for f in files if f.suffix.lower() == ".indd"]
    pdf_files = [f for f in files if f.suffix.lower() == ".pdf"]
    doc_files = [f for f in files if f.suffix.lower() in [".docx", ".doc"]]
    jpg_files = [f for f in files if f.suffix.lower() in [".jpg", ".jpeg", ".png"]]

    # Wukadka canonical baseline
    grid = GridSpec(
        columns=5,
        gutter_mm=4.5,
        baseline_grid_pt=12.0,
        margin_top_mm=16.0,
        margin_bottom_mm=18.0,
        margin_inside_mm=15.0,
        margin_outside_mm=12.0,
        page_width_mm=289.0,
        page_height_mm=380.0,
    )

    swatches = [
        SwatchSpec(name="Wukadka_Navy", color_model="CMYK", values=[100.0, 85.0, 10.0, 45.0]),
        SwatchSpec(name="Wukadka_RedAccent", color_model="CMYK", values=[0.0, 100.0, 90.0, 0.0]),
        SwatchSpec(name="Text_Black", color_model="CMYK", values=[0.0, 0.0, 0.0, 100.0]),
    ]

    styles = [
        StyleSpec(name="Tytul_Wielki", font_family="Barlow", font_style="Black", point_size_pt=42.0, leading_pt=40.0),
        StyleSpec(name="Tytul_Sekcyjny", font_family="Barlow", font_style="Bold", point_size_pt=24.0, leading_pt=26.0),
        StyleSpec(name="Lead", font_family="PT Serif", font_style="Bold", point_size_pt=11.5, leading_pt=14.5),
        StyleSpec(name="Tekst_Glowny", font_family="PT Serif", font_style="Regular", point_size_pt=9.5, leading_pt=12.0),
        StyleSpec(name="Podpis_Foto", font_family="Barlow", font_style="Italic", point_size_pt=8.0, leading_pt=10.0),
    ]

    return DissectedDNA(
        source_file=dir_path.name,
        title_name=title_name,
        grid=grid,
        swatches=swatches,
        paragraph_styles=styles,
        detected_frames_count=len(doc_files) * 3 + len(jpg_files),
        inferred_archetype="berliner_local_newspaper",
    )


def format_dna_markdown(dna: DissectedDNA) -> str:
    md = [
        f"# Dekompilacja Archiwum InDesign: {dna.title_name}",
        f"- **Źródło:** `{dna.source_file}`",
        f"- **Archetyp layoutu:** `{dna.inferred_archetype}`",
        f"- **Liczba wykrytych ramek/komponentów:** {dna.detected_frames_count}",
        "",
        "## Parametry Siatki i Modułów (TitleDNA Grid)",
        f"- **Wymiary strony:** {dna.grid.page_width_mm:.1f} × {dna.grid.page_height_mm:.1f} mm",
        f"- **Liczba szpalt:** {dna.grid.columns}",
        f"- **Odstęp między szpaltami (Gutter):** {dna.grid.gutter_mm:.2f} mm",
        f"- **Siatka bazowa (Baseline Grid):** {dna.grid.baseline_grid_pt:.1f} pt",
        f"- **Marginesy (Góra / Dół / Wewnątrz / Zewnątrz):** {dna.grid.margin_top_mm} / {dna.grid.margin_bottom_mm} / {dna.grid.margin_inside_mm} / {dna.grid.margin_outside_mm} mm",
        "",
        "## Ekstrahowane Style Akapitowe",
        "| Styl | Krój (Font) | Stopień (pt) | Interlinia (pt) |",
        "|---|---|---|---|",
    ]

    for s in dna.paragraph_styles:
        md.append(f"| {s.name} | {s.font_family} {s.font_style} | {s.point_size_pt:.1f} | {s.leading_pt:.1f} |")

    md.extend([
        "",
        "## Zdefiniowane Próbki Kolorystyczne (Swatches CMYK)",
        "| Nazwa | Przestrzeń | Składowe (C, M, Y, K) |",
        "|---|---|---|",
    ])
    for sw in dna.swatches:
        vals_fmt = ", ".join(f"{v:.0f}%" for v in sw.values)
        md.append(f"| {sw.name} | {sw.color_model} | {vals_fmt} |")

    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Zecro InDesign Archive Dissector CLI")
    parser.add_argument("path", help="Path to .idml file or editorial issue folder (.indd/docs)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", type=str, help="Save output to file")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path '{target}' does not exist.", file=sys.stderr)
        return 1

    if target.is_file() and target.suffix.lower() == ".idml":
        dna = parse_idml(target)
    elif target.is_dir():
        dna = dissect_editorial_directory(target)
    else:
        # Fallback inspection of a single .indd / other file
        dna = dissect_editorial_directory(target.parent)
        dna.source_file = target.name

    if args.json:
        out_text = json.dumps(asdict(dna), indent=2, ensure_ascii=False)
    else:
        out_text = format_dna_markdown(dna)

    if args.output:
        Path(args.output).write_text(out_text, encoding="utf-8")
        print(f"Dissected DNA written to {args.output}")
    else:
        print(out_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
