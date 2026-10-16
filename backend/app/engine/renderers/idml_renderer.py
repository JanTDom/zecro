import zipfile
import re
import xml.sax.saxutils as saxutils
from pathlib import Path
from typing import Optional
from ...models.schemas import SceneGraph, TitleDNA
from .production_utils import local_asset

MM_TO_PT = 2.83464567

class IDMLRenderer:
    def __init__(self, dna: Optional[TitleDNA] = None):
        self.dna = dna

    @staticmethod
    def _text_threads(sg: SceneGraph):
        """Resolve editorial frame chains before emitting stories and refs.

        IDML stores a threaded article once, in a Story part. Every frame in
        that chain must point to that same Story and to its neighbouring frame.
        Reject ambiguous metadata rather than write dangling or cyclic refs.
        """
        elements = {elem.id: elem for elem in sg.elements}
        if len(elements) != len(sg.elements):
            raise ValueError("IDML requires unique scene element IDs")
        threads = sg.metadata.get("text_threads") or {}
        if not isinstance(threads, dict):
            raise ValueError("text_threads must map story IDs to ordered text frame IDs")
        groups = []
        references = {}
        for story_key, frame_ids in threads.items():
            if not isinstance(story_key, str) or not story_key:
                raise ValueError("Each text thread must have a non-empty story ID")
            if not isinstance(frame_ids, list):
                raise ValueError("Each text thread must be an ordered list of frame IDs")
            if not frame_ids:
                continue
            for frame_id in frame_ids:
                if not isinstance(frame_id, str) or frame_id not in elements:
                    raise ValueError(f"Unknown text thread frame: {frame_id!r}")
                if elements[frame_id].role in {"photo", "rule", "band", "teaser_band"}:
                    raise ValueError(f"Text thread references a non-text element: {frame_id}")
                if frame_id in references:
                    raise ValueError(f"Text frame occurs in more than one thread position: {frame_id}")
                # Reserve immediately, including within the current chain.
                references[frame_id] = None
            # Preserve the editorial story identity from metadata. IDs are
            # made path-safe because they become Stories/<id>.xml filenames.
            safe_story_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", story_key)
            story_id = f"u_story_{safe_story_key}"
            groups.append((story_id, [elements[frame_id] for frame_id in frame_ids]))
            for index, frame_id in enumerate(frame_ids):
                previous = f"u_tf_{frame_ids[index - 1]}" if index else "n"
                following = f"u_tf_{frame_ids[index + 1]}" if index + 1 < len(frame_ids) else "n"
                references[frame_id] = (story_id, previous, following)
        for elem in sg.elements:
            if elem.role not in {"photo", "band"} and elem.id not in references:
                story_id = f"u_story_{elem.id}"
                groups.append((story_id, [elem]))
                references[elem.id] = (story_id, "n", "n")
        story_ids = [story_id for story_id, _ in groups]
        if len(story_ids) != len(set(story_ids)):
            raise ValueError("IDML text thread IDs collide after sanitization")
        return groups, references

    # ------------------------------------------------------------ typography
    def _face(self, elem):
        """(family, InDesign font style, face record) for a text element."""
        from ..fonts import resolve_face
        st = elem.style
        from ..fonts import style_face_args
        args = style_face_args(st) if st else {"weight": 400, "italic": False, "width": None}
        weight = args["weight"]
        family = (st.font_family if st else None) or "serif"
        face = resolve_face(family, weight=weight, italic=args["italic"], width=args["width"],
                            text=elem.text_content or "")
        if face:
            style = face.get("subfamily") or ("Bold" if weight >= 700 else "Regular")
            self._used_fonts[(face["family"], style)] = face
            return face["family"], style, face
        name = family.split(",")[0].strip()
        style = "Bold" if weight >= 700 else "Regular"
        self._used_fonts[(name, style)] = None
        return name, style, None

    def _shape_fill_xml(self, elem, left_pt, top_pt, w_pt, h_pt, item_transform, layer) -> str:
        from ..shapes import is_rect, shape_polygon
        st = elem.style
        fill = self._swatch(st.bg_color) if st and st.bg_color else "Swatch/None"
        stroke = (f' StrokeColor="{self._swatch(st.border_color)}" StrokeWeight="{float(st.border_width_mm) * MM_TO_PT:.2f}"'
                  if st and st.border_width_mm and st.border_color else ' StrokeWeight="0"')
        tag = "Rectangle" if is_rect(elem.shape) else "Polygon"
        geometry = self._path_geometry(shape_polygon(elem.shape, left_pt, top_pt, w_pt, h_pt))
        return f"""
        <{tag} Self="u_fill_{elem.id}" ItemLayer="{layer}" ItemTransform="{item_transform}" FillColor="{fill}"{stroke}>
          <Properties>
{geometry}
          </Properties>
        </{tag}>"""

    def _swatch(self, hex_color: Optional[str]) -> str:
        if not hex_color or hex_color.lower() in {"#000", "#000000", "#111111", "#0f0f0f"}:
            return "Color/Black"
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        k = 1 - max(r, g, b)
        c, m, y = [(0 if k >= 1 else (1 - v - k) / (1 - k)) for v in (r, g, b)]
        name = f"Color/Z_{h.upper()}"
        self._swatches[name] = f"{c*100:.0f} {m*100:.0f} {y*100:.0f} {k*100:.0f}"
        return name

    def _story_xml(self, story_id, members, style_map, advertorial_labels=None):
        ranges = []
        previous_text = ""
        just = {"justify": "LeftJustified", "left": "LeftAlign", "center": "CenterAlign", "right": "RightAlign"}
        for elem in members:
            text = elem.text_content or ""
            label = (advertorial_labels or {}).get(elem.id) if isinstance(advertorial_labels, dict) else None
            if label:
                text = f"{label}\n{text}"
            if previous_text and text and not previous_text[-1].isspace() and not text[0].isspace():
                text = " " + text
            content_xml = "<Br/>".join(
                f"<Content>{saxutils.escape(line)}</Content>"
                for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            )
            style_name = f"ParagraphStyle/{style_map.get(elem.role, 'Korpus')}"
            st = elem.style
            size = float((st.font_size_pt if st else None) or 9.5)
            leading = float((st.line_height_pt if st else None) or size * 1.2)
            family, fstyle, _ = self._face(elem)
            align = just.get((st.align if st else "left") or "left", "LeftAlign")
            hyph = "true" if size < 14 else "false"
            caps = ' Capitalization="AllCaps"' if st and st.case == "upper" else ""
            if st and st.tracking_em:
                caps += f' Tracking="{st.tracking_em * 1000:.0f}"'  # InDesign: 1/1000 em
            color = self._swatch(st.color if st else None)
            drop_cap_attr = ""
            if st and getattr(st, "drop_cap", False):
                dc_lines = getattr(st, "drop_cap_lines", None) or 3
                drop_cap_attr = f' DropCapLines="{dc_lines}" DropCapCharacters="1"'
            ranges.append(f"""
    <ParagraphStyleRange AppliedParagraphStyle="{style_name}" Justification="{align}" Hyphenation="{hyph}"{drop_cap_attr} HyphenateWordsLongerThan="5" HyphenateAfterFirst="2" HyphenateBeforeLast="3" HyphenationZone="0">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]" AppliedLanguage="$ID/Polish" PointSize="{size:.2f}" FontStyle="{saxutils.escape(fstyle)}" FillColor="{color}"{caps}>
        <Properties><AppliedFont type="string">{saxutils.escape(family)}</AppliedFont><Leading type="unit">{leading:.2f}</Leading></Properties>
        {content_xml}
      </CharacterStyleRange>
    </ParagraphStyleRange>""")
            if text:
                previous_text = text
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <Story Self="{saxutils.escape(story_id, {'"': '&quot;'})}" AppliedNamedGrid="n">
{''.join(ranges)}
  </Story>
