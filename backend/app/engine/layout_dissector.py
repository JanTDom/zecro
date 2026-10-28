"""Layout Dissector: Decompiles IDML packages, InDesign spreads, and PDF files
into native Zecro SceneGraph and TitleDNA contracts.
"""
from __future__ import annotations

import io
import math
import os
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..models.schemas import (
    Element, ElementStyle, FormatDNA, Frame, GridDNA,
    PageMeta, PaletteDNA, PhotoRulesDNA, SceneGraph,
    TitleDNA, TypographyDNA, TypographyScaleDNA
)

PT_TO_MM = 25.4 / 72.0
MM_TO_PT = 72.0 / 25.4


def _pt_to_mm(val_pt: float) -> float:
    return round(float(val_pt) * PT_TO_MM, 2)


def _mm_to_pt(val_mm: float) -> float:
    return round(float(val_mm) * MM_TO_PT, 2)


def _extract_bounds(node: ET.Element) -> Optional[Tuple[float, float, float, float]]:
    """Extract top_pt, left_pt, bottom_pt, right_pt from either GeometricBounds or PathGeometry."""
    bnds_str = node.attrib.get("GeometricBounds", "")
    if bnds_str:
        pts = [float(x) for x in bnds_str.split()]
        if len(pts) >= 4:
            return pts[0], pts[1], pts[2], pts[3]

    # PathGeometry anchor points
    anchors: List[Tuple[float, float]] = []
    for pt_node in node.iter("PathPointType"):
        anchor = pt_node.attrib.get("Anchor", "")
        if anchor:
            coords = [float(c) for c in anchor.split()]
            if len(coords) >= 2:
                anchors.append((coords[0], coords[1]))

    if len(anchors) >= 2:
        xs = [p[0] for p in anchors]
        ys = [p[1] for p in anchors]
        return min(ys), min(xs), max(ys), max(xs)

    return None


@dataclass
class DissectedStory:
    story_id: str
    text: str
    style_names: List[str] = field(default_factory=list)


