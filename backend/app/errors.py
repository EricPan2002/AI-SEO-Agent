"""統一錯誤格式。

不管哪裡出錯，前端收到的形狀永遠是：

    { "error": { "code": "WP_AUTH_FAILED", "message": "WordPress 認證失敗..." } }

code 是給機器看的穩定識別碼，前端依它決定要跳什麼提示、要不要顯示「重試」按鈕。
"""

import logging
from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    # 使用者輸入問題
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # LLM 相關
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"  # 叫不動：金鑰錯、額度用完、逾時、503
    LLM_INVALID_JSON = "LLM_INVALID_JSON"  # 叫得動但吐出來的東西不符結構

    # WordPress 相關
    WP_UNREACHABLE = "WP_UNREACHABLE"  # 連不上：站台沒開、網址錯
    WP_AUTH_FAILED = "WP_AUTH_FAILED"  # 連得上但認證失敗：應用程式密碼錯
    WP_REJECTED = "WP_REJECTED"  # 認證過了但 WordPress 不收這篇文章

    # 兜底
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """本專案所有預期內的錯誤都丟這個。

    帶著 code 與 http_status 一起丟，讓exception handler可以直接翻成統一格式的回應，
    路由層就不用寫一堆 try/except 去組回應。
    """

    def __init__(self, code: ErrorCode, message: str, http_status: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _error_response(code: ErrorCode, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": str(code), "message": message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    """把三種exception都收斂成同一種回應格式。

    有這三層，前端就不可能收到「非預期形狀」的錯誤，
    也就不會因為 response.error.code 讀不到而整個畫面掛掉。
    """

    @app.exception_handler(AppError)    #只要任何地方丟出AppError，就由這個function處理
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        # 預期內的錯誤：記 warning 就好，不需要完整堆疊
        logger.warning("AppError [%s] %s", exc.code, exc.message)
        return _error_response(exc.code, exc.message, exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI 預設的 422 格式又長又技術性，這裡翻成人看得懂的一句話
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        detail = first.get("msg", "輸入格式不正確")
        message = f"{field}：{detail}" if field else detail
        return _error_response(ErrorCode.VALIDATION_ERROR, message, 422)

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # 非預期錯誤：完整logger記在伺服器端，但不回傳給前端。
        logger.exception("Unhandled exception: %s", exc)
        return _error_response(
            ErrorCode.INTERNAL_ERROR, "伺服器發生未預期的錯誤，請稍後再試", 500
        )
