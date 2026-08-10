"""共用元件的單例。

用 lru_cache 讓每個元件只被建立一次：
· GeminiClient / WordPressClient 內部各持有一個 httpx 連線池，
  每次請求都重建的話等於每次都要重新握手，浪費且沒必要。
· Skill 是無狀態的，本來就可以安全共用。
"""

from functools import lru_cache

from .gemini import GeminiClient
from .skills import ArticlePipeline
from .wordpress import WordPressClient


@lru_cache
def get_gemini_client() -> GeminiClient:
    return GeminiClient()


@lru_cache
def get_wordpress_client() -> WordPressClient:
    return WordPressClient()


@lru_cache
def get_pipeline() -> ArticlePipeline:
    return ArticlePipeline(get_gemini_client())
