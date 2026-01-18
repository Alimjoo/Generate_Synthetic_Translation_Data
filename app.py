import json
import os
import tempfile
import uuid
from html import escape
from datetime import datetime
from typing import Dict, List, Tuple

import gradio as gr

from generate_topic import generate_subtopics as build_subtopics
from generate_translation import generate_translations_stream



def get_api_token(user_token: str) -> str:
    env_token = os.getenv("HAPPY_API_TOKEN")
    if env_token:
        return env_token
    if user_token and user_token.strip():
        return user_token.strip()
    raise gr.Error("未找到环境变量 HAPPY_API_TOKEN，请在页面填写。")


def handle_generate_subtopics(
    topic: str, subtopic_count: int, default_translation_count: int, user_token: str
) -> Tuple[List[List[str]], List[List[str]], None, str]:
    token = get_api_token(user_token)
    try:
        rows = build_subtopics(topic, int(subtopic_count), int(default_translation_count), token)
    except ValueError as exc:
        raise gr.Error(str(exc))
    return rows, render_translation_table([]), None, "翻译总数：0"


def handle_generate_translations(
    topic_rows: List[List[str]],
    user_token: str,
    translation_length: int,
):
    token = get_api_token(user_token)
    total_rows = len(topic_rows or [])
    progress_html = render_progress(0, total_rows)
    yield render_translation_table([]), None, "翻译总数：0", progress_html
    try:
        translations: List[Dict[str, str]] = []
        output_path = create_output_jsonl_path()
        for current, total, items in generate_translations_stream(
            topic_rows, token, int(translation_length)
        ):
            if items:
                translations.extend(items)
                append_output_jsonl_items(output_path, items)
            progress_html = render_progress(current, total)
            table_rows = [[t["chinese"], t["uyghur"]] for t in translations]
            total_text = f"翻译总数：{len(translations)}"
            yield render_translation_table(table_rows), None, total_text, progress_html
    except ValueError as exc:
        raise gr.Error(str(exc))

    if not translations:
        raise gr.Error("没有生成任何翻译，请检查数量设置后重试。")

    table_rows = [[t["chinese"], t["uyghur"]] for t in translations]
    jsonl_path = write_jsonl(translations)
    total = f"翻译总数：{len(translations)}"
    yield render_translation_table(table_rows), jsonl_path, total, render_progress(total_rows, total_rows)


def render_progress(current: int, total: int) -> str:
    safe_total = max(total, 1)
    percent = int((current / safe_total) * 100)
    return f"""
<div class="progress-shell">
  <div class="progress-meta">已处理 {current}/{total}</div>
  <div class="progress-track">
    <div class="progress-fill" style="width: {percent}%"></div>
  </div>
</div>
"""


