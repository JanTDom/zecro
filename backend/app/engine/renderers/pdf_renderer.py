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
        roots = [Path("/System/Library/Fonts/Supplemental"), Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/truetype/liberation2")]
        choices = {
            "ZecroSerif": ["Times New Roman.ttf", "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"],
            "ZecroSerifBold": ["Times New Roman Bold.ttf", "DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"],
            "ZecroSans": ["Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
            "ZecroSansBold": ["Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
        }
        for name, filenames in choices.items():
            if name in pdfmetrics.getRegisteredFontNames():
                continue
            font_path = next((root / filename for root in roots for filename in filenames if (root / filename).is_file()), None)
            if font_path is None:
                raise RuntimeError("No local Unicode TTF font is available for PDF export")
            pdfmetrics.registerFont(TTFont(name, str(font_path)))

    def render_to_file(self, sg: SceneGraph, output_pdf_path: str) -> str:
        output = Path(output_pdf_path)
        output.parent.mkdir(parents=True, exist_ok=True)
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
        report = {"renderer": "reportlab_vector", "trim_mm": sg.page.trim, "bleed_mm": bleed / MM_TO_PT, "crop_marks": True, "fonts_embedded": True, "pdfx_compliant": False, "production_ready": False, "missing_assets": [], "overset_elements": [], "warnings": ["PDF/X output intent is not certified: no press ICC profile is configured."]}
        c = canvas.Canvas(str(output), pagesize=(media_w, media_h), pageCompression=1, pdfVersion=(1, 4))
        c.setTitle(sg.metadata.get("title", "ZECRO — strona prasowa"))
        c.setAuthor("ZECRO local layout engine")

        def font_for(elem):
            st = elem.style
            sans = elem.role in ("caption", "kicker", "folio", "byline")
            bold = bool(st and st.font_weight in ("bold", "600", "700", "800", "900"))
            return ("ZecroSans" if sans else "ZecroSerif") + ("Bold" if bold else "")

        for elem in sorted(sg.elements, key=lambda e: e.z):
            f, st = elem.frame, elem.style
            x, y = origin + f.x * MM_TO_PT, origin + (trim_h - (f.y + f.h) * MM_TO_PT)
            w, h = f.w * MM_TO_PT, f.h * MM_TO_PT
            c.saveState()
            if f.rotation_deg:
                c.translate(x + w / 2, y + h / 2); c.rotate(-f.rotation_deg); c.translate(-x - w / 2, -y - h / 2)
            if elem.role == "photo":
                asset = local_asset(elem.image_url)
                if asset:
                    img = Image.open(asset)
                    if img.mode in ("RGBA", "LA"):
                        bg = Image.new("RGB", img.size, (255, 255, 255)); bg.paste(img.convert("RGB"), mask=img.getchannel("A")); img = bg
                    if img.mode != "CMYK": img = img.convert("CMYK")
                    stream = io.BytesIO(); img.save(stream, format="JPEG", quality=95); stream.seek(0)
                    if elem.treatment == "cutout" and elem.contour_points and len(elem.contour_points) > 2:
                        path = c.beginPath()
                        for i, point in enumerate(elem.contour_points):
                            px, py = x + point[0] * MM_TO_PT, origin + trim_h - (f.y + point[1]) * MM_TO_PT
                            (path.moveTo if i == 0 else path.lineTo)(px, py)
                        path.close(); c.clipPath(path, stroke=0, fill=0)
                    c.drawImage(ImageReader(stream), x, y, width=w, height=h, preserveAspectRatio=False)
                else:
                    report["missing_assets"].append({"element": elem.id, "url": elem.image_url})
                    c.setStrokeColorCMYK(0, 0, 0, .5); c.rect(x, y, w, h, stroke=1, fill=0)
                    c.setFillColorCMYK(0, 0, 0, 1); c.setFont("ZecroSans", 8); c.drawString(x + 4, y + 4, f"Brak lokalnego zdjęcia: {elem.id}")
            elif elem.role == "rule":
                c.setStrokeColorCMYK(0, 0, 0, 1); c.setLineWidth(max(.25, ((st.border_width_mm if st else None) or .2) * MM_TO_PT)); c.line(x, y + h / 2, x + w, y + h / 2)
            elif elem.role == "band":
                c.setFillColorCMYK(*cmyk_from_hex(st.bg_color if st else "#111111")); c.rect(x, y, w, h, stroke=0, fill=1)
            else:
                text = elem.text_content or ""
                if st and st.case == "upper": text = text.upper()
                size = float((st.font_size_pt if st else None) or 9.5); leading = float((st.line_height_pt if st else None) or size * 1.2)
                font = font_for(elem); c.setFont(font, size); c.setFillColorCMYK(0, 0, 0, 1); c.setFillOverprint(True)
                columns = max(1, int((st.columns if st else 1) or 1)); gutter = float(self.dna.grid.gutter_mm if self.dna else 4.0) * MM_TO_PT; col_w = max(1, (w - (columns - 1) * gutter) / columns)
                words, index, capacity = re.findall(r"\S+", text), 0, max(1, int(h / leading))
                for col in range(columns):
                    for line_no in range(capacity):
                        if index >= len(words): break
                        line_words = []
                        while index < len(words):
                            candidate = " ".join(line_words + [words[index]])
                            if line_words and pdfmetrics.stringWidth(candidate, font, size) > col_w: break
                            line_words.append(words[index]); index += 1
                            if pdfmetrics.stringWidth(" ".join(line_words), font, size) > col_w: break
                        line = " ".join(line_words); xx = x + col * (col_w + gutter); line_width = pdfmetrics.stringWidth(line, font, size)
                        align = st.align if st else "left"
                        if align == "center": xx += max(0, (col_w - line_width) / 2)
                        elif align == "right": xx += max(0, col_w - line_width)
                        c.drawString(xx, y + h - size - line_no * leading, line)
                if index < len(words): report["overset_elements"].append({"element": elem.id, "remaining_words": len(words) - index})
            c.restoreState()

        c.setStrokeColorCMYK(0, 0, 0, 1); c.setLineWidth(.25); length = 4 * MM_TO_PT
        for xx in (origin, origin + trim_w):
            for yy in (origin, origin + trim_h):
                c.line(xx - bleed - length, yy, xx - bleed, yy); c.line(xx + bleed, yy, xx + bleed + length, yy); c.line(xx, yy - bleed - length, xx, yy - bleed); c.line(xx, yy + bleed, xx, yy + bleed + length)
        c.showPage(); c.save()
        self._set_pdf_boxes(output, media_w, media_h, origin, trim_w, trim_h, bleed)
        report["production_ready"] = not report["missing_assets"] and not report["overset_elements"] and report["pdfx_compliant"]
        report["content_present"] = bool(sg.elements)
        output.with_suffix(".preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output)

    @staticmethod
    def _set_pdf_boxes(path: Path, media_w: float, media_h: float, origin: float, trim_w: float, trim_h: float, bleed: float):
        pypdf = optional_package("pypdf")
        reader = pypdf.PdfReader(str(path)); writer = pypdf.PdfWriter(); page = reader.pages[0]; box = pypdf.generic.RectangleObject
        page.mediabox = box((0, 0, media_w, media_h)); page.cropbox = box((origin, origin, origin + trim_w, origin + trim_h)); page.trimbox = box((origin, origin, origin + trim_w, origin + trim_h)); page.bleedbox = box((origin - bleed, origin - bleed, origin + trim_w + bleed, origin + trim_h + bleed))
        writer.add_page(page); writer.add_metadata({"/Title": "ZECRO — strona prasowa", "/Producer": "ZECRO ReportLab renderer"})
        with path.open("wb") as stream: writer.write(stream)
