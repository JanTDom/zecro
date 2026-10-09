#!/usr/bin/env python3
"""
Polish Editorial Proofreader & Microtypographer
Automates typographic cleanup, hanging conjunction fix (&nbsp;), quote conversion („...”),
dash normalization (– vs — vs -), and detects common Polish linguistic errors.
"""

import argparse
import re
import sys
from pathlib import Path

# Common Polish pleonasms and errors map
PLEONASMS_MAP = {
    r"\bw każdym bądź razie\b": "w każdym razie (lub: bądź co bądź)",
    r"\bcofać się w tył\b": "cofać się",
    r"\bokres czasu\b": "okres (lub: czas)",
    r"\bw miesiącu (styczniu|lutym|marcu|kwietniu|maju|czerwcu|lipcu|sierpniu|wrześniu|październiku|listopadzie|grudniu)\b": r"w \1",
    r"\bakwen wodny\b": "akwen",
    r"\bw cudzysłowiu\b": "w cudzysłowie",
    r"\bpod rząd\b": "z rzędu",
    r"\bza wyjątkiem\b": "z wyjątkiem",
    r"\bpo najmniejszej linii oporu\b": "po linii najmniejszego oporu",
    r"\bwłanczać\b": "włączać",
    r"\bwyłanczać\b": "wyłączać",
    r"\bilość osób\b": "liczba osób",
    r"\bilość ludzi\b": "liczba ludzi",
    r"\bilość samochodów\b": "liczba samochodów",
    r"\bna dzień dzisiejszy\b": "dzisiaj (lub: obecnie)",
    r"\bspadać w dół\b": "spadać",
    r"\bkartka papieru\b": "kartka"
}

def clean_microtypography(text: str, html_mode: bool = True) -> str:
    """
    Applies Polish microtypographic standards:
    1. Converts quotes to Polish editorial „...”
    2. Fixes hanging conjunctions / orphans (a, i, o, u, w, z, na, do, etc.) with non-breaking spaces
    3. Normalizes dashes (en-dash for parenthetical pauses, hyphens for compound words)
    4. Connects numbers with units (e.g. 10 kg, 2026 r.)
    """
    nbsp = "&nbsp;" if html_mode else "\u00A0"

    # 1. Polish Quotes: replace straight quotes "word" with „word”
    # Opening quote after space, newline, or punctuation
    text = re.sub(r'(^|[\s\(\[\{])"(\S)', r'\1„\2', text)
    # Closing quote
    text = re.sub(r'(\S)"', r'\1”', text)
    # Convert English quotes “...” to „...”
    text = text.replace("“", "„").replace("”", "”")

    # 2. Number ranges: replace hyphen with en-dash (e.g. 2020-2026 -> 2020–2026, s. 10-15 -> s. 10–15)
    text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1–\2', text)

    # 3. Dashes in sentences: space + hyphen + space -> space + en-dash + space
    text = re.sub(r'(\s)-(\s)', r'\1–\2', text)

    # 4. Numbers + units / abbreviations
    units = r'(?:r\.|zł|PLN|EUR|USD|tys\.|mln|mld|km|m|cm|mm|kg|g|t|godz\.|art\.|ust\.|s\.|pkt|proc\.|%)'
    text = re.sub(r'(\b\d+)\s+(' + units + r')', r'\1' + nbsp + r'\2', text)

    # 5. Hanging conjunctions and prepositions (sierotki)
    # Single letter words: a, i, o, u, w, z (both lower and upper case)
    single_letters = r'[aiouowzAIOUOWZ]'
    text = re.sub(r'(^|[\s\(\[\{])(' + single_letters + r')\s+', r'\1\2' + nbsp, text)

    # Common short prepositions: na, do, od, po, za, ze, we, ku, że, co, by, to, np., itp.
    short_words = r'(?:na|do|od|po|za|ze|we|ku|że|co|by|to|np\.|itp\.|tzn\.|albo|oraz|lecz|nad|pod|bez|dla|Na|Do|Od|Po|Za|Ze|We|Ku|Że|Co|By|To|Np\.|Albo|Oraz|Lecz|Nad|Pod|Bez|Dla)'
    text = re.sub(r'(^|[\s\(\[\{])(' + short_words + r')\s+', r'\1\2' + nbsp, text)

    return text

def audit_text(text: str):
    issues = []
    for pattern, fix in PLEONASMS_MAP.items():
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for m in matches:
            issues.append({
                "error": m.group(0),
                "suggestion": fix,
                "position": m.start()
            })
    return issues

def proofread(text: str, fix_mode: bool = False, html_mode: bool = True):
    print("=" * 65)
    print(" 🇵🇱 PROFESJONALNA KOREKTA I MIKROTYPOGRAFIA PRASOWA (PL)")
    print("=" * 65)

    issues = audit_text(text)
    print(f" • Długość tekstu: {len(text):,} znaków | {len(text.split()):,} słów")
    print(f" • Znalezione uwagi stylistyczno-językowe: {len(issues)}")
    print("-" * 65)

    if issues:
        print(" ⚠️  UWAGI JĘZYKOWE I PLEONAZMY:")
        for idx, issue in enumerate(issues, 1):
            print(f"    {idx}. Znaleziono: „{issue['error']}” ➔ Sugestia: **{issue['suggestion']}**")
        print("-" * 65)
    else:
        print(" ✅ Brak typowych błędów pleonastycznych i frazeologicznych.")

    cleaned = clean_microtypography(text, html_mode=html_mode)
    
    # Check what microtypography fixed
    hanging_fixed = cleaned.count("&nbsp;") if html_mode else cleaned.count("\u00A0")
    quotes_fixed = cleaned.count("„")

    print(" 📐 MIKROTYPOGRAFIA DTP:")
    print(f"   [✓] Zabezpieczone wiszące spójniki (twarde spacje): {hanging_fixed}")
    print(f"   [✓] Sformatowane polskie cudzysłowy („...”): {quotes_fixed}")
    print(f"   [✓] Znormalizowane pauzy i półpauzy (– / —)")
    print(f"   [✓] Związane liczby z jednostkami i skrótami (np. 2026 r.)")
    print("-" * 65)

    if fix_mode:
        print("\n📄 TEKST PO KOREKCIE I MIKROTYPOGRAFII:")
        print("=" * 65)
        print(cleaned)
        print("=" * 65 + "\n")

    return cleaned

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profesjonalna korekta językowa i mikrotypografia polska")
    parser.add_argument("--text", type=str, help="Tekst do korekty")
    parser.add_argument("--file", type=str, help="Ścieżka do pliku tekstowego")
    parser.add_argument("--fix", action="store_true", help="Wyświetl poprawiony tekst")
    parser.add_argument("--output", type=str, help="Ścieżka do zapisu poprawionego pliku")
    parser.add_argument("--unicode", action="store_true", help="Użyj spacji Unicode (\\u00A0) zamiast HTML (&nbsp;)")

    args = parser.parse_args()

    content = args.text
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Błąd odczytu pliku: {e}")
            sys.exit(1)

    if not content:
        # Default sample text for test
        content = 'W miesiacu maju 2026 r. premier powiedział: "W każdym bądź razie cofamy się w tył o 15 km i czekamy na decyzję UE".'

    result = proofread(content, fix_mode=args.fix or bool(args.output), html_mode=not args.unicode)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"💾 Zapisano poprawiony plik do: {args.output}")
        except Exception as e:
            print(f"Błąd zapisu: {e}")
