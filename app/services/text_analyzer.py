import re
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TextAnalyzer:
    def __init__(self):
        # Patterns for extracting number-label mappings (부호의 설명 섹션)
        # Now supports alphanumeric patterns like 156a, 156b
        self.patterns = {
            'basic': r'(\d{1,4}[a-zA-Z]?)\s*[:：]\s*([가-힣\w\s]+)',
            'dash': r'(\d{1,4}[a-zA-Z]?)\s*[-－]\s*([가-힣\w\s]+)',
            'dots': r'(\d{1,4}[a-zA-Z]?)\s*[\.…]+\s*([가-힣\w\s]+)',
            'parenthesis': r'(\d{1,4}[a-zA-Z]?)\s*\)\s*([가-힣\w\s]+)',
            'korean_style': r'(\d{1,4}[a-zA-Z]?)\s*은\s+([가-힣\w\s]+)',
            'reference': r'참조\s*번호\s*(\d{1,4}[a-zA-Z]?)\s*[:：]?\s*([가-힣\w\s]+)',
            'symbol_list': r'<\s*(\d{1,4}[a-zA-Z]?)\s*>\s*([가-힣\w\s]+)',
            'bracket': r'\[\s*(\d{1,4}[a-zA-Z]?)\s*\]\s*([가-힣\w\s]+)',
            'comma_style': r'(\d{1,4}[a-zA-Z]?)\s*[,，]\s*([가-힣\w\s]+)',
            'space_only': r'^\s*(\d{1,4}[a-zA-Z]?)\s+([가-힣][가-힣\w\s]+)',
            'tab_style': r'(\d{1,4}[a-zA-Z]?)\t+([가-힣\w\s]+)'
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
        
        # Process text line by line for better detection
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Try each pattern on individual lines
            for pattern_name, pattern in self.patterns.items():
                matches = re.finditer(pattern, line)
                for match in matches:
                    number = match.group(1).strip()
                    label = match.group(2).strip()
                    
                    # Clean and validate label
                    label = self._clean_label(label)
                    
                    # Only accept short, component-like labels (not full sentences)
                    if label and 2 <= len(label) <= 30 and not self._is_sentence(label):
                        # Avoid overwriting with less specific labels
                        if number not in mappings or len(label) < len(mappings[number]):
                            mappings[number] = label
                            logger.debug(f"Found mapping via {pattern_name} (line): {number} -> {label}")
        
        # Also try patterns on cleaned full text for multi-line patterns
        text_cleaned = self._clean_text(text)
        for pattern_name, pattern in self.patterns.items():
            matches = re.finditer(pattern, text_cleaned, re.MULTILINE)
            for match in matches:
                number = match.group(1).strip()
                label = match.group(2).strip()
                
                # Clean and validate label
                label = self._clean_label(label)
                
                # Only accept short, component-like labels (not full sentences)
                if label and 2 <= len(label) <= 30 and not self._is_sentence(label):
                    # Avoid overwriting with less specific labels
                    if number not in mappings or len(label) < len(mappings[number]):
                        mappings[number] = label
                        logger.debug(f"Found mapping via {pattern_name} (full): {number} -> {label}")
        
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
        
        label = label.strip()
        
        # Exclude non-component labels
        excluded_labels = ['등록특허', '특허', '발명', '도면', '청구항', '명세서']
        if label in excluded_labels:
            return ''
        
        return label
    
    def _post_process_mappings(self, mappings: Dict[str, str]) -> Dict[str, str]:
        # Remove very short or very long labels
        filtered = {}
        for number, label in mappings.items():
            if 2 <= len(label) <= 35:
                filtered[number] = label
        
        # Try to fill in missing sequential numbers if we have patterns
        # For example, if we have 110, 130, 140, try to find 120
        # Also handle alphanumeric numbers like 156a, 156b
        numeric_keys = []
        for key in filtered.keys():
            # Extract numeric part only
            match = re.match(r'^(\d+)', key)
            if match:
                numeric_keys.append(int(match.group(1)))
        
        numbers = sorted(set(numeric_keys))
        if len(numbers) >= 2:
            # Find gaps in sequences
            for i in range(len(numbers) - 1):
                current = numbers[i]
                next_num = numbers[i + 1]
                
                # Check for regular intervals (e.g., 10, 100, etc.)
                diff = next_num - current
                if diff in [10, 100, 1]:
                    # Fill in missing numbers in this range
                    for missing in range(current + diff, next_num, diff):
                        missing_str = str(missing)
                        if missing_str not in filtered:
                            # Try to find this missing number in the original mappings
                            if missing_str in mappings:
                                filtered[missing_str] = mappings[missing_str]
                                logger.info(f"Recovered missing mapping: {missing_str} -> {mappings[missing_str]}")
        
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
        
        # Pattern for number ranges (e.g., "110~120", "110-120", "156a~156c")
        patterns = [
            r'(\d{1,3}[a-zA-Z]?)\s*[~～]\s*(\d{1,3}[a-zA-Z]?)',
            r'(\d{1,3}[a-zA-Z]?)\s*[-－]\s*(\d{1,3}[a-zA-Z]?)',
            r'(\d{1,3}[a-zA-Z]?)\s*부터\s*(\d{1,3}[a-zA-Z]?)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                start = match.group(1)
                end = match.group(2)
                
                # Validate range - extract numeric parts for comparison
                start_num_match = re.match(r'^(\d+)', start)
                end_num_match = re.match(r'^(\d+)', end)
                
                if start_num_match and end_num_match:
                    start_num = int(start_num_match.group(1))
                    end_num = int(end_num_match.group(1))
                    if start_num <= end_num:
                        ranges.append((start, end))
        
        return ranges