</idPkg:Story>"""

    @staticmethod
    def _path_geometry(points, extra_rings=None):
        """PathGeometry; several GeometryPathType children form a compound
        path (outer ring + holes), which InDesign renders even-odd."""
        rings = [points, *(extra_rings or [])]
        geometry = []
        for ring in rings:
            if len(ring) < 3:
                continue
            point_xml = "\n".join(
                f'                  <PathPointType Anchor="{x:.2f} {y:.2f}" LeftDirection="{x:.2f} {y:.2f}" RightDirection="{x:.2f} {y:.2f}"/>'
                for x, y in ring
            )
            geometry.append(f"""
              <GeometryPathType PathOpen="false">
                <PathPointArray>
{point_xml}
                </PathPointArray>
              </GeometryPathType>""")
        return f"""
            <PathGeometry>{''.join(geometry)}
            </PathGeometry>"""

    def render_package(self, sg: SceneGraph, package_dir: str) -> dict:
        """InDesign-style package: <dir>/<name>.idml + Links/ + Document fonts/ + report."""
        import json, shutil
        out = Path(package_dir)
        (out / "Links").mkdir(parents=True, exist_ok=True)
        idml = out / f"{out.name}.idml"
        self._package_links_dir = out / "Links"
        self.render_to_zip(sg, str(idml))
        fonts_dir = out / "Document fonts"
        fonts_dir.mkdir(exist_ok=True)
        report = []
        from ..fonts import local_file
        for (family, style), face in self._used_fonts.items():
            row = {"family": family, "style": style, "in_library": bool(face), "polish": (face or {}).get("polish"),
                   "embedding": (face or {}).get("embedding"), "packaged": False}
            if face and face.get("embedding") in {"installable", "editable"}:
                src = local_file(face)
                if src:
                    shutil.copy2(src, fonts_dir / src.name.split("_", 1)[-1]); row["packaged"] = True
            elif face:
                row["note"] = "licencja nie pozwala dołączyć pliku — zainstaluj font na komputerze z InDesignem"
            else:
                row["note"] = "font spoza biblioteki"
            report.append(row)
        (out / "fonts_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._package_links_dir = None
        return {"idml": str(idml), "links": sorted(p.name for p in (out / "Links").iterdir()), "fonts": report}

    def render_to_zip(self, sg: SceneGraph, output_idml_path: str) -> str:
        """
        Generate an IDML package from scene geometry and editorial text chains.

        XML and reference integrity are locally testable. Adobe InDesign must
        still open the package to verify composition and final print output.
        """
        self._used_fonts: dict = {}
        self._swatches: dict = {}
        masthead_layer = "u_layer_winieta"
        text_layer, image_layer = "u_layer_tekst", "u_layer_zdjecia"
        pw_pt = sg.page.trim[0] * MM_TO_PT
        ph_pt = sg.page.trim[1] * MM_TO_PT
        bleed_pt = sg.page.bleed_mm * MM_TO_PT
        page_count = 2 if sg.page.page_zone == "spread" else 1
        page_width_pt = pw_pt / page_count
        # Spread trim describes the complete canvas. Pages occupy adjacent
        # halves while page items retain their existing spread coordinates.
        declared_width = sg.metadata.get("single_page_width_mm")
        if page_count == 2 and declared_width is not None:
            if abs(float(declared_width) * 2 - sg.page.trim[0]) > .01:
                raise ValueError("Spread trim must equal twice single_page_width_mm")
            page_width_pt = float(declared_width) * MM_TO_PT

        # 1. mimetype
        mimetype_content = "application/vnd.adobe.indesign-idml-package"

        # 2. META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="designmap.xml" media-type="text/xml"/>
  </rootfiles>
</container>"""

        spread_elements_xml = []
        linked_assets: dict[str, Path] = {}
        style_map = {
            "headline": "Tytul", "lead": "Lead", "body": "Korpus",
            "caption": "Podpis", "kicker": "Nadtytul", "logo": "Winieta",
            "folio": "Folio", "byline": "Autor", "deck": "Deck",
            "pullquote": "Cytat", "infobox": "Infobox", "brief_column": "Krotkie",
            "teaser_band": "Zapowiedz", "jump_line": "CiagDalszy", "column": "Felieton",
            "masthead": "Winieta",
        }
        story_groups, text_references = self._text_threads(sg)
        story_ids = [story_id for story_id, _ in story_groups]
        advertorial_labels = sg.metadata.get("advertorial_labels") or {}
        labels_xml = "".join(
            f'<Label Element="{saxutils.escape(str(element_id))}" Text="{saxutils.escape(str(label))}"/>'
            for element_id, label in advertorial_labels.items()
        ) if isinstance(advertorial_labels, dict) else ""
        stories_xml = {
            f"Stories/Story_{story_id}.xml": self._story_xml(story_id, members, style_map, advertorial_labels)
            for story_id, members in story_groups
        }

        for idx, elem in enumerate(sg.elements):
            x_pt = elem.frame.x * MM_TO_PT
            y_pt = elem.frame.y * MM_TO_PT
            w_pt = elem.frame.w * MM_TO_PT
            h_pt = elem.frame.h * MM_TO_PT

            top_pt = y_pt
            left_pt = x_pt
            bottom_pt = y_pt + h_pt
            right_pt = x_pt + w_pt
            # Transformation: rotation and shear (skew_y_deg) about frame.
            # InDesign uses standard 2D affine transformation matrices: [a, b, c, d, tx, ty].
            rot = float(getattr(elem.frame, "rotation_deg", 0.0) or 0.0)
            skew = float(getattr(elem.frame, "skew_y_deg", 0.0) or 0.0)
            has_rot = abs(rot) > 0.05
            has_skew = abs(skew) > 0.01

            if not has_rot and not has_skew:
                item_transform = "1 0 0 1 0 0"
            else:
                import math as _math
                t_skew = _math.tan(_math.radians(skew)) if has_skew else 0.0
                if not has_rot:
                    _a, _b, _c, _d = 1.0, -t_skew, 0.0, 1.0
                    _tx, _ty = 0.0, t_skew * left_pt
                else:
                    _r = _math.radians(rot)
                    _cos, _sin = _math.cos(_r), _math.sin(_r)
                    _cx, _cy = (left_pt + right_pt) / 2, (top_pt + bottom_pt) / 2
                    _rot_tx = _cx - _cos * _cx + _sin * _cy
                    _rot_ty = _cy - _sin * _cx - _cos * _cy
                    if not has_skew:
                        _a, _b, _c, _d = _cos, _sin, -_sin, _cos
                        _tx, _ty = _rot_tx, _rot_ty
                    else:
                        _a = _cos + _sin * t_skew
                        _b = _sin - _cos * t_skew
                        _c = -_sin
                        _d = _cos
                        _tx = _rot_tx - _sin * (t_skew * left_pt)
                        _ty = _rot_ty + _cos * (t_skew * left_pt)

                item_transform = f"{_a:.6f} {_b:.6f} {_c:.6f} {_d:.6f} {_tx:.3f} {_ty:.3f}"

            if elem.role == "photo" or (elem.role == "logo" and elem.image_url):
                # Keep local files in Links/ so the IDML remains portable. A
                # remote URL is retained as an explicit unresolved link.
                asset = local_asset(elem.image_url)
                asset_name = None
                if asset:
                    suffix = asset.suffix.lower() or ".jpg"
                    asset_name = f"Links/{elem.id}{suffix}"
                    linked_assets[asset_name] = asset
                link_uri = asset_name or (elem.image_url or "")
                links_dir = getattr(self, "_package_links_dir", None)
                if links_dir and asset_name:
                    import os
                    abs_path = str((Path(links_dir) / Path(asset_name).name).resolve())
                    for pair in filter(None, os.getenv("ZECRO_LINK_PATH_MAP", "").split(";")):
                        src_prefix, _, dst_prefix = pair.partition("=")
                        if abs_path.startswith(src_prefix):
                            abs_path = dst_prefix + abs_path[len(src_prefix):]
                    link_uri = "file:" + abs_path
                link_xml = ""
                if link_uri:
                    escaped_link_uri = saxutils.escape(link_uri, {'"': '&quot;'})
                    # Reproduce the scene-graph crop: the full image is placed
                    # in its own coordinates (pixels) and scaled/translated so
                    # that crop_box exactly fills the frame — same crop as PDF.
                    src_w, src_h = elem.source_width_px, elem.source_height_px
                    if (not src_w or not src_h) and asset:
                        try:
                            from PIL import Image as _PILImage
                            with _PILImage.open(asset) as _im:
                                src_w, src_h = _im.size
                        except Exception:
                            src_w = src_h = None
                    if src_w and src_h and elem.role == "photo":
                        l, t, r, b = elem.crop_box or [0.0, 0.0, 1.0, 1.0]
                        sx = w_pt / max(1e-6, (r - l) * src_w)
                        sy = h_pt / max(1e-6, (b - t) * src_h)
                        tx = left_pt - sx * l * src_w
                        ty = top_pt - sy * t * src_h
                        img_transform = f"{sx:.6f} 0 0 {sy:.6f} {tx:.3f} {ty:.3f}"
                        graphic_bounds = f'Left="0" Top="0" Right="{src_w}" Bottom="{src_h}"'
                    elif src_w and src_h and elem.role == "logo":
                        # Logo: proportional fit (contain), centred in frame.
                        sc = min(w_pt / src_w, h_pt / src_h)
                        tx = left_pt + (w_pt - sc * src_w) / 2
                        ty = top_pt + (h_pt - sc * src_h) / 2
                        img_transform = f"{sc:.6f} 0 0 {sc:.6f} {tx:.3f} {ty:.3f}"
                        graphic_bounds = f'Left="0" Top="0" Right="{src_w}" Bottom="{src_h}"'
                    else:
                        img_transform = "1 0 0 1 0 0"
                        graphic_bounds = f'Left="0" Top="0" Right="{w_pt:.2f}" Bottom="{h_pt:.2f}"'
                    link_xml = f"""
            <Image Self="u_image_{elem.id}" ItemTransform="{img_transform}">
              <Properties><GraphicBounds {graphic_bounds} /></Properties>
              <Link Self="u_link_{elem.id}" LinkResourceURI="{escaped_link_uri}" StoredState="Normal" CanPackage="true" CanEmbed="true" />
            </Image>"""

                # IDML's wrap preference belongs to the page item and its
                # offsets are explicit; contour points are frame-relative in
                # the graph and therefore translated to page coordinates.
                wrap_xml = ""
                if elem.text_wrap and elem.text_wrap.mode != "none":
                    offset_pt = elem.text_wrap.offset_mm * MM_TO_PT
                    contour_attr = ""
                    if elem.contour_points:
                        points = [
                            f"{left_pt + p[0] * MM_TO_PT:.2f} {top_pt + p[1] * MM_TO_PT:.2f}"
                            for p in elem.contour_points
                        ]
                        path_data = saxutils.escape(' '.join(points), {'"': '&quot;'})
                        contour_attr = f' PathData="{path_data}"'
                    mode = "Contour" if elem.text_wrap.mode == "contour" else "BoundingBox"
                    wrap_xml = f"""
          <TextWrapPreference TextWrapMode="{mode}" TextWrapSide="BothSides" Inverse="false">
            <Properties><TextWrapOffset Top="{offset_pt:.2f}" Left="{offset_pt:.2f}" Bottom="{offset_pt:.2f}" Right="{offset_pt:.2f}" /></Properties>
            <ContourOption ContourType="SameAsClipping" IncludeInsideEdges="false"{contour_attr} />
          </TextWrapPreference>"""

                is_cutout = elem.treatment == "cutout" and elem.contour_points and len(elem.contour_points) >= 3
                to_page = lambda ring: [(left_pt + point[0] * MM_TO_PT, top_pt + point[1] * MM_TO_PT) for point in ring]
                from ..shapes import is_rect as _is_rect, shape_polygon as _shape_polygon
                shaped = not is_cutout and not _is_rect(elem.shape)
                if is_cutout:
                    clipping_geometry = self._path_geometry(to_page(elem.contour_points), [to_page(r) for r in (elem.contour_holes or [])])
                elif shaped:
                    clipping_geometry = self._path_geometry(_shape_polygon(elem.shape, left_pt, top_pt, w_pt, h_pt))
                else:
                    clipping_geometry = self._path_geometry([
                        (left_pt, top_pt), (right_pt, top_pt),
                        (right_pt, bottom_pt), (left_pt, bottom_pt),
                    ])
                # Non-rectangular (compound) frames are Polygons in InDesign.
                tag = "Polygon" if (is_cutout or shaped) else "Rectangle"
                layer_attr = f' ItemLayer="{masthead_layer if elem.role == "logo" else image_layer}"'
                rect_xml = f"""
        <{tag} Self="u_photo_{elem.id}" ItemTransform="{item_transform}" StrokeWeight="0" Locked="{'true' if elem.role == 'logo' else 'false'}"{layer_attr}>
          <Properties>
{clipping_geometry}
          </Properties>
          {wrap_xml}
          {link_xml}
        </{tag}>"""
                spread_elements_xml.append(rect_xml)

            elif elem.role == "band":
                spread_elements_xml.append(self._shape_fill_xml(elem, left_pt, top_pt, w_pt, h_pt, item_transform, image_layer))

            elif elem.role == "rule":
                ymid = top_pt + h_pt / 2
                weight = max(0.25, float((elem.style.border_width_mm if elem.style else None) or 0.25) * MM_TO_PT)
                spread_elements_xml.append(f"""
        <GraphicLine Self="u_rule_{elem.id}" ItemLayer="{text_layer}" StrokeWeight="{weight:.2f}" StrokeColor="Color/Black" ItemTransform="1 0 0 1 0 0">
          <Properties>
            <PathGeometry>
              <GeometryPathType PathOpen="true">
                <PathPointArray>
                  <PathPointType Anchor="{left_pt:.2f} {ymid:.2f}" LeftDirection="{left_pt:.2f} {ymid:.2f}" RightDirection="{left_pt:.2f} {ymid:.2f}"/>
                  <PathPointType Anchor="{right_pt:.2f} {ymid:.2f}" LeftDirection="{right_pt:.2f} {ymid:.2f}" RightDirection="{right_pt:.2f} {ymid:.2f}"/>
                </PathPointArray>
              </GeometryPathType>
            </PathGeometry>
          </Properties>
        </GraphicLine>""")
            else:
                story_id, previous_frame, next_frame = text_references[elem.id]
                cols = int((elem.style.columns if elem.style else 1) or 1)
                gutter_pt = float(self.dna.grid.gutter_mm if self.dna else 4.0) * MM_TO_PT
                layer = masthead_layer if elem.role == "logo" else text_layer
                if elem.style and elem.style.bg_color and elem.role != "logo":
                    # Colour planes behind copy are real InDesign objects
                    # (previously they were dropped from the IDML).
                    spread_elements_xml.append(self._shape_fill_xml(elem, left_pt, top_pt, w_pt, h_pt, item_transform, text_layer))
                from ..shapes import text_box as _text_box
                _bx, _by, _bw, _bh = _text_box(elem)
                inset = (f"{(_by - elem.frame.y) * MM_TO_PT:.2f} {(_bx - elem.frame.x) * MM_TO_PT:.2f} "
                         f"{(elem.frame.y + elem.frame.h - _by - _bh) * MM_TO_PT:.2f} {(elem.frame.x + elem.frame.w - _bx - _bw) * MM_TO_PT:.2f}")
                vj = {"center": "CenterAlign", "bottom": "BottomAlign"}.get((elem.style.valign if elem.style else None) or "top", "TopAlign")
                tf_xml = f"""
        <TextFrame Self="u_tf_{elem.id}" ParentStory="{story_id}" PreviousTextFrame="{previous_frame}" NextTextFrame="{next_frame}" ContentType="TextType" ItemLayer="{layer}" ItemTransform="{item_transform}">
          <Properties>
            <PathGeometry>
              <GeometryPathType PathOpen="false">
                <PathPointArray>
                  <PathPointType Anchor="{left_pt:.2f} {top_pt:.2f}" LeftDirection="{left_pt:.2f} {top_pt:.2f}" RightDirection="{left_pt:.2f} {top_pt:.2f}"/>
                  <PathPointType Anchor="{right_pt:.2f} {top_pt:.2f}" LeftDirection="{right_pt:.2f} {top_pt:.2f}" RightDirection="{right_pt:.2f} {top_pt:.2f}"/>
                  <PathPointType Anchor="{right_pt:.2f} {bottom_pt:.2f}" LeftDirection="{right_pt:.2f} {bottom_pt:.2f}" RightDirection="{right_pt:.2f} {bottom_pt:.2f}"/>
                  <PathPointType Anchor="{left_pt:.2f} {bottom_pt:.2f}" LeftDirection="{left_pt:.2f} {bottom_pt:.2f}" RightDirection="{left_pt:.2f} {bottom_pt:.2f}"/>
                </PathPointArray>
              </GeometryPathType>
            </PathGeometry>
          </Properties>
          <TextFramePreference TextColumnCount="{cols}" TextColumnGutter="{gutter_pt:.2f}" UseFixedColumnWidth="false" FirstBaselineOffset="AscentOffset" VerticalJustification="{vj}" InsetSpacing="{inset}"/>
        </TextFrame>"""
                spread_elements_xml.append(tf_xml)

        # 3. designmap.xml
        story_idpkg_entries = "\n".join([f'  <idPkg:Story src="Stories/Story_{sid}.xml"/>' for sid in story_ids])
        story_list = " ".join(story_ids)
        designmap_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<?aid style="50" type="document" readerVersion="6.0" featureSet="257" product="8.0(370)" ?>
