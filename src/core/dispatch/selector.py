"""Selector → echotools AdaptiveSelector 别名 + 重导出。"""
from echotools.dispatch.selector import AdaptiveSelector as Selector
from echotools.dispatch.selector import TASRecord, TASWeights

__all__ = ["Selector", "TASRecord", "TASWeights"]
