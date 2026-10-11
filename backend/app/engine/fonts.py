"""Font library: ingest, Polish coverage, licence flags, resolution, conversion.

Sources: files uploaded from the user's Mac (all are accepted except fonts whose
OS/2 ``fsType`` marks them *Restricted License* — not embeddable), fonts shipped
with a corpus/InDesign package, and Google Fonts (OFL, fetched from the
google/fonts repository; variable fonts are instanced to static weights).

Polish coverage is measured from the font's own cmap for every face
separately: ``full`` / ``partial`` (missing list) / ``none``.
"""
from __future__ import annotations
import hashlib, io, json, re, shutil
from pathlib import Path
from typing import Any, Iterable, Optional

from ..config import settings
from ..models.database import db

FONT_DIR = settings.data_dir / "fonts"
CACHE_DIR = FONT_DIR / "_ttf_cache"
POLISH_LETTERS = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
POLISH_TYPO = "„”–…"
FONT_EXT = {".ttf", ".otf", ".ttc", ".otc", ".dfont"}
GENERIC = {
    "serif": ["Source Serif 4", "Utopia", "Minion Pro", "DejaVu Serif", "Liberation Serif", "Times New Roman"],
    "sans": ["Source Sans 3", "Myriad Pro", "Inter", "DejaVu Sans", "Liberation Sans", "Arial"],
    "condensed": ["Roboto Condensed", "Oswald", "Gotham XNarrow", "Nimbus Sans D OT"],
    "display": ["Playfair Display", "Oswald"],
}
DEFAULT_GOOGLE = ["Playfair Display", "PT Serif", "Inter", "Source Serif 4", "Source Sans 3", "Roboto Condensed", "Oswald", "Lora"]


class FontRejected(ValueError):
    pass


def _name(font, ids: Iterable[int]) -> str:
    table = font["name"]
    for nid in ids:
        rec = table.getDebugName(nid)
        if rec:
            return str(rec)
    return ""


def embedding_label(fs_type: int) -> str:
    if fs_type & 0x0002 and not fs_type & 0x000C:
        return "restricted"
    if fs_type & 0x0004:
        return "preview_print"
    if fs_type & 0x0008:
        return "editable"
    return "installable"


def analyse_font(font) -> dict[str, Any]:
    cmap = font.getBestCmap() or {}
    missing = [c for c in POLISH_LETTERS + POLISH_TYPO if ord(c) not in cmap]
    letters_missing = [c for c in missing if c in POLISH_LETTERS]
    polish = "full" if not missing else ("partial" if len(letters_missing) < len(POLISH_LETTERS) else "none")
    os2 = font["OS/2"] if "OS/2" in font else None
    fs_type = int(getattr(os2, "fsType", 0) or 0)
    weight = int(getattr(os2, "usWeightClass", 400) or 400)
    width = int(getattr(os2, "usWidthClass", 5) or 5)
    italic = bool(getattr(os2, "fsSelection", 0) & 1) or ("post" in font and font["post"].italicAngle != 0)
    family = _name(font, [16, 1]) or "Unknown"
    sub = _name(font, [17, 2]) or "Regular"
    kerning = "kern" in font or ("GPOS" in font and any(
        getattr(fr.FeatureTag, "__str__", lambda: "")() == "kern" or fr.FeatureTag == "kern"
        for fr in getattr(getattr(font["GPOS"].table, "FeatureList", None), "FeatureRecord", []) or []))
    return {"family": family.strip(), "subfamily": sub.strip(), "full_name": _name(font, [4]), "postscript_name": _name(font, [6]),
            "weight": weight, "width": width, "italic": italic, "fs_type": fs_type, "embedding": embedding_label(fs_type),
            "polish": polish, "missing_chars": missing, "has_kerning": bool(kerning), "glyph_count": len(font.getGlyphOrder()),
            "format": "cff" if "CFF " in font or "CFF2" in font else "truetype", "is_variable": "fvar" in font}