<Document xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0" Self="d" StoryList="{saxutils.escape(story_list, {'"': '&quot;'})}" Name="Zecro.indd" ActiveLayer="{text_layer}" CMYKProfile="ISOnewspaper26v4" RGBProfile="sRGB IEC61966-2.1">
  <Language Self="Language/$ID/Polish" Name="$ID/Polish" HyphenationVendor="Hunspell" SpellingVendor="Hunspell"/>
  <idPkg:Graphic src="Resources/Graphic.xml"/>
  <idPkg:Fonts src="Resources/Fonts.xml"/>
  <idPkg:Styles src="Resources/Styles.xml"/>
  <idPkg:Preferences src="Resources/Preferences.xml"/>
  <Layer Self="{masthead_layer}" Name="Winieta" Visible="true" Locked="true" Printable="true"/>
  <Layer Self="{text_layer}" Name="Tekst" Visible="true" Locked="false" Printable="true"/>
  <Layer Self="{image_layer}" Name="Zdjęcia" Visible="true" Locked="false" Printable="true"/>
  <idPkg:Spread src="Spreads/Spread_u_spread_0.xml"/>
  <Section Self="u_section_0" Length="{page_count}" Name="" ContinueNumbering="false" IncludeSectionPrefix="false" PageNumberStart="1" Marker="" PageStart="u_page_0" SectionPrefix=""/>
{story_idpkg_entries}
</Document>"""

        # 4. Resources/Styles.xml
        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Styles xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <RootCharacterStyleGroup Self="u_rcsg">
    <CharacterStyle Self="CharacterStyle/$ID/[No character style]" Name="$ID/[No character style]"/>
  </RootCharacterStyleGroup>
  <RootParagraphStyleGroup Self="u_rpsg">
    <ParagraphStyle Self="ParagraphStyle/$ID/[No paragraph style]" Name="$ID/[No paragraph style]"/>
    <ParagraphStyle Self="ParagraphStyle/$ID/[Normal Paragraph Style]" Name="$ID/[Normal Paragraph Style]" PointSize="10" Leading="12"/>
    <ParagraphStyle Self="ParagraphStyle/Tytul" Name="Tytul" PointSize="36" Leading="38" FontStyle="Bold" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Lead" Name="Lead" PointSize="13" Leading="16" FontStyle="SemiBold" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Korpus" Name="Korpus" PointSize="9.5" Leading="11.5" Justification="FullyJustified"/>
    <ParagraphStyle Self="ParagraphStyle/Nadtytul" Name="Nadtytul" PointSize="9" Leading="10" FontStyle="Bold" Capitalization="AllCaps"/>
    <ParagraphStyle Self="ParagraphStyle/Podpis" Name="Podpis" PointSize="7.5" Leading="9" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Winieta" Name="Winieta" PointSize="32" Leading="34" FontStyle="Bold" Justification="CenterAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Folio" Name="Folio" PointSize="8.5" Leading="10" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Autor" Name="Autor" PointSize="8.5" Leading="10" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Deck" Name="Deck" PointSize="14" Leading="17" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Cytat" Name="Cytat" PointSize="18" Leading="22" FontStyle="Italic" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Infobox" Name="Infobox" PointSize="9" Leading="11" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Krotkie" Name="Krotkie" PointSize="9" Leading="11" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Zapowiedz" Name="Zapowiedz" PointSize="9" Leading="10" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/CiagDalszy" Name="CiagDalszy" PointSize="8" Leading="9" Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Felieton" Name="Felieton" PointSize="10" Leading="12" Justification="LeftAlign"/>
  </RootParagraphStyleGroup>
  <RootObjectStyleGroup Self="u_rosg">
    <ObjectStyle Self="ObjectStyle/$ID/[None]" Name="$ID/[None]"/>
    <ObjectStyle Self="ObjectStyle/$ID/[Normal Graphics Frame]" Name="$ID/[Normal Graphics Frame]"/>
    <ObjectStyle Self="ObjectStyle/$ID/[Normal Text Frame]" Name="$ID/[Normal Text Frame]"/>
  </RootObjectStyleGroup>
</idPkg:Styles>"""

        # 5. Resources/Fonts.xml
        families: dict = {}
        for (family, style), face in self._used_fonts.items():
            families.setdefault(family, []).append((style, face))
        fam_xml = []
        for family, faces in families.items():
            fx = "".join(f'\n    <Font Self="di{saxutils.escape(family)}{saxutils.escape(style)}" FontFamily="{saxutils.escape(family)}" Name="{saxutils.escape(family)} {saxutils.escape(style)}" PostScriptName="{saxutils.escape((face or {}).get("postscript_name") or (family + "-" + style).replace(" ", ""))}" Status="Installed" FontStyleName="{saxutils.escape(style)}"/>' for style, face in faces)
            fam_xml.append(f'  <FontFamily Self="di{saxutils.escape(family)}" Name="{saxutils.escape(family)}">{fx}\n  </FontFamily>')
        fonts_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Fonts xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
