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
            if elem.role != "photo" and elem.id not in references:
                story_id = f"u_story_{elem.id}"
                groups.append((story_id, [elem]))
                references[elem.id] = (story_id, "n", "n")
        story_ids = [story_id for story_id, _ in groups]
        if len(story_ids) != len(set(story_ids)):
            raise ValueError("IDML text thread IDs collide after sanitization")
        return groups, references

    @staticmethod
    def _story_xml(story_id, members, style_map):
        ranges = []
        previous_text = ""
        for elem in members:
            text = elem.text_content or ""
            # The zone solver splits body copy at word boundaries. Joining the
            # fragments with one space restores continuous copy; existing
            # whitespace and paragraph breaks remain intact.
            if previous_text and text and not previous_text[-1].isspace() and not text[0].isspace():
                text = " " + text
            content_xml = "<Br/>".join(
                f"<Content>{saxutils.escape(line)}</Content>"
                for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            )
            style_name = f"ParagraphStyle/{style_map.get(elem.role, 'Korpus')}"
            ranges.append(f"""
    <ParagraphStyleRange AppliedParagraphStyle="{style_name}">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">
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
    def _path_geometry(points):
        point_xml = "\n".join(
            f'                  <PathPointType Anchor="{x:.2f} {y:.2f}" LeftDirection="{x:.2f} {y:.2f}" RightDirection="{x:.2f} {y:.2f}"/>'
            for x, y in points
        )
        return f"""
            <PathGeometry>
              <GeometryPathType PathOpen="false">
                <PathPointArray>
{point_xml}
                </PathPointArray>
              </GeometryPathType>
            </PathGeometry>"""

    def render_to_zip(self, sg: SceneGraph, output_idml_path: str) -> str:
        """
        Generate an IDML package from scene geometry and editorial text chains.

        XML and reference integrity are locally testable. Adobe InDesign must
        still open the package to verify composition and final print output.
        """
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
        stories_xml = {
            f"Stories/Story_{story_id}.xml": self._story_xml(story_id, members, style_map)
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
                link_xml = ""
                if link_uri:
                    escaped_link_uri = saxutils.escape(link_uri, {'"': '&quot;'})
                    link_xml = f"""
            <Image Self="u_image_{elem.id}" ItemTransform="1 0 0 1 0 0" GeometricBounds="{top_pt:.2f} {left_pt:.2f} {bottom_pt:.2f} {right_pt:.2f}">
              <Properties><GraphicBounds Left="0" Top="0" Right="{w_pt:.2f}" Bottom="{h_pt:.2f}" /></Properties>
              <Link Self="u_link_{elem.id}" LinkResourceURI="{escaped_link_uri}" AssetURL="{escaped_link_uri}" StoredState="Normal" CanPackage="true" CanEmbed="true" />
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

                if elem.treatment == "cutout" and elem.contour_points and len(elem.contour_points) >= 3:
                    clipping_points = [
                        (left_pt + point[0] * MM_TO_PT, top_pt + point[1] * MM_TO_PT)
                        for point in elem.contour_points
                    ]
                else:
                    clipping_points = [
                        (left_pt, top_pt), (right_pt, top_pt),
                        (right_pt, bottom_pt), (left_pt, bottom_pt),
                    ]
                clipping_geometry = self._path_geometry(clipping_points)
                rect_xml = f"""
        <Rectangle Self="u_photo_{elem.id}" ItemTransform="1 0 0 1 0 0" GeometricBounds="{top_pt:.2f} {left_pt:.2f} {bottom_pt:.2f} {right_pt:.2f}" StrokeWeight="0" Locked="{'true' if elem.role == 'logo' else 'false'}">
          <Properties>
{clipping_geometry}
          </Properties>
          {wrap_xml}
          {link_xml}
        </Rectangle>"""
                spread_elements_xml.append(rect_xml)

            else:
                story_id, previous_frame, next_frame = text_references[elem.id]
                tf_xml = f"""
        <TextFrame Self="u_tf_{elem.id}" ParentStory="{story_id}" PreviousTextFrame="{previous_frame}" NextTextFrame="{next_frame}" ContentType="TextType" TextColumnFixedWidth="{w_pt:.2f}" TextColumnCount="{elem.style.columns or 1}" ItemTransform="1 0 0 1 0 0" GeometricBounds="{top_pt:.2f} {left_pt:.2f} {bottom_pt:.2f} {right_pt:.2f}">
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
        </TextFrame>"""
                spread_elements_xml.append(tf_xml)

        # 3. designmap.xml
        story_idpkg_entries = "\n".join([f'  <idPkg:Story src="Stories/Story_{sid}.xml"/>' for sid in story_ids])
        story_list = " ".join(story_ids)
        designmap_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Document xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0" Self="d" StoryList="{saxutils.escape(story_list, {'"': '&quot;'})}">
  <idPkg:Graphic src="Resources/Graphic.xml"/>
  <idPkg:Fonts src="Resources/Fonts.xml"/>
  <idPkg:Styles src="Resources/Styles.xml"/>
  <idPkg:Preferences src="Resources/Preferences.xml"/>
  <idPkg:Spread src="Spreads/Spread_u_spread_0.xml"/>
{story_idpkg_entries}
</Document>"""

        # 4. Resources/Styles.xml
        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Styles xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <RootParagraphStyleGroup Self="u_rpsg">
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
  <RootCharacterStyleGroup Self="u_rcsg">
    <CharacterStyle Self="CharacterStyle/$ID/[No character style]" Name="$ID/[No character style]"/>
  </RootCharacterStyleGroup>
</idPkg:Styles>"""

        # 5. Resources/Fonts.xml
        fonts_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Fonts xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <FontFamily Self="Playfair Display" Name="Playfair Display">
    <Font Self="Playfair Display-Regular" FontFamily="Playfair Display" Name="Playfair Display Regular" PostScriptName="PlayfairDisplay-Regular"/>
    <Font Self="Playfair Display-Bold" FontFamily="Playfair Display" Name="Playfair Display Bold" PostScriptName="PlayfairDisplay-Bold"/>
  </FontFamily>
  <FontFamily Self="PT Serif" Name="PT Serif">
    <Font Self="PT Serif-Regular" FontFamily="PT Serif" Name="PT Serif Regular" PostScriptName="PTSerif-Regular"/>
  </FontFamily>
  <FontFamily Self="Inter" Name="Inter">
    <Font Self="Inter-Bold" FontFamily="Inter" Name="Inter Bold" PostScriptName="Inter-Bold"/>
  </FontFamily>
</idPkg:Fonts>"""

        # 6. Resources/Graphic.xml
        graphic_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Graphic xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <Color Self="Color/Black" Model="Process" Space="CMYK" ColorValue="0 0 0 100" Name="Black"/>
  <Color Self="Color/Paper" Model="Process" Space="CMYK" ColorValue="0 0 0 0" Name="Paper"/>
  <Color Self="Color/RedAccent" Model="Process" Space="CMYK" ColorValue="0 100 100 0" Name="RedAccent"/>
</idPkg:Graphic>"""

        # 7. Resources/Preferences.xml
        prefs_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Preferences xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <DocumentPreference PageWidth="{page_width_pt:.2f}" PageHeight="{ph_pt:.2f}" BleedTop="{bleed_pt:.2f}" BleedBottom="{bleed_pt:.2f}" BleedInside="{bleed_pt:.2f}" BleedOutside="{bleed_pt:.2f}" PagesPerSpread="{page_count}"/>
</idPkg:Preferences>"""

        # 8. Spreads/Spread_u_spread_0.xml
        spread_children_str = "\n".join(spread_elements_xml)
        spread_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">
  <Spread Self="u_spread_0" PageCount="{page_count}">
    <Page Self="u_page_0" GeometricBounds="0 0 {ph_pt:.2f} {page_width_pt:.2f}">
      <Properties>
        <PageColor Value="Color/Paper"/>
      </Properties>
    </Page>
{f'''    <Page Self="u_page_1" GeometricBounds="0 {page_width_pt:.2f} {ph_pt:.2f} {pw_pt:.2f}">
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
            # Package local photo files in Links/ so InDesign can resolve the
            # LinkResourceURI without a machine-specific absolute path.
            for archive_name, source_path in linked_assets.items():
                zf.write(source_path, archive_name)

        return output_idml_path
