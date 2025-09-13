#!/usr/bin/env python3
"""
Test _clean_label method
"""
from app.services.text_analyzer import TextAnalyzer

def test_clean():
    """Test label cleaning"""

    analyzer = TextAnalyzer()

    test_labels = [
        "회전하는 축",
        "고정시키기 위한 걸림고리",
        "제어부",
        "설치된 프레임",
    ]

    print("=== Testing _clean_label ===\n")

    for label in test_labels:
        cleaned = analyzer._clean_label(label)
        print(f"Original: '{label}'")
        print(f"Cleaned: '{cleaned}'")
        print(f"Length: {len(cleaned)}")
        print(f"Valid (2-30 chars)? {2 <= len(cleaned) <= 30}")
        print()

if __name__ == "__main__":
    test_clean()