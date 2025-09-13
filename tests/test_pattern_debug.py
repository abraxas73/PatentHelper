#!/usr/bin/env python3
"""
Debug inline pattern matching
"""
import re

def test_pattern():
    """Test inline pattern matching"""

    # Pattern from text_analyzer.py
    inline_pattern = r'(?:^|[\s,.]|상기\s+)((?:[가-힣0-9]+\s*(?:을|를|이|가|에|의|와|과|으로|로|하는|되는|된|한|시키기)?\s*(?:위한\s+)?)?[가-힣0-9]{2,}(?:\s[가-힣0-9]{1,8}(?:\s[가-힣0-9]{1,8})?)?)\((\d{1,4}[a-zA-Z]?)\)'

    test_cases = [
        "회전하는 축(303)",
        "고정시키기 위한 걸림고리(153)",
        "제어부(100)",
        "설치된 프레임(404)",
    ]

    print("=== Testing Inline Pattern ===\n")
    print(f"Pattern: {inline_pattern}\n")

    for text in test_cases:
        match = re.search(inline_pattern, text)
        if match:
            print(f"✓ '{text}' matched")
            print(f"  Group 1 (label): '{match.group(1)}'")
            print(f"  Group 2 (number): '{match.group(2)}'")
        else:
            print(f"✗ '{text}' not matched")
        print()

if __name__ == "__main__":
    test_pattern()