def ingest_bytes(data: bytes, filename: str, *, source: str = "upload", license_note: str = "", project_id: Optional[str] = None,
                 allow_restricted: bool = False) -> list[dict[str, Any]]:
    """Store a font file (or every face of a collection) in the library."""
    from fontTools.ttLib import TTFont, TTCollection
    ext = Path(filename).suffix.lower()
    if ext not in FONT_EXT:
        raise FontRejected(f"{filename}: unsupported font format")
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    faces: list[tuple[Any, int]] = []
    if ext == ".dfont":  # Mac resource-fork suitcase stored in the data fork
        import tempfile
        from fontTools.misc.macRes import ResourceReader
        with tempfile.NamedTemporaryFile(suffix=".dfont") as tmp:
            tmp.write(data); tmp.flush()
            reader = ResourceReader(tmp.name)
            sfnts = [res.data for res in (reader.get("sfnt") or [])]
            reader.close()
        if not sfnts:
            raise FontRejected(f"{filename}: no sfnt resources (bitmap/Type 1 suitcase)")
        faces = [(TTFont(io.BytesIO(b), lazy=False), i) for i, b in enumerate(sfnts)]
    elif ext in {".ttc", ".otc"}:
        coll = TTCollection(io.BytesIO(data), lazy=True)
        faces = [(f, i) for i, f in enumerate(coll.fonts)]
    else:
        faces = [(TTFont(io.BytesIO(data), lazy=True), 0)]
    saved = []
    for font, index in faces:
        info = analyse_font(font)
        if info["embedding"] == "restricted" and not allow_restricted:
            saved.append({**info, "status": "rejected", "reason": "fsType: Restricted License — font nie pozwala na osadzanie"})
            continue
        if len(faces) > 1:  # split collection faces into standalone files
            same = [r for r in db.list_fonts(info["family"]) if r.get("postscript_name") == info["postscript_name"]
                    and r.get("subfamily") == info["subfamily"]]
            if same:  # re-serialising big collections is slow; identical PS name = same face
                saved.append({**same[0], "status": "duplicate"})
                continue
            buf = io.BytesIO()
            font.save(buf)
            face_bytes = buf.getvalue()
            face_name = re.sub(r"[^\w.-]+", "_", f"{info['family']}-{info['subfamily']}") + (".otf" if info["format"] == "cff" else ".ttf")
        else:
            face_bytes, face_name = data, re.sub(r"[^\w.-]+", "_", Path(filename).name)
        sha = hashlib.sha256(face_bytes).hexdigest()
        existing = db.get_font_by_sha(sha)
        if existing:
            saved.append({**existing, "status": "duplicate"})
            continue
        target = FONT_DIR / f"{sha[:12]}_{face_name}"
        target.write_bytes(face_bytes)
        from ..storage.asset_store import persist_asset, storage_configured
        ref = str(target)
        if storage_configured():
            copy = FONT_DIR / ("_up_" + target.name)
            shutil.copy2(target, copy)
            ref = persist_asset(copy, prefix="fonts", key=target.name) or str(target)
        rec = db.save_font({**info, "storage_ref": ref, "font_number": 0, "sha256": sha, "source": source,
                            "license_note": license_note, "project_id": project_id})
        saved.append({**rec, "status": "added"})
    return saved


def ingest_path(path: Path, **kw) -> list[dict[str, Any]]:
    return ingest_bytes(Path(path).read_bytes(), Path(path).name, **kw)


def local_file(rec: dict[str, Any]) -> Optional[Path]:
    ref = rec.get("storage_ref") or ""
    p = Path(ref)
    if p.is_file():
        return p
    moved = FONT_DIR / p.name  # library copied between machines (absolute path differs)
    if p.name and moved.is_file():
        return moved
    from ..storage.asset_store import materialize_asset
    return materialize_asset(ref, prefix="fonts", cache_dir=FONT_DIR / "_remote")


