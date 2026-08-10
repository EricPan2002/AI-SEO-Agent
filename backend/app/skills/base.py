"""

每個 Skill 是無狀態的轉換——吃一個輸入、吐一個輸出，不持有任何跨請求資料。
所以同一個 Skill 實例可以同時服務多個請求，後端也能水平擴充。

要擴充成 3 階段（例如加一個「SEO 檢查」），只要再實作一個 Skill 掛進 pipeline，
既有的兩個 Skill 一行都不用改。這就是把工作流拆解成 Skill 的價值。
"""

from abc import ABC, abstractmethod


class Skill[TIn, TOut](ABC):
    #: 程式內部識別用
    name: str = "skill"
    #: 給前端顯示的步驟名稱
    label: str = ""

    @abstractmethod
    async def run(self, payload: TIn) -> TOut:
        """執行這個階段。失敗時丟 AppError，由上層的例外處理器轉成統一錯誤格式。"""
        raise NotImplementedError
