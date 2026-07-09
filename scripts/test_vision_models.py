"""Probe vision / multimodal models for image description via /v1/chat/completions."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1337"
API_KEY = "sk-provider-v2"
AUTH_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}

PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
DATA_URL = f"data:image/png;base64,{PNG_B64}"
PROMPT = "请用一句话描述这张图片的颜色和内容。"
PER_MODEL_TIMEOUT = 75.0


def fetch_models() -> list[dict]:
    """公开方法 fetch_models。"""
    req = urllib.request.Request(f"{BASE}/v1/models", headers=AUTH_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("data") or []


def pick_candidates(models: list[dict]) -> list[str]:
    """公开方法 pick_candidates。"""
    ids = [m["id"] for m in models]
    by_id = {m["id"]: m for m in models}

    chosen: list[str] = []
    seen: set[str] = set()

    def add(model_id: str) -> None:
        """公开方法 add。"""
        if model_id in by_id and model_id not in seen:
            seen.add(model_id)
            chosen.append(model_id)

    # explicit vision flag
    for m in models:
        caps = m.get("capabilities") or {}
        if caps.get("vision") and caps.get("chat"):
            add(m["id"])

    # qwen multimodal / vl family used in WebUI
    keywords = ("vl", "vision", "omni")
    for m in models:
        caps = m.get("capabilities") or {}
        if not caps.get("chat"):
            continue
        name = m["id"].lower()
        if name.startswith("qwen") and any(k in name for k in keywords):
            add(m["id"])

    # a few common defaults
    for mid in (
        "qwen3.7-max",
        "qwen3-max",
        "qwen3.5-omni-flash",
        "qwen3-vl-plus",
        "glm-4.5-flash",
    ):
        add(mid)

    return chosen


def chat(model: str) -> tuple[str, str]:
    """公开方法 chat。"""
    body = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": DATA_URL}},
                ],
            }
        ],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=data,
        headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=PER_MODEL_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        text = (content or "").strip()
        if not text:
            return "empty", "(no content)"
        return "ok", text[:240]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:320]
        return "http_error", f"{exc.code}: {detail}"
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)[:320]


def main() -> int:
    """公开方法 main。"""
    models = fetch_models()
    candidates = pick_candidates(models)
    print(f"Testing {len(candidates)} vision/multimodal candidates...\n")

    ok_list: list[tuple[str, str, float]] = []
    fail_list: list[tuple[str, str, str, float]] = []

    for model in candidates:
        print(f"-> {model}", flush=True)
        t0 = time.time()
        status, detail = chat(model)
        elapsed = time.time() - t0
        if status == "ok":
            ok_list.append((model, detail, elapsed))
            print(f"   OK ({elapsed:.1f}s): {detail}\n", flush=True)
        else:
            fail_list.append((model, status, detail, elapsed))
            print(f"   FAIL [{status}] ({elapsed:.1f}s): {detail}\n", flush=True)

    print("=" * 72)
    print(f"能正常返回描述 ({len(ok_list)}):")
    for model, detail, elapsed in ok_list:
        print(f"  [OK {elapsed:.0f}s] {model}\n      {detail}")

    print(f"\n失败或空响应 ({len(fail_list)}):")
    for model, status, detail, elapsed in fail_list:
        short = detail.replace("\n", " ")
        print(f"  [{status} {elapsed:.0f}s] {model}: {short[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
