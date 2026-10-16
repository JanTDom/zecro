from __future__ import annotations

import pytest
from backend.app.engine.art_director import COMPOSERS, _apply, _vet, _clean_genes, _against_measurements, measurements
from backend.app.engine.framed_cover import compose_framed_cover
from backend.app.engine.critic import LayoutCritic
from backend.scripts.wukadka_demo import material


def test_composer_active_moves_filters_breakout():
    comp = COMPOSERS["framed_cover:wukadka"]()
    # Domyślny tryb breakout - ruchy hero_dy i hero_shift powinny być ukryte
    active_breakout = [m.name for m in comp.active_moves({"hero_mode": "breakout"})]
    assert "hero_dy" not in active_breakout
    assert "hero_shift" not in active_breakout
    assert "bottom" in active_breakout
    assert "lead_lines" in active_breakout

    # Domyślny brak hero_mode oznacza breakout
    active_default = [m.name for m in comp.active_moves({})]
    assert "hero_dy" not in active_default
    assert "hero_shift" not in active_default

    # Tryb frame - ruchy powinny być dostępne
    active_frame = [m.name for m in comp.active_moves({"hero_mode": "frame"})]
    assert "hero_dy" in active_frame
    assert "hero_shift" in active_frame


def test_apply_rejects_inactive_moves_in_breakout():
    comp = COMPOSERS["framed_cover:wukadka"]()
    mat = material()
    log = []
    # Próba zaaplikowania hero_dy w trybie breakout
    genes = {"hero_mode": "breakout"}
    res = _apply(comp, genes, [{"ruch": "hero_dy", "wartosc": 20}], mat, log)
    assert "hero_dy" not in res
    assert any(entry.get("odrzucony_ruch") == "hero_dy" for entry in log)
    assert any("nieaktywny" in entry.get("powod", "") for entry in log)


def test_vet_blocks_return_to_forbidden_genes():
    comp = COMPOSERS["framed_cover:wukadka"]()
    mat = material()
    dna = comp.dna()
    critic = LayoutCritic(dna)

    # Konfiguracja bazowa (narożnik)
    base_genes = {"bottom": "corner", "corner_photos": "framed"}

    # Zakazana konfiguracja (np. strip, która wcześniej przegrała lub dała FAIL)
    forbidden = [{"bottom": "strip", "corner_photos": "framed"}]

    log = []
    # Redaktor proponuje powrót do strip
    fixes = [{"nazwa": "bottom", "wartosc": "strip"}]
    res = _vet(comp, mat, critic, base_genes, fixes, log, forbidden_genes=forbidden)

    # Powrót powinien być zablokowany, geny zachowane jako base_genes
    assert res.get("bottom") == "corner"
    assert any("wszystkie_poprawki" in str(entry) or "odrzucony" in str(entry) for entry in log)


def test_vet_drops_bad_fix_keeps_good_fix():
    comp = COMPOSERS["framed_cover:wukadka"]()
    mat = material()
    dna = comp.dna()
    critic = LayoutCritic(dna)

    base_genes = {"bottom": "corner", "corner_photos": "framed"}
    # Strip jest zakazany, ale zmiana skybox_order jest dozwolona
    forbidden = [{"bottom": "strip", "corner_photos": "framed", "skybox_order": "other_first"},
                 {"bottom": "strip", "corner_photos": "framed"}]

    log = []
    fixes = [
        {"nazwa": "bottom", "wartosc": "strip"},
        {"nazwa": "skybox_order", "wartosc": "other_first"},
    ]
    res = _vet(comp, mat, critic, base_genes, fixes, log, forbidden_genes=forbidden)

    # Poprawka bottom: strip powinna odpaść, a skybox_order: other_first zostać zachowana
    assert res.get("bottom") == "corner"
    assert res.get("skybox_order") == "other_first"


def test_against_measurements_drops_unconfirmed_d30():
    review = {
        "defekty": [
            {"id": "D30", "waga": "major", "opis": "Klin białego papieru rzekomo widoczny"},
            {"id": "D11", "waga": "minor", "opis": "Styk elementu"},
        ],
        "poprawki": [
            {"ruch": "bottom", "wartosc": "corner", "naprawia": "D30"},
            {"ruch": "skybox_split", "wartosc": 130, "naprawia": "D11"},
        ]
    }
    # Bramka nie zgłasza D30
    filtered = _against_measurements(review, violations=[])
    def_ids = [d["id"] for d in filtered["defekty"]]
    assert "D30" not in def_ids
    assert "D11" in def_ids
    # Poprawka powiązana wyłącznie z urojonym D30 powinna odpaść
    fix_moves = [f["ruch"] for f in filtered["poprawki"]]
    assert "bottom" not in fix_moves
    assert "skybox_split" in fix_moves


def test_measurements_includes_window_holes_facts():
    mat = material()
    scene = compose_framed_cover(mat, kit_name="wukadka", genes={"bottom": "corner"})
    meas = measurements(scene)
    assert "dziury_w_oknach" in meas or "dziury_w_oknach_cm2" in meas
