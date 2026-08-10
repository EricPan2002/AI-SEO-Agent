/**
 * 錯誤提示。
 *
 * 題目要求「前端能正確捕捉 Error 並以 Toast / Alert 提示使用者，避免全站 Crash」。
 * 關鍵在於：錯誤只是狀態機的一格（phase === 'error'），
 * 畫面照常渲染，只是多顯示這個提示——整個 app 不會白畫面。
 */

import type { ErrorCode } from '../types'

interface Props {
  code: ErrorCode
  message: string
  onRetry: () => void
  onDismiss: () => void
}

/**
 * 依錯誤碼給出「使用者能實際採取的行動」。
 *
 * 這就是為什麼後端要回 code 而不是只回訊息——有了機器可判讀的代號，
 * 前端才能針對不同錯誤給不同的排解建議。
 */
const HINT: Partial<Record<ErrorCode, string>> = {
  NETWORK_ERROR: '請確認後端服務已啟動（uvicorn app.main:app --port 8000）',
  LLM_UNAVAILABLE: 'AI 服務暫時繁忙，稍等幾秒後重試通常就會成功',
  LLM_INVALID_JSON: 'AI 這次的輸出格式異常，直接重試即可',
  WP_UNREACHABLE: '請確認 Local 的 WordPress 站台正在執行',
  WP_AUTH_FAILED: '請檢查後端 .env 中的 WP_USERNAME 與 WP_APP_PASSWORD',
  WP_REJECTED: 'WordPress 不接受這篇文章，請檢查標題與內容',
}

export function Toast({ code, message, onRetry, onDismiss }: Props) {
  return (
    <div className="toast" role="alert">
      <div className="toast-body">
        <div className="toast-head">
          <strong>發生錯誤</strong>
          <code className="toast-code">{code}</code>
        </div>
        <p className="toast-message">{message}</p>
        {HINT[code] && <p className="toast-hint">{HINT[code]}</p>}
      </div>

      <div className="toast-actions">
        <button type="button" className="btn btn-small" onClick={onRetry}>
          重試
        </button>
        <button
          type="button"
          className="btn btn-small btn-ghost"
          onClick={onDismiss}
        >
          關閉
        </button>
      </div>
    </div>
  )
}
