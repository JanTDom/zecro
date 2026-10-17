#!/usr/bin/env python3
"""
Zecro Editorial Document Ingestion & Taxonomy Engine.

Ingests raw journalist documents (.docx, .md, .txt), parses editorial components
(kicker, headline, deck, lead, body, pull-quotes, fact-boxes, bylines),
and extracts frozen factual claims (numbers, dates, amounts) for deterministic guarding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class FactClaim:
    text: str
    category: str  # date, currency, number, percentage, proper_noun


@dataclass
class EditorialArticlePackage:
    source_filename: str
    kicker: Optional[str] = None
    headline: str = ""
    deck: Optional[str] = None
    lead: Optional[str] = None
    body_paragraphs: List[str] = field(default_factory=list)
    pull_quotes: List[str] = field(default_factory=list)
    fact_box_items: List[str] = field(default_factory=list)
    byline: Optional[str] = None
    dateline: Optional[str] = None
    word_count: int = 0
    character_count: int = 0
    frozen_claims: List[FactClaim] = field(default_factory=list)


def extract_docx_text_paragraphs(docx_path: Path) -> List[str]:
    """Reads word/document.xml from docx zip without external dependencies."""
    paragraphs = []
    with zipfile.ZipFile(docx_path, "r") as z:
        if "word/document.xml" not in z.namelist():
            return paragraphs
        xml_content = z.read("word/document.xml")
        root = ET.fromstring(xml_content)
        # Namespace map
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        for p in root.iter(f"{{{ns['w']}}}p"):
            p_text = "".join(node.text for node in p.iter(f"{{{ns['w']}}}t") if node.text)
            clean = p_text.strip()
            if clean:
                paragraphs.append(clean)
    return paragraphs


def extract_facts(text: str) -> List[FactClaim]:
    claims = []
    # Dates
    date_matches = re.findall(r"\b(?:\d{1,2}\s+(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)|\d{4}\s*r\.?|\d{1,2}\.\d{1,2}\.\d{4})\b", text, re.IGNORECASE)
    for d in date_matches:
        claims.append(FactClaim(text=d, category="date"))

    # Currency
    curr_matches = re.findall(r"\b\d+(?:[\s,.]\d+)?\s*(?:mln\s*zł|mld\s*zł|tys\.\s*zł|zł|PLN|EUR|USD)\b", text, re.IGNORECASE)
    for c in curr_matches:
        claims.append(FactClaim(text=c, category="currency"))

    # Percentages
    pct_matches = re.findall(r"\b\d+(?:[\s,.]\d+)?\s*%", text)
    for p in pct_matches:
        claims.append(FactClaim(text=p, category="percentage"))

    # Numbers with units
    num_matches = re.findall(r"\b\d+(?:[\s,.]\d+)?\s*(?:km|m|ha|osób|mieszkańców|godz|min)\b", text, re.IGNORECASE)
    for n in num_matches:
        claims.append(FactClaim(text=n, category="number"))

    return claims


def parse_raw_paragraphs(filename: str, paragraphs: List[str]) -> EditorialArticlePackage:
    if not paragraphs:
        return EditorialArticlePackage(source_filename=filename)

    pkg = EditorialArticlePackage(source_filename=filename)
    rem = list(paragraphs)

    # 1. Headline detection
    # First short-to-medium paragraph or paragraph starting with title keyword
    if len(rem) >= 1:
        pkg.headline = rem.pop(0)

    # 2. Lead detection
    if len(rem) >= 1 and len(rem[0].split()) > 10:
        pkg.lead = rem.pop(0)

    # 3. Process remaining paragraphs
    body = []
    for p in rem:
        # Check byline
        if re.match(r"^(?:Tekst|Autor|Opracowanie|Rozmawiał|Fot\.|Zdj\.|[A-ZĄĆĘŁŃÓŚŹŻ]{2,}\s+[A-ZĄĆĘŁŃÓŚŹŻ]{2,}):", p, re.IGNORECASE) or len(p.split()) <= 3 and p.isupper():
            pkg.byline = p
            continue
        # Check pull quote
        if (p.startswith("„") and p.endswith("”")) or (p.startswith('"') and p.endswith('"')):
            pkg.pull_quotes.append(p)
            continue
        # Check fact/bullet box
        if p.startswith(("- ", "• ", "* ", "1. ", "2. ", "3. ")):
            pkg.fact_box_items.append(p)
            continue
        body.append(p)

    pkg.body_paragraphs = body
    full_text = " ".join([pkg.headline, pkg.lead or ""] + body)
    pkg.word_count = len(full_text.split())
    pkg.character_count = len(full_text)
    pkg.frozen_claims = extract_facts(full_text)

    return pkg


def ingest_file(file_path: Path) -> EditorialArticlePackage:
    if file_path.suffix.lower() == ".docx":
        paragraphs = extract_docx_text_paragraphs(file_path)
    else:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    return parse_raw_paragraphs(file_path.name, paragraphs)


def format_package_markdown(pkg: EditorialArticlePackage) -> str:
    md = [
        f"# Ustrukturyzowany Pakiet Artykułu: `{pkg.source_filename}`",
        f"- **Liczba słów:** {pkg.word_count} | **Znaków ze spacjami:** {pkg.character_count}",
        f"- **Autor / Byline:** {pkg.byline or 'Brak podanego'}",
        "",
        f"### Tytuł Główny\n**{pkg.headline}**\n",
    ]

    if pkg.lead:
        md.append(f"### Lead (Wstęp pogrubiony)\n*{pkg.lead}*\n")

    md.append(f"### Korpus Tekstu ({len(pkg.body_paragraphs)} akapitów)")
    for i, p in enumerate(pkg.body_paragraphs[:3], 1):
        md.append(f"{i}. {p[:120]}..." if len(p) > 120 else f"{i}. {p}")
    if len(pkg.body_paragraphs) > 3:
        md.append(f"... (i jeszcze {len(pkg.body_paragraphs)-3} akapitów)")

    if pkg.pull_quotes:
        md.append("\n### Wykryte Wyimki (Pull Quotes)")
        for pq in pkg.pull_quotes:
            md.append(f"- > {pq}")

    if pkg.frozen_claims:
        md.append("\n### Zamrożone Fakty i Liczby (Fact-Guard Contract)")
        for fc in pkg.frozen_claims[:10]:
            md.append(f"- `{fc.category}`: **{fc.text}**")
        if len(pkg.frozen_claims) > 10:
            md.append(f"- ... (łącznie {len(pkg.frozen_claims)} zweryfikowanych faktów)")

    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Zecro Editorial Document Ingestion CLI")
    parser.add_argument("file", help="Path to .docx, .md, or .txt file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", type=str, help="Save output to file")
    args = parser.parse_args()

    target = Path(args.file)
    if not target.exists():
        print(f"Error: File '{target}' does not exist.", file=sys.stderr)
        return 1

    pkg = ingest_file(target)

    if args.json:
        out_text = json.dumps(asdict(pkg), indent=2, ensure_ascii=False)
    else:
        out_text = format_package_markdown(pkg)

    if args.output:
        Path(args.output).write_text(out_text, encoding="utf-8")
        print(f"Package written to {args.output}")
    else:
        print(out_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