class LayoutDissector:
    """Dissects external publication files into structured SceneGraph and TitleDNA."""

    def dissect_idml(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
        *,
        title_name: Optional[str] = None
    ) -> Tuple[SceneGraph, TitleDNA, Dict[str, Any]]:
        """Decompiles an Adobe InDesign IDML archive into SceneGraph and TitleDNA."""
        if isinstance(source, (str, Path)):
            zf = zipfile.ZipFile(source, "r")
            filename = Path(source).name
        elif isinstance(source, bytes):
            zf = zipfile.ZipFile(io.BytesIO(source), "r")
            filename = "upload.idml"
        else:
            zf = zipfile.ZipFile(source, "r")
            filename = "upload.idml"

        inferred_name = title_name or filename.split(".")[0].replace("_", " ")

        with zf:
            namelist = zf.namelist()

            # 1. Page Format & Preferences
            page_w_mm, page_h_mm = 280.0, 400.0  # Tabloid / Berliner default
            baseline_pt = 10.5
            margin_top_mm, margin_bottom_mm = 15.0, 15.0
            margin_left_mm, margin_right_mm = 12.0, 12.0

            if "Resources/Preferences.xml" in namelist:
                try:
                    pref_root = ET.fromstring(zf.read("Resources/Preferences.xml"))
                    for grid in pref_root.iter("GridPreference"):
                        inc = grid.attrib.get("BaselineGridIncrement")
                        if inc:
                            baseline_pt = float(inc)
                except Exception:
                    pass

            # 2. Extract Palette / Swatches
            swatches_cmyk: Dict[str, str] = {}
            if "Resources/Graphic.xml" in namelist:
                try:
                    groot = ET.fromstring(zf.read("Resources/Graphic.xml"))
                    for color in groot.iter("Color"):
                        cname = color.attrib.get("Name", "")
                        val_str = color.attrib.get("ColorValue", "")
                        if val_str:
                            vals = [float(v) for v in val_str.split()]
                            if len(vals) >= 4:
                                swatches_cmyk[cname] = f"cmyk({vals[0]:.0f}%, {vals[1]:.0f}%, {vals[2]:.0f}%, {vals[3]:.0f}%)"
                except Exception:
                    pass

            # 3. Extract Stories content
            stories: Dict[str, DissectedStory] = {}
            for item in namelist:
                if item.startswith("Stories/Story_") and item.endswith(".xml"):
                    try:
                        sroot = ET.fromstring(zf.read(item))
                        sid = item.replace("Stories/Story_", "").replace(".xml", "")
                        # Gather all text content inside <Content> tags
                        pieces = []
                        styles_found = []
                        for node in sroot.iter():
                            if node.tag == "Content" and node.text:
                                pieces.append(node.text)
                            elif node.tag == "ParagraphStyleRange":
                                pst = node.attrib.get("AppliedParagraphStyle", "")
                                if pst and pst not in styles_found:
                                    styles_found.append(pst)
                        full_text = "".join(pieces).strip()
                        stories[sid] = DissectedStory(story_id=sid, text=full_text, style_names=styles_found)
                    except Exception:
                        pass

            # 4. Extract Spreads & Geometry
            spread_files = sorted([f for f in namelist if f.startswith("Spreads/Spread_") and f.endswith(".xml")])
            elements: List[Element] = []
            spread_meta: Dict[str, Any] = {}

            if spread_files:
                # Dissect primary spread (usually first spread or cover)
                target_spread = spread_files[0]
                sroot = ET.fromstring(zf.read(target_spread))

                # Page dimensions from spread if available
                for page_node in sroot.iter("Page"):
                    bnds = page_node.attrib.get("GeometricBounds", "")
                    if bnds:
                        pts = [float(x) for x in bnds.split()]
                        if len(pts) == 4:
                            h_pt = abs(pts[2] - pts[0])
                            w_pt = abs(pts[3] - pts[1])
                            if w_pt > 50 and h_pt > 50:
                                page_w_mm = _pt_to_mm(w_pt)
                                page_h_mm = _pt_to_mm(h_pt)

                    for mg in page_node.iter("MarginPreference"):
                        if mg.attrib.get("Top"):
                            margin_top_mm = _pt_to_mm(float(mg.attrib["Top"]))
                        if mg.attrib.get("Bottom"):
                            margin_bottom_mm = _pt_to_mm(float(mg.attrib["Bottom"]))
                        if mg.attrib.get("Left"):
                            margin_left_mm = _pt_to_mm(float(mg.attrib["Left"]))
                        if mg.attrib.get("Right"):
                            margin_right_mm = _pt_to_mm(float(mg.attrib["Right"]))

                # Parse TextFrames
                for tf in sroot.iter("TextFrame"):
                    elem_id = tf.attrib.get("Self", f"tf_{uuid.uuid4().hex[:6]}").replace("u_", "")
                    bounds = _extract_bounds(tf)
                    if not bounds:
                        continue
                    top_pt, left_pt, bottom_pt, right_pt = bounds
                    # Transform coordinates relative to spread page origin
                    x_mm = max(0.0, _pt_to_mm(left_pt))
                    y_mm = max(0.0, _pt_to_mm(top_pt))
                    w_mm = max(4.0, _pt_to_mm(right_pt - left_pt))
                    h_mm = max(4.0, _pt_to_mm(bottom_pt - top_pt))

                    # Story text
                    parent_story = tf.attrib.get("ParentStory", "").replace("u_", "")
                    story_obj = stories.get(parent_story)
                    text_content = story_obj.text if story_obj else ""

                    # Font size estimation from contents or styles
                    font_size_pt = 10.0
                    for fs_node in tf.iter("CharacterStyleRange"):
                        if "PointSize" in fs_node.attrib:
                            try:
                                font_size_pt = float(fs_node.attrib["PointSize"])
                                break
                            except ValueError:
                                pass

                    # Infer semantic role
                    role = self._infer_text_role(text_content, font_size_pt, y_mm, page_h_mm, w_mm)

                    style = ElementStyle(
                        font_size_pt=font_size_pt,
                        font_weight="bold" if font_size_pt >= 20.0 or role == "headline" else "normal",
                        line_height_pt=round(font_size_pt * 1.2, 1),
                        align="left",
                    )

                    elements.append(
                        Element(
                            id=elem_id,
                            role=role,
                            text_content=text_content or f"[{role.upper()}]",
                            frame=Frame(x=round(x_mm, 2), y=round(y_mm, 2), w=round(w_mm, 2), h=round(h_mm, 2)),
                            z=2 if role == "headline" else 3,
                            style=style,
                            importance=0.9 if role == "headline" else 0.5,
                        )
                    )

                # Parse Rectangles / Polygons / Images / Graphic Boxes
                for rect in list(sroot.iter("Rectangle")) + list(sroot.iter("Polygon")):
                    elem_id = rect.attrib.get("Self", f"rect_{uuid.uuid4().hex[:6]}").replace("u_", "")
                    bounds = _extract_bounds(rect)
                    if not bounds:
                        continue
                    top_pt, left_pt, bottom_pt, right_pt = bounds
                    x_mm = max(0.0, _pt_to_mm(left_pt))
                    y_mm = max(0.0, _pt_to_mm(top_pt))
                    w_mm = max(4.0, _pt_to_mm(right_pt - left_pt))
                    h_mm = max(4.0, _pt_to_mm(bottom_pt - top_pt))

                    # Check if it contains an image link
                    has_image = bool(list(rect.iter("Image"))) or bool(list(rect.iter("Link")))
                    fill_color = rect.attrib.get("FillColor", "")

                    if has_image:
                        role = "photo"
                        treatment = "crop"
                        # High area at the top might be masthead / logo
                        if y_mm < 35.0 and w_mm > page_w_mm * 0.5:
                            role = "logo"
                        elements.append(
                            Element(
                                id=elem_id,
                                role=role,
                                frame=Frame(x=round(x_mm, 2), y=round(y_mm, 2), w=round(w_mm, 2), h=round(h_mm, 2)),
                                z=1 if role == "photo" else 4,
                                treatment=treatment,
                                importance=0.85 if role == "photo" else 0.95,
                            )
                        )
                    elif fill_color and fill_color != "Color/None" and fill_color != "Color/Paper":
                        # Colored band or tint plate
                        role = "band" if h_mm <= 12.0 else "infobox"
                        elements.append(
                            Element(
                                id=elem_id,
                                role=role,
                                frame=Frame(x=round(x_mm, 2), y=round(y_mm, 2), w=round(w_mm, 2), h=round(h_mm, 2)),
                                z=0 if role == "band" else 1,
                                treatment="tinted",
                                style=ElementStyle(bg_color=swatches_cmyk.get(fill_color, "#eceae4")),
                                importance=0.4,
                            )
                        )

            # Sort elements by Z and position
            elements.sort(key=lambda e: (e.z, e.frame.y, e.frame.x))

            # Build PageMeta
            page_meta = PageMeta(
                trim=[page_w_mm, page_h_mm],
                bleed_mm=3.0,
                safe_margin_mm=min(margin_top_mm, margin_left_mm),
                grid={"cols": 5 if page_w_mm < 300 else 6, "gutter_mm": 4.5, "baseline_mm": baseline_pt * PT_TO_MM},
            )

            scene_graph = SceneGraph(page=page_meta, elements=elements, metadata={"source_file": filename, "format": "idml"})

            # Build TitleDNA
            title_dna = TitleDNA(
                name=f"{inferred_name} DNA",
                format=FormatDNA(
                    trim_w_mm=page_w_mm,
                    trim_h_mm=page_h_mm,
                    margin_top_mm=margin_top_mm,
                    margin_bottom_mm=margin_bottom_mm,
                    margin_left_mm=margin_left_mm,
                    margin_right_mm=margin_right_mm,
                ),
                grid=GridDNA(
                    columns=5 if page_w_mm < 300 else 6,
                    gutter_mm=4.5,
                    baseline_grid_pt=baseline_pt,
                ),
                palette=PaletteDNA(
                    primary=swatches_cmyk.get("Primary", "#111111"),
                    secondary=swatches_cmyk.get("Secondary", "#c91818"),
                ),
            )

            raw_meta = {
                "detected_elements_count": len(elements),
                "stories_count": len(stories),
                "swatches": swatches_cmyk,
                "baseline_pt": baseline_pt,
            }

            return scene_graph, title_dna, raw_meta

    def dissect_pdf(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
        *,
        title_name: Optional[str] = None
    ) -> Tuple[SceneGraph, TitleDNA, Dict[str, Any]]:
        """Extracts text runs and page geometry from a PDF file using pypdf."""
        import pypdf

        if isinstance(source, (str, Path)):
            reader = pypdf.PdfReader(str(source))
            filename = Path(source).name
        elif isinstance(source, bytes):
            reader = pypdf.PdfReader(io.BytesIO(source))
            filename = "upload.pdf"
        else:
            reader = pypdf.PdfReader(source)
            filename = "upload.pdf"

        inferred_name = title_name or filename.split(".")[0].replace("_", " ")

        if not reader.pages:
            raise ValueError("PDF has no pages")

        page = reader.pages[0]
        # Dimensions: prefer TrimBox or CropBox (trim size) over MediaBox (which includes bleed/slug)
        box = getattr(page, "trimbox", None) or getattr(page, "cropbox", None) or page.mediabox
        pw_pt = float(box.width)
        ph_pt = float(box.height)
        page_w_mm = _pt_to_mm(pw_pt)
        page_h_mm = _pt_to_mm(ph_pt)

        text_runs: List[Dict[str, Any]] = []

        def visitor(text, cm, tm, font_dict, font_size):
            cleaned = text.strip()
            if cleaned and font_size > 0:
                # In PDF, tm[4] = x, tm[5] = y (from bottom-left origin)
                x_pt = tm[4]
                y_pt = ph_pt - tm[5]  # convert to top-left origin
                text_runs.append({
                    "text": cleaned,
                    "x_mm": _pt_to_mm(x_pt),
                    "y_mm": _pt_to_mm(y_pt),
                    "size_pt": float(font_size),
                })

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:
            pass

        # Cluster text runs into elements
        elements: List[Element] = []
        if text_runs:
            # Group text by vertical proximity and font size
            text_runs.sort(key=lambda r: (r["y_mm"], r["x_mm"]))
            current_cluster: List[Dict[str, Any]] = []

            for r in text_runs:
                if not current_cluster:
                    current_cluster.append(r)
                else:
                    prev = current_cluster[-1]
                    dy = abs(r["y_mm"] - prev["y_mm"])
                    dsize = abs(r["size_pt"] - prev["size_pt"])
                    if dy < 15.0 and dsize < 3.0:
                        current_cluster.append(r)
                    else:
                        elem = self._cluster_to_element(current_cluster, page_w_mm, page_h_mm)
                        if elem:
                            elements.append(elem)
                        current_cluster = [r]

            if current_cluster:
                elem = self._cluster_to_element(current_cluster, page_w_mm, page_h_mm)
                if elem:
                    elements.append(elem)

        # Detect images from page.images if any
        try:
            for i, img in enumerate(getattr(page, "images", [])):
                elements.append(
                    Element(
                        id=f"pdf_img_{i+1}",
                        role="photo",
                        frame=Frame(x=15.0, y=40.0 + i * 80.0, w=page_w_mm * 0.6, h=70.0),
                        z=1,
                        importance=0.85 if i == 0 else 0.6,
                    )
                )
        except Exception:
            pass

        page_meta = PageMeta(
            trim=[page_w_mm, page_h_mm],
            bleed_mm=3.0,
            safe_margin_mm=12.0,
            grid={"cols": 5 if page_w_mm < 300 else 6, "gutter_mm": 4.5, "baseline_mm": 4.2},
        )

        scene = SceneGraph(page=page_meta, elements=elements, metadata={"source_file": filename, "format": "pdf"})

        dna = TitleDNA(
            name=f"{inferred_name} DNA",
            format=FormatDNA(trim_w_mm=page_w_mm, trim_h_mm=page_h_mm),
            grid=GridDNA(columns=5 if page_w_mm < 300 else 6, gutter_mm=4.5),
        )

        return scene, dna, {"text_runs_count": len(text_runs), "elements_count": len(elements)}

    def _cluster_to_element(
        self,
        cluster: List[Dict[str, Any]],
        page_w_mm: float,
        page_h_mm: float
    ) -> Optional[Element]:
        if not cluster:
            return None
        min_x = min(r["x_mm"] for r in cluster)
        min_y = min(r["y_mm"] for r in cluster)
        max_x = max(r["x_mm"] for r in cluster) + 40.0  # estimate line width
        max_y = max(r["y_mm"] for r in cluster) + 10.0
        avg_size = sum(r["size_pt"] for r in cluster) / len(cluster)
        full_text = " ".join(r["text"] for r in cluster)

        w = min(page_w_mm - min_x, max(20.0, max_x - min_x))
        h = min(page_h_mm - min_y, max(8.0, max_y - min_y))

        role = self._infer_text_role(full_text, avg_size, min_y, page_h_mm, w)

        return Element(
            id=f"elem_{uuid.uuid4().hex[:6]}",
            role=role,
            text_content=full_text,
            frame=Frame(x=round(min_x, 2), y=round(min_y, 2), w=round(w, 2), h=round(h, 2)),
            z=2,
            style=ElementStyle(font_size_pt=round(avg_size, 1), font_weight="bold" if avg_size >= 18.0 else "normal"),
            importance=0.9 if role == "headline" else 0.5,
        )

    def _infer_text_role(
        self,
        text: str,
        font_size_pt: float,
        y_mm: float,
        page_h_mm: float,
        width_mm: float
    ) -> str:
        """Heuristic semantic role inference for editorial text blocks."""
        cleaned = text.strip()
        word_count = len(cleaned.split())

        # Top banner check
        if y_mm < 30.0 and font_size_pt >= 32.0:
            return "masthead"
        if font_size_pt >= 24.0 or (font_size_pt >= 18.0 and word_count < 14 and y_mm < page_h_mm * 0.6):
            return "headline"
        if font_size_pt >= 13.0 and word_count < 35:
            return "lead"
        if font_size_pt <= 9.0 and word_count < 15 and y_mm > page_h_mm * 0.8:
            return "folio"
        if font_size_pt <= 8.5 and word_count < 25:
            return "caption"
        if font_size_pt >= 9.5 and cleaned.isupper() and word_count <= 4:
            return "kicker"
        return "body"
