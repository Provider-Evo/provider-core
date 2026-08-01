from __future__ import annotations

"""fncall 解析器包。"""
from src.core.fncall.parsers.stream import FncallStreamParser
from src.core.fncall.parsers.xml_parser import parse_fncall, parse_fncall_xml

__all__ = ["FncallStreamParser", "parse_fncall", "parse_fncall_xml"]
