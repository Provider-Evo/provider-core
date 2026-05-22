"""Qwen 常量定义。"""

QWEN_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-turbo"

SUPPORTED_MODELS = [
    "qwen-turbo", "qwen-plus", "qwen-max",
    "qwen-max-longcontext", "qwen-vl-plus",
]

MODEL_CONTEXT_LENGTHS = {
    "qwen-turbo": 8192,
    "qwen-plus": 32768,
    "qwen-max": 8192,
    "qwen-max-longcontext": 32768,
}
