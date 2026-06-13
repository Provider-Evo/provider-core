from __future__ import annotations

"""Ollama embedding 和 detect_capabilities 单元测试。"""

from unittest import mock

from src.platforms.ollama.core.client import detect_capabilities


class TestDetectCapabilitiesEmbedding:
    """detect_capabilities() embedding 检测测试。"""

    def test_default_no_embedding(self) -> None:
        """空详情时 embedding 为 False。"""
        caps = detect_capabilities(None)
        assert caps["chat"] is True
        assert caps["embedding"] is False

    def test_embedding_from_parameters(self) -> None:
        """parameters 字段包含 embedding 时检测为 True。"""
        detail = {"parameters": "This is an embedding model"}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_embedding_from_model_name_bge(self) -> None:
        """模型名称包含 bge 时检测为 embedding。"""
        detail = {"name": "bge-m3:latest", "parameters": ""}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_embedding_from_model_name_nomic(self) -> None:
        """模型名称包含 nomic 时检测为 embedding。"""
        detail = {"name": "nomic-embed-text:latest", "parameters": ""}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_embedding_from_model_name_text2vec(self) -> None:
        """模型名称包含 text2vec 时检测为 embedding。"""
        detail = {"name": "text2vec-large-chinese", "parameters": ""}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_embedding_from_model_name_e5(self) -> None:
        """模型名称包含 e5- 时检测为 embedding。"""
        detail = {"name": "e5-mistral-7b", "parameters": ""}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_embedding_from_model_name_gte(self) -> None:
        """模型名称包含 gte- 时检测为 embedding。"""
        detail = {"name": "gte-large:latest", "parameters": ""}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_embedding_from_model_name_sentence(self) -> None:
        """模型名称包含 sentence 时检测为 embedding。"""
        detail = {"name": "sentence-transformers/all-MiniLM", "parameters": ""}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_embedding_from_model_name_embed(self) -> None:
        """模型名称包含 embed 时检测为 embedding。"""
        detail = {"name": "mxbai-embed-large", "parameters": ""}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is True

    def test_no_embedding_regular_model(self) -> None:
        """普通聊天模型不检测为 embedding。"""
        detail = {"name": "llama3:8b", "parameters": "7B parameters"}
        caps = detect_capabilities(detail)
        assert caps["embedding"] is False

    def test_vision_from_model_info(self) -> None:
        """model_info 中包含 vision 关键词时检测为 vision。"""
        detail = {"model_info": {"general.projector_type": "clip"}}
        caps = detect_capabilities(detail)
        assert caps["vision"] is True

    def test_tools_from_template(self) -> None:
        """template 中包含 .Tools 时检测为 tools。"""
        detail = {"template": "{{ if .Tools }}...{{ end }}"}
        caps = detect_capabilities(detail)
        assert caps["tools"] is True


class TestVerifyServerUrlFormat:
    """_verify_server() URL 格式处理测试。"""

    def test_full_url_no_double_prefix(self) -> None:
        """完整 URL 不应添加重复 http:// 前缀。"""
        from src.platforms.ollama.core.client import _verify_server

        with mock.patch("requests.get") as mock_get:
            # 模拟连接失败，使函数在第一次 GET 时抛异常
            mock_get.side_effect = Exception("connection refused")

            result = _verify_server("http://192.168.1.100:11434")
            assert result is None
            # 验证请求的 URL 不包含 http://http://
            call_args = mock_get.call_args_list[0]
            assert "http://http://" not in call_args[0][0]
            # 应该直接使用传入的 URL
            assert call_args[0][0] == "http://192.168.1.100:11434"

    def test_full_url_trailing_slash_stripped(self) -> None:
        """完整 URL 应去除尾部斜杠。"""
        from src.platforms.ollama.core.client import _verify_server

        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("connection refused")

            _verify_server("http://192.168.1.100:11434/")
            call_args = mock_get.call_args_list[0]
            # 应去除尾部斜杠
            assert call_args[0][0] == "http://192.168.1.100:11434"

    def test_bare_ip_gets_http_prefix(self) -> None:
        """裸 IP:端口 应自动添加 http:// 前缀。"""
        from src.platforms.ollama.core.client import _verify_server

        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("connection refused")

            _verify_server("192.168.1.100:11434")
            call_args = mock_get.call_args_list[0]
            assert call_args[0][0] == "http://192.168.1.100:11434"

    def test_https_url_preserved(self) -> None:
        """https:// URL 应保持不变。"""
        from src.platforms.ollama.core.client import _verify_server

        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("connection refused")

            _verify_server("https://ollama.example.com")
            call_args = mock_get.call_args_list[0]
            assert call_args[0][0] == "https://ollama.example.com"


class TestConstantsEmbedding:
    """constants.py embedding 相关常量测试。"""

    def test_embed_path_defined(self) -> None:
        """EMBED_PATH 常量已定义。"""
        from src.platforms.ollama.core.constants import EMBED_PATH
        assert EMBED_PATH == "/api/embed"

    def test_caps_includes_embedding(self) -> None:
        """CAPS 中包含 embedding 声明。"""
        from src.platforms.ollama.core.constants import CAPS
        assert CAPS.get("embedding") is True


class TestAdapterEmbedding:
    """OllamaAdapter create_embedding 方法测试。"""

    def test_adapter_has_create_embedding(self) -> None:
        """OllamaAdapter 有 create_embedding 方法。"""
        from src.platforms.ollama.core.adaptercore import OllamaAdapter
        adapter = OllamaAdapter()
        assert hasattr(adapter, "create_embedding")
        assert callable(getattr(adapter, "create_embedding"))

    def test_adapter_embedding_uninitialized_raises(self) -> None:
        """未初始化时调用 create_embedding 应抛出 RuntimeError。"""
        import asyncio
        from src.platforms.ollama.core.adaptercore import OllamaAdapter

        adapter = OllamaAdapter()

        async def _call():
            return await adapter.create_embedding(None, "test", "model")

        with pytest.raises(RuntimeError):
            asyncio.run(_call())


import pytest
