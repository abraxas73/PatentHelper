#!/usr/bin/env python3
"""
Test adnominal clause removal
"""
from app.services.text_analyzer import TextAnalyzer

def test_adnominal_removal():
    """Test removal of adnominal clauses"""

    analyzer = TextAnalyzer()

    # Test cases
    test_cases = [
        ("고정시키기 위한 걸림고리(153)", "걸림고리"),
        ("연결을 위한 브라켓(201)", "브라켓"),
        ("지지하기 위한 지지대(102)", "지지대"),
        ("회전하는 축(303)", "축"),
        ("설치된 프레임(404)", "프레임"),
        ("조립하기 위한 조립부(505)", "조립부"),
        ("제어를 위한 제어부(100)", "제어부"),
        ("고정을 이용한 고정장치(123)", "고정장치"),
        ("연결을 통한 연결부(234)", "연결부"),
    ]

    print("=== Testing Adnominal Clause Removal ===\n")

    for test_text, expected_label in test_cases:
        # Extract mappings
        mappings = analyzer.extract_number_mappings(test_text)

        # Get the number from the test text
        import re
        match = re.search(r'\((\d+)\)', test_text)
        if match:
            number = match.group(1)
            if number in mappings:
                result = mappings[number]
                status = "✓" if result == expected_label else "✗"
                print(f"{status} '{test_text}'")
                print(f"   Expected: {expected_label}")
                print(f"   Got: {result}")
                if result != expected_label:
                    print(f"   ** MISMATCH **")
            else:
                print(f"✗ '{test_text}'")
                print(f"   Number {number} not found in mappings")
                print(f"   Mappings: {mappings}")
        print()

if __name__ == "__main__":
    test_adnominal_removal()