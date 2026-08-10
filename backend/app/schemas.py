#用來定義 FastAPI 的 request/response schema。
"""

用 Pydantic 寫成型別後有三個好處：
1. FastAPI 會自動驗證 request，格式不對直接擋掉。
2. /docs 會自動生出可互動的 API 文件，前端不用問就知道要送什麼。
3. Step 1 的 Outline 同時也是丟給 Gemini 的 responseSchema 來源。

"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ─────────────────────────────────────────────────────────
# 共用：大綱結構（Step 1 的產出、Step 2 的輸入）
# ─────────────────────────────────────────────────────────


class OutlineSection(BaseModel):    #文章的一個段落

    heading: str = Field(description="段落小標，會成為文章中的 <h2>")
    key_points: list[str] = Field(description="這個段落要涵蓋的重點")


class Outline(BaseModel):   
    """Step 1 產出的完整大綱。

    這份物件會原封不動回給前端保管，再由前端於 Step 2 帶回來。
    """

    title: str = Field(description="文章主標題，會成為 <h1> 與 WordPress 文章標題")
    meta_description: str = Field(description="SEO 描述，約 80-120 字")
    sections: list[OutlineSection]
    keywords_used: list[str] = Field(description="實際被安排進大綱的關鍵字")


# ─────────────────────────────────────────────────────────
# Step 1：POST /api/outline
# ─────────────────────────────────────────────────────────


class OutlineRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100, description="文章主題")    #基本限制:主題1~100字
    keywords: list[str] = Field(min_length=1, max_length=10, description="目標關鍵字")  #基本限制:關鍵字1~10個

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, v: str) -> str:
        # 前端已經擋過空字串，但只有空白的字串（"   "）會通過 min_length=1，
        # 所以後端要再擋一次。前端驗證是體驗，後端驗證才是防線。
        cleaned = v.strip()     #去掉前後空白
        if not cleaned:
            raise ValueError("主題不可為空白")
        return cleaned

    @field_validator("keywords")
    @classmethod
    def _clean_keywords(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()      #建立一個紀錄哪些關鍵字已經被看過的空集合
        cleaned: list[str] = []     #建立一個空的list放整理好的結果
        for kw in v:
            k = kw.strip()
            if k and k not in seen:  # 如果k不是空的且還沒出現過
                seen.add(k)
                cleaned.append(k)
        if not cleaned:
            raise ValueError("至少需要一個有效的關鍵字")
        return cleaned


# Step 1 的回應直接就是 Outline，不另外包一層。


# ─────────────────────────────────────────────────────────
# Step 2：POST /api/content
# ─────────────────────────────────────────────────────────


class ContentRequest(BaseModel):
    #outline 欄位：Step 1 的產出由前端帶回來。

    topic: str = Field(min_length=1, max_length=100)
    keywords: list[str] = Field(min_length=1, max_length=10)
    outline: Outline


class Article(BaseModel):
    """Step 2 產出的完整文章。"""

    title: str
    html: str = Field(description="已通過白名單淨化的 HTML，前端可安全渲染")
    word_count: int


# ─────────────────────────────────────────────────────────
# 整條 pipeline 一次跑完：POST /api/generate
# 前端不走這支（走拆開的兩支才有真實進度），主要供整合測試使用。
# ─────────────────────────────────────────────────────────


class GenerateResponse(BaseModel):
    outline: Outline
    article: Article


# ─────────────────────────────────────────────────────────
# Step 3：POST /api/publish
# ─────────────────────────────────────────────────────────


class PublishRequest(BaseModel):
    title: str = Field(min_length=1)
    html: str = Field(min_length=1)
    # 題目要求預設 draft。開成 Literal 而非 str，是為了不讓前端傳進任意值。
    status: Literal["draft", "publish"] = "draft"


class PublishResponse(BaseModel):
    id: int
    status: str
    link: str = Field(description="文章前台網址")
    edit_link: str = Field(description="WordPress 後台編輯頁，Demo 時可直接點開")


# ─────────────────────────────────────────────────────────
# 健康檢查
# ─────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    model: str
    wordpress: str
