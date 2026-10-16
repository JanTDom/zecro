import os
import subprocess
from pathlib import Path

HTML_CONTENT = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>ZECRO — Architektura Systemu Generatywnego Składu Prasowego</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;600&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }
  
  body {
    width: 3840px;
    height: 2160px;
    background: #080b12;
    background-image: 
      radial-gradient(circle at 50% 0%, rgba(225, 38, 47, 0.15) 0%, transparent 45%),
      radial-gradient(circle at 10% 30%, rgba(14, 165, 233, 0.12) 0%, transparent 40%),
      radial-gradient(circle at 90% 70%, rgba(168, 85, 247, 0.12) 0%, transparent 40%),
      linear-gradient(to bottom, #07090e 0%, #0a0e17 50%, #05070a 100%);
    color: #e2e8f0;
    font-family: 'Plus Jakarta Sans', sans-serif;
    overflow: hidden;
    position: relative;
    padding: 60px 80px;
  }

  /* Siatka tła 3D */
  .grid-bg {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background-size: 80px 80px;
    background-image: 
      linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
    pointer-events: none;
    z-index: 0;
  }

  /* Nagłówek stacyjny 3D */
  .header {
    position: relative;
    z-index: 10;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 40px;
    margin-bottom: 50px;
  }

  .logo-block {
    display: flex;
    align-items: center;
    gap: 36px;
  }

  .logo-3d-box {
    width: 110px;
    height: 110px;
    border-radius: 26px;
    background: linear-gradient(135deg, #e1262f 0%, #991b1b 50%, #450a0a 100%);
    box-shadow: 
      0 20px 40px rgba(225, 38, 47, 0.45),
      inset 0 2px 4px rgba(255, 255, 255, 0.4),
      inset 0 -4px 8px rgba(0, 0, 0, 0.6);
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .logo-letter {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 64px;
    font-weight: 800;
    color: #ffffff;
    text-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    letter-spacing: -2px;
  }

  .title-content h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 58px;
    font-weight: 800;
    letter-spacing: -1px;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .title-content h1 span.brand-accent {
    color: #e1262f;
    text-shadow: 0 0 30px rgba(225, 38, 47, 0.5);
  }

  .title-content p.subtitle {
    font-size: 20px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 5px;
    color: #94a3b8;
    margin-top: 6px;
  }

  .header-badges {
    display: flex;
    gap: 16px;
  }

  .badge-3d {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(16px);
    border-radius: 16px;
    padding: 16px 28px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.15);
  }

  .badge-label {
    font-size: 13px;
    font-family: 'JetBrains Mono', monospace;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 4px;
  }

  .badge-val {
    font-size: 20px;
    font-weight: 700;
    color: #f8fafc;
  }

  /* Główny kontener kolumn architektury */
  .architecture-flow {
    position: relative;
    z-index: 10;
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 36px;
    height: 1640px;
  }

  /* Karta etapowa 3D */
  .stage-card {
    background: linear-gradient(170deg, rgba(20, 27, 45, 0.75) 0%, rgba(10, 14, 25, 0.85) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 28px;
    padding: 36px 30px;
    display: flex;
    flex-direction: column;
    box-shadow: 
      0 30px 60px rgba(0, 0, 0, 0.5),
      inset 0 1px 2px rgba(255, 255, 255, 0.12);
    position: relative;
    backdrop-filter: blur(20px);
  }

  .stage-card::before {
    content: '';
    position: absolute;
    top: 0; left: 30px; right: 30px;
    height: 4px;
    border-radius: 4px;
  }

  .stage-1::before { background: linear-gradient(90deg, #0ea5e9, #38bdf8); box-shadow: 0 0 20px #0ea5e9; }
  .stage-2::before { background: linear-gradient(90deg, #a855f7, #c084fc); box-shadow: 0 0 20px #a855f7; }
  .stage-3::before { background: linear-gradient(90deg, #e1262f, #f43f5e); box-shadow: 0 0 25px #e1262f; }
  .stage-4::before { background: linear-gradient(90deg, #eab308, #fde047); box-shadow: 0 0 20px #eab308; }
  .stage-5::before { background: linear-gradient(90deg, #10b981, #34d399); box-shadow: 0 0 20px #10b981; }

  .stage-header {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-bottom: 24px;
  }

  .stage-num {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
  }

  .stage-1 .stage-num { background: #0284c7; }
  .stage-2 .stage-num { background: #9333ea; }
  .stage-3 .stage-num { background: #e1262f; }
  .stage-4 .stage-num { background: #ca8a04; }
  .stage-5 .stage-num { background: #059669; }

  .stage-title-wrap h2 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
  }

  .stage-title-wrap p {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #94a3b8;
    margin-top: 2px;
    font-family: 'JetBrains Mono', monospace;
  }

  /* Sekcje wewnątrz kart */
  .component-box {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 18px;
    padding: 22px 20px;
    margin-bottom: 18px;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
  }

  .component-title {
    font-size: 16px;
    font-weight: 700;
    color: #f1f5f9;
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }

  .component-desc {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.55;
  }

  .pill-group {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
  }

  .pill {
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
  }

  .pill.highlight {
    background: rgba(225, 38, 47, 0.15);
    border-color: rgba(225, 38, 47, 0.4);
    color: #fca5a5;
  }

  .pill.highlight-cyan {
    background: rgba(14, 165, 233, 0.15);
    border-color: rgba(14, 165, 233, 0.4);
    color: #7dd3fc;
  }

  .pill.highlight-purple {
    background: rgba(168, 85, 247, 0.15);
    border-color: rgba(168, 85, 247, 0.4);
    color: #d8b4fe;
  }

  .pill.highlight-green {
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.4);
    color: #6ee7b7;
  }

  .pill.highlight-gold {
    background: rgba(234, 179, 8, 0.15);
    border-color: rgba(234, 179, 8, 0.4);
    color: #fde047;
  }

  /* Schematy wizualne 3D w kartach */
  .visual-diagram {
    background: rgba(10, 15, 28, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 16px;
    margin-top: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .diagram-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    border-left: 3px solid #64748b;
  }

  .diagram-row.active {
    border-left-color: #e1262f;
    background: rgba(225, 38, 47, 0.08);
  }

  .diagram-row span.name {
    font-weight: 600;
    color: #f8fafc;
  }

  .diagram-row span.meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #94a3b8;
  }

  /* Belka łącząca i stopka */
  .footer-bar {
    position: absolute;
    bottom: 50px;
    left: 80px;
    right: 80px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .footer-loop {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .loop-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: rgba(225, 38, 47, 0.2);
    border: 1px solid rgba(225, 38, 47, 0.4);
    display: flex;
    justify-content: center;
    align-items: center;
    color: #f43f5e;
  }

  .loop-text h4 {
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
  }

  .loop-text p {
    font-size: 13px;
    color: #94a3b8;
  }

  .system-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #64748b;
    text-align: right;
  }
</style>
</head>
<body>

<div class="grid-bg"></div>

<!-- NAGŁÓWEK -->
<header class="header">
  <div class="logo-block">
    <div class="logo-3d-box">
      <div class="logo-letter">Z</div>
    </div>
    <div class="title-content">
      <h1>ZECRO <span class="brand-accent">AI ART DIRECTOR</span></h1>
      <p class="subtitle">System Generatywnego Składu Prasowego & Architektura Silnika DTP</p>
    </div>
  </div>

  <div class="header-badges">
    <div class="badge-3d">
      <div class="badge-label">KORPUS REFERENCYJNY</div>
      <div class="badge-val">1041 Stron · 51 Tytułów</div>
    </div>
    <div class="badge-3d">
      <div class="badge-label">PRODUKCJA</div>
      <div class="badge-val">IDML + PDF/X + Vector SVG</div>
    </div>
    <div class="badge-3d">
      <div class="badge-label">KLUCZOWY MODEL</div>
      <div class="badge-val">Eksploracja × Selekcja</div>
    </div>
  </div>
</header>

<!-- PRZEPŁYW GŁÓWNY SYSTEMU (5 KOLUMN) -->
<main class="architecture-flow">

  <!-- ETAP 1 -->
  <section class="stage-card stage-1">
    <div class="stage-header">
      <div class="stage-num">01</div>
      <div class="stage-title-wrap">
        <h2>Wejście i Redakcja</h2>
        <p>EDITORIAL INGESTION</p>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#38bdf8" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
        Materiały i Hierarchia
      </div>
      <div class="component-desc">
        Parser semantyczny analizuje surowe teksty redakcyjne, przypisując wagi ważności (importance 0.1–1.0) oraz role prasowe.
      </div>
      <div class="pill-group">
        <span class="pill highlight-cyan">Lead Story</span>
        <span class="pill">Second (2-3)</span>
        <span class="pill">Briefs / Notatki</span>
        <span class="pill">Teasers / Paski</span>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#38bdf8" stroke-width="2" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
        Moduł Editorial Writer
      </div>
      <div class="component-desc">
        Rygorystyczna adiustacja do ramy makiety. Zero halucynacji: zakaz dodawania faktów i przymiotników. Naturalna polszczyzna redakcyjna.
      </div>
      <div class="pill-group">
        <span class="pill">Dopasowanie do znaków</span>
        <span class="pill">Rytm nagłówków</span>
        <span class="pill">Polska składnia</span>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#38bdf8" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        Pakiet Ilustracyjny & Kadry
      </div>
      <div class="component-desc">
        Weryfikacja rozdzielczości (min. 180–300 DPI), kierunku spojrzenia (gaze direction) i punktu centralnego (focal point).
      </div>
    </div>
  </section>

  <!-- ETAP 2 -->
  <section class="stage-card stage-2">
    <div class="stage-header">
      <div class="stage-num">02</div>
      <div class="stage-title-wrap">
        <h2>Gramatyka i DNA Tytułu</h2>
        <p>TITLE DNA AS DATA</p>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#c084fc" stroke-width="2" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        5 Archetypów Prasowych
      </div>
      <div class="component-desc">
        DNA tytułu istnieje jako elastyczny model parametrów (nie szablon). Obejmuje 5 zdefiniowanych rodzin:
      </div>
      <div class="visual-diagram">
        <div class="diagram-row">
          <span class="name">Poważna i Opiniotwórcza</span>
          <span class="meta">quality_press · 6 szpalt</span>
        </div>
        <div class="diagram-row active">
          <span class="name">Gazeta Środka (Mid-market)</span>
          <span class="meta">mass_market · 5 szpalt</span>
        </div>
        <div class="diagram-row">
          <span class="name">Gazeta Bulwarowa (Tabloid)</span>
          <span class="meta">tabloid · wysoka energia</span>
        </div>
        <div class="diagram-row">
          <span class="name">Magazyn i Reportaż</span>
          <span class="meta">editorial_magazine · 4 szpalty</span>
        </div>
        <div class="diagram-row">
          <span class="name">Program TV i Poradnik</span>
          <span class="meta">tv_guide · modułowa ramówka</span>
        </div>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#c084fc" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        Siatka Modułowa & Typografia
      </div>
      <div class="component-desc">
        Ścisły rejestr linii bazowych (baseline grid 9.5–10.5 pt), odstępy międzyłamowe (gutters 3.5–5 mm) i skale krojów.
      </div>
      <div class="pill-group">
        <span class="pill highlight-purple">Baseline Grid</span>
        <span class="pill">Marginesy milimetrowe</span>
        <span class="pill">Page Energy Budget</span>
      </div>
    </div>
  </section>

  <!-- ETAP 3 -->
  <section class="stage-card stage-3">
    <div class="stage-header">
      <div class="stage-num">03</div>
      <div class="stage-title-wrap">
        <h2>Silniki Wykonawcze</h2>
        <p>EXECUTION SUBSYSTEMS</p>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#f43f5e" stroke-width="2" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        Google Gemini AI Szparowanie
      </div>
      <div class="component-desc">
        Wizyjny model AI automatycznie usuwa tło zdjęć, wycina sylwetki postaci i generuje wektorowy wielokąt konturu dla opływania.
      </div>
      <div class="pill-group">
        <span class="pill highlight">Alpha Mask</span>
        <span class="pill highlight">Vector Polygon</span>
        <span class="pill">Auto-Fallback</span>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#f43f5e" stroke-width="2" viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
        Infografiki Prasowe SVG
      </div>
      <div class="component-desc">
        Wektorowe widgety redakcyjne: wykresy słupkowe, wskaźniki procentowe, osie czasu, moduły faktów i finansowe pigułki wiedzy.
      </div>
      <div class="pill-group">
        <span class="pill">Wykresy wektorowe</span>
        <span class="pill">Klocki danych</span>
        <span class="pill">Dynamiczne SVG</span>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#f43f5e" stroke-width="2" viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>
        Odsyłacze Stron (Jump Lines)
      </div>
      <div class="component-desc">
        Inteligentny podział długich artykułów między pierwszą stroną a wnętrzem („dokończenie ze str. 1”, „czytaj na str. 4”).
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#f43f5e" stroke-width="2" viewBox="0 0 24 24"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/></svg>
        Polska Korekta Zecerska
      </div>
      <div class="component-desc">
        Rygor mikrotypograficzny: niełamliwe spacje dla wiszących spójników (w, z, o, i, a, u), polskie cudzysłowy dolno-górne („...”) i półpauzy (–).
      </div>
    </div>
  </section>

  <!-- ETAP 4 -->
  <section class="stage-card stage-4">
    <div class="stage-header">
      <div class="stage-num">04</div>
      <div class="stage-title-wrap">
        <h2>Graf Sceny i Krytyk</h2>
        <p>SCENE GRAPH & TASTE LOOP</p>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#fde047" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        Graf Sceny (Scene Graph JSON)
      </div>
      <div class="component-desc">
        Uniwersalny model obiektowy makiety: precyzyjne ramki milimetrowe [x, y, w, h], warstwy Z, relacje, traktowanie i ścieżki obcinające.
      </div>
      <div class="pill-group">
        <span class="pill highlight-gold">Czysty JSON</span>
        <span class="pill">Niezależny od formatu</span>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#fde047" stroke-width="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        Dwuwarstwowy Krytyk
      </div>
      <div class="component-desc">
        Ścisłe rozdzielenie generatora od selekcji:
      </div>
      <div class="visual-diagram">
        <div class="diagram-row active">
          <span class="name">Twarda Bramka (Pass/Fail)</span>
          <span class="meta">Zero kolizji · Jedna dominanta · TAC &lt; 240%</span>
        </div>
        <div class="diagram-row">
          <span class="name">Miękki Sędzia VLM (Ranking)</span>
          <span class="meta">Ocena wzrokowa kompozycji i równowagi</span>
        </div>
        <div class="diagram-row">
          <span class="name">Anty-Kopiowanie (Novelty)</span>
          <span class="meta">Odległość od korpusu · Zero plagiatu</span>
        </div>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#fde047" stroke-width="2" viewBox="0 0 24 24"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
        Pętla Gustu Redakcyjnego
      </div>
      <div class="component-desc">
        Nauka preferencji artystycznych (A vs B) na podstawie decyzji dyrektora artystycznego i poprawek geometrycznych.
      </div>
    </div>
  </section>

  <!-- ETAP 5 -->
  <section class="stage-card stage-5">
    <div class="stage-header">
      <div class="stage-num">05</div>
      <div class="stage-title-wrap">
        <h2>Formaty i Produkcja</h2>
        <p>HYBRID DUAL OUTPUT</p>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#34d399" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
        Błyskawiczny PDF z Przeglądarki
      </div>
      <div class="component-desc">
        Natychmiastowy skład wektorowy SVG bezpośrednio na urządzeniu redaktora. Zerowa latencja sieciowa, milimetrowy standard druku @page.
      </div>
      <div class="pill-group">
        <span class="pill highlight-green">0 sekund opóźnienia</span>
        <span class="pill">Wektorowa ostrość</span>
        <span class="pill">Wydruk natywny</span>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#34d399" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        Adobe InDesign IDML
      </div>
      <div class="component-desc">
        Produkcyjny eksport DTP dla zecerów: zachowane style akapitowe i znakowe, połączone ramki tekstowe, wektorowe obrysy zdjęć.
      </div>
      <div class="pill-group">
        <span class="pill">Style akapitowe</span>
        <span class="pill">Ścieżki obcinania</span>
      </div>
    </div>

    <div class="component-box">
      <div class="component-title">
        <svg width="20" height="20" fill="none" stroke="#34d399" stroke-width="2" viewBox="0 0 24 24"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
        Prepress & Naświetlanie PDF/X
      </div>
      <div class="component-desc">
        Sprawdzenie preflight: separacja barwna CMYK, limit farby TAC &lt; 240% (newsprint), spady (bleed 3-5 mm) i pasery drukarskie.
      </div>
      <div class="pill-group">
        <span class="pill">PDF/X-1a / PDF/X-4</span>
        <span class="pill">Czysta czerń 100% K</span>
      </div>
    </div>
  </section>

</main>

<!-- STOPKA ARCHITEKTURY -->
<footer class="footer-bar">
  <div class="footer-loop">
    <div class="loop-icon">
      <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
    </div>
    <div class="loop-text">
      <h4>Pętla Eksploracji i Selekcji (AI Art Director Taste Feedback Loop)</h4>
      <p>Maszyna eksploruje tysiące wariantów sceny geometrycznej; krytyk dwuwarstwowy eliminuje błędy prepress i wybiera optymalny układ.</p>
    </div>
  </div>

  <div class="system-meta">
    ZECRO SYSTEM ENGINE v2.6 · ARCHETYP: GAZETA ŚRODKA (MID-MARKET) · TYPST / IDML / BROWSER HYBRID COMPILER
  </div>
</footer>

</body>
</html>
"""

def main():
    docs_dir = Path("/Users/macbookpro/PROJEKTY/LAYOUT/docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    html_file = docs_dir / "zecro_architecture.html"
    png_file = docs_dir / "zecro_architecture_system_infographic.png"

    html_file.write_text(HTML_CONTENT, encoding="utf-8")
    print(f"HTML saved to {html_file}")

    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size=3840,2160",
        f"--screenshot={png_file}",
        f"file://{html_file.resolve()}"
    ]
    print("Rendering 4K UHD PNG via Headless Chrome...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    if png_file.exists() and png_file.stat().st_size > 50000:
        print(f"SUCCESS! Infographic rendered: {png_file} (size: {png_file.stat().st_size / 1024:.1f} KB)")
    else:
        print("FAILED or output file too small. STDERR:", res.stderr)

if __name__ == "__main__":
    main()
