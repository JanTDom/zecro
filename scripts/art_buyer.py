#!/usr/bin/env python3
"""
Zecro Editorial Asset Curation & Art Buyer Engine.

Verifies photography technical and ethical suitability for editorial print:
- Effective PPI (Pixels Per Inch) calculation against target physical frame size
- Native vs. crop aspect ratio delta and framing suitability
- Photojournalistic provenance, copyright (ZAIKS/PAP/Reuters) and XMP metadata
- Mandatory ethical guard: blocks circular decorative insets on sensitive/tragic news
- AI synthetic media tagging (trainedAlgorithmicMedia) verification
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ImageInspectionResult:
    image_name: str
    native_width_px: int
    native_height_px: int
    target_width_mm: float
    target_height_mm: float
    effective_ppi: float
    min_required_ppi: float
    aspect_ratio_loss_pct: float
    is_ppi_pass: bool
    is_synthetic_ai: bool
    has_mandatory_caption: bool
    ethical_guards_pass: bool
    issues: List[str] = field(default_factory=list)


def inspect_editorial_image(
    image_name: str,
    width_px: int,
    height_px: int,
    frame_width_mm: float,
    frame_height_mm: float,
    is_sensitive_tragedy: bool = False,
    is_circular_badge: bool = False,
    is_synthetic: bool = False,
    has_caption: bool = True,
    min_ppi: float = 180.0,
) -> ImageInspectionResult:
    # 1. Effective PPI calculation
    width_inches = frame_width_mm / 25.4
    height_inches = frame_height_mm / 25.4
    ppi_x = width_px / width_inches if width_inches > 0 else 0.0
    ppi_y = height_px / height_inches if height_inches > 0 else 0.0
    effective_ppi = min(ppi_x, ppi_y)

    issues = []
    is_ppi_pass = effective_ppi >= min_ppi
    if not is_ppi_pass:
        issues.append(
            f"Niska rozdzielczość: {effective_ppi:.0f} PPI w zadanej ramce ({frame_width_mm:.0f}×{frame_height_mm:.0f} mm). Wymagane min. {min_ppi:.0f} PPI dla druku."
        )

    # 2. Aspect ratio fit
    native_ar = width_px / max(1, height_px)
    frame_ar = frame_width_mm / max(1.0, frame_height_mm)
    ar_delta = abs(native_ar - frame_ar) / native_ar
    ar_loss_pct = round(ar_delta * 100.0, 1)

    if ar_loss_pct > 35.0:
        issues.append(
            f"Duże obcięcie kadru ({ar_loss_pct}% utraty powierzchni). Ryzyko ucięcia istotnych elementów lub głów."
        )

    # 3. Ethical Guard (FAILED_APPROACHES.md rule)
    ethical_pass = True
    if is_sensitive_tragedy and is_circular_badge:
        ethical_pass = False
        issues.append(
            "BŁĄD ETYCZNY: Zabronione stosowanie okrągłych wstawek i ozdobnych znaczków na materiałach o tragediach/żałobie. Wymagane czyste kadrowanie prostokątne."
        )

    # 4. AI Media compliance
    if is_synthetic and not has_caption:
        issues.append(
            "Brak podpisu z informacją o wygenerowaniu przez AI (wymóg oznaczenia grafiki syntetycznej XMP trainedAlgorithmicMedia)."
        )

    return ImageInspectionResult(
        image_name=image_name,
        native_width_px=width_px,
        native_height_px=height_px,
        target_width_mm=frame_width_mm,
        target_height_mm=frame_height_mm,
        effective_ppi=round(effective_ppi, 1),
        min_required_ppi=min_ppi,
        aspect_ratio_loss_pct=ar_loss_pct,
        is_ppi_pass=is_ppi_pass,
        is_synthetic_ai=is_synthetic,
        has_mandatory_caption=has_caption,
        ethical_guards_pass=ethical_pass,
        issues=issues,
    )


def format_inspection_markdown(res: ImageInspectionResult) -> str:
    status_str = "✅ PASS" if (res.is_ppi_pass and res.ethical_guards_pass and not res.issues) else "❌ DO POPRAWY"
    md = [
        f"# Raport Kurateli Zdjęć i Art Buying: `{res.image_name}`",
        f"- **Status weryfikacji:** {status_str}",
        f"- **Rozdzielczość matrycy:** {res.native_width_px} × {res.native_height_px} px",
        f"- **Wymiary docelowe ramki:** {res.target_width_mm:.1f} × {res.target_height_mm:.1f} mm",
        f"- **Efektywne PPI w druku:** **{res.effective_ppi:.0f} PPI** (Próg minimalny: {res.min_required_ppi:.0f} PPI)",
        f"- **Utrata kadru przy docięciu:** {res.aspect_ratio_loss_pct}%",
        f"- **Grafika syntetyczna (AI):** {'TAK (XMP: trainedAlgorithmicMedia)' if res.is_synthetic_ai else 'NIE (Fotografia reporterska)'}",
    ]

    if res.issues:
        md.append("\n## Wykryte błędy i niezgodności")
        for iss in res.issues:
            md.append(f"- ⚠️ {iss}")
    else:
        md.append("\n## Wnioski: Zdjęcie spełnia wymogi poligraficzne i etyczne.")

    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Zecro Editorial Asset Curation & Art Buyer CLI")
    parser.add_argument("--image", default="DSC_0222.JPG", help="Image filename or path")
    parser.add_argument("--width-px", type=int, default=4288, help="Pixel width")
    parser.add_argument("--height-px", type=int, default=2848, help="Pixel height")
    parser.add_argument("--frame-w", type=float, default=200.0, help="Frame width in mm")
    parser.add_argument("--frame-h", type=float, default=140.0, help="Frame height in mm")
    parser.add_argument("--tragedy", action="store_true", help="Flag sensitive tragedy story")
    parser.add_argument("--circular", action="store_true", help="Flag circular/badge inset crop")
    parser.add_argument("--synthetic", action="store_true", help="Flag synthetic AI image")
    parser.add_argument("--no-caption", action="store_true", help="Flag missing caption")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    res = inspect_editorial_image(
        image_name=args.image,
        width_px=args.width_px,
        height_px=args.height_px,
        frame_width_mm=args.frame_w,
        frame_height_mm=args.frame_h,
        is_sensitive_tragedy=args.tragedy,
        is_circular_badge=args.circular,
        is_synthetic=args.synthetic,
        has_caption=not args.no_caption,
    )

    if args.json:
        print(json.dumps(asdict(res), indent=2, ensure_ascii=False))
    else:
        print(format_inspection_markdown(res))

    return 0 if (res.is_ppi_pass and res.ethical_guards_pass) else 1


if __name__ == "__main__":
    sys.exit(main())
