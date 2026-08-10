"""HTML 淨化：保證送到前端的內容一定是安全、乾淨的片段。

為什麼需要這一層？因為前端要用 dangerouslySetInnerHTML 渲染預覽，
而 LLM 的輸出本質上是「不可信輸入」——它可能被使用者輸入的內容影響
（prompt injection），也可能自己夾帶 Markdown 圍欄或多餘的外層標籤。

原則：prompt 負責「請你這樣寫」，程式負責「保證就是這樣」。
只靠 prompt 約束等於沒有防線，因為那是機率問題不是保證。
"""

import re

import bleach

# 白名單：只允許這些標籤，其餘一律剝掉（內容保留）。
# 用白名單而不是黑名單——黑名單永遠列不完，白名單只放進確定安全的。
ALLOWED_TAGS = {
    "h1",
    "h2",
    "h3",
    "p",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "blockquote",
    "br",
}

# 不允許任何屬性：沒有 style 就沒有 CSS 注入，沒有 href 就沒有惡意連結，
# 沒有 onclick 就沒有事件處理器。這篇文章的預覽不需要它們。
ALLOWED_ATTRIBUTES: dict[str, list[str]] = {}

# 模型有時仍會習慣性地用 ```html ... ``` 把輸出包起來
_CODE_FENCE = re.compile(r"^\s*```(?:html)?\s*|\s*```\s*$", re.IGNORECASE)

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

# 文章開頭的 <h1>…</h1>
_LEADING_H1 = re.compile(r"\A\s*<h1[^>]*>.*?</h1>\s*", re.IGNORECASE | re.DOTALL)


def sanitize_html(raw: str) -> str:
    """剝掉 Markdown 圍欄與所有不在白名單內的標籤。"""
    text = _CODE_FENCE.sub("", raw.strip())
    cleaned = bleach.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,  # 遇到不允許的標籤時剝掉標籤本身，但保留裡面的文字
    )
    return cleaned.strip()


def strip_leading_h1(html: str) -> str:
    """移除開頭的 <h1>，供發布到 WordPress 時使用。

    為什麼要拿掉？因為 WordPress 的資料模型把「標題」和「內文」分成兩個欄位，
    標題會由佈景主題自己渲染成 <h1>。我們如果連內文也帶一個 <h1>，
    後台和前台就會看到標題出現兩次。

    但前端預覽仍然保留 <h1>——那裡是一份獨立的 HTML 文件，需要自己的主標題，
    題目也要求產出的文章要包含 <h1>。
    所以差異不在「文章對不對」，而在「送去的地方對標題的定義不同」。
    """
    return _LEADING_H1.sub("", html, count=1).strip()


def count_words(html: str) -> int:
    """粗略統計字數。

    中文沒有空格分詞，所以直接數「非空白字元數」比數空格分隔的詞更有意義。
    這只是給使用者看的參考值，不需要精確。
    """
    text = _TAG.sub("", html)
    return len(_WHITESPACE.sub("", text))
