/**
 * 前後端契約的 TypeScript 版本。
 *
 * 這裡的每個型別都對應 backend/app/schemas.py 裡的同名 Pydantic 模型。
 * 兩邊型別對齊之後，後端改了欄位、前端這裡沒改，TypeScript 會在編譯時就報錯，
 * 而不是等到執行時畫面才出現 undefined。
 */

// ── Step 1 產出 ────────────────────────────────────
export interface OutlineSection {
  heading: string
  key_points: string[]
}

export interface Outline {
  title: string
  meta_description: string
  sections: OutlineSection[]
  keywords_used: string[]
}

// ── Step 2 產出 ────────────────────────────────────
export interface Article {
  title: string
  html: string
  word_count: number
}

// ── 發布結果 ───────────────────────────────────────
export interface PublishResult {
  id: number
  status: string
  link: string
  edit_link: string
}

// ── 使用者輸入 ─────────────────────────────────────
export interface GenerateInput {
  topic: string
  keywords: string[]
}

/**
 * 錯誤碼。前七個來自後端 errors.py，NETWORK_ERROR 是前端專用的
 * ——當後端根本連不上時（沒啟動、網路斷線），根本收不到後端的回應，
 * 所以這個代號只可能由前端產生。
 */
export type ErrorCode =
  | 'VALIDATION_ERROR'
  | 'LLM_UNAVAILABLE'
  | 'LLM_INVALID_JSON'
  | 'WP_UNREACHABLE'
  | 'WP_AUTH_FAILED'
  | 'WP_REJECTED'
  | 'INTERNAL_ERROR'
  | 'NETWORK_ERROR'
