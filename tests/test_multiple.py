#!/usr/bin/env python3
"""
Test extraction of multiple numbers in one sentence
"""
from app.services.text_analyzer import TextAnalyzer

def test_multiple():
    """Test extraction of sentences with multiple numbers"""

    analyzer = TextAnalyzer()

    test_cases = [
        "각각 하부 고정각재(41)와 상부 고정각재(42)",
        "하부 고정각재(41)와 상부 고정각재(42)",
        "하부 고정각재(41)",
        "상부 고정각재(42)",
        "고정각재(41)와 고정각재(42)",
        "제1 고정각재(41), 제2 고정각재(42)",
    ]

    print("=== Testing Multiple Number Extraction ===\n")

    for text in test_cases:
        mappings = analyzer.extract_number_mappings(text)

        print(f"Text: '{text}'")
        print(f"  Spaces: {text.count(' ')}")

        if '41' in mappings:
            print(f"  ✓ 41 -> {mappings['41']}")
        else:
            print(f"  ✗ 41 not found")

        if '42' in mappings:
            print(f"  ✓ 42 -> {mappings['42']}")
        else:
            print(f"  ✗ 42 not found")

        if not mappings:
            print(f"  No mappings found")
        elif '41' not in mappings and '42' not in mappings:
            print(f"  Other mappings: {mappings}")
        print()

    # Detailed analysis
    print("=== Detailed Analysis ===\n")

    text = "각각 하부 고정각재(41)와 상부 고정각재(42)"
    print(f"Analyzing: '{text}'\n")

    # Test inline pattern
    import re
    matches = list(re.finditer(analyzer.inline_pattern, text))
    print(f"Inline pattern matches: {len(matches)}")
    for i, match in enumerate(matches):
        print(f"  Match {i+1}:")
        print(f"    Full: '{match.group(0)}'")
        print(f"    Label: '{match.group(1)}'")
        print(f"    Number: '{match.group(2)}'")

        # Test cleaning
        label = match.group(1)
        cleaned = analyzer._clean_label(label)
        print(f"    Cleaned: '{cleaned}'")
        print(f"    Spaces in cleaned: {cleaned.count(' ')}")
        print()

    # Test extraction
    mappings = analyzer._extract_inline_mappings(text)
    print(f"Inline mappings: {mappings}")

    # Test full extraction
    full_mappings = analyzer.extract_number_mappings(text)
    print(f"Full mappings: {full_mappings}")

if __name__ == "__main__":
    test_multiple()