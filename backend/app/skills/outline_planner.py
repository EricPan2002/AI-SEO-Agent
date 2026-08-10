"""Step 1：大綱規劃 (Outline Planner)。

Prompt 的分工原則：
  · 「格式正確」交給 responseSchema —— API 層級強制，模型不可能加開場白或 ``` 圍欄。
  · 「內容品質」才交給 prompt 文字 —— 語氣、段落數、關鍵字分布、繁體中文。
"""

import logging

from pydantic import ValidationError

from ..errors import AppError, ErrorCode
from ..gemini import GeminiClient
from ..schema_bridge import to_gemini_schema
from ..schemas import Outline, OutlineRequest
from .base import Skill

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """你是一位專精中文內容行銷的資深 SEO 策略師。
你的任務是依據使用者提供的主題與關鍵字，規劃一篇部落格文章的大綱。

規劃原則：
1. 標題需自然包含主要關鍵字，長度 30 字以內，且要有讓人想點進來的誘因。
2. meta_description 控制在 80-120 字，帶入主要關鍵字，並清楚說明讀者能得到什麼。
3. 段落數量 4 到 6 段，依邏輯推進：先建立動機 → 再談具體做法 → 最後處理常見疑問。
4. 段落小標要具體，避免「簡介」「結論」「總結」這類空泛用詞。
5. 每段列出 2 到 4 個重點，寫「這段要涵蓋什麼」，不要寫成完整的文章句子。
6. 關鍵字自然分散到不同段落，不要全部塞在同一段。
7. 一律使用繁體中文。"""

# 由 Pydantic 模型自動推導，確保「後端期待的結構」與「要求模型產出的結構」是同一份定義
RESPONSE_SCHEMA = to_gemini_schema(Outline)


class OutlinePlanner(Skill[OutlineRequest, Outline]):
    name = "outline_planner"
    label = "規劃文章大綱"

    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def run(self, payload: OutlineRequest) -> Outline:
        prompt = (
            f"主題：{payload.topic}\n"
            f"關鍵字：{'、'.join(payload.keywords)}\n\n"
            "請為這個主題規劃一篇 SEO 部落格文章的大綱。"
        )

        raw = await self._client.generate_json(
            system_instruction=SYSTEM_INSTRUCTION,
            prompt=prompt,
            response_schema=RESPONSE_SCHEMA,
            # 溫度偏低：這一步要的是穩定的結構，不是創意發散
            temperature=0.4,
        )

        try:
            # schema 保證了「形狀」，這裡再用 Pydantic 驗一次「內容」
            # （欄位是否齊全、型別是否正確）。雙重保險，成本極低。
            return Outline.model_validate(raw)
        except ValidationError as exc:
            logger.error("大綱結構驗證失敗：%s\n原始輸出：%.500s", exc, raw)
            raise AppError(
                ErrorCode.LLM_INVALID_JSON,
                "AI 產出的大綱結構不完整，請重試",
                http_status=502,
            ) from exc