""" + "\n".join(fam_xml) + """
</idPkg:Fonts>"""

        # 6. Resources/Graphic.xml
        graphic_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Graphic xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <Swatch Self="Swatch/None" Name="None"/>
  <Color Self="Color/Registration" Model="Registration" Space="CMYK" ColorValue="100 100 100 100" Name="Registration"/>
  <Color Self="Color/Black" Model="Process" Space="CMYK" ColorValue="0 0 0 100" Name="Black"/>
  <Color Self="Color/Paper" Model="Process" Space="CMYK" ColorValue="0 0 0 0" Name="Paper"/>
  <Color Self="Color/RedAccent" Model="Process" Space="CMYK" ColorValue="0 100 100 0" Name="RedAccent"/>
""" + "".join(f'  <Color Self="{k}" Model="Process" Space="CMYK" ColorValue="{v}" Name="{k.split("/")[1]}"/>\n' for k, v in self._swatches.items()) + """</idPkg:Graphic>"""

        # 7. Resources/Preferences.xml
        prefs_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Preferences xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <DocumentPreference PageWidth="{page_width_pt:.2f}" PageHeight="{ph_pt:.2f}" BleedTop="{bleed_pt:.2f}" BleedBottom="{bleed_pt:.2f}" BleedInside="{bleed_pt:.2f}" BleedOutside="{bleed_pt:.2f}" PagesPerSpread="{page_count}"/>
