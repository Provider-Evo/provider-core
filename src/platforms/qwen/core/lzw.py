"""LZW 压缩 + 自定义 base64 编码。

源于 Qwen 前端 ``lz-string`` JS 库的 Python 等价实现，
专门用于生成 ``ssxmod_itna`` / ``ssxmod_itna2`` Cookie 字段。

本模块为纯函数，无任何 I/O。LZW 是位级状态机算法，主流程
通过私有类 :class:`_LzwEncoder` 承载状态，对外仅暴露
:func:`lzw_compress` 与 :func:`custom_encode` 两个无副作用函数。
"""

from __future__ import annotations

from typing import Callable, Dict, List

from .endpoints import CUSTOM_BASE64_CHARS


class _LzwEncoder:
    """LZW 流式位写入编码器（内部实现，非公开 API）。

    Args:
        bits: 每个输出字符表示的位数。
        char_func: 索引到字符的映射函数。

    Notes:
        本类的状态机长度天然超过 50 行（位级算法不可避免地耦合），
        但已通过把 closure 提取为成员方法、把字典管理拆出 helper
        来控制最长方法 ``encode`` 在 50 行内。
    """

    def __init__(
        self, bits: int, char_func: Callable[[int], str]
    ) -> None:
        self._bits = bits
        self._char = char_func
        self._val = 0
        self._pos = 0
        self._out: List[str] = []
        # 字典与扩容状态
        self._dict: Dict[str, int] = {}
        self._to_create: Dict[str, bool] = {}
        self._dict_size = 3
        self._num_bits = 2
        self._enlarge_in = 2

    # ------------------------------------------------------------ 公开
    def encode(self, data: str) -> str:
        """对输入字符串执行 LZW 压缩，返回拼接后的字符序列。"""
        w = ""
        for ch in data:
            self._ensure_in_dict(ch)
            wc = w + ch
            if wc in self._dict:
                w = wc
                continue
            self._emit_word(w)
            self._dict[wc] = self._dict_size
            self._dict_size += 1
            w = ch
        if w:
            self._emit_word(w)
        # 结束标记 + flush
        self._write_bits(2, self._num_bits)
        self._flush_tail()
        return "".join(self._out)

    # ------------------------------------------------------------ 字典
    def _ensure_in_dict(self, ch: str) -> None:
        """新字符首次出现时登记到字典。"""
        if ch in self._dict:
            return
        self._dict[ch] = self._dict_size
        self._dict_size += 1
        self._to_create[ch] = True

    def _emit_word(self, w: str) -> None:
        """根据字典状态发出 ``w`` 的编码项，并维护扩容计数。"""
        if w in self._to_create:
            self._new_char(w[0], self._num_bits)
            del self._to_create[w]
        else:
            self._write_bits(self._dict[w], self._num_bits)
        self._tick_enlarge()

    def _tick_enlarge(self) -> None:
        """每写入一个码字，递减扩容计数；归零时位宽 +1。"""
        self._enlarge_in -= 1
        if self._enlarge_in == 0:
            self._enlarge_in = 2 ** self._num_bits
            self._num_bits += 1

    # ----------------------------------------------------------- 位输出
    def _write_bits(self, code: int, bit_count: int) -> None:
        """按位写入 ``bit_count`` 位 ``code``。"""
        for _ in range(bit_count):
            self._val = (self._val << 1) | (code & 1)
            self._advance_pos()
            code >>= 1

    def _write_zeros(self, count: int) -> None:
        """连续写入 ``count`` 个 0 位。"""
        for _ in range(count):
            self._val <<= 1
            self._advance_pos()

    def _new_char(self, ch: str, nb: int) -> None:
        """写入新字符项：8 位 ASCII 或 16 位 Unicode。"""
        cp = ord(ch)
        if cp < 256:
            self._write_zeros(nb)
            self._write_bits(cp, 8)
            return
        # Unicode：先写 nb 位的标记 (1 后面跟 nb-1 个 0)
        self._val = (self._val << 1) | 1
        self._advance_pos()
        if nb > 1:
            self._write_zeros(nb - 1)
        self._write_bits(cp, 16)

    def _advance_pos(self) -> None:
        """位指针前进；若填满一个字符则 flush 到输出。"""
        if self._pos == self._bits - 1:
            self._pos = 0
            self._out.append(self._char(self._val))
            self._val = 0
        else:
            self._pos += 1

    def _flush_tail(self) -> None:
        """结束时把剩余位左移补齐并输出最后一个字符。"""
        while True:
            self._val <<= 1
            if self._pos == self._bits - 1:
                self._out.append(self._char(self._val))
                return
            self._pos += 1


def lzw_compress(
    data: str,
    bits: int,
    char_func: Callable[[int], str],
) -> str:
    """执行 LZW 压缩。

    Args:
        data: 待压缩字符串。
        bits: 每个输出字符表示的位数（典型为 ``6``）。
        char_func: 索引（``0``..``2**bits-1``）到字符的映射函数。

    Returns:
        压缩后的字符串；输入为空时返回空串。
    """
    if not data:
        return ""
    return _LzwEncoder(bits, char_func).encode(data)


def custom_encode(data: str, url_safe: bool = True) -> str:
    """使用自定义字符集编码数据。

    Args:
        data: 待编码字符串。
        url_safe: 是否使用 URL 安全模式（不追加 ``=`` 填充）。

    Returns:
        编码后的字符串；输入为空时返回空串。
    """
    if not data:
        return ""
    cs = CUSTOM_BASE64_CHARS
    compressed = lzw_compress(data, 6, lambda idx: cs[idx])
    if url_safe:
        return compressed
    rem = len(compressed) % 4
    padding_map = {1: "===", 2: "==", 3: "="}
    return compressed + padding_map.get(rem, "")
