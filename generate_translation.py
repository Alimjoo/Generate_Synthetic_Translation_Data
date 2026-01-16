from typing import Any, Dict, Iterable, List, Tuple

from generate_topic import HAPPY_API_HOST, MODEL, parse_json_from_text, stream_chat_completion


def normalize_translations(data: Any) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    raw = data
    if isinstance(data, dict):
        raw = data.get("translations") or data.get("data") or []
    if not isinstance(raw, list):
        return items
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        zh = str(entry.get("chinese", "")).strip()
        ug = str(entry.get("uyghur", "")).strip()
        if zh and ug:
            items.append({"chinese": zh, "uyghur": ug})
    return items


def build_translation_prompt(subtopic: str, count: int, length: int) -> str:
    return (
        "请生成用于训练的中-维吾尔语翻译数据，中文为原文，维吾尔语使用阿拉伯字母。\n"
        f"子话题: {subtopic}\n"
        f"生成数量: {count}\n"
        f"每条中文长度约 {length} 个字。\n"
        "仅返回JSON，不要输出额外说明。\n"
        '返回格式: {"translations": [{"chinese": "中文", "uyghur": "维吾尔语"}]}'
    )


def generate_translations(
    topic_rows: List[List[Any]],
    token: str,
    length: int,
) -> List[Dict[str, str]]:
    if not topic_rows:
        raise ValueError("没有子话题，请先生成子话题。")
    if length < 20 or length > 100:
        raise ValueError("翻译长度必须在 20 到 100 之间。")
    translations: List[Dict[str, str]] = []
    for _, _, items in generate_translations_stream(topic_rows, token, length):
        if items:
            translations.extend(items)
    return translations


def generate_translations_stream(
    topic_rows: List[List[Any]],
    token: str,
    length: int,
) -> Iterable[Tuple[int, int, List[Dict[str, str]]]]:
    if not topic_rows:
        raise ValueError("没有子话题，请先生成子话题。")
    if length < 20 or length > 100:
        raise ValueError("翻译长度必须在 20 到 100 之间。")
    total_rows = len(topic_rows)
    yield 0, total_rows, []
    for index, row in enumerate(topic_rows):
        items: List[Dict[str, str]] = []
        if not row or len(row) < 2:
            yield index + 1, total_rows, items
            continue
        subtopic = str(row[0]).strip()
        try:
            count = int(float(row[1]))
        except (ValueError, TypeError):
            count = 0
        if not subtopic or count <= 0:
            yield index + 1, total_rows, items
            continue
        prompt = build_translation_prompt(subtopic, count, length)
        response = stream_chat_completion(prompt, token, HAPPY_API_HOST, MODEL)
        parsed = parse_json_from_text(response)
        items = normalize_translations(parsed)
        yield index + 1, total_rows, items