# ---------------------------------------------------------------- Google Fonts
def google_catalog(polish_only: bool = True) -> list[dict[str, Any]]:
    import requests
    r = requests.get("https://fonts.google.com/metadata/fonts", timeout=30)
    r.raise_for_status()
    text = r.text[r.text.find("{"):]
    rows = json.loads(text).get("familyMetadataList", [])
    out = []
    for f in rows:
        subsets = f.get("subsets", [])
        if polish_only and "latin-ext" not in subsets:
            continue
        out.append({"family": f["family"], "category": f.get("category"), "subsets": subsets,
                    "weights": sorted({int(k.rstrip("i") or 400) for k in (f.get("fonts") or {}).keys() if k.rstrip("i").isdigit()}),
                    "license": "OFL/Apache (Google Fonts)", "popularity": f.get("popularity")})
    return out


def install_google_font(family: str, weights: Iterable[int] = (400, 700), italics: bool = False) -> list[dict[str, Any]]:
    """Download from github.com/google/fonts, instance variable fonts to static weights."""
    import requests
    slug = re.sub(r"[^a-z0-9]", "", family.lower())
    files = []
    for lic in ("ofl", "apache", "ufl"):
        r = requests.get(f"https://api.github.com/repos/google/fonts/contents/{lic}/{slug}", timeout=30,
                         headers={"Accept": "application/vnd.github+json", "User-Agent": "Zecro"})
        if r.status_code == 200:
            files = [x for x in r.json() if x["name"].lower().endswith((".ttf", ".otf"))]
            break
    if not files:
        raise FontRejected(f"Google Fonts family '{family}' not found")
    results = []
    from fontTools.ttLib import TTFont
    for item in files:
        is_italic = "italic" in item["name"].lower()
        if is_italic and not italics:
            continue
        data = requests.get(item["download_url"], timeout=60).content
        font = TTFont(io.BytesIO(data))
        if "fvar" in font:
            from fontTools.varLib.instancer import instantiateVariableFont
            axes = {a.axisTag: a for a in font["fvar"].axes}
            for weight in weights:
                inst = TTFont(io.BytesIO(data))
                loc = {}
                if "wght" in axes:
                    loc["wght"] = max(axes["wght"].minValue, min(axes["wght"].maxValue, weight))
                for tag, axis in axes.items():
                    if tag != "wght":
                        loc[tag] = axis.defaultValue
                inst = instantiateVariableFont(inst, loc, updateFontNames=True)
                _rename_static(inst, family, int(loc.get("wght", weight)), is_italic)
                buf = io.BytesIO(); inst.save(buf)
                style = _style_name(int(loc.get("wght", weight)), is_italic)
                results += ingest_bytes(buf.getvalue(), f"{slug}-{style}.ttf", source="google_fonts", license_note="SIL OFL / Apache — Google Fonts")
        else:
            results += ingest_bytes(data, item["name"], source="google_fonts", license_note="SIL OFL / Apache — Google Fonts")
    return results


def _style_name(weight: int, italic: bool) -> str:
    names = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}
    base = names.get(round(weight / 100) * 100, str(weight))
    return (base if base != "Regular" or not italic else "") + ("Italic" if italic else "") or "Regular"


def _rename_static(font, family: str, weight: int, italic: bool) -> None:
    style = _style_name(weight, italic)
    name = font["name"]
    ps = re.sub(r"\s+", "", family) + "-" + style
    for nid, value in ((1, f"{family} {style}" if style not in {"Regular", "Bold", "Italic", "BoldItalic"} else family), (2, style if style in {"Regular", "Bold", "Italic", "BoldItalic"} else "Regular"),
                       (4, f"{family} {style}"), (6, ps), (16, family), (17, style)):
        name.setName(value, nid, 3, 1, 0x409)
    font["OS/2"].usWeightClass = weight


# ---------------------------------------------------------------- resolution
def families(require_polish: bool = False) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for rec in db.list_fonts():
        g = groups.setdefault(rec["family"], {"family": rec["family"], "faces": [], "polish": "full", "sources": set()})
        g["faces"].append({k: rec[k] for k in ("id", "subfamily", "weight", "italic", "polish", "missing_chars", "embedding", "format", "has_kerning")})
        g["sources"].add(rec.get("source") or "")
        if rec["polish"] != "full":
            g["polish"] = "partial" if g["polish"] == "full" and rec["polish"] == "partial" else ("none" if rec["polish"] == "none" else "partial")
    out = [{**g, "sources": sorted(g["sources"])} for g in groups.values()]
    if require_polish:
        out = [g for g in out if any(f["polish"] == "full" for f in g["faces"])]
    return sorted(out, key=lambda g: g["family"].lower())


