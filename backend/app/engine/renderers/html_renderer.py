import html
from typing import Optional
from ...models.schemas import SceneGraph, TitleDNA
import re
from ..image_ops import contour_to_css_polygon, contour_to_svg_path, offset_contour_polygon


def _unit_path(outer, holes, w, h):
    rings = [outer, *(holes or [])]
    parts = []
    for ring in rings:
        if len(ring) < 3:
            continue
        parts.append("M " + " L ".join(f"{p[0] / w:.4f} {p[1] / h:.4f}" for p in ring) + " Z")
    return " ".join(parts)

class HTMLRenderer:
    def __init__(self, dna: Optional[TitleDNA] = None):
        self.dna = dna

    def render(self, sg: SceneGraph) -> str:
        """
        Renders SceneGraph to production-ready HTML/CSS Paged Media document.
        """
        pw = sg.page.trim[0]
        ph = sg.page.trim[1]
        bg_col = self.dna.palette.background if self.dna else "#fcfbf7"
        text_col = self.dna.palette.text if self.dna else "#1a1a1a"

        html_elements = []
        advertorial_labels = sg.metadata.get("advertorial_labels") or {}

        for elem in sorted(sg.elements, key=lambda e: e.z):
            fr = elem.frame
            st = elem.style

            # Box styling
            transform = f"transform: rotate({fr.rotation_deg}deg);" if abs(fr.rotation_deg) > 0.1 else ""
            pos_style = (
                f"position: absolute; left: {fr.x:.2f}mm; top: {fr.y:.2f}mm; "
                f"width: {fr.w:.2f}mm; height: {fr.h:.2f}mm; z-index: {elem.z}; {transform}"
            )

            if elem.role == "photo":
                clip_css = ""
                wrap_css = ""
                clip_svg = ""
                if elem.treatment == "cutout" and elem.contour_points:
                    # Holes need an even-odd clip; CSS polygon() cannot express
                    # them, so use an objectBoundingBox SVG clipPath.
                    clip_svg = (f'<svg width="0" height="0" style="position:absolute"><clipPath id="clip-{elem.id}" '
                                f'clipPathUnits="objectBoundingBox"><path clip-rule="evenodd" d="{_unit_path(elem.contour_points, elem.contour_holes, fr.w, fr.h)}"/></clipPath></svg>')
                    clip_css = f"clip-path: url(#clip-{elem.id}); -webkit-clip-path: url(#clip-{elem.id});"
                    wrap_poly = contour_to_css_polygon(
                        offset_contour_polygon(elem.contour_points, (elem.text_wrap.offset_mm if elem.text_wrap else 3.0)),
                        fr.w,
                        fr.h,
                    )
                    # shape-outside follows the outer ring (text never flows
                    # into an enclosed hole), same as InDesign's contour wrap.
                    wrap_css = f"shape-outside: {wrap_poly}; -webkit-shape-outside: {wrap_poly}; float: left;"
                position_css = "object-position: 50% 50%;"
                if elem.crop_box:
                    l, t, r, b = elem.crop_box
                    px = 50.0 if (1 - (r - l)) < 1e-6 else l / (1 - (r - l)) * 100
                    py = 50.0 if (1 - (b - t)) < 1e-6 else t / (1 - (b - t)) * 100
                    position_css = f"object-position: {px:.2f}% {py:.2f}%;"

                img_src = elem.image_url if elem.image_url else ""
                if img_src:
                    content_html = f'<img src="{html.escape(img_src)}" style="width: 100%; height: 100%; object-fit: cover; {position_css} {clip_css} {wrap_css}" alt="Photo"/>{clip_svg}'
                else:
                    content_html = f'<div style="width: 100%; height: 100%; background: #e0ded8; display: flex; align-items: center; justify-content: center; color: #777; font-family: sans-serif; font-size: 10pt; {clip_css} {wrap_css}">Photo: {elem.id}</div>'

                label = advertorial_labels.get(elem.id) if isinstance(advertorial_labels, dict) else None
                badge = f'<span class="advertorial-label">{html.escape(str(label))}</span>' if label else ''
                html_elements.append(f'<div id="{elem.id}" class="element photo-element" style="{pos_style}">{badge}{content_html}</div>')

            elif elem.role == "logo":
                font_fam = (st.font_family if st else None) or "Playfair Display, Georgia, serif"
                font_pt = (st.font_size_pt if st else None) or 36.0
                color_val = (st.color if st else None) or "#111"
                logo_content = (f'<img src="{html.escape(elem.image_url)}" alt="{html.escape(elem.text_content or "Winieta")}" style="max-width:100%; max-height:100%; object-fit:contain"/>' if elem.image_url else html.escape(elem.text_content or ""))
                label = advertorial_labels.get(elem.id) if isinstance(advertorial_labels, dict) else None
                badge = f'<span class="advertorial-label">{html.escape(str(label))}</span>' if label else ''
                html_elements.append(
                    f'<div id="{elem.id}" class="element masthead" style="{pos_style} '
                    f'font-family: {font_fam}; font-size: {font_pt:.1f}pt; font-weight: bold; '
                    f'text-align: center; color: {color_val}; letter-spacing: 1px; '
                    f'border-bottom: 2px solid #111; display: flex; align-items: center; justify-content: center;">'
                    f'{badge}{logo_content}'
                    f'</div>'
                )

            elif elem.role == "folio":
                label = advertorial_labels.get(elem.id) if isinstance(advertorial_labels, dict) else None
                badge = f'<span class="advertorial-label">{html.escape(str(label))}</span>' if label else ''
                html_elements.append(
                    f'<div id="{elem.id}" class="element folio-bar" style="{pos_style} '
                    f'font-family: Inter, sans-serif; font-size: 7.5pt; font-weight: bold; text-transform: uppercase; '
                    f'border-top: 1px solid #111; border-bottom: 1px solid #111; display: flex; align-items: center; '
                    f'justify-content: space-between; padding: 0 2mm; color: #333;">'
                    f'{badge}<span>{html.escape(elem.text_content or "")}</span>'
                    f'</div>'
                )

            elif elem.role in {"pullquote", "infobox", "brief_column", "teaser_band", "jump_line", "column"}:
                bg = (st.bg_color if st else None) or ("#f2ede4" if elem.role in {"infobox", "brief_column"} else "transparent")
                border = "border-left: 1.5mm solid #900;" if elem.role == "pullquote" else "border: 0.3mm solid #222;"
                label = advertorial_labels.get(elem.id) if isinstance(advertorial_labels, dict) else None
                badge = f'<span class="advertorial-label">{html.escape(str(label))}</span>' if label else ''
                html_elements.append(
                    f'<div id="{elem.id}" class="element module {elem.role}" style="{pos_style} background: {bg}; {border} '
                    f'padding: 2mm; box-sizing: border-box; overflow: hidden; white-space: pre-wrap;">{badge}{html.escape(elem.text_content or "")}</div>'
                )

            else:
                # Text Elements
                font_fam = (st.font_family if st else None) or ("Playfair Display, serif" if elem.role == "headline" else "PT Serif, serif")
                font_pt = (st.font_size_pt if st else None) or (24.0 if elem.role == "headline" else 9.5)
                line_h_pt = (st.line_height_pt if st else None) or (font_pt * 1.2)
                col_count = (st.columns if st else 1) or 1
                col_css = f"column-count: {col_count}; column-gap: 4mm; column-rule: 0.5px solid #eae6de;" if col_count > 1 else ""
                weight = (st.font_weight if st else None) or ("bold" if elem.role in ["headline", "kicker"] else "normal")
                case = f"text-transform: {st.case};" if (st and st.case and st.case != "normal") else ""
                align = f"text-align: {st.align};" if (st and st.align) else "text-align: left;"
                col = f"color: {st.color};" if (st and st.color) else f"color: {text_col};"

                # Text content formatting with paragraphs
                paragraphs = (elem.text_content or "").split("\n\n")
                p_nodes = []
                for idx, p in enumerate(paragraphs):
                    indent = "0" if idx == 0 else "1.5em"
                    p_nodes.append(f"<p style='margin: 0 0 1.5em 0; text-indent: {indent};'>{html.escape(p)}</p>")
                inner_text_html = "".join(p_nodes)
                label = advertorial_labels.get(elem.id) if isinstance(advertorial_labels, dict) else None
                badge = f'<span class="advertorial-label">{html.escape(str(label))}</span>' if label else ''

                html_elements.append(
                    f'<div id="{elem.id}" class="element text-block {elem.role}" style="{pos_style} '
                    f'font-family: {font_fam}; font-size: {font_pt:.1f}pt; line-height: {line_h_pt:.1f}pt; '
                    f'{weight}; {case} {align} {col} {col_css} overflow: hidden; box-sizing: border-box;">'
                    f'{badge}{inner_text_html}'
                    f'</div>'
                )

        elements_rendered = "\n".join(html_elements)

        return f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(sg.metadata.get("title", "Newspaper Page Layout"))}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=PT+Serif:ital,wght@0,400;0,700;1,400&family=Playfair+Display:ital,wght@0,700;0,900;1,700&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: {pw:.1f}mm {ph:.1f}mm;
            margin: 0;
        }}
        @media print {{
            body {{
                margin: 0;
                padding: 0;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .page-sheet {{
                box-shadow: none !important;
                margin: 0 !important;
            }}
        }}
        html, body {{
            margin: 0;
            padding: 0;
            background-color: #525659;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .page-sheet {{
            width: {pw:.1f}mm;
            height: {ph:.1f}mm;
            background-color: {bg_col};
            position: relative;
            box-shadow: 0 8px 30px rgba(0,0,0,0.3);
            overflow: hidden;
            box-sizing: border-box;
        }}
        .element p:last-child {{
            margin-bottom: 0;
        }}
        .advertorial-label {{
            display: inline-block; background: #111; color: #fff; padding: 0.6mm 1.2mm;
            font: 600 6pt/1.1 sans-serif; letter-spacing: .04em; text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <div class="page-sheet">
{elements_rendered}
    </div>
</body>
</html>
"""
