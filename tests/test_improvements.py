#!/usr/bin/env python3

import sys
from pathlib import Path
from app.core.pdf_processor import PDFProcessor
from app.services.text_analyzer import TextAnalyzer
from app.services.image_extractor import ImageExtractor
from app.services.image_annotator import ImageAnnotator

def test_improvements():
    # Test PDF path
    pdf_path = Path("data/input/1020210171864A (1).pdf")
    
    if not pdf_path.exists():
        print(f"❌ Test PDF not found: {pdf_path}")
        print("Please upload a patent PDF through the web interface first.")
        return
    
    print(f"Testing improvements with: {pdf_path.name}")
    print("=" * 60)
    
    # 1. Test text analyzer for part list extraction
    print("\n1. Testing Part List Extraction:")
    print("-" * 40)
    
    text_analyzer = TextAnalyzer()
    
    with PDFProcessor(pdf_path) as processor:
        full_text = processor.extract_text()
        
        # Extract number mappings (should prioritize part list)
        mappings = text_analyzer.extract_number_mappings(full_text)
        
        print(f"Found {len(mappings)} number-label mappings:")
        
        # Show first 10 mappings
        for i, (num, label) in enumerate(list(mappings.items())[:10]):
            print(f"  {num}: {label}")
            if i == 9 and len(mappings) > 10:
                print(f"  ... and {len(mappings) - 10} more")
        
        # Check if we found part list section
        part_list_section = text_analyzer._extract_part_list_section(full_text)
        if part_list_section:
            print(f"\n✅ Found dedicated part list section")
            print(f"   Section length: {len(part_list_section)} chars")
        else:
            print("\n⚠️ No dedicated part list section found")
    
    # 2. Test image extraction with text region removal
    print("\n2. Testing Drawing Extraction (with text removal):")
    print("-" * 40)
    
    output_dir = Path("data/output/images")
    extractor = ImageExtractor(output_dir)
    
    with PDFProcessor(pdf_path) as processor:
        # Get page with drawing
        for page_num in range(min(5, processor.get_page_count())):
            images = processor.extract_images_from_page(page_num)
            
            if images:
                print(f"\nPage {page_num + 1}:")
                print(f"  Extracted {len(images)} image(s)")
                
                # Save and process first image
                saved = extractor.extract_and_save_images(images[:1], pdf_path.stem)
                if saved:
                    img_info = saved[0]
                    print(f"  Saved: {img_info['filename']}")
                    print(f"  Size: {img_info['width']}x{img_info['height']}")
                    
                    if img_info.get('figure_number'):
                        print(f"  Figure: {img_info['figure_number']}")
    
    # 3. Test annotation with improved mappings
    print("\n3. Testing Annotation with Part Names:")
    print("-" * 40)
    
    annotator = ImageAnnotator(Path("data/output/annotated"))
    
    # Find an extracted image to annotate
    extracted_images = list(output_dir.glob("*.png"))
    if extracted_images:
        test_image = extracted_images[0]
        print(f"Annotating: {test_image.name}")
        
        # Find numbered regions
        numbered_regions = extractor.find_numbered_regions(str(test_image))
        print(f"Found {len(numbered_regions)} numbered regions")
        
        if numbered_regions and mappings:
            # Annotate
            annotated_path = annotator.annotate_image(
                str(test_image),
                numbered_regions,
                mappings
            )
            
            if annotated_path:
                print(f"✅ Annotated image saved: {Path(annotated_path).name}")
            else:
                print("❌ Annotation failed")
    
    print("\n" + "=" * 60)
    print("Test complete! Check the web interface to see the results.")

if __name__ == "__main__":
    test_improvements()