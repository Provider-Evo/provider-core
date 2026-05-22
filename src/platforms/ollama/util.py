"""Ollama 工具函数。"""

OLLAMA_MODELS = ["llama3", "llama3:70b", "mistral", "codellama", "phi3"]


def validate_model(model: str) -> bool:
    return model in OLLAMA_MODELS
