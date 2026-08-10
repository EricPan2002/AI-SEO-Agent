"""Gemini API 客戶端。

這一層只負責「把話送出去、把結果拿回來」，不含任何 SEO 業務邏輯。
業務邏輯（要問什麼、期待什麼結構）住在 skills/ 裡。

分層的好處：未來要換成 OpenAI 或 Claude，只要換掉這個檔案，
兩個 Skill 一行都不用改。
"""

import asyncio
import json
import logging
from typing import Any

import httpx

from .config import get_settings
from .errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

# 這些狀態碼代表「暫時性」失敗（塞車、限流、上游抖動），重試有機會成功。
# 401/400 這種是「你做錯了」，重試一百次也一樣，所以不列入。
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.gemini_model
        self._max_retries = settings.gemini_max_retries
        # 共用一個連線池，避免每次請求都重新握手。
        # 生命週期由 main.py 的 lifespan 管理。
        self._client = httpx.AsyncClient(
            base_url=API_ROOT,
            headers={"x-goog-api-key": settings.gemini_api_key},
            timeout=settings.gemini_timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── 對外的兩個方法 ────────────────────────────────

    async def generate_json(
        self,
        *,
        system_instruction: str,
        prompt: str,
        response_schema: dict[str, Any],
        temperature: float = 0.4,
        max_output_tokens: int = 4096,
    ) -> dict[str, Any]:
        """要求模型產出符合 response_schema 的 JSON。

        關鍵在 responseMimeType + responseSchema：這不是在 prompt 裡「拜託」模型
        回 JSON，而是 API 層級的強制約束——模型在生成時就被限制只能產出符合
        該結構的內容，物理上不可能加開場白或 ```json 圍欄。
        """
        raw = await self._generate(
            system_instruction=system_instruction,
            prompt=prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            # 理論上有 schema 就不該發生，但仍要處理——
            # 「理論上不會發生」的事情在正式環境總是會發生。
            logger.error("Gemini 回傳無法解析的 JSON: %.500s", raw)
            raise AppError(
                ErrorCode.LLM_INVALID_JSON,
                "AI 回傳的資料格式不正確，請重試",
                http_status=502,
            ) from exc

        if not isinstance(parsed, dict):
            raise AppError(
                ErrorCode.LLM_INVALID_JSON,
                "AI 回傳的資料結構不正確，請重試",
                http_status=502,
            )
        return parsed

    async def generate_text(
        self,
        *,
        system_instruction: str,
        prompt: str,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> str:
        """要求模型產出純文字（Step 2 用來產 HTML）。"""
        return await self._generate(
            system_instruction=system_instruction,
            prompt=prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    # ── 內部實作 ──────────────────────────────────────

    async def _generate(
        self,
        *,
        system_instruction: str,
        prompt: str,
        temperature: float,
        max_output_tokens: int,
        response_mime_type: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type
        if response_schema:
            generation_config["responseSchema"] = response_schema

        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }

        data = await self._post_with_retry(payload)
        return self._extract_text(data)

    async def _post_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        """遇到暫時性錯誤時重試，每次等待時間加倍（指數退避）。

        為什麼要退避而不是馬上重試？因為對方回 429/503 通常就是忙不過來，
        立刻重打只會讓情況更糟。
        """
        url = f"/models/{self._model}:generateContent"
        last_error: str = ""

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                last_error = f"請求逾時：{exc}"
            except httpx.RequestError as exc:
                last_error = f"無法連線至 Gemini：{exc}"
            else:
                if response.status_code == 200:
                    return response.json()

                last_error = self._describe_http_error(response)

                if response.status_code not in RETRYABLE_STATUS:
                    # 不可重試的錯誤（金鑰無效、模型名稱錯、請求格式錯）直接放棄
                    logger.error("Gemini 回應 %s：%s", response.status_code, last_error)
                    raise AppError(
                        ErrorCode.LLM_UNAVAILABLE, last_error, http_status=502
                    )

            if attempt < self._max_retries:
                backoff = 2**attempt  # 1 秒、2 秒、4 秒……
                logger.warning(
                    "Gemini 第 %s 次嘗試失敗（%s），%s 秒後重試",
                    attempt + 1,
                    last_error,
                    backoff,
                )
                await asyncio.sleep(backoff)

        raise AppError(
            ErrorCode.LLM_UNAVAILABLE,
            f"AI 服務暫時無法使用，請稍後再試（{last_error}）",
            http_status=503,
        )

    @staticmethod
    def _describe_http_error(response: httpx.Response) -> str:
        """把 Gemini 的錯誤回應翻成一句人看得懂的話。"""
        try:
            message = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            message = response.text[:200]

        if response.status_code in (401, 403):
            return "Gemini API 金鑰無效或權限不足"
        if response.status_code == 429:
            return "Gemini API 已達用量上限"
        if response.status_code == 404:
            return f"找不到模型（{message}）"
        return message or f"Gemini 回應 HTTP {response.status_code}"

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """從 Gemini 的回應結構中取出文字。

        Gemini 3 系列可能在 parts 裡夾帶思考過程（thought=true），
        那些不是給使用者看的內容，要濾掉。
        """
        candidates = data.get("candidates") or []
        if not candidates:
            # 通常是被安全設定攔截，回應裡沒有 candidates
            reason = data.get("promptFeedback", {}).get("blockReason", "未知原因")
            raise AppError(
                ErrorCode.LLM_UNAVAILABLE,
                f"AI 未產出內容（{reason}），請換個主題再試",
                http_status=502,
            )

        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(
            part["text"]
            for part in parts
            if isinstance(part.get("text"), str) and not part.get("thought")
        )

        if candidate.get("finishReason") == "MAX_TOKENS":
            raise AppError(
                ErrorCode.LLM_INVALID_JSON,
                "AI 產出的內容超過長度上限而被截斷，請縮短主題或減少關鍵字",
                http_status=502,
            )

        if not text.strip():
            raise AppError(
                ErrorCode.LLM_UNAVAILABLE, "AI 回傳了空白內容，請重試", http_status=502
            )

        return text