</idPkg:Preferences>"""

        # 8. Spreads/Spread_u_spread_0.xml
        spread_children_str = "\n".join(spread_elements_xml)
        spread_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <Spread Self="u_spread_0" PageCount="{page_count}" ItemTransform="1 0 0 1 0 0" BindingLocation="0">
    <Page Self="u_page_0" Name="1" AppliedMaster="n" ItemTransform="1 0 0 1 0 0" GeometricBounds="0 0 {ph_pt:.2f} {page_width_pt:.2f}">
      <Properties>
        <PageColor Value="Color/Paper"/>
      </Properties>
    </Page>
{f'''    <Page Self="u_page_1" Name="2" AppliedMaster="n" ItemTransform="1 0 0 1 0 0" GeometricBounds="0 {page_width_pt:.2f} {ph_pt:.2f} {pw_pt:.2f}">
      <Properties>
        <PageColor Value="Color/Paper"/>
      </Properties>
    </Page>
''' if page_count == 2 else ''}
{spread_children_str}
  </Spread>
</idPkg:Spread>"""

        # Write ZIP Package
        with zipfile.ZipFile(output_idml_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. mimetype (MUST be first and uncompressed)
            zf.writestr("mimetype", mimetype_content, compress_type=zipfile.ZIP_STORED)
            # 2. container.xml
            zf.writestr("META-INF/container.xml", container_xml)
            # 3. designmap.xml
            zf.writestr("designmap.xml", designmap_xml)
            # 4. Resources
            zf.writestr("Resources/Styles.xml", styles_xml)
            zf.writestr("Resources/Fonts.xml", fonts_xml)
            zf.writestr("Resources/Graphic.xml", graphic_xml)
            zf.writestr("Resources/Preferences.xml", prefs_xml)
            # 5. Spreads
            zf.writestr("Spreads/Spread_u_spread_0.xml", spread_xml)
            # 6. Stories
            for path, xml_data in stories_xml.items():
                zf.writestr(path, xml_data)
            if labels_xml:
                zf.writestr("Metadata/AdvertorialLabels.xml", f'<?xml version="1.0" encoding="UTF-8"?><AdvertorialLabels>{labels_xml}</AdvertorialLabels>')
            # Package local photo files in Links/ so InDesign can resolve the
            # LinkResourceURI without a machine-specific absolute path.
            for archive_name, source_path in linked_assets.items():
                zf.write(source_path, archive_name)
        links_dir = getattr(self, "_package_links_dir", None)
        if links_dir:
            import shutil
            for archive_name, source_path in linked_assets.items():
                shutil.copy2(source_path, Path(links_dir) / Path(archive_name).name)

        return output_idml_path
