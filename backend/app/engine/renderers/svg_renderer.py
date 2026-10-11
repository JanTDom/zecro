import html
from typing import Optional
from ...models.schemas import SceneGraph, TitleDNA
from ..image_ops import contour_to_svg_path

class SVGRenderer:
    def __init__(self, dna: Optional[TitleDNA] = None):
        self.dna = dna

    def render(self, sg: SceneGraph, show_grid: bool = False) -> str:
        """
        Renders SceneGraph to a high-fidelity standalone SVG string.
        """
        pw = sg.page.trim[0]
        ph = sg.page.trim[1]
        bg_color = self.dna.palette.background if self.dna else "#fcfbf7"

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {pw:.1f} {ph:.1f}" width="100%" height="100%" '
            f'style="background-color: {bg_color}; font-family: Playfair Display, PT Serif, Georgia, serif;">',
            f'<rect width="{pw:.1f}" height="{ph:.1f}" fill="{bg_color}"/>'
        ]

        # Definitions for clip paths
        svg_lines.append('<defs>')
        for elem in sg.elements:
            if elem.treatment == "cutout" and elem.contour_points:
                path_d = contour_to_svg_path(elem.contour_points)
                svg_lines.append(f'<clipPath id="clip-{elem.id}"><path d="{path_d}"/></clipPath>')
        svg_lines.append('</defs>')

        # Optional subtle modular grid lines
        if show_grid and self.dna:
            g = self.dna.grid
            f = self.dna.format
            svg_lines.append('<g id="grid-guides" stroke="#e8e4dc" stroke-width="0.3" opacity="0.7">')
            # Column lines
            col_w = (sg.page.trim[0] - f.margin_left_mm - f.margin_right_mm - (g.columns - 1) * g.gutter_mm) / g.columns
            for c in range(g.columns):
                cx = f.margin_left_mm + c * (col_w + g.gutter_mm)
                svg_lines.append(f'<rect x="{cx:.1f}" y="{f.margin_top_mm:.1f}" width="{col_w:.1f}" height="{sg.page.trim[1] - f.margin_top_mm - f.margin_bottom_mm:.1f}" fill="none"/>')
            svg_lines.append('</g>')

        # Sort elements by Z-index
        sorted_elements = sorted(sg.elements, key=lambda e: e.z)

        for elem in sorted_elements:
            fr = elem.frame
            rot = fr.rotation_deg
            transform_attr = f' transform="rotate({rot:.1f} {fr.x + fr.w/2:.1f} {fr.y + fr.h/2:.1f})"' if abs(rot) > 0.1 else ""

            svg_lines.append(f'<g id="elem-g-{elem.id}"{transform_attr}>')

            # Render Photos / Images
            if elem.role == "photo":
                clip_attr = f' clip-path="url(#clip-{elem.id})"' if elem.treatment == "cutout" and elem.contour_points else ""
                # Background placeholder rect
                svg_lines.append(
                    f'<rect x="{fr.x:.1f}" y="{fr.y:.1f}" width="{fr.w:.1f}" height="{fr.h:.1f}" '
                    f'fill="#dcd8cd" rx="1.0"{clip_attr}/>'
                )

                if elem.image_url and elem.image_url.startswith("http"):
                    svg_lines.append(
                        f'<image xlink:href="{html.escape(elem.image_url)}" x="{fr.x:.1f}" y="{fr.y:.1f}" '
                        f'width="{fr.w:.1f}" height="{fr.h:.1f}" preserveAspectRatio="xMidYMid slice"{clip_attr}/>'
                    )
                else:
                    # Graphic illustration placeholder
                    svg_lines.append(
                        f'<rect x="{fr.x:.1f}" y="{fr.y:.1f}" width="{fr.w:.1f}" height="{fr.h:.1f}" '
                        f'fill="#555" opacity="0.15"{clip_attr}/>'
                    )
                    svg_lines.append(
                        f'<text x="{fr.x + fr.w/2:.1f}" y="{fr.y + fr.h/2:.1f}" font-size="6" text-anchor="middle" '
                        f'fill="#666" font-family="sans-serif">PHOTO ASSET: {elem.id}</text>'
                    )

                # Framed border if requested
                if elem.treatment == "framed":
                    svg_lines.append(
                        f'<rect x="{fr.x:.1f}" y="{fr.y:.1f}" width="{fr.w:.1f}" height="{fr.h:.1f}" '
                        f'fill="none" stroke="#222" stroke-width="0.8"/>'
                    )

            # Render Logo / Masthead
            elif elem.role == "logo":
                if elem.image_url:
                    svg_lines.append(f'<image xlink:href="{html.escape(elem.image_url)}" x="{fr.x:.1f}" y="{fr.y:.1f}" width="{fr.w:.1f}" height="{fr.h:.1f}" preserveAspectRatio="xMidYMid meet"/>')
                else:
                    svg_lines.append(
                        f'<text x="{fr.x + fr.w/2:.1f}" y="{fr.y + fr.h*0.75:.1f}" font-size="{fr.h*0.7:.1f}" '
                        f'font-weight="900" font-family="Playfair Display, Georgia, serif" text-anchor="middle" '
                        f'letter-spacing="0.8" fill="{elem.style.color or "#111"}">{html.escape(elem.text_content or "")}</text>'
                    )

            # Render Folio Bar & Rules
            elif elem.role == "folio":
                svg_lines.append(
                    f'<line x1="{fr.x:.1f}" y1="{fr.y:.1f}" x2="{fr.x + fr.w:.1f}" y2="{fr.y:.1f}" stroke="#111" stroke-width="0.7"/>'
                )
                svg_lines.append(
                    f'<text x="{fr.x:.1f}" y="{fr.y + fr.h*0.75:.1f}" font-size="3.2" font-family="Inter, sans-serif" '
                    f'font-weight="bold" fill="#333" letter-spacing="0.5">{html.escape(elem.text_content or "")}</text>'
                )
                svg_lines.append(
                    f'<line x1="{fr.x:.1f}" y1="{fr.y + fr.h:.1f}" x2="{fr.x + fr.w:.1f}" y2="{fr.y + fr.h:.1f}" stroke="#111" stroke-width="0.4"/>'
                )

            # Render Rule Line
            elif elem.role == "rule":
                svg_lines.append(
                    f'<line x1="{fr.x:.1f}" y1="{fr.y + fr.h/2:.1f}" x2="{fr.x + fr.w:.1f}" y2="{fr.y + fr.h/2:.1f}" '
                    f'stroke="{elem.style.color or "#222"}" stroke-width="{elem.style.border_width_mm or 0.5}"/>'
                )

            elif elem.role in {"pullquote", "infobox", "brief_column", "teaser_band", "jump_line", "column"}:
                # Editorial modules retain their semantic role in the cheap
                # evaluation render; production renderers consume the same
                # scene graph and can map these to paragraph styles.
                bg = (elem.style.bg_color if elem.style else None) or ("#f2ede4" if elem.role in {"infobox", "brief_column"} else "none")
                if bg != "none":
                    svg_lines.append(f'<rect x="{fr.x:.1f}" y="{fr.y:.1f}" width="{fr.w:.1f}" height="{fr.h:.1f}" fill="{html.escape(bg)}" stroke="#222" stroke-width="0.4"/>')
                if elem.role == "pullquote":
                    svg_lines.append(f'<line x1="{fr.x:.1f}" y1="{fr.y:.1f}" x2="{fr.x:.1f}" y2="{fr.y+fr.h:.1f}" stroke="#900" stroke-width="1.2"/>')
                st = elem.style
                font_pt = (st.font_size_pt if st else None) or (18 if elem.role == "pullquote" else 9)
                svg_lines.append(f'<text x="{fr.x+2:.1f}" y="{fr.y+font_pt*.45:.1f}" font-size="{font_pt*.3528:.2f}" fill="{(st.color if st else None) or "#1a1a1a"}">{html.escape(elem.text_content or "")}</text>')

            # Render Text Elements (Headline, Lead, Body, Kicker, Caption, Byline)
            else:
                # Use foreignObject for perfect multiline wrapping and multi-column CSS
                st = elem.style
                font_fam = st.font_family or ("Playfair Display, serif" if elem.role == "headline" else "PT Serif, serif")
                font_pt = st.font_size_pt or (24.0 if elem.role == "headline" else 9.5)
                # Convert pt to mm in SVG space (1 pt ~ 0.3528 mm)
                font_mm = font_pt * 0.3528
                line_h_mm = (st.line_height_pt or (font_pt * 1.15)) * 0.3528
                text_col = st.color or ("#900" if elem.role == "kicker" else "#1a1a1a")
                align = st.align or "left"
                weight = st.font_weight or "normal"
                case = "uppercase" if st.case == "upper" else "none"
                col_count = st.columns or 1

                svg_lines.append(
                    f'<foreignObject x="{fr.x:.1f}" y="{fr.y:.1f}" width="{fr.w:.1f}" height="{fr.h:.1f}">'
                    f'<div xmlns="http://www.w3.org/1999/xhtml" style="'
                    f'font-family: {font_fam}; font-size: {font_mm:.2f}px; line-height: {line_h_mm:.2f}px; '
                    f'color: {text_col}; font-weight: {weight}; text-transform: {case}; text-align: {align}; '
                    f'column-count: {col_count}; column-gap: 3.5px; height: 100%; overflow: hidden; '
                    f'margin: 0; padding: 0; box-sizing: border-box;">'
                    f'{html.escape(elem.text_content or "").replace(chr(10), "<br/>")}'
                    f'</div>'
                    f'</foreignObject>'
                )

            svg_lines.append('</g>')

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)
