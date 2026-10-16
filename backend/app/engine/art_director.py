"""AI art director + technical editor around the measured engine.

Roles (rulebook: ``app/knowledge/rulebook.md``):

* the **art director** (vision LLM) reads the title's DNA, its reference
  pages, the issue's material and photos, and returns a page plan expressed
  ONLY in the composer's declared moves;
* the **engine** executes the plan exactly (measured typesetting, Polish
  glyph ink, title fonts, print geometry) and the **hard gate** rejects what
  is never acceptable;
* the **technical editor** (vision LLM) looks at the render — the whole page
  and high-resolution close-ups — names defects from the catalogue and
  proposes fixes, again only as moves; the engine re-composes.

The loop keeps the best page that passes the gate; a new round replaces it
only when a blind pairwise judgement (both orders) prefers it.  Every call,
plan and review is kept in the trace, nothing is invented: if the AI is
unavailable the engine's default composition is returned with that reason.

Composers are registered with their move space, so the same loop drives any
newspaper type that has a composer (framed tabloid cover, collage cover,
broadsheet/compact front, magazine, TV).
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

KNOWLEDGE = Path(__file__).resolve().parents[1] / "knowledge"


# ------------------------------------------------------------------ moves
@dataclass
class Move:
    name: str
    kind: str                      # enum | number | lines | words
    describe: str
    options: Any = None            # enum: list; number: (lo, hi)
    default: Any = None
    story_rank: Optional[str] = None  # lines/words: which story's headline

    measured: Any = None           # engine measurements of the options (filled per material)

    def brief(self, current: Any = None) -> dict:
        d = {"nazwa": self.name, "typ": self.kind, "opis": self.describe, "domyslna": self.default}
        if self.measured is not None:
            d["zmierzone"] = self.measured
        if self.options is not None:
            d["dozwolone"] = list(self.options)
        if current is not None:
            d["aktualna"] = current
        return d

    def parse(self, raw: str, material) -> Any:
        raw = (raw or "").strip()
        if self.kind == "enum":
            if raw not in self.options:
                raise ValueError(f"{self.name}: '{raw}' spoza {self.options}")
            return raw
        if self.kind == "number":
            m_ = re.search(r"-?\d+(?:[.,]\d+)?", raw)
            if not m_:
                raise ValueError(f"{self.name}: '{raw}' nie jest liczbą")
            v = float(m_.group(0).replace(",", "."))
            lo, hi = self.options
            return max(lo, min(hi, v))
        story = next((s for s in material.stories if s.rank == self.story_rank), None)
        if story is None:
            raise ValueError(f"{self.name}: brak tekstu rangi {self.story_rank}")
        parts = [p.strip() for p in raw.split("|") if p.strip()]
        norm = lambda w: re.sub(r"[^\wąćęłńóśźż]", "", w.lower())
        words = [norm(w) for w in story.headline.split()]
        if self.kind == "lines":
            got = [norm(w) for p in parts for w in p.split()]
            if got != words:
                raise ValueError(f"{self.name}: wiersze nie składają się na tytuł „{story.headline}”")
            return parts
        if self.kind == "words":
            parts = [w for p in parts for w in p.split()]
            pick = [p for p in parts if norm(p) in words]
            if not pick:
                raise ValueError(f"{self.name}: żadne ze słów {parts} nie występuje w tytule")
            return pick[:3]
        raise ValueError(self.kind)


@dataclass
class Composer:
    key: str
    genre: str
    kit: str
    compose: Callable[[Any, dict], Any]
    moves: list[Move]
    dna: Callable[[], Any]
    describe_title: Callable[[Any], dict]
    references: list[Path] = field(default_factory=list)
    measure_moves: Optional[Callable[[Any, Any], None]] = None
    filter_moves: Optional[Callable[[list[Move], dict], list[Move]]] = None

    def move(self, name: str) -> Optional[Move]:
        return next((m for m in self.moves if m.name == name), None)

    def active_moves(self, genes: Optional[dict] = None) -> list[Move]:
        if self.filter_moves and genes is not None:
            return self.filter_moves(self.moves, genes)
        return self.moves


def _framed_wukadka() -> Composer:
    from .framed_cover import compose_framed_cover
    from .layered_cover import Kit

    def compose(material, genes):
        return compose_framed_cover(material, kit_name="wukadka", genes=dict(genes))

    def dna():
        return kit_dna("wukadka")

    def describe(material):
        from .cover_modules import wukadka_skeleton
        kit = Kit("wukadka")
        sk = wukadka_skeleton(kit, material, {})
        return {"nazwa": kit.data.get("name"), "gatunek": "G-TABLOID-FRAME",
                "format_mm": kit.data["format"]["trim_mm"],
                "kroje": {k: v.get("family") for k, v in (kit.data.get("fonts") or {}).items() if isinstance(v, dict)},
                "paleta": kit.data.get("palette"),
                "moduly": {n: {"rodzaj": m.kind, "kotwice": m.anchors} for n, m in sk.items()},
                "zasady_tytulu": ["rama (pas winiety, lewa listwa, belka 13°, dolna listwa) jest stała",
                                  "tytuł główny ŚCIĘTY 8,8° (shear): pionowe kreski liter zostają pionowe, prawy koniec "
                                  "wiersza jest wyżej — tak wygląda poprawne ścięcie, to nie obrót; wiersze wypełniają okno",
                                  "gwiazda wycięta przy prawym spadzie, głowa może zachodzić na winietę do 12 %",
                                  "roundel na osi belki; skybox: rozmowa + zapowiedź; dolna zapowiedź narożnik albo pas"]}

    root = Path(__file__).resolve().parent / "title_kits" / "wukadka" / "references"
    moves = [
        Move("bottom", "enum", "dolna zapowiedź: narożnik przy stopie belki albo pas na całą szerokość pod ramą",
             ["corner", "strip"], "corner"),
        Move("corner_photos", "enum", "portrety w dolnej zapowiedzi (narożnik lub pas): w prostokątach wypełniających "
             "wysokość albo wycięte głowy na kolorowej apli (wycięcie zawsze potrzebuje gruntu)", ["framed", "cutout"],
             "framed"),
        Move("skybox_order", "enum", "kolejność modułów skyboxu", ["interview_first", "other_first"], "interview_first"),
        Move("skybox_split", "number", "prawa krawędź lewego skyboxu, mm (szerszy lewy = większa rozmowa)", (112, 150), 132.0),
        Move("hero_dy", "number", "o ile mm obniżyć górę postaci (mniejsza postać, więcej winiety widać)", (0, 40), 0),
        Move("hero_shift", "number", "o ile mm przesunąć postać w prawo poza spad (mniej postaci na stronie)", (0, 30), 0),
        Move("lead_lines", "lines", "łamanie tytułu głównego: wybierz JEDNO z łamań zmierzonych przez silnik (pole "
             "`zmierzone`: wypełnienie wysokości, szerokości i powierzchni okna, stopnie wierszy; okno ma być "
             "wypełnione jak cegła — wysokie wypełnienie powierzchni). Pomiar zależy od akcentu: wybierz pozycję i ustaw "
             "`lead_emphasis` na jej `akcent`; podaj wiersze dokładnie jako tekst z |", None, None, "lead"),
        Move("lead_emphasis", "words", "1–3 słowa tytułu głównego w kolorze akcentu (czerwony), rozdzielone |", None,
             None, "lead"),
        Move("hero_emphasis", "words", "1–3 słowa tytułu gwiazdy w kolorze akcentu, rozdzielone |", None, None, "second"),
    ]
    def measure(comp, material):
        """Breaking × accent, measured together: the accent sets the line
        sizes (unstressed lines ≤ 0.8 × the stressed one), so the two are
        one decision for the director."""
        from .cover_modules import lead_breakings, wukadka_skeleton
        kit = Kit("wukadka")
        lead = next((s for s in material.stories if s.rank == "lead"), None)
        if lead is None:
            return
        sk = wukadka_skeleton(kit, material, {})
        words = lead.headline.split()
        accents = [list(lead.headline_emphasis)] if lead.headline_emphasis else []
        accents += [[w] for w in words if len(w) > 2]
        accents += [[a, b] for a, b in zip(words, words[1:])]
        seen, rows = set(), []
        for acc in accents:
            key = tuple(w.lower() for w in acc)
            if key in seen:
                continue
            seen.add(key)
            st = lead.model_copy(update={"headline_emphasis": acc})
            for d in lead_breakings(kit, sk, st, limit=4):
                rows.append({**d, "akcent": " | ".join(acc)})
        rows.sort(key=lambda d: ((d.get("dziura_okna_cm2", 0) > 30), -d["wypelnienie_powierzchni"] + (.5 if d["uwagi"] else 0)))
        comp.move("lead_lines").measured = rows[:12]

    def filter_moves(moves_list: list[Move], current_genes: dict) -> list[Move]:
        hero_mode = (current_genes or {}).get("hero_mode", "breakout")
        if hero_mode == "breakout":
            return [m for m in moves_list if m.name not in ("hero_dy", "hero_shift")]
        return moves_list

    return Composer("framed_cover:wukadka", "G-TABLOID-FRAME", "wukadka", compose, moves, dna, describe,
                    sorted(root.glob("*.jpg")), measure, filter_moves=filter_moves)


# the engine's five base archetypes (corpus_indexer.create_archetype_dnas)
ARCHETYPE_GENRE = {"quality_press": "G-BROADSHEET", "mass_market": "G-COMPACT", "tabloid": "G-TABLOID-COLLAGE",
                   "editorial_magazine": "G-MAGAZINE", "tv_guide": "G-TV"}


def _planned_page(archetype: str, zone: str = "front_page") -> Composer:
    """The generic page composer (zone solver / plan composer) for any title
    archetype, front or inside page.  Moves: page architecture, photo
    treatment, the dominant story, variation."""
    from .corpus_indexer import create_archetype_dnas
    from .zone_solver import compose_page

    genre = "G-INSIDE" if zone != "front_page" else ARCHETYPE_GENRE.get(archetype, "G-COMPACT")

    def dna():
        return create_archetype_dnas()[archetype]

    def compose(material, genes):
        genes = dict(genes)
        lead_id = genes.pop("dominant_story", None)
        if lead_id and any(st.id == lead_id for st in material.stories):
            stories = []
            for st in material.stories:
                if st.id == lead_id:
                    st = st.model_copy(update={"rank": "lead", "importance": 1.0})
                elif st.rank == "lead":
                    st = st.model_copy(update={"rank": "second", "importance": min(st.importance, .8)})
                stories.append(st)
            material = material.model_copy(update={"stories": stories})
        return compose_page(dna(), material.model_copy(update={"page_zone": zone}), genes)

    def describe(material):
        d = dna()
        return {"nazwa": d.name, "gatunek": genre, "archetyp": archetype, "strefa": zone,
                "format_mm": [d.format.trim_w_mm, d.format.trim_h_mm], "lamy": d.grid.columns,
                "rowek_mm": d.grid.gutter_mm,
                "zasady_tytulu": ["siatka tytułu bez wyjątków; moduły prostokątne na łamach",
                                  "jedna dominanta; tytuły stopniowane skokami; reklama/skrzynka to moduł"]}

    moves = [
        Move("layout_mode", "enum", "architektura strony: dominanta z lewej (szpalta boczna z prawej), z prawej, "
             "siatka modułowa, zdjęcie wiodące u góry, układ warstwowy (stacked)",
             ["dominant-left", "dominant-right", "modular-grid", "photo-top", "stacked"], "dominant-left"),
        Move("photo_treatment", "enum", "traktowanie zdjęć: kadr prostokątny albo wycięcie (tylko gdy są maski)",
             ["crop", "cutout"], "crop"),
        Move("variation", "number", "wariant architektury (0 = zachowawczy, 1 = śmielszy)", (0, 1), .5),
        Move("dominant_story", "enum", "który tekst jest dominantą strony (id)", [], None),
    ]
    comp = Composer(f"planned_page:{archetype}:{zone}", genre, archetype, compose, moves, dna, describe, [])

    def measure(c, material):
        c.move("dominant_story").options = [st.id for st in material.stories]
    comp.measure_moves = measure
    return comp


def _kit_composer(kit_name: str, zone: str = "front_page") -> Composer:
    from .corpus_indexer import create_archetype_dnas
    from .zone_solver import compose_page
    from .layered_cover import load_kit

    kit_data = load_kit(kit_name)
    genre = kit_data.get("genre", "G-COMPACT")

    def dna():
        return kit_dna(kit_name)

    def compose(material, genes):
        genes = dict(genes)
        lead_id = genes.pop("dominant_story", None)
        if lead_id and any(st.id == lead_id for st in material.stories):
            stories = []
            for st in material.stories:
                if st.id == lead_id:
                    st = st.model_copy(update={"rank": "lead", "importance": 1.0})
                elif st.rank == "lead":
                    st = st.model_copy(update={"rank": "second", "importance": min(st.importance, .8)})
                stories.append(st)
            material = material.model_copy(update={"stories": stories})
        return compose_page(dna(), material.model_copy(update={"page_zone": zone}), genes)

    def describe(material):
        d = dna()
        return {"nazwa": d.name, "gatunek": genre, "kit": kit_name, "strefa": zone,
                "format_mm": [d.format.trim_w_mm, d.format.trim_h_mm], "lamy": d.grid.columns,
                "rowek_mm": d.grid.gutter_mm,
                "zasady_tytulu": ["rygorystyczna siatka tytułu; proporcje i skala z zestawu marki",
                                  "jedna dominanta, zrównoważone kolumny, brak uwięzionej bieli"]}

    moves = [
        Move("layout_mode", "enum", "architektura strony: dominanta z lewej, z prawej, siatka modułowa, zdjęcie u góry, układ warstwowy",
             ["dominant-left", "dominant-right", "modular-grid", "photo-top", "stacked"], "dominant-left"),
        Move("photo_treatment", "enum", "traktowanie zdjęć: kadr prostokątny albo wycięcie",
             ["crop", "cutout"], "crop"),
        Move("variation", "number", "wariant architektury (0 = zachowawczy, 1 = dynamiczny)", (0, 1), .5),
        Move("dominant_story", "enum", "który tekst jest dominantą strony (id)", [], None),
    ]
    comp = Composer(f"title_kit:{kit_name}", genre, kit_name, compose, moves, dna, describe, [])

    def measure(c, material):
        c.move("dominant_story").options = [st.id for st in material.stories]
    comp.measure_moves = measure
    return comp


COMPOSERS: dict[str, Callable[[], Composer]] = {
    "framed_cover:wukadka": _framed_wukadka,
    "title_kit:daily_broadsheet": lambda: _kit_composer("daily_broadsheet"),
    "title_kit:opinion_magazine": lambda: _kit_composer("opinion_magazine"),
}
for _arch in ARCHETYPE_GENRE:
    for _zone in ("front_page", "spread"):          # "spread" = inside page in the engine's schema
        COMPOSERS[f"planned_page:{_arch}:{_zone}"] = (lambda a=_arch, z=_zone: _planned_page(a, z))


def kit_dna(kit_name: str):
    """TitleDNA for a title kit: the archetype's DNA with the kit's measured
    format and live area."""
    from .corpus_indexer import create_archetype_dnas
    from .layered_cover import load_kit
    kit = load_kit(kit_name)
    arch = kit.get("archetype") or ("quality_press" if kit.get("genre") == "G-BROADSHEET" else ("editorial_magazine" if kit.get("genre") == "G-MAGAZINE" else "tabloid"))
    dna = create_archetype_dnas()[arch]
    fmt = kit["format"]
    dna.name = kit["name"]
    dna.format.trim_w_mm, dna.format.trim_h_mm = fmt["trim_mm"]
    dna.format.bleed_mm = fmt["bleed_mm"]
    live = fmt["live"]
    dna.format.margin_left_mm = live["left"]
    dna.format.margin_right_mm = fmt["trim_mm"][0] - live["right"]
    dna.format.margin_top_mm = live["top"]
    dna.format.margin_bottom_mm = fmt["trim_mm"][1] - live["bottom"]
    return dna


# --------------------------------------------------------------- knowledge
def _norms(genre: str) -> dict:
    try:
        from .press_norms import norms_for
        return norms_for(genre)
    except Exception:
        return {}


def knowledge() -> dict:
    rb = (KNOWLEDGE / "rulebook.md").read_text(encoding="utf-8")
    defects = json.loads((KNOWLEDGE / "defects.json").read_text(encoding="utf-8"))["defects"]
    out = {"zasady_i_gramatyki": rb,
           "defekty": [{k: d[k] for k in ("id", "name", "severity", "rule", "desc")} for d in defects]}
    pn = KNOWLEDGE / "press_norms.md"
    if pn.exists():
        txt = pn.read_text(encoding="utf-8")
        i = txt.find("## Wnioski")
        if i >= 0:
            out["wnioski_z_pomiarow_prasy"] = txt[i:]
    return out


def material_brief(material) -> tuple[dict, list[dict]]:
    """Facts about the copy and photos; photos also returned as image parts."""
    from .cutout_quality import cut_sides
    stories, photos = [], []
    for s in material.stories:
        st = {"id": s.id, "ranga": s.rank, "grupa": s.group, "nadtytul": s.kicker, "tytul": s.headline,
              "lead": (s.lead or "")[:400], "odsylacz": s.page_ref, "akcent_redakcji": s.headline_emphasis, "zdjecia": []}
        for im in s.images:
            an = im.photo_analysis or {}
            faces = an.get("faces") or []
            st["zdjecia"].append({"id": im.id, "px": [im.width_px, im.height_px], "wyciecie": bool(im.alpha_mask_url),
                                  "twarze": len(faces),
                                  "twarz_wys_udzial": round(faces[0][3] - faces[0][1], 2) if faces else None,
                                  "kadr_ucina_postac": list(cut_sides(im.alpha_mask_url)) if im.alpha_mask_url else []})
            photos.append({"id": im.id, "path": im.url})
        stories.append(st)
    return {"wydanie": material.issue_number, "data": material.issue_date, "nastroj": material.editorial_mood,
            "teksty": stories, "zdjecia": [p["id"] for p in photos]}, photos


def _jpeg(img, max_side: int = 1400, quality: int = 86) -> dict:
    from PIL import Image
    if not isinstance(img, Image.Image):
        img = Image.open(img)
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    b = io.BytesIO()
    img.save(b, "JPEG", quality=quality)
    return {"data": b.getvalue(), "mime_type": "image/jpeg"}


def render(scene, dna, out_pdf: Path):
    """PDF for print + page image + six close-ups (2×3) for the editor."""
    import pypdfium2 as pdfium
    from .renderers.pdf_renderer import PDFRenderer
    PDFRenderer(dna).render_to_file(scene, str(out_pdf))
    page = pdfium.PdfDocument(str(out_pdf))[0]
    big = page.render(scale=4.0).to_pil()
    W, H = big.size
    full = big.copy()
    full.thumbnail((1200, 1700))
    full.save(out_pdf.with_suffix(".png"))
    crops = []
    for r in range(3):
        for c in range(2):
            box = (int(W * c / 2 - (W * .04 if c else 0)), int(H * r / 3 - (H * .03 if r else 0)),
                   int(W * (c + 1) / 2 + (W * .04 if not c else 0)), int(H * (r + 1) / 3 + (H * .03 if r < 2 else 0)))
            crops.append(big.crop(box))
    return full, crops


def measurements(scene) -> dict:
    """What the engine measured on the page: given to the editor as facts."""
    from .cutout_quality import cut_sides
    from .layered_cover import Silhouette
    meta = scene.metadata or {}
    masks = meta.get("cutout_masks") or {}
    modules = meta.get("modules") or {}
    out: dict[str, Any] = {"wyciecia": [], "twarze_mm": {}, "winieta": None}
    sheared = [e for e in scene.elements if e.frame.skew_y_deg]
    if sheared:
        out["typografia"] = {"sciete_elementy": len(sheared),
                             "kat_sciecia_deg": sorted({round(e.frame.skew_y_deg, 1) for e in sheared}),
                             "obrot_deg": sorted({round(e.frame.rotation_deg or 0, 1) for e in sheared}),
                             "fakt": "pionowe kreski liter są pionowe (obrót 0°), linia pisma wznosi się — to ścięcie, "
                                     "zgodne z tradycją tytułu; nie jest to obrót"}
    from .layered_rules import cut_edge_report, empty_in_boxes, window_holes
    cuts = cut_edge_report(scene.elements, meta, list(scene.page.trim or []))
    wh = window_holes(scene.elements, meta)
    if wh:
        out["dziury_w_oknach_cm2"] = {name: round(a, 1) for name, a in wh}
    else:
        out["dziury_w_oknach"] = "brak dziur w oknach powyżej dopuszczalnego limitu"
    eb = empty_in_boxes(scene.elements, meta)
    if eb:
        out["puste_pola_w_pudelkach"] = {pid: {"cm2": round(a, 1), "proc": round(s, 1)} for pid, a, s in eb}
    for e in scene.elements:
        if e.role != "photo":
            continue
        tag = next((t.split(":", 1)[1] for t in (e.constraints or []) if t.startswith("module:")), None)
        item = {"element": e.id, "tekst": e.story_ref, "modul": tag, "traktowanie": e.treatment}
        if e.treatment == "cutout" and e.id in masks:
            item["krawedz"] = "kontur wygładzony po wewnętrznej stronie włosów, brzeg odkażony, zmiękczenie ~0,15 mm"
            rep = next((r for r in cuts if r["element"] == e.id), None)
            if rep:
                item["proste_ciecia"] = {k: (v["where"] + (f", widoczne {v['visible_mm']} mm" if v["visible_mm"] else ""))
                                         for k, v in rep["sides"].items()}
        out["wyciecia"].append(item)
    for pid, boxes in (meta.get("face_boxes") or {}).items():
        out["twarze_mm"][pid] = [round(b[3] - b[1], 1) for b in boxes]
    rule = meta.get("logo_rule") or {}
    logo = next((e for e in scene.elements if e.id == rule.get("element")), None)
    if logo:
        worst = 0.0
        for e in scene.elements:
            if e.role == "photo" and e.treatment == "cutout" and e.id in masks and e.z > logo.z:
                ext = Silhouette(masks[e.id], e.frame, e.crop_box).x_extent(logo.frame.y, logo.frame.y + logo.frame.h)
                lx1 = logo.frame.x + logo.frame.w
                if ext and ext[0] < lx1 and ext[1] > logo.frame.x:
                    worst = max(worst, (min(lx1, ext[1]) - max(logo.frame.x, ext[0])) / logo.frame.w)
        out["winieta"] = {"zaslonieta_szerokosc": round(worst, 3), "limit_tytulu": rule.get("max_covered_share"),
                          "zmierzone_na_oryginale_NR21": 0.09}
    try:
        from .aesthetics import evaluate_page_aesthetics
        aes = evaluate_page_aesthetics(scene)
        out["estetyka_kompozycyjna"] = {
            "indeks_estetyki": aes.total_aesthetic_index,
            "rownowaga_optyczna": aes.balance_score,
            "rownomiernosc_pionowa": aes.equilibrium_score,
            "czystosc_osi_rytm": aes.rhythm_score,
            "uwieziona_biel_cm2": aes.trapped_whitespace_cm2,
            "jasnosc_punktu_wejscia": aes.entry_point_score,
            "spojrzenie_postaci_do_wewnatrz": aes.gaze_alignment_score,
            "kotwica_dolna": aes.bottom_anchor_score,
            "rekomendacje": aes.recommendations[:4],
        }
    except Exception as exc:
        out["estetyka_kompozycyjna"] = {"error": str(exc)[:160]}
    return out


# Defects the engine measures exactly: the editor's eye is overruled by the
# instrument when the gate found none of them (and its fixes for them dropped).
MEASURED = {"D07": ("Twarz na zdjęciu",), "D09": ("kończy się prostą krawędzią",), "D26": ("stoi na białym papierze",), "D27": ("Martwe pole",),
            "D29": ("rozminęły się",), "D30": ("Klin białego", "nie sięga pod belkę")}


def _against_measurements(review: dict, violations: list[str]) -> dict:
    if not isinstance(review, dict) or not review.get("defekty"):
        return review
    import re
    dropped = {d for d, marks in MEASURED.items() if not any(m in v for v in violations for m in marks)}
    keep, gone = [], []
    for d in review["defekty"]:
        (gone if d.get("id") in dropped else keep).append(d)
    if not gone:
        return review
    gone_ids = {d.get("id") for d in gone}
    kept_ids = {d.get("id") for d in keep}
    fixes = []
    for f in review.get("poprawki") or []:
        ids = set(re.findall(r"D\d\d", str(f.get("naprawia", ""))))
        if ids and ids <= gone_ids and not ids & kept_ids:
            continue
        fixes.append(f)
    return {**review, "defekty": keep, "poprawki": fixes,
            "odrzucone_przez_pomiar": [{**d, "powod": "pomiar silnika nie potwierdza"} for d in gone]}


def _clean_genes(g: dict) -> dict:
    return {k: v for k, v in (g or {}).items() if k != "hero_place"}


def _vet(comp: Composer, material, critic, genes: dict, fixes: list[dict], log: list, max_tries: int = 3,
         forbidden_genes: Optional[list[dict]] = None) -> dict:
    """The technical editor tries the proposed moves on the engine before a
    round is spent on them: when the set breaks the gate or returns to a
    forbidden/lost configuration, the move whose removal clears the problem
    is dropped (logged with the reason)."""
    clean_forbidden = [_clean_genes(fg) for fg in (forbidden_genes or [])]

    def run(fx):
        g = _apply(comp, genes, fx, material, [])
        g.pop("hero_place", None)
        cg = _clean_genes(g)
        if any(cg == fg for fg in clean_forbidden):
            return g, ["konfiguracja już sprawdzona lub przegrana we wcześniejszej rundzie"]
        try:
            v = list(critic.evaluate_hard_gate(comp.compose(material, dict(g))).violations)
        except Exception as exc:          # a move the composer cannot build
            v = [f"kompozytor: {exc}"]
        return g, v

    new, viol = run(fixes)
    tries = 1
    while viol and len(fixes) > 1 and tries < max_tries:
        best = None
        for i in range(len(fixes)):
            if tries >= max_tries:
                break
            g, v = run(fixes[:i] + fixes[i + 1:])
            tries += 1
            if best is None or len(v) < len(best[2]):
                best = (i, g, v)
        if best is None or len(best[2]) >= len(viol):
            break
        log.append({"ruch": fixes[best[0]], "powod": "po próbie na silniku odrzucony: " + "; ".join(viol[:2])})
        fixes = fixes[:best[0]] + fixes[best[0] + 1:]
        new, viol = best[1], best[2]

    # Re-apply final remaining fixes and verify
    applied = _apply(comp, genes, fixes, material, log)
    applied.pop("hero_place", None)
    clean_applied = _clean_genes(applied)

    if any(clean_applied == fg for fg in clean_forbidden):
        log.append({"ruch": "wszystkie_poprawki", "powod": "prowadzi do konfiguracji z listy zakazanych/przetestowanych"})
        return dict(genes)

    try:
        final_viol = list(critic.evaluate_hard_gate(comp.compose(material, dict(applied))).violations)
        if final_viol:
            log.append({"ruch": "poprawki", "powod": "po próbie na silniku łamie bramkę: " + "; ".join(final_viol[:2])})
            return dict(genes)
    except Exception as exc:
        log.append({"ruch": "poprawki", "powod": f"kompozytor: {exc}"})
        return dict(genes)

    return applied


def _blocker_weight(rec: dict) -> float:
    rv = rec.get("review") or {}
    w = {"blocker": 3.0, "major": 1.0, "minor": .3}
    return sum(w.get(d.get("waga"), 1.0) for d in rv.get("defekty") or [])


def compare(comp, title, know, refs, new_img, best_img, new_rec, best_rec) -> str:
    """Blind comparison by a judge who knows the title (its reference pages
    and the rulebook), in both orders.  A split verdict is a tie, settled by
    the editors' defect weight (blockers 3, major 1, minor 0.3), then by the
    incumbent."""
    from ..ai.gemini_client import AIUnavailable
    from ..ai.runtime import run_task
    from ..ai.schemas import PairwiseJudgement
    votes = []
    measured = {"new": {"typografia": (new_rec.get("pomiary_typografia")), "normy": [
                    {k: r[k] for k in ("miara", "nasza", "mediana", "ocena")} for r in (new_rec.get("normy") or [])
                    if "miara" in r][:12]},
                "best": {"typografia": (best_rec.get("pomiary_typografia")), "normy": [
                    {k: r[k] for k in ("miara", "nasza", "mediana", "ocena")} for r in (best_rec.get("normy") or [])
                    if "miara" in r][:12]}}
    for a, b in (("new", "best"), ("best", "new")):
        imgs = {"new": _jpeg(new_img, 1300), "best": _jpeg(best_img, 1300)}
        try:
            facts = {"A": measured.get(a), "B": measured.get(b)}
            pj = run_task("layout_pairwise", "layout_pairwise",
                          {"podrecznik": know, "tytul": title, "pomiary": facts}, PairwiseJudgement,
                          images=[imgs[a], imgs[b]] + refs, timeout_s=150, max_retries=1).data
            winner = {"A": a, "B": b}.get(pj.get("winner"), "tie")
            new_rec.setdefault("pairwise", []).append({"A": a, "B": b, "winner": winner,
                                                       "reasons": pj.get("reasons", [])[:3]})
            votes.append(winner)
        except AIUnavailable as exc:
            new_rec.setdefault("pairwise", []).append({"error": str(exc)})
    if votes.count("new") == 2:
        return "new"
    if votes.count("best") == 2:
        return "best"
    # split verdict: the measured distance from the genre's norms decides
    # (same instrument as the corpus); the editors' defect weight is second
    from .press_norms import norm_distance
    dn, db = norm_distance(new_rec.get("normy") or []), norm_distance(best_rec.get("normy") or [])
    wn, wb = _blocker_weight(new_rec), _blocker_weight(best_rec)
    new_rec["tie_break"] = {"norm_distance_new": dn, "norm_distance_best": db,
                            "defect_weight_new": wn, "defect_weight_best": wb}
    if dn != db:
        return "new" if dn < db else "best"
    return "new" if wn < wb - 1.0 else "best"


# --------------------------------------------------------------- the loop
def _apply(composer: Composer, genes: dict, raw_moves: list[dict], material, log: list) -> dict:
    out = dict(genes)
    active_names = {m.name for m in composer.active_moves(genes)}
    for mv in raw_moves:
        name = mv.get("nazwa") or mv.get("ruch")
        value = mv.get("wartosc")
        if name not in active_names:
            m = composer.move(name or "")
            if m is not None:
                log.append({"odrzucony_ruch": name, "powod": f"ruch nieaktywny w trybie {genes.get('hero_mode', 'breakout')}"})
            else:
                log.append({"odrzucony_ruch": name, "powod": "spoza listy ruchów"})
            continue
        m = composer.move(name or "")
        try:
            out[m.name] = m.parse(str(value), material)
        except Exception as exc:
            log.append({"odrzucony_ruch": name, "wartosc": value, "powod": str(exc)})
    return out


def art_direct(material, composer_key: str = "framed_cover:wukadka", *, dna=None, rounds: int = 3,
               out_dir: Optional[Path] = None, tag: str = "ad", start_genes: Optional[dict] = None,
               resume: bool = False, max_new_rounds: Optional[int] = None) -> dict:
    """``resume``: continue a saved trace (one call may run only
    ``max_new_rounds`` rounds; the trace and every round's scene are saved
    after each round, so a long direction survives short worker limits)."""
    from ..ai.gemini_client import AIUnavailable
    from ..ai.runtime import run_task
    from ..ai.schemas import ArtPlan, LayoutReview, PairwiseJudgement
    from .critic import LayoutCritic

    comp = COMPOSERS[composer_key]()
    if comp.measure_moves:
        comp.measure_moves(comp, material)
    dna = dna or comp.dna()
    out_dir = Path(out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    know = knowledge()
    mat, photos = material_brief(material)
    title = comp.describe_title(material)
    refs = [_jpeg(p, 1000) for p in comp.references]
    trace: dict[str, Any] = {"composer": composer_key, "rounds": []}
    genes = dict(start_genes or {})
    trace_path = out_dir / f"{tag}.trace.json"
    from ..models.schemas import SceneGraph
    from PIL import Image
    best = None
    resumed = resume and trace_path.exists()
    if resumed:
        trace = json.loads(trace_path.read_text())
        plan = trace.get("plan") or {}
        genes = dict(trace.get("next_genes") or {})
        if trace.get("best_round"):
            br = next(r for r in trace["rounds"] if r["round"] == trace["best_round"])
            best = (SceneGraph.model_validate_json(Path(br["scene"]).read_text()), br,
                    Image.open(Path(br["pdf"]).with_suffix(".png")).convert("RGB"))
        if trace.get("done"):
            return {"scene": best[0] if best else None, "trace": trace}

    # 1. plan --------------------------------------------------------------
    if resumed:
        pass
    else:
      try:
        r = run_task("art_direction", "art_director",
                     {"podrecznik": know, "tytul": title, "material": mat,
                      "normy_z_korpusu": _norms(comp.genre),
                      "ruchy": [m.brief() for m in comp.active_moves(genes)]},
                     ArtPlan, images=refs + [_jpeg(p["path"], 900) for p in photos], timeout_s=180, max_retries=1)
        plan = r.data
        trace["plan"] = plan
        trace["plan_provenance"] = {k: r.provenance.get(k) for k in ("provider", "model", "prompt_id", "prompt_version", "cached")}
        log: list = []
        genes = _apply(comp, genes, plan.get("ruchy") or [], material, log)
        trace["plan_rejected_moves"] = log
      except AIUnavailable as exc:
        trace["plan"] = None
        trace["ai_unavailable"] = str(exc)
        plan = {}

    if not resumed:
        trace["next_genes"] = genes
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=1, default=str))
        if max_new_rounds == 0:
            return {"scene": None, "trace": trace}
    critic = LayoutCritic(dna)
    done_rounds = len(trace["rounds"])
    budget = max_new_rounds if max_new_rounds is not None else rounds
    for k in range(done_rounds, min(rounds, done_rounds + budget)):
        scene = comp.compose(material, genes)
        gate = critic.evaluate_hard_gate(scene)
        pdf = out_dir / f"{tag}-r{k + 1}.pdf"
        full, crops = render(scene, dna, pdf)
        try:
            from .press_norms import norm_report, scene_metrics
            rec_norms = norm_report(scene_metrics(scene, str(pdf.with_suffix(".png"))), comp.genre)
        except Exception as exc:  # norms are advisory; never block a round
            rec_norms = [{"error": str(exc)[:160]}]
        scene_path = pdf.with_suffix(".scene.json")
        scene_path.write_text(scene.model_dump_json())
        rec: dict[str, Any] = {"round": k + 1, "genes": _clean_genes(genes),
                               "gate": "PASS" if gate.passed else "FAIL", "violations": list(gate.violations), "pdf": str(pdf),
                               "scene": str(scene_path), "normy": rec_norms,
                               "pomiary_typografia": measurements(scene).get("typografia")}
        if "ai_unavailable" in trace:
            trace["rounds"].append(rec)
            best = best or (scene, rec, full)
            break

        failed_rounds = [r for r in trace["rounds"] if r.get("gate") == "FAIL" or r.get("accepted") is False]
        forbidden_genes = [_clean_genes(r["genes"]) for r in failed_rounds]
        all_tried = [_clean_genes(r["genes"]) for r in trace["rounds"]]

        trial_history = [
            {"runda": r["round"], "geny": _clean_genes(r["genes"]), "bramka": r["gate"],
             "naruszenia": r.get("violations", [])[:5],
             "odrzucone_poprawki": r.get("rejected_fixes", [])}
            for r in trace["rounds"]
        ]

        try:
            rv = run_task("layout_review", "layout_review",
                          {"podrecznik": know, "tytul": title, "plan": plan,
                           "ruchy": [m.brief(genes.get(m.name)) for m in comp.active_moves(genes)],
                           "bramka": {"wynik": rec["gate"], "naruszenia": rec["violations"][:20]},
                           "pomiary": measurements(scene),
                           "polozenie_w_normach_gatunku": rec.get("normy"),
                           "historia_prob": trial_history},
                          LayoutReview, images=[_jpeg(full, 1600)] + [_jpeg(c, 1400) for c in crops] + refs,
                          timeout_s=180, max_retries=1, use_cache=False)
            review = rv.data
        except AIUnavailable as exc:
            review = {"error": str(exc)}
        review = _against_measurements(review, rec["violations"])
        rec["review"] = review
        # 2. keep the best page that passes the gate (blind pairwise, both orders)
        if gate.passed:
            if best is None:
                best = (scene, rec, full)
                rec["accepted"] = "first page passing the gate"
            else:
                verdict = compare(comp, title, know, refs, full, best[2], rec, best[1])
                rec["pairwise_verdict"] = verdict
                if verdict == "new":
                    best = (scene, rec, full)
                    rec["accepted"] = "preferred by the title's judge"
                else:
                    rec["accepted"] = False
        trace["rounds"].append(rec)
        trace["best_round"] = best[1]["round"] if best else None
        if review.get("do_druku") and gate.passed:
            trace["done"] = "ready for print"
        else:
            fixes = [{"nazwa": f.get("ruch"), "wartosc": f.get("wartosc")} for f in (review.get("poprawki") or [])]
            log = []
            new_genes = _vet(comp, material, critic, genes, fixes, log,
                             forbidden_genes=forbidden_genes + all_tried)
            rec["rejected_fixes"] = log
            new_genes.pop("hero_place", None)  # re-solve the hero for the new moves
            clean_new = _clean_genes(new_genes)
            if clean_new in all_tried or clean_new in forbidden_genes:
                trace["done"] = "no new applicable fix"
            trace["next_genes"] = new_genes
            genes = dict(new_genes)
        if k + 1 >= rounds:
            trace["done"] = trace.get("done") or "round limit"
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=1, default=str))
        if trace.get("done"):
            break
    trace["best_round"] = best[1]["round"] if best else None
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=1, default=str))
    return {"scene": best[0] if best else None, "trace": trace}
