#!/usr/bin/env python3
"""
Debug detailed extraction process
"""
from app.services.text_analyzer import TextAnalyzer
import re

def test_detailed():
    """Test detailed extraction process"""

    analyzer = TextAnalyzer()

    test_text = "회전하는 축(303)"

    print("=== Testing Full Extraction Process ===\n")
    print(f"Test text: '{test_text}'\n")

    # Test inline pattern directly
    match = re.search(analyzer.inline_pattern, test_text)
    if match:
        print(f"✓ Pattern matched:")
        print(f"  Label: '{match.group(1)}'")
        print(f"  Number: '{match.group(2)}'")
    else:
        print("✗ Pattern not matched")

    print("\n=== Testing extract_number_mappings ===\n")

    # Test full extraction
    mappings = analyzer.extract_number_mappings(test_text)
    print(f"Mappings: {mappings}")

    if '303' in mappings:
        print(f"✓ 303 found: {mappings['303']}")
    else:
        print("✗ 303 not found")

    # Test _extract_inline_mappings directly
    print("\n=== Testing _extract_inline_mappings directly ===\n")
    inline_mappings = analyzer._extract_inline_mappings(test_text)
    print(f"Inline mappings: {inline_mappings}")

if __name__ == "__main__":
    test_detailed()