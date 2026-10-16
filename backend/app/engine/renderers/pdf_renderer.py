from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ...models.schemas import SceneGraph, TitleDNA
from .html_renderer import HTMLRenderer
from .production_utils import cmyk_from_hex, local_asset, optional_package

MM_TO_PT = 72.0 / 25.4


class PDFRenderer:
    """Render a scene graph with a print engine or a real local vector fallback.

    The fallback embeds searchable text and local photo assets; it never emits
    a blank placeholder. PDF/X conformance remains explicitly un-certified
    until a press ICC output intent and external validator are configured.
    """

    _system_font_roots = (
        Path("/System/Library/Fonts/Supplemental"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/liberation2"),
    )
    _fallback_paths: dict[str, str] = {}

    def __init__(self, dna: Optional[TitleDNA] = None):
        self.dna = dna
        self.html_renderer = HTMLRenderer(dna)

    @staticmethod
    def _find_binary(names: list[str]) -> Optional[str]:
        for name in names:
            if os.path.isabs(name) and os.path.exists(name):
                return name
            resolved = shutil.which(name)
            if resolved:
                return resolved
        return None

    @staticmethod
    def _register_fonts() -> None:
        optional_package("reportlab")
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from ..fonts import resolve_font, ttf_for_pdf
        roots = PDFRenderer._system_font_roots
        choices = {
            "ZecroSerif": (["Times New Roman.ttf", "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"], "PT Serif, serif", False),
            "ZecroSerifBold": (["Times New Roman Bold.ttf", "DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"], "PT Serif, serif", True),
            "ZecroSans": (["Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"], "Inter, sans-serif", False),
            "ZecroSansBold": (["Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"], "Inter, sans-serif", True),
        }
        for name, (filenames, family, bold) in choices.items():
            if name in pdfmetrics.getRegisteredFontNames():
                continue
            font_path = next((root / filename for root in roots for filename in filenames if (root / filename).is_file()), None)
            if font_path is None:
                # Serverless hosts have no OS font directory. The same approved,
                # embeddable library used by the typesetter is the PDF fallback.
                font_path = resolve_font(family, bold=bold, text="Zażółć gęślą jaźń")
            if font_path is None:
                raise RuntimeError("No Unicode font is available in the font library for PDF export")
            embedded_path = ttf_for_pdf(str(font_path))
            pdfmetrics.registerFont(TTFont(name, embedded_path))
            PDFRenderer._fallback_paths[name] = embedded_path

    def render_to_file(self, sg: SceneGraph, output_pdf_path: str) -> str:
        output = Path(output_pdf_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if os.getenv("ZECRO_PDF_ENGINE", "typesetter") == "typesetter":
            return self._render_reportlab(sg, output)
        html_content = self.html_renderer.render(sg)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as handle:
            handle.write(html_content)
            html_path = handle.name
        try:
            weasy = self._find_binary(["weasyprint"])
            if weasy:
                subprocess.run([weasy, html_path, str(output)], check=True, capture_output=True)
                self._write_engine_report(output, "weasyprint", sg)
            else:
                chrome = self._find_binary(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium", "chromium-browser"])
                if chrome:
                    profile = tempfile.mkdtemp(prefix="zecro-chrome-")
                    try:
                        try:
                            subprocess.run([chrome, "--headless", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profile}", f"--print-to-pdf={output}", "--no-pdf-header-footer", html_path], check=True, capture_output=True)
                        except (OSError, subprocess.CalledProcessError):
                            return self._render_reportlab(sg, output)
                    finally:
                        shutil.rmtree(profile, ignore_errors=True)
                    self._write_engine_report(output, "chrome", sg)
                else:
                    return self._render_reportlab(sg, output)
            if not output.exists() or output.stat().st_size < 100:
                raise RuntimeError("PDF print engine produced no usable output")
            return str(output)
        finally:
            try:
                os.unlink(html_path)
            except FileNotFoundError:
                pass

    @staticmethod
    def _write_engine_report(output: Path, renderer: str, sg: SceneGraph) -> None:
        """Record the limits of browser/WeasyPrint output for preflight.

        A successful print engine invocation proves that a PDF was written, but
        it does not prove PDF/X output intent, separations, TAC, or font
        embedding. Keeping that distinction in a sidecar prevents a browser
        render from being mistaken for a press-certified deliverable.
        """
        report = {
            "renderer": renderer,
            "trim_mm": sg.page.trim,
            "bleed_mm": sg.page.bleed_mm,
            "crop_marks": False,
            "fonts_embedded": "unverified",
            "pdfx_compliant": False,
            "production_ready": False,
            "missing_assets": [],
            "overset_elements": [],
            "warnings": [
                "PDF/X output intent and press preflight are not certified for this print-engine PDF.",
            ],
            "content_present": bool(sg.elements),
        }
        output.with_suffix(".preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _render_reportlab(self, sg: SceneGraph, output: Path) -> str:
        self._register_fonts()
        optional_package("reportlab")
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.lib.utils import ImageReader
        from PIL import Image

        trim_w, trim_h = (float(v) * MM_TO_PT for v in sg.page.trim)
        bleed = max(3.0, float(sg.page.bleed_mm)) * MM_TO_PT
        mark_gap = 7.0 * MM_TO_PT
        origin = bleed + mark_gap
        media_w, media_h = trim_w + 2 * origin, trim_h + 2 * origin
        report = {"renderer": "zecro_typesetter", "trim_mm": sg.page.trim, "bleed_mm": bleed / MM_TO_PT, "crop_marks": True, "fonts_embedded": True, "pdfx_compliant": False, "production_ready": False, "missing_assets": [], "overset_elements": [], "warnings": ["PDF/X output intent is not certified: no press ICC profile is configured."]}
        c = canvas.Canvas(str(output), pagesize=(media_w, media_h), pageCompression=1, pdfVersion=(1, 4))
        c.setTitle(sg.metadata.get("title", "ZECRO — strona prasowa"))
        c.setAuthor("ZECRO local layout engine")
        # PDF pages are technically transparent unless painted. Several
        # previewers render that transparency as black, which reverses the
        # intended palette and makes a valid newspaper page appear broken.
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, media_w, media_h, stroke=0, fill=1)

        def font_for(elem):
            st = elem.style
            sans = elem.role in ("caption", "kicker", "folio", "byline")
            bold = bool(st and st.font_weight in ("bold", "600", "700", "800", "900"))
            return ("ZecroSans" if sans else "ZecroSerif") + ("Bold" if bold else "")

        from ..shapes import is_rect, shape_polygon

        def shape_path(elem):
            fr = elem.frame
            path = c.beginPath()
            for i, (px, py) in enumerate(shape_polygon(elem.shape, fr.x, fr.y, fr.w, fr.h)):
                X, Y = origin + px * MM_TO_PT, origin + trim_h - py * MM_TO_PT
                (path.moveTo if i == 0 else path.lineTo)(X, Y)
            path.close()
            return path

        def fill_frame(elem, color):
            c.setFillColorCMYK(*cmyk_from_hex(color))
            if is_rect(elem.shape):
                fr = elem.frame
                c.rect(origin + fr.x * MM_TO_PT, origin + (trim_h - (fr.y + fr.h) * MM_TO_PT), fr.w * MM_TO_PT, fr.h * MM_TO_PT, stroke=0, fill=1)
            else:
                c.drawPath(shape_path(elem), stroke=0, fill=1)

        for elem in sorted(sg.elements, key=lambda e: e.z):
            f, st = elem.frame, elem.style
            x, y = origin + f.x * MM_TO_PT, origin + (trim_h - (f.y + f.h) * MM_TO_PT)
            w, h = f.w * MM_TO_PT, f.h * MM_TO_PT
            c.saveState()
            if f.rotation_deg:
                c.translate(x + w / 2, y + h / 2); c.rotate(-f.rotation_deg); c.translate(-x - w / 2, -y - h / 2)
            if getattr(f, "skew_y_deg", 0):
                import math as _m
                _t = _m.tan(_m.radians(f.skew_y_deg))
                c.transform(1, _t, 0, 1, 0, -_t * x)  # y-up: the right end rises
            if st and st.bg_color and elem.role not in {"photo", "band"}:
                fill_frame(elem, st.bg_color)
            border = bool(st and st.border_width_mm and st.border_color and elem.role not in {"rule", "photo"})
            if elem.role == "photo":
                asset = local_asset(elem.image_url)
                if asset:
                    from ..image_ops import cover_crop_box, crop_pixels
                    img = Image.open(asset)
                    # A real cutout uses the segmented RGBA. Keep its alpha
                    # in the review PDF so hair and enclosed gaps reveal the
                    # actual scene field, rather than an artificial white halo.
                    mask_asset = local_asset(elem.mask_ref) if elem.treatment == "cutout" and elem.mask_ref else None
                    if mask_asset and ".refined-" not in str(mask_asset):
                        # every cut-out, from any composer, is finished like a
                        # retoucher's before print (rulebook U7, defect D08)
                        try:
                            from ..cutout_quality import refine_cutout
                            mask_asset = refine_cutout(str(mask_asset), source_path=str(asset))
                        except Exception as exc:
                            report["warnings"].append(f"wycięcie {elem.id}: wykończenie nieudane ({str(exc)[:80]})")
                    if mask_asset:
                        img = Image.open(mask_asset)
                    crop = elem.crop_box or cover_crop_box(img.width, img.height, f.w, f.h, elem.focal_point)
                    img = img.crop(crop_pixels(img.size, crop))
                    fade_spec = next((c_[5:] for c_ in (elem.constraints or []) if c_.startswith("fade:")), None)
                    if fade_spec:
                        # U18 smooth transition: an alpha ramp on the given sides
                        import numpy as _np
                        img = img.convert("RGBA")
                        a = _np.asarray(img.getchannel("A"), dtype=_np.float32)
                        hh, ww = a.shape
                        for part in fade_spec.split(","):
                            side, mm = part.split("=")
                            frac_w = float(mm) / max(1e-6, f.w)
                            frac_h = float(mm) / max(1e-6, f.h)
                            if side in ("left", "right"):
                                n = max(1, int(ww * frac_w))
                                ramp = _np.linspace(0, 1, n, dtype=_np.float32) ** 1.4
                                sl = slice(0, n) if side == "left" else slice(ww - n, ww)
                                a[:, sl] *= (ramp if side == "left" else ramp[::-1])[None, :]
                            else:
                                n = max(1, int(hh * frac_h))
                                ramp = _np.linspace(0, 1, n, dtype=_np.float32) ** 1.4
                                sl = slice(0, n) if side == "top" else slice(hh - n, hh)
                                a[sl, :] *= (ramp if side == "top" else ramp[::-1])[:, None]
                        img.putalpha(Image.fromarray(a.clip(0, 255).astype(_np.uint8)))
                    soft_cutout = bool((mask_asset and elem.treatment == "cutout" or fade_spec)
                                       and img.mode in ("RGBA", "LA", "P"))
                    if img.mode in ("RGBA", "LA", "P") and not soft_cutout:
                        img = img.convert("RGBA")
                        bg = Image.new("RGB", img.size, (255, 255, 255)); bg.paste(img.convert("RGB"), mask=img.getchannel("A")); img = bg
                    if soft_cutout:
                        img = img.convert("RGBA")
                        stream = io.BytesIO(); img.save(stream, format="PNG"); stream.seek(0)
                    else:
                        if img.mode != "CMYK": img = img.convert("CMYK")
                        stream = io.BytesIO(); img.save(stream, format="JPEG", quality=95); stream.seek(0)
                    if not is_rect(elem.shape) and elem.treatment != "cutout":
                        c.clipPath(shape_path(elem), stroke=0, fill=0)
                    # a soft alpha already IS the cut (feathered, decontaminated);
                    # a polygon clip on top of it would draw facets/teeth (D08)
                    if elem.treatment == "cutout" and not soft_cutout and elem.contour_points and len(elem.contour_points) > 2:
                        path = c.beginPath()
                        for ring in [elem.contour_points, *(elem.contour_holes or [])]:
                            if len(ring) < 3:
                                continue
                            for i, point in enumerate(ring):
                                px, py = x + point[0] * MM_TO_PT, origin + trim_h - (f.y + point[1]) * MM_TO_PT
                                (path.moveTo if i == 0 else path.lineTo)(px, py)
                            path.close()
                        c.clipPath(path, stroke=0, fill=0, fillMode=0)  # 0 = even-odd: holes stay open
                    c.drawImage(ImageReader(stream), x, y, width=w, height=h,
                                preserveAspectRatio=False, mask="auto" if soft_cutout else None)
                else:
                    report["missing_assets"].append({"element": elem.id, "url": elem.image_url})
                    c.setStrokeColorCMYK(0, 0, 0, .5); c.rect(x, y, w, h, stroke=1, fill=0)
                    c.setFillColorCMYK(0, 0, 0, 1); c.setFont("ZecroSans", 8); c.drawString(x + 4, y + 4, f"Brak lokalnego zdjęcia: {elem.id}")
            elif elem.role == "logo" and elem.image_url and local_asset(elem.image_url):
                from ..logo import rasterize
                src = Path(local_asset(elem.image_url))
                img = rasterize(src, width=max(600, int(f.w / 25.4 * 600)))
                if img is None:
                    report["missing_assets"].append({"element": elem.id, "url": elem.image_url})
                else:
                    bbox = img.getchannel("A").getbbox()
                    if bbox:
                        img = img.crop(bbox)
                    scale = min(w / img.width, h / img.height)
                    dw, dh = img.width * scale, img.height * scale
                    if img.getchannel("A").getextrema()[0] < 255:
                        # A logo on a coloured plate keeps its transparency;
                        # flattening it on white would print a white box.
                        stream = io.BytesIO(); img.save(stream, format="PNG"); stream.seek(0)
                        c.drawImage(ImageReader(stream), x + (w - dw) / 2, y + (h - dh) / 2, width=dw, height=dh, mask="auto")
                    else:
                        flat = Image.new("RGB", img.size, (255, 255, 255)); flat.paste(img, mask=img.getchannel("A"))
                        stream = io.BytesIO(); flat.convert("CMYK").save(stream, format="JPEG", quality=96); stream.seek(0)
                        c.drawImage(ImageReader(stream), x + (w - dw) / 2, y + (h - dh) / 2, width=dw, height=dh)
                    if src.suffix.lower() not in {".svg", ".pdf", ".eps", ".ai"}:
                        report["warnings"].append("logo rastrowe w PDF — dostarcz wektor (SVG/PDF)")
            elif elem.role == "rule":
                c.setStrokeColorCMYK(0, 0, 0, 1); c.setLineWidth(max(.25, ((st.border_width_mm if st else None) or .2) * MM_TO_PT)); c.line(x, y + h / 2, x + w, y + h / 2)
            elif elem.role == "band":
                fill_frame(elem, st.bg_color if st and st.bg_color else "#111111")
            else:
                self._draw_text(c, elem, x, y, w, h, report)
            if border:
                c.setStrokeColorCMYK(*cmyk_from_hex(st.border_color))
                c.setLineWidth(float(st.border_width_mm) * MM_TO_PT)
                c.setLineJoin(1)
                c.drawPath(shape_path(elem), stroke=1, fill=0)
            c.restoreState()

        c.setStrokeColorCMYK(0, 0, 0, 1); c.setLineWidth(.25); length = 4 * MM_TO_PT
        for xx in (origin, origin + trim_w):
            for yy in (origin, origin + trim_h):
                c.line(xx - bleed - length, yy, xx - bleed, yy); c.line(xx + bleed, yy, xx + bleed + length, yy); c.line(xx, yy - bleed - length, xx, yy - bleed); c.line(xx, yy + bleed, xx, yy + bleed + length)
        c.showPage(); c.save()
        self._set_pdf_boxes(output, media_w, media_h, origin, trim_w, trim_h, bleed)
        placeholder = (sg.metadata or {}).get("copy_mode") == "placeholder" or any(
            e.content_revision_ref == "placeholder" for e in sg.elements)
        if placeholder:
            report["warnings"].append("tekst markowany — strona próbna, nie do druku")
        pending = (sg.metadata or {}).get("copy_requests") or []
        if pending:
            report["warnings"].append(f"{len(pending)} ramek czeka na tekst od redakcji/AI")
        report["production_ready"] = (not report["missing_assets"] and not report["overset_elements"]
                                      and report["pdfx_compliant"] and not placeholder and not pending)
        report["content_present"] = bool(sg.elements)
        output.with_suffix(".preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output)


    # ------------------------------------------------------------ typesetter
    _registered: dict = {}

    @staticmethod
    def _sans_family(family: str) -> bool:
        value = family.lower()
        return ("sans" in value or "arial" in value or "helvetica" in value
                or any(name in value for name in (
                    "gotham", "amsi", "oswald", "roboto condensed",
                    "nimbus sans", "franklin", "inter", "source sans",
                )))

    def _pdf_font(self, elem, text: str):
        """(reportlab font name, shaping path, face record) for an element."""
        from ..fonts import resolve_face, local_file, ttf_for_pdf
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        st = elem.style
        from ..fonts import style_face_args
        args = style_face_args(st) if st else {"weight": 400, "italic": False, "width": None}
        weight = args["weight"]
        family = (st.font_family if st else None) or ("sans" if elem.role in ("caption", "kicker", "folio", "byline") else "serif")
        face = resolve_face(family, weight=weight, italic=args["italic"], text=text, width=args["width"])
        if face:
            src = local_file(face)
            if src:
                try:
                    ttf = ttf_for_pdf(str(src))
                    name = "Z_" + (face.get("postscript_name") or face["id"]).replace(" ", "")[:40]
                    if name not in pdfmetrics.getRegisteredFontNames():
                        pdfmetrics.registerFont(TTFont(name, ttf))
                    return name, ttf, face
                except (OSError, RuntimeError) as exc:
                    # A substituted font changes line breaks after copyfit.
                    # Stop export instead of silently delivering a different
                    # headline from the approved scene graph.
                    raise RuntimeError(f"Nie można osadzić kroju {family} w PDF: {exc}") from exc
                except (ImportError, ModuleNotFoundError):
                    pass
        try:
            self._register_fonts()
        except (ImportError, ModuleNotFoundError, OSError, RuntimeError):
            pass
        use_sans = self._sans_family(family) or elem.role in ("caption", "kicker", "folio", "byline")
        fallback = ("ZecroSans" if use_sans else "ZecroSerif") + ("Bold" if weight >= 700 else "")
        if fallback in pdfmetrics.getRegisteredFontNames():
            # Shape with the exact embedded fallback. Drawing a TTF with a
            # generic 0.48-em advance creates the conspicuous spaced-out
            # letters that made early cover proofs look mechanical.
            fallback_path = self._fallback_paths.get(fallback)
            return fallback, fallback_path, ({"full_name": fallback, "polish": "full"}
                                             if fallback_path else None)
        builtin = ("Helvetica-Bold" if weight >= 700 else "Helvetica") if use_sans else ("Times-Bold" if weight >= 700 else "Times-Roman")
        return builtin, None, None

    def _draw_text(self, c, elem, x, y, w, h, report):
        from ..shaper import shape_text, glyph_offsets, hyphenate_for, LETTER_STRETCH, WORD_STRETCH, WORD_SHRINK, LETTER_SHRINK, width_pt
        from ..shapes import text_box
        st = elem.style
        # Inset / shape-inscribed text box (same box the copyfit measures).
        bx, by, bw, bh = text_box(elem)
        x += (bx - elem.frame.x) * MM_TO_PT
        y += (elem.frame.y + elem.frame.h - (by + bh)) * MM_TO_PT
        w, h = bw * MM_TO_PT, bh * MM_TO_PT
        text = elem.text_content or ""
        if st and st.case == "upper":
            text = text.upper()
        size = float((st.font_size_pt if st else None) or 9.5)
        leading = float((st.line_height_pt if st else None) or size * 1.2)
        name, shape_path, face = self._pdf_font(elem, text)
        c.setFont(name, size)
        c.setFillColorCMYK(*cmyk_from_hex((st.color if st and st.color else "#000000")))
        c.setFillOverprint(True)
        columns = max(1, int((st.columns if st else 1) or 1))
        gutter = float(self.dna.grid.gutter_mm if self.dna else 4.0) * MM_TO_PT
        col_w = max(1.0, (w - (columns - 1) * gutter) / columns)
        trk = float((st.tracking_em if st else None) or 0.0)
        shaped = shape_text(text, width_pt=col_w, font_size_pt=size, leading_pt=leading, font_path=shape_path,
                            hyphenate=hyphenate_for(size), tracking_em=trk)
        align = (st.align if st else "left") or "left"
        per_col = max(1, int(h / leading + 1e-6))
        space = width_pt(" ", size, shape_path, trk)
        outline_color = st.outline_color if st else None
        outline_width = float(st.outline_width_pt or 0) if st else 0.0
        shadow_color = st.shadow_color if st else None
        shadow_dx = float(st.shadow_offset_x_pt or 0) if st else 0.0
        shadow_dy = float(st.shadow_offset_y_pt or 0) if st else 0.0

        def draw_glyph(ch, gx, gy):
            if shadow_color:
                c.saveState()
                c.setFillColorCMYK(*cmyk_from_hex(shadow_color))
                c.drawString(gx + shadow_dx, gy - shadow_dy, ch)
                c.restoreState()
            if outline_color and outline_width:
                c.saveState()
                c.setStrokeColorCMYK(*cmyk_from_hex(outline_color))
                c.setFillColorCMYK(*cmyk_from_hex((st.color if st and st.color else "#000000")))
                c.setLineWidth(outline_width)
                c.setLineJoin(1)
                t = c.beginText(gx, gy)
                t.setFont(name, size)
                t.setTextRenderMode(2)  # fill and stroke the same glyph outline
                t.textOut(ch)
                c.drawText(t)
                c.restoreState()
            else:
                c.drawString(gx, gy, ch)

        drawn = 0
        valign = (st.valign if st else None) or "top"
        offset = 0.0
        single_logo = elem.role == "logo" and len(shaped.lines) == 1
        if valign in {"center", "bottom"} and columns == 1 and not single_logo:
            rows = min(len(shaped.lines), per_col)
            block = size * .8 + max(0, rows - 1) * leading + size * .22
            offset = max(0.0, h - block) * (.5 if valign == "center" else 1.0)
        for i, line in enumerate(shaped.lines):
            col, row = divmod(i, per_col)
            if col >= columns:
                break
            xx = x + col * (col_w + gutter)
            baseline = (y + (h - size * .72) / 2 if single_logo else y + h - size * .8 - row * leading - offset)
            justify = align == "justify" and not line.last and len(line.words) > 1
            r = line.ratio if justify else 0.0
            if align == "center":
                xx += max(0, (col_w - line.width_pt) / 2)
            elif align == "right":
                xx += max(0, col_w - line.width_pt)
            pen = xx
            for wi, (word, ww) in enumerate(line.words):
                k = (LETTER_STRETCH if r >= 0 else LETTER_SHRINK) * r
                offsets = glyph_offsets(word, shape_path) if shape_path else [j * 0.48 for j in range(len(word))]
                n = max(1, len(word) - 1)
                for j, ch in enumerate(word):
                    draw_glyph(ch, pen + offsets[j] * size + j * trk * size + (ww * k) * (j / n if len(word) > 1 else 0),
                               baseline)
                pen += ww * (1 + k)
                if wi < len(line.words) - 1:
                    pen += space * (1 + (WORD_STRETCH if r >= 0 else WORD_SHRINK) * r)
            drawn += 1
        if drawn < shaped.line_count:
            report["overset_elements"].append({"element": elem.id, "overset_lines": shaped.line_count - drawn})
        report.setdefault("typeset", []).append({"element": elem.id, "lines": shaped.line_count, "drawn": drawn,
                                                  "measure": shaped.status, "font": (face or {}).get("full_name") or name,
                                                  "polish": (face or {}).get("polish")})
        if face is None:
            report["warnings"].append(f"{elem.id}: krój spoza biblioteki (zastępczy {name}) — pomiar szacunkowy")

    @staticmethod
    def _set_pdf_boxes(path: Path, media_w: float, media_h: float, origin: float, trim_w: float, trim_h: float, bleed: float):
        pypdf = optional_package("pypdf")
        reader = pypdf.PdfReader(str(path)); writer = pypdf.PdfWriter(); page = reader.pages[0]; box = pypdf.generic.RectangleObject
        page.mediabox = box((0, 0, media_w, media_h)); page.cropbox = box((origin, origin, origin + trim_w, origin + trim_h)); page.trimbox = box((origin, origin, origin + trim_w, origin + trim_h)); page.bleedbox = box((origin - bleed, origin - bleed, origin + trim_w + bleed, origin + trim_h + bleed))
        writer.add_page(page); writer.add_metadata({"/Title": "ZECRO — strona prasowa", "/Producer": "ZECRO ReportLab renderer"})
        with path.open("wb") as stream: writer.write(stream)
