"""兩階段 Skill Pipeline。

Pipeline 有兩種使用方式，對應題目的兩個不同要求：

  · 前端走 **拆開的兩支端點**（/api/outline → /api/content）。
    因為只有請求真的回來了，前端才能確定 Step 1 完成、可以把畫面切到 Step 2。
    這樣進度是真的，不是用計時器假裝的。

  · 這個 Pipeline 類別提供 **一次跑完** 的入口（/api/generate）。
    用途是整合測試：一行 curl 就能驗證整條後端流程，不必開前端。

兩者共用同一組 Skill 實例，所以不會有「兩條路走出不同結果」的問題。
"""

from ..gemini import GeminiClient
from ..schemas import Article, ContentRequest, Outline, OutlineRequest
from .base import Skill
from .content_writer import ContentWriter
from .outline_planner import OutlinePlanner


class ArticlePipeline:
    def __init__(self, client: GeminiClient) -> None:
        self.planner = OutlinePlanner(client)
        self.writer = ContentWriter(client)

    @property
    def steps(self) -> tuple[Skill, ...]:
        """依執行順序排列的階段，/api/health 會用它回報 pipeline 組成。"""
        return (self.planner, self.writer)

    async def run(self, request: OutlineRequest) -> tuple[Outline, Article]:
        """順序執行兩個階段，中間的資料只在記憶體傳遞（題目要求 No DB）。"""
        outline = await self.planner.run(request)

        # 階段之間的轉接：Step 1 的輸出 + 原始輸入，組成 Step 2 的輸入。
        # 這段就是前端在方案 A 裡做的事——把大綱帶回來再送出去。
        article = await self.writer.run(
            ContentRequest(
                topic=request.topic,
                keywords=request.keywords,
                outline=outline,
            )
        )
        return outline, article
