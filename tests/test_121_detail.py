#!/usr/bin/env python3
"""
Detailed analysis of 121 extraction issue
"""
from pathlib import Path
from app.core.pdf_processor import PDFProcessor
from app.services.text_analyzer import TextAnalyzer
import re

def detailed_analysis():
    """Detailed analysis of why 121 is not extracted"""

    pdf_path = Path("/Users/seungukkang/Repos/PatentHelper/tests/1020200111481B1.pdf")

    with PDFProcessor(pdf_path) as processor:
        full_text = processor.extract_text()

    # Find the exact text around 121: 앵글
    pattern = r'(\d{3}:\s*[가-힣]+\s+\d{3}:\s*[가-힣]+)'
    matches = re.finditer(pattern, full_text)

    print("=== Finding pattern around 121: 앵글 ===\n")

    # Look for the specific section
    section_pattern = r'120:.*?122:'
    section_matches = re.finditer(section_pattern, full_text, re.DOTALL)

    for match in section_matches:
        section = match.group(0)
        print(f"Found section:\n{repr(section[:200])}\n")

    # Test different patterns on the actual text
    test_text = "121: 앵글\n122"

    print("=== Testing patterns on '121: 앵글\\n122' ===\n")

    analyzer = TextAnalyzer()

    # Test basic pattern
    basic_pattern = r'(\d{1,4}[a-zA-Z]?)\s*[:：]\s*([가-힣\w\s]+)'
    match = re.search(basic_pattern, test_text)
    if match:
        print(f"Basic pattern matched: {match.group(1)} -> {match.group(2)}")
    else:
        print("Basic pattern failed")

    # Check line by line processing
    lines = test_text.split('\n')
    print(f"\nLines: {lines}")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        print(f"\nProcessing line: '{line}'")
        match = re.search(basic_pattern, line)
        if match:
            number = match.group(1).strip()
            label = match.group(2).strip()
            # Apply cleaning
            label = analyzer._clean_label(label)
            print(f"  Extracted: {number} -> {label}")

    # Test with actual extraction
    print("\n=== Testing with TextAnalyzer ===\n")

    # Try extracting from the problematic text
    test_texts = [
        "121: 앵글",
        "121: 앵글\n",
        "121: 앵글\n122",
        "121: 앵글\n122: 장공",
        "[0052] 120: GMT 판재 121: 앵글",
    ]

    for text in test_texts:
        print(f"Testing: {repr(text)}")
        mappings = analyzer.extract_number_mappings(text)
        if '121' in mappings:
            print(f"  ✓ 121 -> {mappings['121']}")
        else:
            print(f"  ✗ 121 not found")
            # Show what was found
            if mappings:
                print(f"  Found: {mappings}")

if __name__ == "__main__":
    detailed_analysis()