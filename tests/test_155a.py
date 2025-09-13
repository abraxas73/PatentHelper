#!/usr/bin/env python3
"""
Test extraction of '통공을 통해 볼트(155a)'
"""
from app.services.text_analyzer import TextAnalyzer

def test_155a():
    """Test extraction of 155a from various patterns"""

    analyzer = TextAnalyzer()

    test_cases = [
        "통공을 통해 볼트(155a)",
        "통공을 통한 볼트(155a)",
        "볼트(155a)",
        "고정 볼트(155a)",
        "연결용 볼트(155a)",
        "통공을 통해 볼트(155a)가 삽입된다",
        "너트(155b)와 볼트(155a)를 사용하여",
    ]

    print("=== Testing 155a Extraction ===\n")

    for text in test_cases:
        mappings = analyzer.extract_number_mappings(text)

        print(f"Text: '{text}'")
        if '155a' in mappings:
            print(f"  ✓ 155a -> {mappings['155a']}")
        else:
            print(f"  ✗ 155a not found")
            if mappings:
                print(f"  Found mappings: {mappings}")
        print()

    # Test the specific case in detail
    print("=== Detailed Analysis for '통공을 통해 볼트(155a)' ===\n")

    text = "통공을 통해 볼트(155a)"

    # Test inline pattern matching
    import re
    match = re.search(analyzer.inline_pattern, text)
    if match:
        print(f"Inline pattern matched:")
        print(f"  Full match: '{match.group(0)}'")
        print(f"  Label (group 1): '{match.group(1)}'")
        print(f"  Number (group 2): '{match.group(2)}'")
    else:
        print("Inline pattern not matched")

    print()

    # Test label cleaning
    if match:
        label = match.group(1)
        cleaned = analyzer._clean_label(label)
        print(f"Label cleaning:")
        print(f"  Original: '{label}'")
        print(f"  Cleaned: '{cleaned}'")
        print(f"  Length: {len(cleaned)}")
        print(f"  Valid (2-30 chars): {2 <= len(cleaned) <= 30}")

if __name__ == "__main__":
    test_155a()