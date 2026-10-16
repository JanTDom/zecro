from types import SimpleNamespace

from backend.app.engine.editorial_style import editorial_style_label


def test_ten_editorial_intents_remain_distinct_for_ai():
    points = [
        (.10, .20, .25), (.32, .24, .45), (.58, .40, .55),
        (.90, .75, .82), (.45, .60, .72), (.40, .15, .35),
        (.16, .28, .18), (.68, .55, .78), (.22, .43, .44), (.42, .67, .68),
    ]
    labels = [editorial_style_label(SimpleNamespace(
        opinion_to_tabloid=x, classical_to_avantgarde=y, dense_to_photo=z))
        for x, y, z in points]
    assert len(set(labels)) == 10
    assert labels[1] == "gazeta lokalna"
    assert labels[4] == "magazyn redakcyjny"
