#!/usr/bin/env python3
"""
Newspaper Copyfitting Engine
Calculates copy fit, characters per pica (CPP), total lines, column depth,
and provides copy adjustment recommendations for print layouts.
"""

import argparse
import sys

def calculate_copyfit(word_count=None, char_count=None, columns=3, column_width_mm=54.0, 
                      allocated_height_mm=200.0, font_size_pt=10.0, leading_pt=13.0):
    if char_count is None:
        if word_count is None:
            print("Error: Provide either --words, --chars, or --file.")
            sys.exit(1)
        char_count = int(word_count * 5.6)  # Standard average chars per word including space
    else:
        word_count = int(char_count / 5.6)

    # 1 pica = 4.2333 mm = 12 points
    # 1 inch = 25.4 mm = 6 picas = 72 points
    col_width_picas = column_width_mm / 4.2333
    col_width_inches = column_width_mm / 25.4

    # Estimated Characters Per Pica (CPP) based on font size
    # Standard serif 10pt = ~2.6 CPP; 9pt = ~2.9 CPP; 11pt = ~2.3 CPP
    cpp = 26.0 / font_size_pt
    chars_per_line = int(col_width_picas * cpp)
    
    total_lines = int((char_count / chars_per_line) * 1.05) # Add 5% for short paragraph ends
    lines_per_column = int(total_lines / columns)

    # Calculate required depth in points, inches, and mm
    required_depth_pts = lines_per_column * leading_pt
    required_depth_inches = required_depth_pts / 72.0
    required_depth_mm = required_depth_inches * 25.4

    difference_mm = required_depth_mm - allocated_height_mm
    diff_percent = (difference_mm / allocated_height_mm) * 100

    print("=" * 60)
    print(" 📰 NEWSPAPER COPYFITTING ANALYSIS")
    print("=" * 60)
    print(f" • Total Words:           {word_count:,}")
    print(f" • Total Characters:      {char_count:,}")
    print(f" • Number of Columns:     {columns}")
    print(f" • Column Width:          {column_width_mm:.1f} mm ({col_width_picas:.1f} picas / {col_width_inches:.2f} in)")
    print(f" • Typography Setting:    {font_size_pt}pt font on {leading_pt}pt leading (~{chars_per_line} chars/line)")
    print(f" • Total Estimated Lines: {total_lines} lines ({lines_per_column} lines per column)")
    print("-" * 60)
    print(f" • Allocated Depth:       {allocated_height_mm:.1f} mm ({allocated_height_mm / 25.4:.2f} in)")
    print(f" • Required Depth:        {required_depth_mm:.1f} mm ({required_depth_inches:.2f} in)")
    print("-" * 60)

    if abs(difference_mm) <= 5.0:
        print(" ✅ STATUS: PERFECT FIT! (Within ±5mm tolerance)")
    elif difference_mm > 0:
        print(f" ⚠️ STATUS: OVERSET (Copy is TOO LONG by {difference_mm:.1f} mm / +{diff_percent:.1f}%)")
        words_to_cut = int((difference_mm / required_depth_mm) * word_count)
        print(f" 💡 RECOMMENDATIONS TO FIX OVERSET:")
        print(f"    1. Cut approximately {words_to_cut} words from the copy.")
        print(f"    2. Reduce leading from {leading_pt}pt to {leading_pt * (allocated_height_mm / required_depth_mm):.1f}pt.")
        print(f"    3. Reduce font size from {font_size_pt}pt to {font_size_pt * 0.95:.1f}pt with tighter tracking (-0.015em).")
        print(f"    4. Split article and add jump line: 'Continued on Page A6'.")
    else:
        under_mm = abs(difference_mm)
        print(f" ℹ️ STATUS: UNDERSET / HOLE (Copy is TOO SHORT by {under_mm:.1f} mm / {diff_percent:.1f}%)")
        words_to_add = int((under_mm / required_depth_mm) * word_count)
        print(f" 💡 RECOMMENDATIONS TO FILL THE HOLE:")
        print(f"    1. Add approximately {words_to_add} words to the article.")
        print(f"    2. Expand headline with a 2-line or 3-line deck/subhead.")
        print(f"    3. Insert a framed pull-quote (takes ~30-45mm depth).")
        print(f"    4. Add a photo or infographic sidebar (takes ~50-80mm depth).")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Newspaper Copyfitting Calculator")
    parser.add_argument("--words", type=int, help="Word count of the article")
    parser.add_argument("--chars", type=int, help="Total character count")
    parser.add_argument("--file", type=str, help="Path to text/markdown file to analyze")
    parser.add_argument("--columns", type=int, default=3, help="Number of text columns (default: 3)")
    parser.add_argument("--width-mm", type=float, default=54.0, help="Column width in mm (default: 54.0mm)")
    parser.add_argument("--height-mm", type=float, default=200.0, help="Allocated column depth in mm (default: 200.0mm)")
    parser.add_argument("--font-size", type=float, default=10.0, help="Body font size in pt (default: 10.0pt)")
    parser.add_argument("--leading", type=float, default=13.0, help="Line leading in pt (default: 13.0pt)")

    args = parser.parse_args()

    chars = args.chars
    words = args.words

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()
                chars = len(content)
                words = len(content.split())
        except Exception as e:
            print(f"Error reading file {args.file}: {e}")
            sys.exit(1)

    if words is None and chars is None:
        # Default demo calculation
        words = 650

    calculate_copyfit(word_count=words, char_count=chars, columns=args.columns,
                      column_width_mm=args.width_mm, allocated_height_mm=args.height_mm,
                      font_size_pt=args.font_size, leading_pt=args.leading)
