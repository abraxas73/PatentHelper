#!/usr/bin/env python3
"""
Debug sentence splitting
"""
import re

def test_split():
    """Test sentence splitting"""

    test_text = "회전하는 축(303)"

    print(f"Original text: '{test_text}'")
    print(f"Length: {len(test_text)}")
    print()

    # Test split
    sentences = re.split(r'[.。]', test_text)
    print(f"After split by [.。]: {sentences}")
    print(f"Number of sentences: {len(sentences)}")
    print()

    # Check each sentence
    for i, sentence in enumerate(sentences):
        print(f"Sentence {i}: '{sentence}'")
        print(f"  Length: {len(sentence)}")
        print(f"  Empty? {not sentence}")

if __name__ == "__main__":
    test_split()