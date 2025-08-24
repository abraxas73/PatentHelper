#!/usr/bin/env python
"""
CLI 테스트 도구 - PDF 처리 및 도면 추출 테스트

사용법:
    python tests/test_pdf_cli.py <PDF_파일_경로>
    
예시:
    python tests/test_pdf_cli.py sample.pdf
"""

import sys
import os
import argparse
from pathlib import Path
import json
import time

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.pdf_processor import PDFProcessor
from app.services.image_extractor import ImageExtractor
from app.services.text_analyzer import TextAnalyzer
from app.services.image_annotator import ImageAnnotator


def test_pdf_processing(pdf_path: str, output_dir: str = "test_output"):
    """PDF 처리 전체 파이프라인 테스트"""
    
    print(f"\n{'='*60}")
    print(f"PDF 처리 테스트 시작")
    print(f"{'='*60}")
    print(f"입력 파일: {pdf_path}")
    print(f"출력 디렉토리: {output_dir}")
    print(f"{'='*60}\n")
    
    # 출력 디렉토리 생성
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    images_dir = output_path / "images"
    annotated_dir = output_path / "annotated"
    images_dir.mkdir(exist_ok=True)
    annotated_dir.mkdir(exist_ok=True)
    
    try:
        # 1. PDF 처리기 초기화 및 도면 추출
        print("1. PDF 처리기 초기화...")
        start_time = time.time()
        
        with PDFProcessor(Path(pdf_path)) as processor:
            # 2. 도면 추출
            print("2. 도면 추출 중...")
            extracted_images = processor.extract_all_images()
            extraction_time = time.time() - start_time
            
            # 텍스트 추출 (컨텍스트 내에서)
            full_text = processor.extract_text()
        
        print(f"   - 추출된 도면 수: {len(extracted_images)}개")
        print(f"   - 추출 소요 시간: {extraction_time:.2f}초")
        
        if not extracted_images:
            print("   ⚠️  추출된 도면이 없습니다.")
            return
        
        # 도면을 파일로 저장하고 정보 출력
        saved_images = []
        for idx, img_info in enumerate(extracted_images, 1):
            # PIL 이미지를 파일로 저장
            img_filename = f"page_{img_info.get('page', idx)}_{idx}.png"
            img_path = images_dir / img_filename
            img_info['pil_image'].save(img_path)
            img_info['file_path'] = str(img_path)
            saved_images.append(img_info)
            
            print(f"   - 도면 {idx}: 페이지 {img_info.get('page', 0) + 1}, "
                  f"크기 {img_info['width']}x{img_info['height']}")
            print(f"     저장됨: {img_path.name}")
        
        # 3. 텍스트 분석
        print("\n3. 텍스트 분석 중...")
        text_analyzer = TextAnalyzer()
        # full_text는 이미 위에서 추출됨
        number_mappings = text_analyzer.extract_number_mappings(full_text)
        
        print(f"   - 발견된 번호-명칭 매핑: {len(number_mappings)}개")
        if number_mappings:
            print("   - 전체 번호-명칭 매핑:")
            for num, name in sorted(number_mappings.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
                print(f"     {num}: {name}")
        
        # 4. OCR을 통한 도면 내 번호 인식
        print("\n4. 도면 내 번호 인식 (OCR)...")
        extractor = ImageExtractor(images_dir)
        all_numbered_regions = {}
        
        for img_info in saved_images:  # saved_images 사용
            img_path = img_info['file_path']
            print(f"   - {Path(img_path).name} 처리 중...")
            
            # 도면 번호 감지
            figure_info = extractor.detect_figure_number(img_path)
            if figure_info:
                print(f"     도면 번호: {figure_info.get('figure_number', 'N/A')}")
            
            # 번호 영역 찾기
            numbered_regions = extractor.find_numbered_regions(img_path)
            all_numbered_regions[img_path] = numbered_regions
            
            if numbered_regions:
                print(f"     발견된 번호: {len(numbered_regions)}개")
                numbers = [r['number'] for r in numbered_regions]
                print(f"     번호 목록: {', '.join(numbers[:10])}{'...' if len(numbers) > 10 else ''}")
        
        # 5. 어노테이션 적용
        print("\n5. 도면 어노테이션 적용...")
        annotator = ImageAnnotator(annotated_dir)
        annotated_count = 0
        
        for img_info in saved_images:  # saved_images 사용
            img_path = img_info['file_path']
            regions = all_numbered_regions.get(img_path, [])
            
            if regions and number_mappings:
                output_name = f"{Path(img_path).stem}_annotated.png"
                print(f"   - {output_name} 생성 중...")
                
                try:
                    annotated_path = annotator.annotate_image(
                        img_path,
                        regions,
                        number_mappings,
                        output_name
                    )
                    annotated_count += 1
                    print(f"     ✅ 저장됨: {annotated_path}")
                except Exception as e:
                    print(f"     ❌ 실패: {e}")
        
        # 6. 결과 요약
        print(f"\n{'='*60}")
        print("처리 결과 요약")
        print(f"{'='*60}")
        print(f"✅ 추출된 도면: {len(extracted_images)}개")
        print(f"✅ 번호-명칭 매핑: {len(number_mappings)}개")
        print(f"✅ 어노테이션 적용: {annotated_count}개")
        print(f"✅ 전체 처리 시간: {time.time() - start_time:.2f}초")
        print(f"✅ 출력 위치: {output_path.absolute()}")
        
        # JSON 결과 저장
        result_file = output_path / "test_result.json"
        result_data = {
            "pdf_file": pdf_path,
            "extracted_images": len(extracted_images),
            "number_mappings": len(number_mappings),
            "annotated_images": annotated_count,
            "processing_time": time.time() - start_time,
            "images": [
                {
                    "page": img.get('page', 0) + 1,
                    "path": str(img.get('file_path', 'N/A')),
                    "size": f"{img.get('width', 0)}x{img.get('height', 0)}",
                    "figure_number": img.get('figure_number', 'N/A')
                }
                for img in saved_images
            ]
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        print(f"\n📄 상세 결과가 {result_file}에 저장되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='PDF 처리 CLI 테스트 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python tests/test_pdf_cli.py sample.pdf
  python tests/test_pdf_cli.py sample.pdf --output my_test
  python tests/test_pdf_cli.py sample.pdf -o results --verbose
        """
    )
    
    parser.add_argument('pdf_file', help='처리할 PDF 파일 경로')
    parser.add_argument('-o', '--output', default='test_output',
                        help='출력 디렉토리 (기본값: test_output)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='상세 로그 출력')
    
    args = parser.parse_args()
    
    # PDF 파일 확인
    if not os.path.exists(args.pdf_file):
        print(f"❌ 파일을 찾을 수 없습니다: {args.pdf_file}")
        sys.exit(1)
    
    # 로깅 설정
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # 테스트 실행
    success = test_pdf_processing(args.pdf_file, args.output)
    
    # 종료 코드 반환
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()