def _candidates(family: Optional[str]) -> list[str]:
    names: list[str] = []
    for part in [p.strip().strip("'\"") for p in (family or "serif").split(",") if p.strip()]:
        low = part.lower()
        if low in {"serif", "sans", "sans-serif", "condensed", "display"}:
            names += GENERIC["sans" if low.startswith("sans") else low]
        else:
            names.append(part)
    names += GENERIC["serif"] if not any(n in GENERIC["sans"] for n in names) else GENERIC["sans"]
    return list(dict.fromkeys(names))


def resolve_face(family: Optional[str], *, weight: int = 400, italic: bool = False, text: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Closest library face for a CSS-like family stack that covers ``text``."""
    needed = set(text or "") & set(POLISH_LETTERS + POLISH_TYPO)
    for name in _candidates(family):
        faces = db.list_fonts(name)
        usable = [f for f in faces if not (needed & set(f["missing_chars"]))]
        if not usable:
            continue
        usable.sort(key=lambda f: (f["italic"] != italic, abs((f["weight"] or 400) - weight), f["width"] != 5))
        if local_file(usable[0]):
            return usable[0]
    return None


def resolve_font(family: Optional[str], *, bold: bool = False, italic: bool = False, text: Optional[str] = None) -> Optional[str]:
    face = resolve_face(family, weight=700 if bold else 400, italic=italic, text=text)
    path = local_file(face) if face else None
    return str(path) if path else None


def ttf_for_pdf(path: str) -> str:
    """ReportLab embeds TrueType outlines only; convert CFF fonts once (cu2qu)."""
    from fontTools.ttLib import TTFont
    src = Path(path)
    font = TTFont(str(src), lazy=True)
    if "glyf" in font:
        return str(src)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / (hashlib.sha256(src.read_bytes()).hexdigest()[:16] + ".ttf")
    if target.exists():
        return str(target)
    font = TTFont(str(src))
    _otf_to_ttf(font)
    font.save(str(target))
    return str(target)


def _otf_to_ttf(font, max_err: float = 1.0, reverse_direction: bool = True) -> None:
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable
    glyph_order = font.getGlyphOrder()
    font["loca"] = newTable("loca")
    font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = glyph_order
    glyf.glyphs = {}
    glyph_set = font.getGlyphSet()
    for name in glyph_order:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, max_err, reverse_direction=reverse_direction))
        glyf[name] = pen.glyph()
    font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    for attr in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs", "maxStackElements", "maxSizeOfInstructions", "maxComponentElements"):
        setattr(maxp, attr, 0)
    maxp.maxZones = 1
    post = font["post"]
    post.formatType, post.extraNames, post.mapping = 2.0, [], {}
    post.glyphOrder = glyph_order
    for tag in ("CFF ", "CFF2", "VORG"):
        if tag in font:
            del font[tag]
    font.sfntVersion = "\x00\x01\x00\x00"
    font["head"].glyphDataFormat = 0
    font["glyf"].compile(font)  # sanity


def font_report(scene_fonts: Iterable[tuple[str, int, bool]]) -> list[dict[str, Any]]:
    """For exports: which faces are used, where the file is, licence/embedding."""
    out = []
    for family, weight, italic in sorted(set(scene_fonts)):
        face = resolve_face(family, weight=weight, italic=italic)
        out.append({"requested": {"family": family, "weight": weight, "italic": italic},
                    "resolved": ({k: face[k] for k in ("family", "subfamily", "postscript_name", "polish", "embedding", "source")} if face else None),
                    "packaged": bool(face and face["embedding"] in {"installable", "editable"}),
                    "note": None if face else "font nie jest w bibliotece — zainstaluj go na komputerze z InDesignem"})
    return out
