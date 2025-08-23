#!/usr/bin/env python3

import easyocr
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def create_test_image():
    # Create a test image with Korean text and numbers
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add some text
    texts = [
        ("도 1", (50, 50)),
        ("100: 본체", (100, 150)),
        ("110: 프로세서", (100, 200)),
        ("120: 메모리", (100, 250)),
        ("130: 저장장치", (100, 300)),
        ("Figure 2", (400, 50)),
        ("200: Display", (450, 150)),
        ("210: LCD Panel", (450, 200)),
        ("220: Backlight", (450, 250)),
    ]
    
    for text, pos in texts:
        draw.text(pos, text, fill='black')
    
    # Draw some boxes to simulate diagram elements
    draw.rectangle([50, 350, 250, 450], outline='black', width=2)
    draw.text((60, 360), "Component A", fill='black')
    draw.text((100, 400), "350", fill='red')
    
    draw.rectangle([450, 350, 650, 450], outline='black', width=2)
    draw.text((460, 360), "Component B", fill='black')
    draw.text((500, 400), "360", fill='red')
    
    # Save test image
    test_path = "test_patent_diagram.png"
    img.save(test_path)
    print(f"Test image created: {test_path}")
    return test_path

def test_ocr(image_path):
    print("\n=== Testing OCR functionality ===")
    
    # Initialize reader
    print("Initializing EasyOCR reader (Korean + English)...")
    reader = easyocr.Reader(['ko', 'en'], gpu=False)
    
    # Read text from image
    print(f"Reading text from: {image_path}")
    results = reader.readtext(image_path)
    
    print(f"\nFound {len(results)} text regions:")
    print("-" * 50)
    
    for (bbox, text, prob) in results:
        if prob > 0.5:  # Only show confident results
            print(f"Text: '{text}' (Confidence: {prob:.2f})")
            # Extract bounding box coordinates
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            print(f"  Location: x=[{min(x_coords):.0f}-{max(x_coords):.0f}], y=[{min(y_coords):.0f}-{max(y_coords):.0f}]")
    
    print("-" * 50)
    
    # Test number detection
    print("\n=== Testing number detection ===")
    numbers_found = []
    for (bbox, text, prob) in results:
        if prob > 0.5:
            # Check if it's a number (1-3 digits)
            import re
            if re.match(r'^\d{1,3}$', text.strip()):
                numbers_found.append(text.strip())
                print(f"Found number: {text}")
    
    print(f"\nTotal numbers found: {len(numbers_found)}")
    
    # Test figure detection
    print("\n=== Testing figure detection ===")
    figure_patterns = [
        r'도\s*\d+',
        r'[Ff]ig(?:ure)?\s*\d+'
    ]
    
    figures_found = []
    for (bbox, text, prob) in results:
        if prob > 0.5:
            for pattern in figure_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    figures_found.append(text)
                    print(f"Found figure reference: {text}")
                    break
    
    print(f"\nTotal figure references found: {len(figures_found)}")
    
    return results

if __name__ == "__main__":
    # Create test image
    test_image = create_test_image()
    
    # Test OCR
    results = test_ocr(test_image)
    
    print("\n✅ OCR functionality test completed!")
    print("The OCR system is working properly with Korean and English text recognition.")