import json
import re
from typing import Any, List

import requests

HAPPY_API_HOST = "https://happyapi.org/v1"
MODEL = "gemini-3-pro"

MODELS = (
    "gemini-3-flash-preview",
    "gemini-3-fast",
    "gemini-2.5-pro-preview-06-05",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-pro-preview-03-25",
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-09-2025",
    "gemini-2.5-flash-lite",
)


def iter_model_fallbacks(primary: str) -> List[str]:
    ordered = [primary] + [m for m in MODELS if m != primary]
    seen = set()
    unique: List[str] = []
    for name in ordered:
        if name and name not in seen:
            seen.add(name)
            unique.append(name)
    return unique

def stream_chat_completion(
    instruction: str,
    token: str,
    host: str,
    model: str = MODEL,
    timeout: int = 300,
) -> str:
    url = host.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    last_error: Exception | None = None
    for candidate in iter_model_fallbacks(model):
        payload = {
            "model": candidate,
            "messages": [{"role": "user", "content": instruction}],
            "stream": True,
        }
        out_parts: List[str] = []
        try:
            with requests.post(
                url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=timeout,
            ) as r:
                r.raise_for_status()
                r.encoding = "utf-8"
                for line in r.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0] or {}).get("delta") or {}
                    content = delta.get("content")
                    if content:
                        out_parts.append(content)
            return "".join(out_parts)
        except requests.RequestException as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return ""


def parse_json_from_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None


def normalize_topics(data: Any) -> List[str]:
    if isinstance(data, dict):
        topics = data.get("topics") or data.get("topic") or []
        if isinstance(topics, str):
            return [topics]
        if isinstance(topics, list):
            return [str(t).strip() for t in topics if str(t).strip()]
        return []
    if isinstance(data, list):
        return [str(t).strip() for t in data if str(t).strip()]
    return []


def build_subtopic_prompt(topic: str, count: int) -> str:
    return (
        "请基于以下主题生成子话题，使用简体中文。\n"
        f"主题: {topic}\n"
        f"子话题数量: {count}\n"
        "仅返回JSON，不要输出额外说明。\n"
        '返回格式: {"topics": ["子话题1", "子话题2", "..."]}'
    )


def generate_subtopics(
    topic: str,
    subtopic_count: int,
    default_translation_count: int,
    token: str,
) -> List[List[str]]:
    if not topic or not topic.strip():
        raise ValueError("请输入中文大主题。")
    if subtopic_count < 1 or subtopic_count > 50:
        raise ValueError("子话题数量必须在 1 到 50 之间。")
    prompt = build_subtopic_prompt(topic.strip(), int(subtopic_count))
    response = stream_chat_completion(prompt, token, HAPPY_API_HOST, MODEL)
    parsed = parse_json_from_text(response)
    topics = normalize_topics(parsed)
    if not topics:
        raise ValueError("解析子话题失败，请重试。")
    return [[t, int(default_translation_count)] for t in topics]
