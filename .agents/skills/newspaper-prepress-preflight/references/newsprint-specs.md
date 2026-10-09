# ISOnewspaper & Newsprint Specifications

## Standard Printing Profiles
- **WAN-IFRA / ISOnewspaper26v4**: Dot gain 26%, Total ink limit 220–240%, Screen ruling 85–100 LPI (lines per inch).
- **SNAP (Specifications for Newsprint Advertising Production)**: North American standard, 220% TAC.

## Preflight Pass/Fail Gate
- `TAC > 240%`: **FAIL**
- `Text < 14pt not 100% K`: **FAIL**
- `Missing embedded font`: **FAIL**
- `Image DPI < 150`: **FAIL**
- `Unresolved bleed on trimmed element`: **FAIL**
