#!/usr/bin/env python3
"""
Test cleaning of '통공을 통해 볼트'
"""
from app.services.text_analyzer import TextAnalyzer
import re

def test_clean():
    """Test label cleaning"""

    analyzer = TextAnalyzer()
    label = "통공을 통해 볼트"

    print(f"Original label: '{label}'")
    print()

    # Test if pattern matches
    patterns = [
        r'.*[을를]\s*위한\s+',  # ~를 위한
        r'.*하기\s*위한\s+',     # ~하기 위한
        r'.*시키기\s*위한\s+',   # ~시키기 위한
        r'.*[을를]\s*이용한\s+', # ~를 이용한
        r'.*[을를]\s*통한\s+',   # ~를 통한
        r'.*[을를]\s*통해\s+',   # ~를 통해 (missing?)
    ]

    print("Pattern matching test:")
    for pattern in patterns:
        match = re.match(pattern, label)
        if match:
            print(f"  ✓ Matched: '{pattern}'")
            print(f"    Remaining: '{label[match.end():].strip()}'")
        else:
            print(f"  ✗ Not matched: '{pattern}'")

    print()

    # Test actual cleaning
    cleaned = analyzer._clean_label(label)
    print(f"Cleaned result: '{cleaned}'")

if __name__ == "__main__":
    test_clean()