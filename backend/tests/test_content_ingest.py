import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from backend.app.main import app
from backend.app.engine.content_ingest import redact_editorial_article, extract_document_file

client = TestClient(app)

def test_redact_editorial_article_deterministic():
    raw_text = (
        "Wicepremier i minister cyfryzacji poinformował w środę o rozpoczęciu nowego programu wsparcia. "
        "Program o wartości 500 milionów złotych ma na celu unowocześnienie infrastruktury w całym kraju. "
        "Pierwsze dotacje trafią do beneficjentów już w listopadzie tego roku. "
        "To ogromny krok naprzód dla polskiej gospodarki, podkreślają eksperci z branży."
    )
    result = redact_editorial_article("Wielki program cyfryzacji", raw_text, domain="gov.pl")
    assert result["headline"]
    assert result["kicker"]
    assert result["body"]
    assert "gov.pl" in result["byline"]
    assert len(result["body"]) > 50

def test_ingest_text_endpoint():
    res = client.post("/editorial/redact-text", json={
        "title": "Nowe inwestycje drogowe",
        "text": "Generalna Dyrekcja Dróg Krajowych i Autostrad ogłosiła przetarg na budowę nowego odcinka trasy ekspresowej. Wartość kontraktu to ponad 800 mln zł. Zakończenie prac przewidziano na 2028 rok."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["leadStory"]["headline"]
    assert data["leadStory"]["kicker"]
    assert data["leadStory"]["body"]

def test_extract_txt_document(tmp_path):
    doc_path = tmp_path / "artykul.txt"
    doc_path.write_text("Tytuł artykułu w pliku\n\nTreść pierwszego akapitu z ważnymi informacjami.\n\nDruga część tekstu dokumentu.", encoding="utf-8")
    extracted = extract_document_file(doc_path, "artykul.txt")
    assert "Tytuł artykułu" in extracted["raw_title"]
    assert "Treść pierwszego akapitu" in extracted["raw_body"]