def write_jsonl(translations: List[Dict[str, str]]) -> str:
    fd, path = tempfile.mkstemp(prefix="uyghur_translations_", suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for item in translations:
            line = json.dumps(
                {"chinese": item["chinese"], "uyghur": item["uyghur"]},
                ensure_ascii=False,
            )
            f.write(line + "\n")
    return path


def write_output_jsonl(translations: List[Dict[str, str]]) -> str:
    out_dir = os.path.join(os.getcwd(), "out")
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"uyghur_translations_{timestamp}_{uuid.uuid4().hex}.jsonl"
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        for item in translations:
            line = json.dumps(
                {"chinese": item["chinese"], "uyghur": item["uyghur"]},
                ensure_ascii=False,
            )
            f.write(line + "\n")
    return path


def create_output_jsonl_path() -> str:
    out_dir = os.path.join(os.getcwd(), "out")
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"uyghur_translations_{timestamp}_{uuid.uuid4().hex}.jsonl"
    return os.path.join(out_dir, filename)


def append_output_jsonl_items(path: str, items: List[Dict[str, str]]) -> None:
    if not items:
        return
    with open(path, "a", encoding="utf-8") as f:
        for item in items:
            line = json.dumps(
                {"chinese": item["chinese"], "uyghur": item["uyghur"]},
                ensure_ascii=False,
            )
            f.write(line + "\n")


def render_translation_table(rows: List[List[str]]) -> str:
    header = (
        "<table class=\"translation-table\">"
        "<thead><tr><th>中文</th><th>维吾尔语</th></tr></thead><tbody>"
    )
    body = "".join(
        f"<tr><td>{escape(chinese)}</td><td dir=\"rtl\">{escape(uyghur)}</td></tr>"
        for chinese, uyghur in rows
    )
    return f"{header}{body}</tbody></table>"


with gr.Blocks(
    title="维吾尔语翻译数据生成器"
) as demo:
    gr.Markdown(
        "根据大主题生成子话题，并批量生成中文↔维吾尔语翻译数据。"
    )
    with gr.Row():
        with gr.Column(scale=3):
            big_topic = gr.Textbox(
                label="大主题（中文）",
                placeholder="例如：新疆传统美食、现代交通、医疗等",
            )
            subtopic_count = gr.Slider(
                1,
                50,
                value=5,
                step=1,
                label="子话题数量（最多 50）",
            )
            default_translation_count = gr.Slider(
                1,
                50,
                value=5,
                step=1,
                label="每个子话题生成翻译数量",
            )
            translation_length = gr.Slider(
                20,
                100,
                value=40,
                step=1,
                label="每条源译文长度(只是大概, 不会定死)",
            )
        with gr.Column(scale=2):
            api_token = gr.Textbox(
                label="HAPPY_API_TOKEN",
                type="password",
                placeholder="粘贴 Token",
                elem_id="happy-api-token",
            )
            gen_subtopics_btn = gr.Button("生成子话题", variant="primary")
            gen_translations_btn = gr.Button("生成翻译数据", variant="secondary")
            total_text = gr.Markdown("翻译总数：0")

    subtopic_table = gr.Dataframe(
        headers=["子话题", "数量"],
        datatype=["str", "number"],
        row_count=(0, "fixed"),
        column_count=(2, "fixed"),
        type="array",
        label="子话题（可编辑子话题和数量）",
    )

    translation_table = gr.HTML(label="已生成翻译", elem_id="translation-table")
    progress_bar = gr.HTML(value=render_progress(0, 0))
    download_file = gr.File(label="下载 JSONL")

    gen_subtopics_btn.click(
        handle_generate_subtopics,
        inputs=[big_topic, subtopic_count, default_translation_count, api_token],
        outputs=[subtopic_table, translation_table, download_file, total_text],
    )

    gen_translations_btn.click(
        handle_generate_translations,
        inputs=[subtopic_table, api_token, translation_length],
        outputs=[translation_table, download_file, total_text, progress_bar],
        show_progress="full",
    )

js = """
(function () {
  const STORAGE_KEY = "happy_api_token";

  function findTokenInput() {
    const root = document.getElementById("happy-api-token");
    if (!root) return null;
    return root.querySelector("input, textarea");
  }

  function hydrate() {
    const input = findTokenInput();
    if (!input) return false;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && !input.value) {
      input.value = stored;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    input.addEventListener("input", () => {
      const value = input.value || "";
      if (value.trim()) {
        localStorage.setItem(STORAGE_KEY, value);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    });
    return true;
  }

  if (hydrate()) return;

  const observer = new MutationObserver(() => {
    if (hydrate()) {
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
"""

css="""
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic&display=swap');

#translation-table {
  overflow-x: hidden;
  width: 100%;
  max-height: 60vh;
  overflow-y: auto !important;
}

#translation-table .translation-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

#translation-table .translation-table th,
#translation-table .translation-table td {
  padding: 12px 14px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  vertical-align: top;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  width: 50%;
  max-width: 50%;
  user-select: text;
}

#translation-table .translation-table th {
  text-align: left;
  font-weight: 600;
  background: rgba(148, 163, 184, 0.08);
}

#translation-table .translation-table td:last-child,
#translation-table .translation-table th:last-child {
  font-family: 'Noto Sans Arabic', sans-serif;
  direction: rtl;
  text-align: right;
  unicode-bidi: plaintext;
}

#translation-table table th:nth-child(2),
#translation-table table td:nth-child(2) {
  font-family: 'Noto Sans Arabic', sans-serif !important;
  direction: rtl;
  text-align: right;
  unicode-bidi: plaintext;
}

.progress-shell {
  display: grid;
  gap: 6px;
}

.progress-meta {
  font-size: 13px;
  opacity: 0.85;
}

.progress-track {
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2dd4bf, #22c55e);
  transition: width 0.2s ease;
}
"""

demo.queue(default_concurrency_limit=4)
demo.launch(
    css=css,
    js=js,
    theme=gr.themes.Ocean(),
    # server_name="0.0.0.0", 
    # server_port=80
    )
