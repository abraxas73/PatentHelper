#!/usr/bin/env python3
"""
Test pattern matching
"""
import re

def test_pattern():
    """Test adnominal pattern matching"""

    label = "회전하는 축"

    patterns = [
        r'.*[을를]\s*위한\s+',  # ~를 위한
        r'.*하기\s*위한\s+',     # ~하기 위한
        r'.*되는\s+',           # ~되는
        r'.*하는\s+',           # ~하는
        r'.*[된한]\s+',         # ~된, ~한
        r'.*시키기\s*위한\s+',   # ~시키기 위한
        r'.*[을를]\s*이용한\s+', # ~를 이용한
        r'.*[을를]\s*통한\s+',   # ~를 통한
    ]

    print(f"Testing: '{label}'\n")

    for i, pattern in enumerate(patterns):
        match = re.match(pattern, label)
        if match:
            print(f"Pattern {i} matched: '{pattern}'")
            print(f"  Match end: {match.end()}")
            print(f"  Remaining: '{label[match.end():].strip()}'")
            print(f"  Remaining length: {len(label[match.end():].strip())}")
        else:
            print(f"Pattern {i} not matched: '{pattern}'")

if __name__ == "__main__":
    test_pattern()