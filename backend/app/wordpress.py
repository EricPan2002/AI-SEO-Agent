"""WordPress REST API 客戶端。

為什麼 WordPress 由後端呼叫，而不是前端直接打？

1. **憑證安全**：應用程式密碼等同帳號權限。放在前端等於公開——
   任何人打開瀏覽器開發者工具就看得到。放在後端的環境變數才安全。

2. **沒有 CORS 問題**：瀏覽器的同源政策只管「網頁發出的請求」。
   後端對 WordPress 是 server-to-server，不經過瀏覽器，因此完全沒有 CORS 這回事。
   若讓前端直接打，WordPress 預設不會回應跨來源的 preflight，請求會被瀏覽器擋下。
   （常見的錯誤解法是裝外掛把 CORS 全開，那等於把大門拆了。）

認證方式是 HTTP Basic Auth：把「使用者名稱:應用程式密碼」做 Base64 編碼，
放進 Authorization 標頭。所謂的「串接認證」實際上就只有這幾行。
"""

import base64
import logging
from typing import Any

import httpx

from .config import get_settings
from .errors import AppError, ErrorCode
from .schemas import PublishResponse

logger = logging.getLogger(__name__)


class WordPressClient:
    def __init__(self) -> None:
        settings = get_settings()
        # WordPress 產生的應用程式密碼帶空格（xxxx xxxx xxxx ...），
        # 有無空格它都收，但統一去掉可以避免使用者複製時多帶到空白造成困擾。
        password = settings.wp_app_password.replace(" ", "")
        credentials = f"{settings.wp_username}:{password}".encode()
        token = base64.b64encode(credentials).decode()

        self._site_url = settings.wp_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=settings.wp_api_base,
            headers={"Authorization": f"Basic {token}"},
            timeout=settings.wp_timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_post(
        self, *, title: str, html: str, status: str = "draft"
    ) -> PublishResponse:
        payload = {"title": title, "content": html, "status": status}
        data = await self._request("POST", "/posts", json=payload)

        post_id = data["id"]
        return PublishResponse(
            id=post_id,
            status=data.get("status", status),
            link=data.get("link", f"{self._site_url}/?p={post_id}"),
            # 草稿沒有前台網址可看，後台編輯連結才是 Demo 時真正要點的那個
            edit_link=f"{self._site_url}/wp-admin/post.php?post={post_id}&action=edit",
        )

    async def whoami(self) -> str:
        """健康檢查用：確認站台連得上且認證有效。"""
        data = await self._request("GET", "/users/me")
        return data.get("name", "unknown")

    # ── 內部實作 ──────────────────────────────────────

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise AppError(
                ErrorCode.WP_UNREACHABLE,
                "連線 WordPress 逾時，請確認站台是否正在執行",
                http_status=504,
            ) from exc
        except httpx.RequestError as exc:
            # 站台沒開、網址打錯、DNS 解不到都會走到這裡
            logger.error("無法連線 WordPress：%s", exc)
            raise AppError(
                ErrorCode.WP_UNREACHABLE,
                f"無法連線至 WordPress（{self._site_url}），請確認 Local 站台已啟動",
                http_status=503,
            ) from exc

        if response.status_code in (200, 201):
            return response.json()

        raise self._translate_error(response)

    def _translate_error(self, response: httpx.Response) -> AppError:
        """把 WordPress 的錯誤回應翻成我們自己的錯誤碼。

        前端只認得我們定義的 code，不需要知道 WordPress 內部的錯誤代號長什麼樣。
        這層轉譯讓「換掉 WordPress 改用別的 CMS」時，前端完全不用改。
        """
        try:
            body = response.json()
            wp_code = body.get("code", "")
            wp_message = body.get("message", "")
        except ValueError:
            wp_code, wp_message = "", response.text[:200]

        logger.error(
            "WordPress 回應 %s [%s] %s", response.status_code, wp_code, wp_message
        )

        if response.status_code in (401, 403):
            return AppError(
                ErrorCode.WP_AUTH_FAILED,
                "WordPress 認證失敗，請確認使用者名稱與應用程式密碼是否正確",
                http_status=502,
            )

        if response.status_code == 404:
            return AppError(
                ErrorCode.WP_UNREACHABLE,
                "找不到 WordPress REST API，請確認站台網址是否正確",
                http_status=502,
            )

        return AppError(
            ErrorCode.WP_REJECTED,
            f"WordPress 拒絕了這篇文章（{wp_message or response.status_code}）",
            http_status=502,
        )
