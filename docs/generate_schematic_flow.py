import os
import base64
import subprocess
from pathlib import Path

def get_base64_image(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def build_html(logo_b64: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>Zecro — schemat przepływu systemu generatywnego składu prasowego</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  
  body {{
    width: 3840px;
    height: 2160px;
    background: #06080e;
    background-image: 
      radial-gradient(circle at 50% 10%, rgba(225, 38, 47, 0.12) 0%, transparent 50%),
      radial-gradient(circle at 15% 45%, rgba(14, 165, 233, 0.08) 0%, transparent 45%),
      radial-gradient(circle at 85% 55%, rgba(16, 185, 129, 0.08) 0%, transparent 45%),
      linear-gradient(to bottom, #05070c 0%, #080c16 50%, #040609 100%);
    color: #e2e8f0;
    font-family: 'Plus Jakarta Sans', sans-serif;
    overflow: hidden;
    position: relative;
    padding: 45px 80px;
  }}

  .grid-pattern {{
    position: absolute;
    top: 0; left: 0; width: 3840px; height: 2160px;
    background-size: 60px 60px;
    background-image: 
      linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
    pointer-events: none;
    z-index: 0;
  }}

  .flow-canvas {{
    position: absolute;
    top: 0; left: 0; width: 3840px; height: 2160px;
    pointer-events: none;
    z-index: 5;
  }}

  .header {{
    position: relative;
    z-index: 10;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 25px;
    margin-bottom: 35px;
  }}

  .logo-block {{
    display: flex;
    align-items: center;
    gap: 32px;
  }}

  .official-logo-img {{
    height: 105px;
    width: auto;
    object-fit: contain;
    filter: drop-shadow(0 15px 30px rgba(0, 0, 0, 0.6));
    border-radius: 12px;
  }}

  .title-content h1 {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 46px;
    font-weight: 800;
    letter-spacing: -1px;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 16px;
  }}

  .title-content h1 span.accent {{
    color: #e1262f;
    text-shadow: 0 0 25px rgba(225, 38, 47, 0.6);
  }}

  .title-content p.subtitle {{
    font-size: 19px;
    font-weight: 600;
    color: #94a3b8;
    margin-top: 4px;
    letter-spacing: 0.5px;
  }}

  .legend-bar {{
    display: flex;
    gap: 24px;
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 14px 28px;
    border-radius: 16px;
    backdrop-filter: blur(16px);
  }}

  .legend-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    font-weight: 600;
    color: #cbd5e1;
  }}

  .legend-dot {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
  }}

  .diagram-container {{
    position: relative;
    z-index: 10;
    height: 1730px;
    width: 3680px;
  }}

  .node-box {{
    position: absolute;
    background: linear-gradient(160deg, rgba(22, 30, 50, 0.88) 0%, rgba(11, 16, 28, 0.94) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 24px;
    padding: 24px 28px;
    box-shadow: 
      0 20px 45px rgba(0, 0, 0, 0.6),
      inset 0 1px 2px rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(20px);
  }}

  .node-box::before {{
    content: '';
    position: absolute;
    top: 0; left: 24px; right: 24px;
    height: 3px;
    border-radius: 3px;
  }}

  .node-cyan::before {{ background: #0ea5e9; box-shadow: 0 0 15px #0ea5e9; }}
  .node-purple::before {{ background: #a855f7; box-shadow: 0 0 15px #a855f7; }}
  .node-crimson::before {{ background: #e1262f; box-shadow: 0 0 20px #e1262f; }}
  .node-gold::before {{ background: #eab308; box-shadow: 0 0 15px #eab308; }}
  .node-green::before {{ background: #10b981; box-shadow: 0 0 15px #10b981; }}

  .node-header {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
  }}

  .node-badge {{
    padding: 4px 10px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
  }}

  .badge-cyan {{ background: rgba(14, 165, 233, 0.2); color: #38bdf8; border: 1px solid rgba(14, 165, 233, 0.4); }}
  .badge-purple {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }}
  .badge-crimson {{ background: rgba(225, 38, 47, 0.2); color: #f87171; border: 1px solid rgba(225, 38, 47, 0.4); }}
  .badge-gold {{ background: rgba(234, 179, 8, 0.2); color: #fde047; border: 1px solid rgba(234, 179, 8, 0.4); }}
  .badge-green {{ background: rgba(16, 185, 129, 0.2); color: #4ade80; border: 1px solid rgba(16, 185, 129, 0.4); }}

  .node-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
  }}

  .node-desc {{
    font-size: 13.5px;
    color: #94a3b8;
    line-height: 1.5;
    margin-bottom: 12px;
  }}

  .node-list {{
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}

  .node-item {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .node-item strong {{
    color: #f1f5f9;
  }}

  .node-item span.tag {{
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    color: #64748b;
  }}

  .arrow-label {{
    position: absolute;
    background: rgba(9, 14, 26, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    padding: 6px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 600;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
    z-index: 20;
    white-space: nowrap;
  }}

  .label-cyan {{ color: #38bdf8; border-color: rgba(14, 165, 233, 0.4); }}
  .label-purple {{ color: #c084fc; border-color: rgba(168, 85, 247, 0.4); }}
  .label-crimson {{ color: #f87171; border-color: rgba(225, 38, 47, 0.5); }}
  .label-gold {{ color: #fde047; border-color: rgba(234, 179, 8, 0.4); }}
  .label-green {{ color: #4ade80; border-color: rgba(16, 185, 129, 0.4); }}

  .footer-bar {{
    position: absolute;
    bottom: 35px;
    left: 80px;
    right: 80px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }}

  .footer-text {{
    font-size: 14px;
    color: #94a3b8;
  }}

  .footer-text strong {{
    color: #f1f5f9;
  }}

  .footer-meta {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12.5px;
    color: #64748b;
  }}
</style>
</head>
<body>

<div class="grid-pattern"></div>

<!-- NAGŁÓWEK Z OFICJALNYM LOGO PROJEKTU -->
<header class="header">
  <div class="logo-block">
    <img src="data:image/png;base64,{logo_b64}" alt="Logo Zecro" class="official-logo-img" />
    <div class="title-content">
      <h1>Zecro <span class="accent">AI Art Director</span></h1>
      <p class="subtitle">Schemat przepływu danych i mechanizmów generatywnego składu prasowego</p>
    </div>
  </div>

  <div class="legend-bar">
    <div class="legend-item"><div class="legend-dot" style="background:#0ea5e9;"></div> Dane wejściowe</div>
    <div class="legend-item"><div class="legend-dot" style="background:#a855f7;"></div> Sterowanie DNA tytułu</div>
    <div class="legend-item"><div class="legend-dot" style="background:#e1262f;"></div> Silniki i generator</div>
    <div class="legend-item"><div class="legend-dot" style="background:#eab308;"></div> Kontrola jakości i pętla gustu</div>
    <div class="legend-item"><div class="legend-dot" style="background:#10b981;"></div> Wyjście hybrydowe</div>
  </div>
</header>

<!-- STRZAŁKI WEKTOROWE SVG -->
<svg class="flow-canvas" viewBox="0 0 3840 2160">
  <defs>
    <marker id="arrow-cyan" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
      <path d="M 0 0 L 8 4 L 0 8 z" fill="#0ea5e9" />
    </marker>
    <marker id="arrow-purple" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
      <path d="M 0 0 L 8 4 L 0 8 z" fill="#a855f7" />
    </marker>
    <marker id="arrow-crimson" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
      <path d="M 0 0 L 8 4 L 0 8 z" fill="#e1262f" />
    </marker>
    <marker id="arrow-gold" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
      <path d="M 0 0 L 8 4 L 0 8 z" fill="#eab308" />
    </marker>
    <marker id="arrow-green" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
      <path d="M 0 0 L 8 4 L 0 8 z" fill="#10b981" />
    </marker>

    <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glow-crimson" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glow-gold" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- 1. Redakcja -> Moduł adiustacji i Google Gemini AI -->
  <path d="M 520 380 L 660 380" stroke="#0ea5e9" stroke-width="4" fill="none" marker-end="url(#arrow-cyan)" filter="url(#glow-cyan)" />
  <path d="M 520 440 L 600 440 L 600 680 L 660 680" stroke="#0ea5e9" stroke-width="4" fill="none" marker-end="url(#arrow-cyan)" filter="url(#glow-cyan)" />

  <!-- 2. Adiustacja i Gemini -> Generator makiety -->
  <path d="M 1160 380 L 1320 380 L 1320 620 L 1400 620" stroke="#0ea5e9" stroke-width="4" fill="none" marker-end="url(#arrow-cyan)" filter="url(#glow-cyan)" />
  <path d="M 1160 680 L 1400 680" stroke="#0ea5e9" stroke-width="4" fill="none" marker-end="url(#arrow-cyan)" filter="url(#glow-cyan)" />

  <!-- 3. TitleDNA (Archetypy i siatka) -> Generator makiety -->
  <path d="M 1160 1060 L 1320 1060 L 1320 740 L 1400 740" stroke="#a855f7" stroke-width="4" fill="none" marker-end="url(#arrow-purple)" />
  <path d="M 1160 1420 L 1360 1420 L 1360 800 L 1400 800" stroke="#a855f7" stroke-width="4" fill="none" marker-end="url(#arrow-purple)" />

  <!-- 4. Mikrosilniki wspomagające -> Generator makiety -->
  <path d="M 1670 1200 L 1670 940" stroke="#e1262f" stroke-width="4" fill="none" marker-end="url(#arrow-crimson)" filter="url(#glow-crimson)" />

  <!-- 5. Generator makiety -> Graf sceny -->
  <path d="M 1940 700 L 2100 700" stroke="#e1262f" stroke-width="5" fill="none" marker-end="url(#arrow-crimson)" filter="url(#glow-crimson)" />

  <!-- 6. Graf sceny -> Twarda bramka krytyka -->
  <path d="M 2580 700 L 2720 700" stroke="#eab308" stroke-width="4" fill="none" marker-end="url(#arrow-gold)" filter="url(#glow-gold)" />

  <!-- 7. Pętla powrotna przy błędzie (Fail -> regeneracja) -->
  <path d="M 2990 540 L 2990 260 L 1670 260 L 1670 520" stroke="#f43f5e" stroke-width="4" stroke-dasharray="10 6" fill="none" marker-end="url(#arrow-crimson)" />

  <!-- 8. Twarda bramka zdana (Pass) -> Sędzia VLM i pętla gustu -->
  <path d="M 2990 860 L 2990 1040" stroke="#eab308" stroke-width="4" fill="none" marker-end="url(#arrow-gold)" />

  <!-- 9. Sędzia VLM -> Rozgałęzienie formatów -->
  <path d="M 2990 1360 L 2990 1520 L 3220 1520" stroke="#10b981" stroke-width="5" fill="none" marker-end="url(#arrow-green)" />
  <path d="M 2990 1360 L 2990 1200 L 3220 1200" stroke="#10b981" stroke-width="5" fill="none" marker-end="url(#arrow-green)" />
</svg>

<!-- ETYKIETY I WĘZŁY SCHEMATU -->
<div class="diagram-container">

  <!-- Etykiety na strzałkach -->
  <div class="arrow-label label-cyan" style="top: 350px; left: 535px;">Teksty źródłowe</div>
  <div class="arrow-label label-cyan" style="top: 550px; left: 535px;">Surowe fotografie</div>
  <div class="arrow-label label-cyan" style="top: 480px; left: 1220px;">Skrócony tekst i wagi</div>
  <div class="arrow-label label-cyan" style="top: 650px; left: 1200px;">Maski alfa i kontury</div>
  <div class="arrow-label label-purple" style="top: 890px; left: 1220px;">Archetyp i budżet energii</div>
  <div class="arrow-label label-purple" style="top: 1080px; left: 1220px;">Siatka i skala pism</div>
  <div class="arrow-label label-crimson" style="top: 1060px; left: 1685px;">Infografiki, odsyłacze i mikrotypografia</div>
  <div class="arrow-label label-crimson" style="top: 670px; left: 1955px;">Propozycja sceny makiety</div>
  <div class="arrow-label label-gold" style="top: 670px; left: 2595px;">Bramka zgodności</div>
  <div class="arrow-label label-crimson" style="top: 230px; left: 2200px;">Błąd prepress lub kolizja ➔ ponowne generowanie (mutacja geometrii)</div>
  <div class="arrow-label label-gold" style="top: 940px; left: 2840px;">Bramka zdana: ocena gustu VLM</div>
  <div class="arrow-label label-green" style="top: 1170px; left: 3020px;">Render natychmiastowy</div>
  <div class="arrow-label label-green" style="top: 1490px; left: 3020px;">Produkcja do druku DTP</div>

  <!-- WĘZEŁ 1: REDAKCJA -->
  <div class="node-box node-cyan" style="top: 300px; left: 60px; width: 460px; height: 360px;">
    <div class="node-header">
      <span class="node-badge badge-cyan">Wejście 01</span>
      <h3 class="node-title">Redakcja i materiały</h3>
    </div>
    <p class="node-desc">Dziennikarz lub redaktor wprowadza materiały do wydania. Parser określa hierarchię ważności.</p>
    <div class="node-list">
      <div class="node-item"><strong>Teksty artykułów</strong> (nagłówek, lead, treść)<span class="tag">txt</span></div>
      <div class="node-item"><strong>Wagi ważności</strong> (otwarcie=1.0, drugi=0.7, notatki=0.3)<span class="tag">rank</span></div>
      <div class="node-item"><strong>Surowe fotografie</strong> (DPI, twarze, kadry)<span class="tag">img</span></div>
      <div class="node-item"><strong>Metadane wydania</strong> (data, numer, winieta)<span class="tag">meta</span></div>
    </div>
  </div>

  <!-- WĘZEŁ 2A: MODUŁ ADIUSTACJI -->
  <div class="node-box node-cyan" style="top: 260px; left: 660px; width: 500px; height: 260px;">
    <div class="node-header">
      <span class="node-badge badge-cyan">Moduł 02A</span>
      <h3 class="node-title">Moduł adiustacji tekstu</h3>
    </div>
    <p class="node-desc">Skraca i redaguje tekst do fizycznej ramy makiety. Zero halucynacji: zakaz dopisywania nieobecnych faktów.</p>
    <div class="node-list">
      <div class="node-item"><strong>Liczenie znaków i linii</strong> (target_words, target_lines)</div>
      <div class="node-item"><strong>Rytm nagłówka</strong> (zależny od stylu gazety)</div>
    </div>
  </div>

  <!-- WĘZEŁ 2B: GEMINI AI -->
  <div class="node-box node-cyan" style="top: 560px; left: 660px; width: 500px; height: 260px;">
    <div class="node-header">
      <span class="node-badge badge-cyan">Moduł 02B</span>
      <h3 class="node-title">Szparowanie w Google Gemini AI</h3>
    </div>
    <p class="node-desc">Multimodalny model AI wycina tło ze zdjęć i wektoryzuje sylwetkę postaci do oblewania tekstem.</p>
    <div class="node-list">
      <div class="node-item"><strong>Maska alfa postaci</strong> (szparowanie sylwetki)</div>
      <div class="node-item"><strong>Wektorowy kontur wielokąta</strong> (do opływania tekstem)</div>
    </div>
  </div>

  <!-- WĘZEŁ 3A: TITLE DNA -->
  <div class="node-box node-purple" style="top: 920px; left: 660px; width: 500px; height: 320px;">
    <div class="node-header">
      <span class="node-badge badge-purple">Sterowanie 03A</span>
      <h3 class="node-title">Archetypy TitleDNA</h3>
    </div>
    <p class="node-desc">Gramatyka wizualna zapisana w postaci danych, a nie sztywnych szablonów. Definiuje styl:</p>
    <div class="node-list">
      <div class="node-item"><strong>Gazeta środka (mid-market)</strong> (zrównoważona, 5 kolumn)</div>
      <div class="node-item"><strong>Gazeta poważna</strong> (opiniotwórcza, tekstowa, 6 kolumn)</div>
      <div class="node-item"><strong>Gazeta bulwarowa</strong> (tabloid, mocna dominanta)</div>
      <div class="node-item"><strong>Magazyn</strong> (reportaż, światło) oraz <strong>program TV</strong> (ramówka)</div>
    </div>
  </div>

  <!-- WĘZEŁ 3B: SIATKA I BUDŻET NAPIĘCIA -->
  <div class="node-box node-purple" style="top: 1280px; left: 660px; width: 500px; height: 280px;">
    <div class="node-header">
      <span class="node-badge badge-purple">Sterowanie 03B</span>
      <h3 class="node-title">Siatka i budżet napięcia</h3>
    </div>
    <p class="node-desc">Ścisłe reguły geometryczne oraz limity dynamicznych efektów:</p>
    <div class="node-list">
      <div class="node-item"><strong>Siatka bazowa (baseline grid)</strong> (9.5–10.5 pt)</div>
      <div class="node-item"><strong>Odstępy międzyłamowe</strong> (3.5–5 mm)</div>
      <div class="node-item"><strong>Budżet napięcia strony</strong> (limit rotacji i apli)</div>
    </div>
  </div>

  <!-- WĘZEŁ 4: GENERATOR MAKIETY -->
  <div class="node-box node-crimson" style="top: 520px; left: 1400px; width: 540px; height: 420px; box-shadow: 0 0 50px rgba(225, 38, 47, 0.25);">
    <div class="node-header">
      <span class="node-badge badge-crimson">Serce systemu 04</span>
      <h3 class="node-title">Generator makiety i solver</h3>
    </div>
    <p class="node-desc">Algorytm eksplorujący przestrzeń rozwiązań. Łączy teksty, wycięte zdjęcia i siatkę, budując unikalny układ strony od zera.</p>
    <div class="node-list">
      <div class="node-item"><strong>Wyznaczanie dominanty</strong> (artykuł otwierający ze zdjęciem)</div>
      <div class="node-item"><strong>Boczny pas modułowy</strong> (pas krótkich wiadomości)</div>
      <div class="node-item"><strong>Pasek zapowiedzi</strong> (pasek górny z numerami stron)</div>
      <div class="node-item"><strong>Wieloszpaltowe oblewanie</strong> (opływanie konturu postaci)</div>
    </div>
  </div>

  <!-- WĘZEŁ 4B: MIKROSILNIKI WSPOMAGAJĄCE -->
  <div class="node-box node-crimson" style="top: 1200px; left: 1400px; width: 540px; height: 360px;">
    <div class="node-header">
      <span class="node-badge badge-crimson">Silniki akcyjne 04B</span>
      <h3 class="node-title">Wyspecjalizowane podsilniki</h3>
    </div>
    <p class="node-desc">Automatyczne moduły wstrzykujące profesjonalne elementy DTP bezpośrednio do kompozycji:</p>
    <div class="node-list">
      <div class="node-item"><strong>Infografiki prasowe SVG</strong> (wykresy, pigułki wiedzy, dane)</div>
      <div class="node-item"><strong>Odsyłacze stron (jump lines)</strong> (podział artykułu: „dokończenie ze str. 1”)</div>
      <div class="node-item"><strong>Polska mikrotypografia</strong> (spacje niełamliwe, cudzysłowy „...”)</div>
    </div>
  </div>

  <!-- WĘZEŁ 5: GRAF SCENY -->
  <div class="node-box node-gold" style="top: 560px; left: 2100px; width: 480px; height: 320px;">
    <div class="node-header">
      <span class="node-badge badge-gold">Reprezentacja 05</span>
      <h3 class="node-title">Graf sceny (Scene Graph)</h3>
    </div>
    <p class="node-desc">Abstrakcyjna, obiektowa reprezentacja strony w formacie JSON. Całkowicie niezależna od silnika renderującego.</p>
    <div class="node-list">
      <div class="node-item"><strong>Współrzędne milimetrowe</strong> [x, y, w, h]</div>
      <div class="node-item"><strong>Kolejność warstw Z</strong> (zdjęcie, apla, tekst)</div>
      <div class="node-item"><strong>Wielokąty wycięć</strong> (ścieżki obcinające)</div>
      <div class="node-item"><strong>Style akapitowe i typografia</strong></div>
    </div>
  </div>

  <!-- WĘZEŁ 6A: TWARDA BRAMKA -->
  <div class="node-box node-gold" style="top: 540px; left: 2720px; width: 540px; height: 320px;">
    <div class="node-header">
      <span class="node-badge badge-gold">Krytyk: etap 1</span>
      <h3 class="node-title">Twarda bramka (Hard Gate)</h3>
    </div>
    <p class="node-desc">Matematyczny filtr zgodności technicznej. Jeśli strona zawiera błąd, jest bezwzględnie odrzucana i wraca do generatora:</p>
    <div class="node-list">
      <div class="node-item"><strong>Zero kolizji ramek</strong> (brak nachodzenia elementów)</div>
      <div class="node-item"><strong>Jedna dominanta</strong> (brak chaosu w hierarchii)</div>
      <div class="node-item"><strong>Zgodność prepress</strong> (limit nafarbienia TAC &lt; 240%)</div>
      <div class="node-item"><strong>Brak wiszących spójników</strong> (sierotki na końcach linii)</div>
    </div>
  </div>

  <!-- WĘZEŁ 6B: MIĘKKI SĘDZIA VLM -->
  <div class="node-box node-gold" style="top: 1040px; left: 2720px; width: 540px; height: 320px;">
    <div class="node-header">
      <span class="node-badge badge-gold">Krytyk: etap 2</span>
      <h3 class="node-title">Sędzia VLM i pętla gustu</h3>
    </div>
    <p class="node-desc">Krytyk wzrokowy z wyuczonym gustem dyrektora artystycznego oceniający estetykę i unikalność:</p>
    <div class="node-list">
      <div class="node-item"><strong>Ranking wzrokowy VLM</strong> (balans światła i czytelność)</div>
      <div class="node-item"><strong>Pętla gustu (RLHF/DPO)</strong> (wybory A kontra B dyrektora)</div>
      <div class="node-item"><strong>Metryka nowości</strong> (odległość od korpusu, brak plagiatu)</div>
    </div>
  </div>

  <!-- WĘZEŁ 7A: BŁYSKAWICZNY PDF -->
  <div class="node-box node-green" style="top: 1040px; left: 3220px; width: 440px; height: 260px;">
    <div class="node-header">
      <span class="node-badge badge-green">Produkt A</span>
      <h3 class="node-title">Błyskawiczny PDF</h3>
    </div>
    <p class="node-desc">Skład po stronie przeglądarki klienta:</p>
    <div class="node-list">
      <div class="node-item"><strong>Zero sekund opóźnienia</strong> (natychmiastowy)</div>
      <div class="node-item"><strong>Wektorowy SVG</strong> (idealna ostrość)</div>
      <div class="node-item"><strong>Druk @page</strong> (milimetrowe pasowanie)</div>
    </div>
  </div>

  <!-- WĘZEŁ 7B: PRODUKCJA DTP -->
  <div class="node-box node-green" style="top: 1360px; left: 3220px; width: 440px; height: 260px;">
    <div class="node-header">
      <span class="node-badge badge-green">Produkt B</span>
      <h3 class="node-title">Produkcja DTP i druk</h3>
    </div>
    <p class="node-desc">Standard dla profesjonalnych naświetlarni:</p>
    <div class="node-list">
      <div class="node-item"><strong>Adobe InDesign IDML</strong> (style akapitowe)</div>
      <div class="node-item"><strong>Prepress PDF/X-1a</strong> (pasery, spady, CMYK)</div>
      <div class="node-item"><strong>Czysty kanał 100% K</strong> dla tekstu głównego</div>
    </div>
  </div>

</div>

<!-- STOPKA ARCHITEKTURY -->
<footer class="footer-bar">
  <div class="footer-text">
    <strong>Zasada fundamentalna Zecro:</strong> Kreatywność = eksploracja (generator nie kopiuje szablonu) × selekcja (twardy krytyk techniczny + miękki gust AI Art Directora).
  </div>
  <div class="footer-meta">
    Zecro System Component Graph · Archetyp: Gazeta środka (mid-market) · Pełna infografika procesowa 4K UHD
  </div>
</footer>

</body>
</html>
"""

def main():
    repo_root = Path("/Users/macbookpro/PROJEKTY/LAYOUT")
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    html_file = docs_dir / "zecro_schematic_flow.html"
    png_file = docs_dir / "zecro_schematic_flow.png"

    # Używamy oficjalnego logo projektu: logo-zecro-generative-layout-engine-vibrant.png
    logo_path = repo_root / "logo-zecro-generative-layout-engine-vibrant.png"
    if not logo_path.exists():
        logo_path = repo_root / "logo-zecro-mark-vibrant.png"
    
    logo_b64 = get_base64_image(logo_path)
    html_content = build_html(logo_b64)

    html_file.write_text(html_content, encoding="utf-8")
    print(f"Updated HTML with official logo saved to {html_file}")

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
    print("Rendering updated 4K Schematic Flow PNG with official logo...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if png_file.exists() and png_file.stat().st_size > 50000:
        print(f"SUCCESS! Rendered PNG with official logo: {png_file} (size: {png_file.stat().st_size / 1024:.1f} KB)")
        
        desktop_dst = Path("/Users/macbookpro/Desktop/ZECRO_SCHEMAT_SYSTEMU_4K.png")
        artifact_dst = Path("/Users/macbookpro/.gemini/antigravity/brain/e90afadb-d5d8-4b7b-9754-cac9d0c5d004/zecro_schematic_flow.png")
        
        import shutil
        shutil.copyfile(png_file, desktop_dst)
        shutil.copyfile(png_file, artifact_dst)
        print(f"Copied updated version to Desktop: {desktop_dst}")
        
        subprocess.run(["open", str(desktop_dst)])
    else:
        print("FAILED. STDERR:", res.stderr)

if __name__ == "__main__":
    main()
