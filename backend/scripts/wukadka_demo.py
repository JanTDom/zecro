"""Wukadka: okładka warstwowa z materiałów prawdziwej okładki NR21.

Uruchom z katalogu backend:  python -m scripts.wukadka_demo [--variants N]
Wymaga: output/wukadka-demo/src (zdjęcia z PDF NR21) i output/wukadka-demo/cut
(wycięcia rembg + analiza twarzy).  Wynik: output/wukadka-demo/*.pdf|png.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.schemas import PageInputMaterial, StoryInput, StoryImageInput, TitleDNA  # noqa: E402
from app.engine.layered_cover import compose_layered_cover, load_kit  # noqa: E402

DEMO = ROOT / "output" / "wukadka-demo"


def image(name: str, *, cutout: bool) -> StoryImageInput:
    from PIL import Image
    src = DEMO / "src" / f"{name}.png"
    an = json.loads((DEMO / "cut" / "analysis.json").read_text())[name]
    with Image.open(src) as im:
        w, h = im.size
    faces = an.get("faces") or []
    focal = [(faces[0][0] + faces[0][2]) / 2, (faces[0][1] + faces[0][3]) / 2] if faces else [.5, .4]
    return StoryImageInput(id=name, url=str(src), width_px=w, height_px=h, focal_point=focal,
                           alpha_mask_url=str(DEMO / "cut" / f"{name}.png") if cutout else None,
                           photo_analysis={"faces": faces, "alpha_bbox": an["alpha_bbox"],
                                           "segmentation": an["segmentation"], "face_detector": an["face_detector"]})


def material() -> PageInputMaterial:
    return PageInputMaterial(
        issue_number="21", issue_date="12 lipca 2023", section_name="Okładka", masthead_title="Wukadka",
        editorial_mood="scandal",
        stories=[
            StoryInput(id="kieszonkowcy", rank="lead", importance=1.0, kicker="Złodzieje nas przeklną...",
                       headline="Tak nie dasz się okraść", headline_emphasis=["nie", "dasz"], page_ref="STR. 4–5",
                       lead=("Wakacje, tłumy turystów na ulicach i ten rozleniwiający upał... Na to rozleniwienie "
                             "liczą złodzieje – kieszonkowcy zwani dawniej doliniarzami. Pokazujemy, co "
                             "niebezpiecznego może się zdarzyć wokół nas, jak kieszonkowcy próbują nas podejść. "
                             "Trzeba mieć oczy dookoła głowy. Złodziei można przechytrzyć. Wystarczy być czujnym."),
                       body="—"),
            StoryInput(id="koroniewska", rank="second", importance=.85, kicker="Joanna Koroniewska",
                       headline="Atakują ją, bo nie jest malowaną lalą!", headline_emphasis=["malowaną", "lalą"],
                       page_ref="STR. 4", images=[image("koroniewska", cutout=True)],
                       lead=("Joanna Koroniewska atakowana jest w sieci za to, że nie chce zrezygnować z "
                             "normalności. Stajemy po jej stronie! Nie podrasowuje zdjęć w Photoshopie, nie "
                             "korzysta z medycyny estetycznej. Po prostu jest sobą. I to zasługuje, zwłaszcza w "
                             "dzisiejszych czasach, na szacunek. Bo dość mamy celebrytów z silikonu!"),
                       body="—"),
            StoryInput(id="zeglarze", rank="teaser", group="interview", headline="Kochamy wiatr i żagle",
                       page_ref="STR. 2", images=[image("lyszkowski", cutout=True)],
                       lead=("Rozmawiamy z Mirosławem Łyszkowskim, prezesem Grodziskiego Klubu Żeglarskiego "
                             "„Czysty Wiatr”."), body="—"),
            StoryInput(id="ai", rank="teaser", pin_zone="top", headline="Kajdanki dla sztucznej inteligencji",
                       page_ref="STR. 8", images=[image("ai", cutout=False)],
                       lead=("Taki jest pomysł! Powstał zespół, który pilnuje, by przyszła superinteligencja "
                             "zbytnio się nie rozszalała naszym kosztem!"), body="—"),
            StoryInput(id="kreml", rank="teaser", headline="Po co Stany rozmawiają z Kremlem", page_ref="STR. 6",
                       images=[image("biden", cutout=True), image("lavrov", cutout=True)], body="—"),
            StoryInput(id="krzyzowka", rank="teaser", group="promo", kicker="W środku",
                       headline="Krzyżówka Wukadki", page_ref="STR. 6", body="—"),
        ])


def dna_for(kit_name: str) -> TitleDNA:
    kit = load_kit(kit_name)
    from app.engine.corpus_indexer import create_archetype_dnas
    dna = create_archetype_dnas()["tabloid"]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="a")
    ap.add_argument("--genes", default="{}")
    ap.add_argument("--framed", action="store_true")
    args = ap.parse_args()
    from app.engine.critic import LayoutCritic
    from app.engine.renderers.pdf_renderer import PDFRenderer
    import pypdfium2 as pdfium
    genes = json.loads(args.genes)
    if args.framed:
        from app.engine.framed_cover import compose_framed_cover
        scene = compose_framed_cover(material(), genes=genes)
    else:
        scene = compose_layered_cover(material(), genes=genes)
    dna = dna_for("wukadka")
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    out = DEMO / f"okladka-{args.tag}.pdf"
    PDFRenderer(dna).render_to_file(scene, str(out))
    pdfium.PdfDocument(str(out))[0].render(scale=1.4).to_pil().save(str(out.with_suffix(".png")))
    (DEMO / f"okladka-{args.tag}.scene.json").write_text(scene.model_dump_json(indent=1))
    print("GATE", "PASS" if gate.passed else "FAIL")
    for v in gate.violations:
        print("  -", v)
    print("decisions", json.dumps(scene.metadata["photo_driven_decisions"], ensure_ascii=False))
    print("missing", scene.metadata["missing_content_refs"])


if __name__ == "__main__":
    main()
