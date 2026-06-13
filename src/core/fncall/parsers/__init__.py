# src/core/fncall/parsers/__init__.py
"""fncall 解析器包。"""

from src.core.fncall.parsers.xml_parser import parse_fncall, parse_fncall_xml
from src.core.fncall.parsers.stream import FncallStreamParser

__all__ = ["parse_fncall", "parse_fncall_xml", "FncallStreamParser"]
