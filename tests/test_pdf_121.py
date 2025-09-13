#!/usr/bin/env python3
"""
Test why 121 is not extracted from specific PDF
"""
from pathlib import Path
from app.core.pdf_processor import PDFProcessor
from app.services.text_analyzer import TextAnalyzer
import re

def analyze_pdf_121():
    """Analyze why 121 is not extracted from the PDF"""

    pdf_path = Path("/Users/seungukkang/Repos/PatentHelper/tests/1020200111481B1.pdf")

    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        return

    print(f"Analyzing PDF: {pdf_path}\n")

    # Extract text from PDF
    with PDFProcessor(pdf_path) as processor:
        full_text = processor.extract_text()

    print("=== Searching for '121' in PDF text ===\n")

    # Find all occurrences of 121
    pattern_121 = r'.{0,50}121.{0,50}'  # 121 with 50 chars context
    matches = re.finditer(pattern_121, full_text, re.IGNORECASE)

    occurrences = []
    for match in matches:
        context = match.group(0).strip()
        occurrences.append(context)

    if occurrences:
        print(f"Found {len(occurrences)} occurrences of '121':\n")
        for i, context in enumerate(occurrences[:10], 1):  # Show first 10
            print(f"{i}. ...{context}...")
            print()
    else:
        print("No occurrences of '121' found in the PDF text")

    print("\n=== Testing pattern matching for '121' ===\n")

    # Look for specific patterns
    patterns_to_test = [
        r'앵글\s*\(\s*121\s*\)',
        r'121\s*[:：]\s*[가-힣\w\s]+',
        r'121\s*[-－]\s*[가-힣\w\s]+',
        r'[가-힣\w\s]+\(\s*121\s*\)',
    ]

    for pattern in patterns_to_test:
        matches = re.finditer(pattern, full_text)
        found = False
        for match in matches:
            if not found:
                print(f"Pattern '{pattern}' found:")
                found = True
            print(f"  - {match.group(0)}")
        if not found:
            print(f"Pattern '{pattern}': No matches")
        print()

    print("\n=== Testing TextAnalyzer extraction ===\n")

    # Test with TextAnalyzer
    analyzer = TextAnalyzer()
    mappings = analyzer.extract_number_mappings(full_text)

    if '121' in mappings:
        print(f"✓ 121 extracted: {mappings['121']}")
    else:
        print("✗ 121 not found in mappings")
        print(f"Total mappings found: {len(mappings)}")

        # Show nearby numbers
        nearby = []
        for num in mappings.keys():
            try:
                num_val = int(num.rstrip('abcdefghijklmnopqrstuvwxyz'))
                if 115 <= num_val <= 125:
                    nearby.append((num, mappings[num]))
            except:
                pass

        if nearby:
            print("\nNearby numbers found:")
            for num, label in sorted(nearby):
                print(f"  {num}: {label}")

if __name__ == "__main__":
    analyze_pdf_121()