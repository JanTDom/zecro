from backend.app.engine.infographics import (
    create_weather_ear_box,
    create_quote_callout_box,
    create_fact_box,
    create_market_ticker_box,
    create_editorial_badge_box,
    extract_story_facts,
)
from backend.app.models.schemas import Frame


def test_create_editorial_badge_box():
    badge = create_editorial_badge_box("TYLKO U NAS", category="ŚLEDZTWO")
    assert badge.role == "infobox"
    assert "ŚLEDZTWO" in badge.text_content
    assert "TYLKO" in badge.text_content and "NAS" in badge.text_content
    assert badge.style.bg_color == "#C2410C"
    assert badge.style.color == "#FFFFFF"


def test_extract_story_facts():
    class DummyStory:
        lead = "Wypadek na trasie S8 pod Warszawą."
        body = "Zderzyły się 3 pojazdy o godz. 14:30. Straty oszacowano na 250 tys. zł, a korek miał 12 km."
        infobox = None

    facts = extract_story_facts(DummyStory())
    assert len(facts) >= 1
    assert any("250 tys. zł" in f or "12 km" in f for f in facts)


def test_create_weather_ear_box():
    box = create_weather_ear_box("Gdańsk", 21, 14, "slonce", date_str="16.10")
    assert box.role == "infobox"
    assert "POGODA" in box.text_content
    assert "GDAŃSK" in box.text_content
    assert "21°C" in box.text_content
    assert box.frame.w == 45.0

def test_create_quote_callout_box():
    quote = create_quote_callout_box(
        "Kreatywność w mediach to nie chaos, lecz precyzyjna eksploracja i selekcja.",
        "Jan Nowak",
        title_affiliation="Dyrektor Artystyczny"
    )
    assert quote.role == "pullquote"
    assert "Kreatywność" in quote.text_content
    assert "Jan Nowak" in quote.text_content
    assert "Dyrektor Artystyczny" in quote.text_content
    assert quote.style.font_style == "italic"

def test_create_fact_box():
    facts = [
        "Ponad 14 tysięcy stron w korpusie badawczym.",
        "Obsługa standardów InDesign IDML i PDF/X.",
        "Automatyczny copyfitting z polską mikrotypografią."
    ]
    box = create_fact_box("Trzy filary silnika", facts)
    assert box.role == "infobox"
    assert "TRZY FILARY SILNIKA" in box.text_content
    assert "tysięcy" in box.text_content
    assert box.style.bg_color == "#F3F4F6"

def test_create_market_ticker_box():
    indices = [
        {"name": "WIG20", "value": "2450", "change": 1.2},
        {"name": "EUR/PLN", "value": "4.28", "change": -0.3}
    ]
    ticker = create_market_ticker_box(indices)
    assert ticker.role == "band"
    assert "WIG20" in ticker.text_content
    assert "EUR/PLN" in ticker.text_content
    assert "▲ +1.2%" in ticker.text_content
    assert "▼ -0.3%" in ticker.text_content
