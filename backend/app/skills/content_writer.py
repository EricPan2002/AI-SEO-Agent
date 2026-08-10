"""Step 2：內文生成 (Content Writer)。

這一步要的是「合法 HTML」，而 HTML 沒有 responseSchema 這種 API 層級的保證機制，
所以採取兩道防線：

  第一道（prompt）：明確列出允許的標籤與禁止事項，讓模型大部分時候直接寫對。
  第二道（程式）：sanitize_html() 用白名單過濾，把漏網之魚剝掉。

只有第一道等於沒有防線——prompt 是機率，不是保證。
只有第二道則會讓輸出品質變差（模型亂寫、程式硬剝，結構會殘破）。
兩道一起才穩。
"""

from ..gemini import GeminiClient
from ..sanitize import ALLOWED_TAGS, count_words, sanitize_html
from ..schemas import Article, ContentRequest, Outline
from .base import Skill

_TAG_LIST = "、".join(f"<{tag}>" for tag in ["h1", "h2", "p", "ul", "li", "strong"])

SYSTEM_INSTRUCTION = f"""你是一位資深的中文內容寫手，擅長把大綱擴寫成可直接發布的部落格文章。

輸出格式規則（務必嚴格遵守）：
1. 只輸出 HTML 片段本身，不要有 <!DOCTYPE>、<html>、<head>、<body> 等外層標籤。
2. 不要使用 Markdown 語法，也不要用 ``` 把輸出包起來。
3. 可使用的標籤僅限：{_TAG_LIST}、<em>、<h3>、<ol>、<blockquote>。
4. 標籤不要加任何 style、class 或其他屬性。
5. 全篇只能有一個 <h1>，內容為文章主標題。

內容撰寫規則：
6. 每個段落小標用 <h2>，小標下的說明文字用 <p>，條列項目用 <ul><li>。
7. 每個 <h2> 段落至少要有 2 個 <p>，讓內容有厚度而不是只有條列。
8. 全篇至少使用一組 <ul>，把可條列的重點整理出來。
9. 自然融入指定關鍵字，不要生硬堆砌或重複塞入。
10. 全篇長度約 1000 至 1500 字。
11. 一律使用繁體中文（台灣用語），語氣專業但親切，適合部落格讀者。"""


class ContentWriter(Skill[ContentRequest, Article]):
    name = "content_writer"
    label = "撰寫 HTML 內文"

    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def run(self, payload: ContentRequest) -> Article:
        prompt = (
            f"主題：{payload.topic}\n"
            f"關鍵字：{'、'.join(payload.keywords)}\n\n"
            f"請依照以下大綱撰寫完整文章：\n\n{self._render_outline(payload.outline)}"
        )

        raw = await self._client.generate_text(
            system_instruction=SYSTEM_INSTRUCTION,
            prompt=prompt,
            # 溫度略高：這一步要的是流暢的文字，比 Step 1 需要更多變化
            temperature=0.7,
            max_output_tokens=8192,
        )

        html = sanitize_html(raw)
        return Article(
            title=payload.outline.title,
            html=html,
            word_count=count_words(html),
        )

    @staticmethod
    def _render_outline(outline: Outline) -> str:
        """把大綱轉成模型好讀的純文字。

        直接把 JSON 丟給模型也能動，但轉成條列式文字的效果更好——
        模型看到 JSON 容易「跟著格式走」而把文章也寫得像結構化資料。
        """
        lines = [f"文章標題：{outline.title}", f"SEO 描述：{outline.meta_description}", ""]
        for index, section in enumerate(outline.sections, start=1):
            lines.append(f"第 {index} 段小標：{section.heading}")
            for point in section.key_points:
                lines.append(f"  - {point}")
            lines.append("")
        return "\n".join(lines)


__all__ = ["ContentWriter", "ALLOWED_TAGS"]
