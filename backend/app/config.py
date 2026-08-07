"""集中管理所有外部憑證與可調參數。

憑證一律從 .env 讀取，不寫死在程式碼裡，理由有二：
1. .env 已被 .gitignore 排除，不會誤推上 GitHub。
2. 換環境（換一台 WordPress、換一把金鑰）只要改 .env，程式碼不用動。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目錄。用絕對路徑找 .env，這樣不管從哪個目錄啟動 uvicorn 都讀得到。
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Gemini ──────────────────────────────────
    gemini_api_key: str
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: float = 90.0
    # 遇到 429/503 這類「暫時性」錯誤時的重試次數
    gemini_max_retries: int = 2

    # ── WordPress ───────────────────────────────
    wp_base_url: str = "http://ai-seo.local"
    wp_username: str = "admin"
    wp_app_password: str
    wp_timeout_seconds: float = 20.0

    # ── CORS ────────────────────────────────────
    # 只允許前端開發伺服器來訪。不用 "*"，因為那等於把白名單拆掉。
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @property
    def wp_api_base(self) -> str:
        """WordPress REST API 的根路徑，順手去掉結尾多餘的斜線。"""
        return f"{self.wp_base_url.rstrip('/')}/wp-json/wp/v2"


@lru_cache
def get_settings() -> Settings:
    """快取設定物件，避免每次請求都重讀 .env。"""
    return Settings()
