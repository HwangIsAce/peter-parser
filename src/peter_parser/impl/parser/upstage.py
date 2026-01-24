"""Upstage parser implementation (production)."""
import requests
import re
from typing import Union, Optional, List, Dict, Any
from io import BytesIO
from pydantic import BaseModel, Field

from peter_parser_core import BaseParser, ParsedDocument
from peter_parser_core.common.types import Page, Table, TableCell, Image, Element, ContentModel


class UpstageParser(BaseParser):
    """Upstage parser implementation."""
    
    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.upstage.ai/v1/document-digitization",
        default_ocr: str = "force",
        default_base64_encoding: str = "['table']",
        default_model: str = "document-parse",
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.default_ocr = default_ocr
        self.default_base64_encoding = default_base64_encoding
        self.default_model = default_model
            
    def _call_api(self, document: Union[str, bytes], options: dict) -> requests.Response:
        """Call Upstage API"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "ocr": options.get("ocr", self.default_ocr),
            "base64_encoding": options.get("base64_encoding", self.default_base64_encoding),
            "model": options.get("model", self.default_model),
        }
        
        if isinstance(document, str):
            with open(document, "rb") as f:
                files = {"document": f}
                response = requests.post(self.api_url, headers=headers, files=files, data=data)
        else:
            files = {"document": BytesIO(document)}
            response = requests.post(self.api_url, headers=headers, files=files, data=data)
        
        response.raise_for_status()
        return response

    
    def _extract_text_from_element(self, element: dict) -> str:
        """Extract text from element"""
        if "content" in element and isinstance(element["content"], dict):
            content = element["content"]

            text = content.get("text") or content.get("markdown") # text or markdown 우선
            if text:
                return text
            
            if content.get("html"): # HTML이 있으면
                html = content["html"]
                html = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n") # <br>을 줄바꿈으로, 나머지 태그 제거
                text = re.sub(r'<[^>]+>', '', html) # HTML 태그 제거
                text = re.sub(r'\s+', ' ', text).strip() # 공백 정리
                return text
        
        text = element.get("text") or element.get("content", "") # 그렇지 않으면 element에서 사용
        if isinstance(text, str):
            return text
        if isinstance(text, dict):
            return text.get("text") or text.get("content") or ""
        return str(text) if text else ""
    
    def _parse_table(self, element: dict) -> Table | None:
        """Parse table element"""
        cells = []
        for cell in element.get("cells", []):
            if isinstance(cell, dict):
                cells.append(TableCell(
                    row=cell.get("row", 0),
                    column=cell.get("column", 0),
                    content=cell.get("content", cell.get("text", "")),
                    row_span=cell.get("row_span", 1),
                    column_span=cell.get("column_span", 1),
                ))
        
        if not cells:
            return None
        
        return Table(
            table_index=element.get("table_index", 0),
            page_number=element.get("page_number", 1),
            rows=element.get("rows", 0),
            columns=element.get("columns", 0),
            cells=cells,
            bbox=element.get("bbox"),
        )
    
    def _parse_image(self, element: dict) -> Image | None:
        """Parse image element"""
        return Image(
            image_index=element.get("image_index", 0),
            page_number=element.get("page_number", 1),
            bbox=element.get("bbox"),
            base64=element.get("base64") or element.get("data"),
        )
    
    def _parse_element(self, element: dict) -> Element:
        """Parse element from API response to Element object."""
        element_id = element.get("id", 0)
        page_number = element.get("page_number") or element.get("page", 1)
        category = element.get("category") or element.get("type", "paragraph")
        text = self._extract_text_from_element(element)
        coordinates = element.get("coordinates")
        
        return Element(
            element_id=element_id,
            page_number=page_number,
            category=category,
            text=text,
            coordinates=coordinates,
            enrichment_metadata=None,  # Will be set during enrichment
            chunk_uuid=None,  # Will be set during chunking
        )
    
    def _convert_page(self, page_data: dict) -> Page:
        """Convert page data to Page object"""
        tables = [
            Table(
                table_index=t.get("table_index", 0),
                page_number=t.get("page_number", page_data.get("page_number", 1)),
                rows=t.get("rows", 0),
                columns=t.get("columns", 0),
                cells=[
                    TableCell(
                        row=c.get("row", 0),
                        column=c.get("column", 0),
                        content=c.get("content", ""),
                        row_span=c.get("row_span", 1),
                        column_span=c.get("column_span", 1),
                    )
                    for c in t.get("cells", [])
                    if isinstance(c, dict)
                ],
                bbox=t.get("bbox"),
            )
            for t in page_data.get("tables", [])
            if isinstance(t, dict)
        ]
        
        images = [
            Image(
                image_index=i.get("image_index", 0),
                page_number=i.get("page_number", page_data.get("page_number", 1)),
                bbox=i.get("bbox"),
                base64=i.get("base64"),
            )
            for i in page_data.get("images", [])
            if isinstance(i, dict)
        ]
        
        return Page(
            page_number=page_data.get("page_number", 1),
            text=page_data.get("text", ""),
            tables=tables,
            images=images,
            width=page_data.get("width"),
            height=page_data.get("height"),
        )
        
    def _build_pages_from_elements(self, elements: list) -> list[Page]:
        """Build pages from elements array"""
        if not elements:
            return []
        
        pages_dict = {}
        
        for element in elements:
            if not isinstance(element, dict):
                continue
            
            # page_number 또는 page 필드 사용
            page_num = element.get("page_number") or element.get("page", 1)
            if page_num not in pages_dict:
                pages_dict[page_num] = {
                    "text": [],
                    "tables": [],
                    "images": []
                }
            
            # 텍스트 추출
            text = self._extract_text_from_element(element)
            if text:
                pages_dict[page_num]["text"].append(text)
            
            # 테이블/이미지 처리
            element_type = element.get("category") or element.get("type")
            if element_type == "table":
                table = self._parse_table(element)
                if table:
                    pages_dict[page_num]["tables"].append(table)
            elif element_type in ["image", "figure"]:
                image = self._parse_image(element)
                if image:
                    pages_dict[page_num]["images"].append(image)
        
        # Page 객체 생성
        return [
            Page(
                page_number=page_num,
                text="\n".join(pages_dict[page_num]["text"]),
                tables=pages_dict[page_num]["tables"],
                images=pages_dict[page_num]["images"]
            )
            for page_num in sorted(pages_dict.keys())
        ]
        
    def _convert_response(self, api_response: dict) -> ParsedDocument:
        """Convert Upstage API JSON response to ParsedDocument."""
        # Upstage API v2.0: {"api": "2.0", "content": {"html": "..."}, "elements": [...]}
        elements_raw = api_response.get("elements", [])
        
        if elements_raw:
            # Parse elements
            elements = [
                self._parse_element(elem)
                for elem in elements_raw
                if isinstance(elem, dict)
            ]
            
            # Build pages from elements (기존 로직 유지)
            pages = self._build_pages_from_elements(elements_raw)
            
            # Extract content
            content_data = api_response.get("content", {})
            if isinstance(content_data, dict):
                content = ContentModel(
                    html=content_data.get("html"),
                    markdown=content_data.get("markdown"),
                    text=content_data.get("text"),
                    summary=None,  # Will be set during enrichment
                )
            else:
                content = ContentModel()
            
            metadata = {
                "api_version": api_response.get("api", "2.0"),
                "model": api_response.get("model"),
                "ocr": api_response.get("ocr"),
                "usage": api_response.get("usage", {}),
            }
            
            # Try to create ParsedDocument with new fields
            try:
                return ParsedDocument(
                    pages=pages,
                    elements=elements,
                    content=content,
                    metadata=metadata
                )
            except TypeError:
                # Fallback: if ParsedDocument doesn't support new fields yet
                return ParsedDocument(pages=pages, metadata=metadata)
        
        pages_data = api_response.get("pages", [])
        if pages_data:
            pages = [self._convert_page(page) for page in pages_data if isinstance(page, dict)]
            # Try with new fields, fallback if not supported
            try:
                return ParsedDocument(
                    pages=pages,
                    elements=[],
                    content=ContentModel(),
                    metadata=api_response.get("metadata", {})
                )
            except TypeError:
                return ParsedDocument(pages=pages, metadata=api_response.get("metadata", {}))
        
        # Empty document
        try:
            return ParsedDocument(
                pages=[],
                elements=[],
                content=ContentModel(),
                metadata=api_response
            )
        except TypeError:
            return ParsedDocument(pages=[], metadata=api_response)

    def parse(
        self,
        document: Union[str, bytes],
        **kwargs
    ) -> ParsedDocument:
        """Parse a document using the Upstage API"""
        # API 호출
        response = self._call_api(document, kwargs)
        result = response.json()
        
        # Upstage API v2.0 형식으로 변환
        return self._convert_response(result)