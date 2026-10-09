import re

def polish_microtypography(text: str, html_mode: bool = False) -> str:
    """
    Automatically formats Polish editorial text:
    1. Converts quotes to Polish editorial „...”
    2. Fixes hanging conjunctions / orphans (a, i, o, u, w, z, na, do, etc.) with non-breaking spaces
    3. Normalizes dashes (en-dash – for parenthetical pauses, hyphens for compound words)
    4. Connects numbers with units (e.g. 10 kg, 2026 r.)
    """
    if not text:
        return text

    nbsp = "&nbsp;" if html_mode else "\u00A0"

    # 1. Polish Quotes: replace straight quotes "word" with „word”
    text = re.sub(r'(^|[\s\(\[\{])"(\S)', r'\1„\2', text)
    text = re.sub(r'(\S)"', r'\1”', text)
    text = text.replace("“", "„").replace("”", "”")

    # 2. Number ranges: replace hyphen with en-dash (e.g. 2020-2026 -> 2020–2026)
    text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1–\2', text)

    # 3. Dashes in sentences: space + hyphen + space -> space + en-dash + space
    text = re.sub(r'(\s)-(\s)', r'\1–\2', text)

    # 4. Numbers + units / abbreviations
    units = r'(?:r\.|zł|PLN|EUR|USD|tys\.|mln|mld|km|m|cm|mm|kg|g|t|godz\.|art\.|ust\.|s\.|pkt|proc\.|%)'
    text = re.sub(r'(\b\d+)\s+(' + units + r')', r'\1' + nbsp + r'\2', text)

    # 5. Hanging single-letter conjunctions and prepositions (sierotki: a, i, o, u, w, z)
    single_letters = r'[aiouowzAIOUOWZ]'
    text = re.sub(r'(^|[\s\(\[\{])(' + single_letters + r')\s+', r'\1\2' + nbsp, text)

    # Common short prepositions
    short_words = r'(?:na|do|od|po|za|ze|we|ku|że|co|by|to|np\.|itp\.|tzn\.|albo|oraz|lecz|nad|pod|bez|dla|Na|Do|Od|Po|Za|Ze|We|Ku|Że|Co|By|To|Np\.|Albo|Oraz|Lecz|Nad|Pod|Bez|Dla)'
    text = re.sub(r'(^|[\s\(\[\{])(' + short_words + r')\s+', r'\1\2' + nbsp, text)

    return text

def sanitize_editorial_material(material):
    """
    Cleans all text fields across an editorial material bundle automatically.
    """
    if not material:
        return material

    material = material.model_copy(deep=True) if hasattr(material, "model_copy") else material
    for story in getattr(material, "stories", []):
        locked = set(getattr(story, "locked_passages", []) or [])
        def clean(value):
            # Locked passages are human decisions.  Protect them while the
            # surrounding copy receives typography cleanup so later layout
            # runs cannot silently rewrite an approved quote/name/phrase.
            if not value or not locked:
                return polish_microtypography(value)
            protected = {}
            result = value
            for index, passage in enumerate(sorted((item for item in locked if item), key=len, reverse=True)):
                marker = f"\ue000{index}\ue001"
                if passage in result:
                    protected[marker] = passage
                    result = result.replace(passage, marker)
            result = polish_microtypography(result)
            for marker, passage in protected.items():
                result = result.replace(marker, passage)
            return result
        if hasattr(story, "headline") and story.headline:
            story.headline = clean(story.headline)
        if hasattr(story, "kicker") and story.kicker:
            story.kicker = clean(story.kicker)
        if hasattr(story, "deck") and story.deck:
            story.deck = clean(story.deck)
        if hasattr(story, "lead") and story.lead:
            story.lead = clean(story.lead)
        if hasattr(story, "body") and story.body:
            story.body = clean(story.body)
        if hasattr(story, "byline") and story.byline:
            story.byline = clean(story.byline)
        if hasattr(story, "pullquote") and story.pullquote:
            story.pullquote = clean(story.pullquote)
        if hasattr(story, "pull_quote") and story.pull_quote:
            story.pull_quote = clean(story.pull_quote)
        for photo in getattr(story, "images", []):
            if photo.caption:
                photo.caption = clean(photo.caption)
            if photo.credit:
                photo.credit = clean(photo.credit)

    for photo in getattr(material, "photos", []):
        if hasattr(photo, "caption") and photo.caption:
            photo.caption = polish_microtypography(photo.caption)

    return material
