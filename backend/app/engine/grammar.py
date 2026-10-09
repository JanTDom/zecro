import math
from typing import Tuple, Dict, Any, List
from ..models.schemas import TitleDNA, FormatDNA, GridDNA, TypographyDNA, PaletteDNA, PhotoRulesDNA, TransgressionDef

def create_default_broadsheet_dna() -> TitleDNA:
    return TitleDNA(
        name="The Daily Chronicle (Broadsheet)",
        version=1,
        format=FormatDNA(
            trim_w_mm=350.0,
            trim_h_mm=500.0,
            bleed_mm=3.0,
            margin_top_mm=18.0,
            margin_bottom_mm=18.0,
            margin_left_mm=15.0,
            margin_right_mm=15.0
        ),
        grid=GridDNA(
            columns=6,
            gutter_mm=4.5,
            baseline_grid_pt=10.5,
            rows=14,
            row_gutter_mm=4.0
        ),
        palette=PaletteDNA(
            primary="#111111",
            secondary="#990000",
            accent="#d4af37",
            background="#fcfbf7",
            text="#1f1f1f",
            tint_bg="#f3efe6",
            scrim="rgba(0,0,0,0.65)"
        ),
        photo_rules=PhotoRulesDNA(
            allow_cutout=True,
            allow_full_bleed=True,
            default_treatment="crop",
            min_dpi=250,
            max_photos_per_page=4,
            text_wrap_offset_mm=3.5
        ),
        page_energy_budget=0.8
    )

def create_default_tabloid_dna() -> TitleDNA:
    return TitleDNA(
        name="Gazeta Codzienna (Tabloid/Expressive)",
        version=1,
        format=FormatDNA(
            trim_w_mm=280.0,
            trim_h_mm=390.0,
            bleed_mm=3.0,
            margin_top_mm=14.0,
            margin_bottom_mm=14.0,
            margin_left_mm=10.0,
            margin_right_mm=10.0
        ),
        grid=GridDNA(
            columns=5,
            gutter_mm=4.0,
            baseline_grid_pt=9.5,
            rows=12,
            row_gutter_mm=3.5
        ),
        palette=PaletteDNA(
            primary="#0b0b0b",
            secondary="#d91414",
            accent="#ffcc00",
            background="#ffffff",
            text="#111111",
            tint_bg="#fee",
            scrim="rgba(0,0,0,0.7)"
        ),
        photo_rules=PhotoRulesDNA(
            allow_cutout=True,
            allow_full_bleed=True,
            default_treatment="cutout",
            min_dpi=200,
            max_photos_per_page=3,
            text_wrap_offset_mm=4.0
        ),
        page_energy_budget=1.2
    )

class LayoutGrammar:
    def __init__(self, dna: TitleDNA):
        self.dna = dna
        self._calculate_derived_geometry()

    def _calculate_derived_geometry(self):
        f = self.dna.format
        g = self.dna.grid

        self.printable_w_mm = f.trim_w_mm - (f.margin_left_mm + f.margin_right_mm)
        self.printable_h_mm = f.trim_h_mm - (f.margin_top_mm + f.margin_bottom_mm)

        # Total width minus gutters
        total_gutter_w = (g.columns - 1) * g.gutter_mm
        self.col_w_mm = max(10.0, (self.printable_w_mm - total_gutter_w) / g.columns)

        # Row height
        total_row_gutter_h = (g.rows - 1) * g.row_gutter_mm
        self.row_h_mm = max(10.0, (self.printable_h_mm - total_row_gutter_h) / g.rows)

        # Baseline in mm (1 pt = 0.352778 mm)
        self.baseline_mm = g.baseline_grid_pt * 0.352778

    def col_to_x_mm(self, col_idx: int) -> float:
        """Returns X coordinate in mm from trim left margin for given 0-indexed column."""
        return self.dna.format.margin_left_mm + col_idx * (self.col_w_mm + self.dna.grid.gutter_mm)

    def row_to_y_mm(self, row_idx: int) -> float:
        """Returns Y coordinate in mm from trim top margin for given 0-indexed row."""
        return self.dna.format.margin_top_mm + row_idx * (self.row_h_mm + self.dna.grid.row_gutter_mm)

    def span_to_w_mm(self, col_span: int) -> float:
        """Returns width in mm for a given number of spanned columns (including internal gutters)."""
        col_span = max(1, min(col_span, self.dna.grid.columns))
        return col_span * self.col_w_mm + (col_span - 1) * self.dna.grid.gutter_mm

    def span_to_h_mm(self, row_span: int) -> float:
        """Returns height in mm for a given number of spanned rows (including internal gutters)."""
        row_span = max(1, min(row_span, self.dna.grid.rows))
        return row_span * self.row_h_mm + (row_span - 1) * self.dna.grid.row_gutter_mm

    def snap_to_baseline(self, y_mm: float) -> float:
        """Snaps a vertical coordinate to the nearest baseline grid step."""
        top = self.dna.format.margin_top_mm
        if y_mm <= top:
            return top
        rel_y = y_mm - top
        snapped_rel = round(rel_y / self.baseline_mm) * self.baseline_mm
        return top + snapped_rel

    def get_role_style(self, role: str, type_scale_key: str = "headline_l") -> Dict[str, Any]:
        """Resolves typography styling, font size and line height according to DNA."""
        typo = self.dna.typography
        scales = typo.scales.model_dump()
        role_cfg = typo.roles.get(role, {})

        font_family_key = role_cfg.get("font", "body")
        font_family = typo.fonts.get(font_family_key, typo.fonts.get("body", "serif"))
        font_size_pt = scales.get(type_scale_key, scales.get(role, 10.0))
        multiplier = role_cfg.get("line_height_multiplier", 1.2)
        line_height_pt = font_size_pt * multiplier

        return {
            "font_family": font_family,
            "font_size_pt": font_size_pt,
            "line_height_pt": line_height_pt,
            "font_weight": role_cfg.get("weight", "normal"),
            "case": role_cfg.get("case", "normal"),
            "align": "justify" if role == "body" else ("left" if role in ["headline", "lead", "kicker"] else "center"),
            "color": self.dna.palette.text if role in ["body", "lead"] else self.dna.palette.primary,
            "bg_color": None
        }
