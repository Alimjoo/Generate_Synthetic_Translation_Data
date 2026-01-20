import json
import os
from typing import Any, Dict, List

from generate_topic import generate_subtopics
from generate_translation import generate_translations_stream
from tqdm import tqdm

TOPICS_PATH = "topics.txt"
OUTPUT_DIR = "out_multiple"
PROGRESS_PATH = os.path.join(OUTPUT_DIR, "topic_progress.json")
SUBTOPIC_COUNT = 20
TRANSLATION_COUNT = 20
TRANSLATION_LENGTH = 50


def load_topics(path: str) -> List[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到主题文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_progress(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        value = int(data.get("next_index", 0))
        return max(value, 0)
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return 0


def save_progress(path: str, next_index: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"next_index": next_index}, f, ensure_ascii=False, indent=2)


def get_api_token() -> str:
    token = os.getenv("HAPPY_API_TOKEN")
    if token and token.strip():
        return token.strip()
    raise RuntimeError("未找到环境变量 HAPPY_API_TOKEN。")


def write_topic_json(index: int, payload: Dict[str, Any]) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"topic_{index:04d}.json"
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def process_topic(index: int, topic: str, token: str) -> str:
    subtopic_rows = generate_subtopics(
        topic, SUBTOPIC_COUNT, TRANSLATION_COUNT, token
    )
    subtopics_payload: List[Dict[str, Any]] = []
    total_translations = 0

    with tqdm(total=len(subtopic_rows), desc=f"子话题进度: {topic}", unit="topic") as bar:
        for current, total, items in generate_translations_stream(
            subtopic_rows, token, TRANSLATION_LENGTH
        ):
            if current == 0:
                continue
            subtopic_name = str(subtopic_rows[current - 1][0])
            subtopics_payload.append(
                {"subtopic": subtopic_name, "translations": items}
            )
            total_translations += len(items)
            bar.update(1)

    payload = {
        "topic": topic,
        "subtopic_count": len(subtopic_rows),
        "translation_length": TRANSLATION_LENGTH,
        "translation_total": total_translations,
        "subtopics": subtopics_payload,
    }
    return write_topic_json(index, payload)


def main() -> None:
    token = get_api_token()
    topics = load_topics(TOPICS_PATH)
    if not topics:
        print("topics.txt 为空，未生成。")
        return

    start_index = load_progress(PROGRESS_PATH)
    if start_index >= len(topics):
        print("已处理完所有主题。")
        return

    for index in range(start_index, len(topics)):
        topic = topics[index]
        print(f"处理主题 {index + 1}/{len(topics)}: {topic}")
        try:
            output_path = process_topic(index, topic, token)
        except Exception as exc:
            print(f"主题处理失败: {topic}，错误: {exc}")
            break
        save_progress(PROGRESS_PATH, index + 1)
        print(f"已保存: {output_path}")


if __name__ == "__main__":
    main()

