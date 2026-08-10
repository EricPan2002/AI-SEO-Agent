"""FastAPI 應用程式進入點：CORS、例外處理、路由。"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .deps import get_gemini_client, get_pipeline, get_wordpress_client
from .errors import register_error_handlers
from .schemas import (
    Article,
    ContentRequest,
    GenerateResponse,
    HealthResponse,
    Outline,
    OutlineRequest,
    PublishRequest,
    PublishResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("後端啟動 | 模型=%s | WordPress=%s", settings.gemini_model, settings.wp_base_url)
    yield
    # 關閉時把兩個 httpx 連線池收乾淨，避免留下未關閉的 socket
    await get_gemini_client().aclose()
    await get_wordpress_client().aclose()


app = FastAPI(
    title="AI SEO 文章 Agent",
    description="2 階段 AI Skill Pipeline：大綱規劃 → 內文生成 → 發布至 WordPress",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 只開在「前端 ↔ 本後端」這一段。
# 用明確的白名單而不是 "*"，因為 "*" 等於沒有限制。
# 後端呼叫 WordPress 是 server-to-server，不經瀏覽器，與 CORS 無關。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

register_error_handlers(app)


# ─────────────────────────────────────────────────────────
# 健康檢查
# ─────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse, tags=["系統"])
async def health() -> HealthResponse:
    """回報後端設定與 WordPress 連線狀態，方便排查是環境問題還是程式問題。"""
    try:
        wp_status = f"已連線（{await get_wordpress_client().whoami()}）"
    except Exception as exc:  # noqa: BLE001 - 健康檢查本身不該因為下游掛掉而失敗
        wp_status = f"無法連線：{exc}"
    return HealthResponse(model=settings.gemini_model, wordpress=wp_status)


# ─────────────────────────────────────────────────────────
# Skill Pipeline
# ─────────────────────────────────────────────────────────


@app.post("/api/outline", response_model=Outline, tags=["Pipeline"])
async def create_outline(request: OutlineRequest) -> Outline:
    """Step 1：依主題與關鍵字規劃大綱。

    回應會由前端保管，並在呼叫 /api/content 時原封不動帶回來——
    題目要求 No DB，所以後端不持有跨請求狀態。
    """
    return await get_pipeline().planner.run(request)


@app.post("/api/content", response_model=Article, tags=["Pipeline"])
async def create_content(request: ContentRequest) -> Article:
    """Step 2：依 Step 1 的大綱撰寫 HTML 文章。"""
    return await get_pipeline().writer.run(request)


@app.post("/api/generate", response_model=GenerateResponse, tags=["Pipeline"])
async def generate(request: OutlineRequest) -> GenerateResponse:
    """一次跑完兩階段。前端不走這支，主要供整合測試用（一行 curl 驗證整條後端流程）。"""
    outline, article = await get_pipeline().run(request)
    return GenerateResponse(outline=outline, article=article)


# ─────────────────────────────────────────────────────────
# 發布
# ─────────────────────────────────────────────────────────


@app.post("/api/publish", response_model=PublishResponse, tags=["WordPress"])
async def publish(request: PublishRequest) -> PublishResponse:
    """把文章寫入 WordPress，狀態預設為草稿。"""
    return await get_wordpress_client().create_post(
        title=request.title,
        html=request.html,
        status=request.status,
    )
