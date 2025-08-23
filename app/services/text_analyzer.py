import re
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TextAnalyzer:
    def __init__(self):
        # Patterns for extracting number-label mappings (부호의 설명 섹션)
        self.patterns = {
            'basic': r'(\d{1,3})\s*[:：]\s*([가-힣\w\s]+)',
            'dash': r'(\d{1,3})\s*[-－]\s*([가-힣\w\s]+)',
            'dots': r'(\d{1,3})\s*[\.…]+\s*([가-힣\w\s]+)',
            'parenthesis': r'(\d{1,3})\s*\)\s*([가-힣\w\s]+)',
            'korean_style': r'(\d{1,3})\s*은\s+([가-힣\w\s]+)',
            'reference': r'참조\s*번호\s*(\d{1,3})\s*[:：]?\s*([가-힣\w\s]+)',
            'symbol_list': r'<\s*(\d{1,3})\s*>\s*([가-힣\w\s]+)',
            'bracket': r'\[\s*(\d{1,3})\s*\]\s*([가-힣\w\s]+)'
        }
        
        # Keywords that indicate part/component listings
        self.part_list_keywords = [
            '부호의 설명',
            '도면 부호의 설명',
            '참조 부호의 설명',
            '부품 목록',
            '구성요소',
            '도면의 주요 부분',
            '도면부호',
            '참조번호',
            '도면 참조 부호',
            'Reference Numerals',
            'Parts List',
            'Component List'
        ]
        
    def extract_number_mappings(self, text: str) -> Dict[str, str]:
        mappings = {}
        
        # First, try to find dedicated part list section
        part_list_section = self._extract_part_list_section(text)
        
        if part_list_section:
            # Extract mappings from part list section (higher priority)
            mappings = self._extract_from_section(part_list_section)
            logger.info(f"Found {len(mappings)} mappings from part list section")
        
        # If not enough mappings found, search entire text
        if len(mappings) < 5:
            full_text_mappings = self._extract_from_section(text)
            # Merge, preferring part list mappings
            for num, label in full_text_mappings.items():
                if num not in mappings:
                    mappings[num] = label
        
        # Post-process mappings
        mappings = self._post_process_mappings(mappings)
        
        return mappings
    
    def _extract_part_list_section(self, text: str) -> str:
        """Extract the section that contains part/component listings"""
        for keyword in self.part_list_keywords:
            pattern = rf'{keyword}.*?(?=\n\n|\Z)'
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                section = text[match.start():]
                # Find the end of this section (usually ends with another heading or double newline)
                end_pattern = r'\n\s*\n\s*[가-힣\w\s]{2,20}\s*\n|발명의 상세한 설명|청구범위|도면의 간단한 설명'
                end_match = re.search(end_pattern, section)
                if end_match:
                    section = section[:end_match.start()]
                return section
        return ""
    
    def _extract_from_section(self, text: str) -> Dict[str, str]:
        """Extract number-label mappings from a text section"""
        mappings = {}
        
        # Clean text
        text = self._clean_text(text)
        
        # Try each pattern
        for pattern_name, pattern in self.patterns.items():
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                number = match.group(1).strip()
                label = match.group(2).strip()
                
                # Clean and validate label
                label = self._clean_label(label)
                
                # Only accept short, component-like labels (not full sentences)
                if label and 2 <= len(label) <= 20 and not self._is_sentence(label):
                    # Avoid overwriting with less specific labels
                    if number not in mappings or len(label) < len(mappings[number]):
                        mappings[number] = label
                        logger.debug(f"Found mapping via {pattern_name}: {number} -> {label}")
        
        return mappings
    
    def _is_sentence(self, text: str) -> bool:
        """Check if text is a sentence rather than a component name"""
        # Sentences typically have verbs, are longer, or end with periods
        sentence_indicators = [
            '이다', '있다', '되다', '하다', '한다', '된다',
            '이고', '있고', '되고', '하고',
            '으로', '에서', '에게', '부터', '까지',
            '.', '。'
        ]
        
        # Long text is likely a sentence
        if len(text) > 30:
            return True
        
        # Check for sentence patterns
        for indicator in sentence_indicators:
            if indicator in text:
                return True
        
        return False
    
    def find_figure_descriptions(self, text: str) -> Dict[str, Dict[str, str]]:
        figure_descriptions = {}
        
        # Patterns for figure descriptions
        figure_patterns = [
            r'\[도\s*(\d+)\](.*?)(?=\[도|\Z)',
            r'도\s*(\d+)\s*은(.*?)(?=도\s*\d+|$)',
            r'도면\s*(\d+)\s*[:：](.*?)(?=도면\s*\d+|$)',
            r'[Ff]ig(?:ure)?\s*(\d+)[\.:]?(.*?)(?=[Ff]ig|\Z)'
        ]
        
        for pattern in figure_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                fig_num = match.group(1)
                description = match.group(2).strip()
                
                if description:
                    # Extract number mappings from this figure's description
                    mappings = self.extract_number_mappings(description)
                    if mappings:
                        figure_descriptions[f"도 {fig_num}"] = mappings
        
        return figure_descriptions
    
    def _clean_text(self, text: str) -> str:
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and headers/footers
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
        
        return text
    
    def _clean_label(self, label: str) -> str:
        # Remove trailing punctuation
        label = re.sub(r'[,，.。;；、]+$', '', label)
        
        # Remove trailing numbers (often reference numbers)
        label = re.sub(r'\s*\d+$', '', label)
        
        # Remove line breaks and excessive spaces
        label = re.sub(r'\s+', ' ', label)
        
        # Limit length
        if len(label) > 50:
            label = label[:50]
        
        return label.strip()
    
    def _post_process_mappings(self, mappings: Dict[str, str]) -> Dict[str, str]:
        # Remove very short or very long labels
        filtered = {}
        for number, label in mappings.items():
            if 2 <= len(label) <= 30:
                filtered[number] = label
        
        return filtered
    
    def extract_component_hierarchy(self, text: str) -> Dict[str, List[str]]:
        hierarchy = {}
        
        # Pattern for hierarchical relationships (e.g., "100은 ... 110, 120을 포함")
        patterns = [
            r'(\d{1,3})\s*은.*?(\d{1,3})[,，]\s*(\d{1,3})',
            r'(\d{1,3})\s*는.*?(\d{1,3})[,，]\s*(\d{1,3})',
            r'(\d{1,3})\s*에\s*포함.*?(\d{1,3})[,，]\s*(\d{1,3})'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                parent = match.group(1)
                children = [g.strip() for g in match.groups()[1:] if g]
                
                if parent not in hierarchy:
                    hierarchy[parent] = []
                hierarchy[parent].extend(children)
        
        # Remove duplicates
        for parent in hierarchy:
            hierarchy[parent] = list(set(hierarchy[parent]))
        
        return hierarchy
    
    def find_number_ranges(self, text: str) -> List[Tuple[str, str]]:
        ranges = []
        
        # Pattern for number ranges (e.g., "110~120", "110-120")
        patterns = [
            r'(\d{1,3})\s*[~～]\s*(\d{1,3})',
            r'(\d{1,3})\s*[-－]\s*(\d{1,3})',
            r'(\d{1,3})\s*부터\s*(\d{1,3})'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                start = match.group(1)
                end = match.group(2)
                
                # Validate range
                if start.isdigit() and end.isdigit():
                    if int(start) < int(end):
                        ranges.append((start, end))
        
        return ranges