#!/usr/bin/env python3
"""
Test extraction of '각각 체결됨과 동시에 컵와셔(86)'
"""
from app.services.text_analyzer import TextAnalyzer

def test_cupwasher():
    """Test extraction with adverbs and excessive spaces"""

    analyzer = TextAnalyzer()

    test_cases = [
        "각각 체결됨과 동시에 컵와셔(86)",
        "동시에 컵와셔(86)",
        "즉시 컵와셔(86)",
        "함께 설치되는 컵와셔(86)",
        "순차적으로 배치되는 컵와셔(86)",
        "컵와셔(86)",
    ]

    print("=== Testing Cupwasher Extraction ===\n")

    for text in test_cases:
        mappings = analyzer.extract_number_mappings(text)

        print(f"Text: '{text}'")
        # Count spaces
        space_count = text[:text.find('(')].count(' ') if '(' in text else 0
        print(f"  Spaces before '(': {space_count}")

        if '86' in mappings:
            print(f"  ✓ 86 -> {mappings['86']}")
            result_spaces = mappings['86'].count(' ')
            print(f"  Spaces in result: {result_spaces}")
            if result_spaces > 2:
                print(f"  ⚠️ WARNING: Too many spaces (max 2 allowed)")
        else:
            print(f"  ✗ 86 not found")
            if mappings:
                print(f"  Found mappings: {mappings}")
        print()

    # Detailed analysis
    print("=== Detailed Analysis ===\n")

    text = "각각 체결됨과 동시에 컵와셔(86)"

    # Test inline pattern
    import re
    match = re.search(analyzer.inline_pattern, text)
    if match:
        print(f"Inline pattern matched:")
        print(f"  Full match: '{match.group(0)}'")
        print(f"  Label (group 1): '{match.group(1)}'")
        print(f"  Number (group 2): '{match.group(2)}'")

        # Test cleaning
        label = match.group(1)
        cleaned = analyzer._clean_label(label)
        print(f"\nLabel cleaning:")
        print(f"  Original: '{label}'")
        print(f"  Cleaned: '{cleaned}'")
    else:
        print("Inline pattern not matched")

if __name__ == "__main__":
    test_cupwasher()