from backend.app.engine.copyfit import split_article_with_jump

def test_split_article_with_jump_paragraphs():
    text = (
        "To jest pierwszy akapit bardzo długiego artykułu dziennikarskiego na pierwszą stronę.\n\n"
        "To jest drugi akapit, który jeszcze mieści się w wyznaczonym module.\n\n"
        "To jest trzeci akapit, który powinien powędrować na stronę czwartą jako dokończenie tekstu."
    )
    # Target characters roughly around the end of paragraph 2 (~160 chars)
    result = split_article_with_jump(text, target_characters=170, target_page=4, source_page=1)
    
    assert "DOKOŃCZENIE NA S. 4" in result.lead_text
    assert "DOKOŃCZENIE ZE S. 1" in result.continuation_text
    assert "pierwszy akapit" in result.lead_text
    assert "trzeci akapit" in result.continuation_text
    assert result.target_page == 4
    assert result.source_page == 1
    assert 0.0 < result.ratio < 1.0

def test_split_article_with_jump_sentences():
    text = (
        "Warszawa ogłosiła nowy plan transportowy dla aglomeracji. "
        "Inwestycje obejmą nowe linie tramwajowe oraz modernizację węzłów przesiadkowych. "
        "Koszt całego przedsięwzięcia szacowany jest na kilkaset milionów złotych w ciągu najbliższych pięciu lat."
    )
    result = split_article_with_jump(text, target_characters=150, target_page="6", source_page="1")
    assert "DOKOŃCZENIE NA S. 6" in result.lead_text
    assert "DOKOŃCZENIE ZE S. 1" in result.continuation_text
    assert "Warszawa ogłosiła" in result.lead_text
    assert "Koszt całego przedsięwzięcia" in result.continuation_text
