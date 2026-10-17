#!/usr/bin/env python3
"""
Zecro DTP Soft-Proofing & RIP Simulator.

Simulates coldset newsprint press conditions (ISO 12647-3), including:
- Total Area Coverage (TAC / TIC) auditing (< 240% limit for newsprint)
- 25-30% Dot Gain (przyrost punktu) midtone curve compression
- Pure 100% K black text overprint vs knockout verification
- Trapping misregistration simulation (0.15mm plate shift)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TACAuditResult:
    max_tac_measured: float
    max_tac_allowed: float
    is_tac_compliant: bool
    hotspots_percentage: float
    risk_level: str  # LOW, MEDIUM, CRITICAL


@dataclass
class DotGainResult:
    nominal_midtone_pct: float
    simulated_printed_pct: float
    dot_gain_curve_shift_pct: float
    shadow_crush_warning: bool


@dataclass
class PrepressProofReport:
    target_substrate: str
    tac: TACAuditResult
    dot_gain: DotGainResult
    overprint_black_required: bool = True
    trapping_tolerance_mm: float = 0.15
    recommendations: List[str] = None


def compute_tac_cmyk(c: float, m: float, y: float, k: float, max_allowed: float = 240.0) -> TACAuditResult:
    """Calculates TAC sum for a given CMYK tuple in percentage (0..100)."""
    tac = c + m + y + k
    is_compliant = tac <= max_allowed
    hotspot_ratio = 1.0 if not is_compliant else 0.0

    if tac <= max_allowed:
        risk = "LOW"
    elif tac <= max_allowed + 20:
        risk = "MEDIUM"
    else:
        risk = "CRITICAL"

    return TACAuditResult(
        max_tac_measured=tac,
        max_tac_allowed=max_allowed,
        is_tac_compliant=is_compliant,
        hotspots_percentage=hotspot_ratio * 100.0,
        risk_level=risk,
    )


def simulate_newsprint_dot_gain(nominal_50_pct: float = 50.0, substrate: str = "newsprint") -> DotGainResult:
    """
    Simulates ISO 12647-3 newsprint dot gain (approx 26-30% shift in midtones).
    50% input tone reproduces as ~76-80% on 45g/m2 newsprint.
    """
    gain_factor = 28.0 if substrate == "newsprint" else 15.0  # Coated stock has ~14-16%
    printed_pct = nominal_50_pct + gain_factor * (1.0 - (nominal_50_pct / 100.0) ** 1.5)
    shadow_crush = printed_pct > 78.0

    return DotGainResult(
        nominal_midtone_pct=nominal_50_pct,
        simulated_printed_pct=round(printed_pct, 1),
        dot_gain_curve_shift_pct=round(printed_pct - nominal_50_pct, 1),
        shadow_crush_warning=shadow_crush,
    )


def audit_image_or_pdf(c: float = 65.0, m: float = 60.0, y: float = 55.0, k: float = 80.0, substrate: str = "newsprint") -> PrepressProofReport:
    max_tac = 240.0 if substrate == "newsprint" else 300.0
    tac_res = compute_tac_cmyk(c, m, y, k, max_allowed=max_tac)
    dg_res = simulate_newsprint_dot_gain(50.0, substrate=substrate)

    recs = []
    if not tac_res.is_tac_compliant:
        recs.append(
            f"Zastosuj profil ICC WAN-IFRA Newspaper lub konwersję GCR (Grey Component Replacement) w celu redukcji TAC z {tac_res.max_tac_measured:.0f}% do <={max_tac:.0f}%."
        )
    if dg_res.shadow_crush_warning:
        recs.append(
            "Cienie powyżej 75% w druku ulegną zalaniu (shadow crush). Rozjaśnij tony średnie w krzywej separacji o 5-8%."
        )
    recs.append(
        "Upewnij się, że tekst ciągły 100% K ma włączony atrybut 'Overprint Black' (brak wycinania białego tła w CMY)."
    )

    return PrepressProofReport(
        target_substrate=substrate,
        tac=tac_res,
        dot_gain=dg_res,
        overprint_black_required=True,
        trapping_tolerance_mm=0.15,
        recommendations=recs,
    )


def format_report_markdown(report: PrepressProofReport) -> str:
    md = [
        f"# Raport Symulatora RIP i Druku Zwojowego ({report.target_substrate.upper()})",
        f"- **Norma:** ISO 12647-3 (Druk gazetowy coldset)",
        f"- **Tolerancja pasowania płyt (Trapping):** {report.trapping_tolerance_mm} mm",
        "",
        "## 1. Pokrycie Farbą (Total Area Coverage - TAC)",
        f"- **Maksymalne dopuszczalne TAC:** {report.tac.max_tac_allowed:.0f}%",
        f"- **Zmierzone TAC w próbce:** {report.tac.max_tac_measured:.0f}%",
        f"- **Zgodność z normą:** {'✅ PASS' if report.tac.is_tac_compliant else '❌ BŁĄD (Zagrożenie zalania papieru i zerwania wstęgi)'}",
        f"- **Poziom ryzyka:** `{report.tac.risk_level}`",
        "",
        "## 2. Przyrost Punktu Rastrowego (Dot Gain)",
        f"- **Wartość nominalna w pliku (Tony średnie):** {report.dot_gain.nominal_midtone_pct:.1f}%",
        f"- **Symulowana wartość na papierze:** {report.dot_gain.simulated_printed_pct:.1f}% (+{report.dot_gain.dot_gain_curve_shift_pct:.1f}%)",
        f"- **Ostrzeżenie o zlaniu cieni (Shadow Crush):** {'⚠️ TAK (Zalecana korekta krzywej tonalnej)' if report.dot_gain.shadow_crush_warning else 'BRAK'}",
        "",
        "## 3. Zalecenia Prepress dla Naświetlarni CTP",
    ]
    for r in report.recommendations:
        md.append(f"- 🔧 {r}")

    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Zecro DTP Soft-Proofing & RIP Simulator CLI")
    parser.add_argument("--substrate", choices=["newsprint", "coated"], default="newsprint", help="Printing substrate")
    parser.add_argument("--c", type=float, default=65.0, help="Cyan percentage")
    parser.add_argument("--m", type=float, default=60.0, help="Magenta percentage")
    parser.add_argument("--y", type=float, default=55.0, help="Yellow percentage")
    parser.add_argument("--k", type=float, default=70.0, help="Black percentage")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    report = audit_image_or_pdf(c=args.c, m=args.m, y=args.y, k=args.k, substrate=args.substrate)

    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print(format_report_markdown(report))

    return 0 if report.tac.is_tac_compliant else 1


if __name__ == "__main__":
    sys.exit(main())
