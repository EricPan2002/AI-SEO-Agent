/**
 * 後端 API 的唯一出入口。
 *
 * 所有 fetch 都集中在這裡，元件不直接碰網路。好處是：
 * 1. 錯誤處理只寫一次——不管哪支 API 失敗，都會丟出同一種 ApiError。
 * 2. 元件裡看到的是 createOutline(...) 這種有意義的名字，不是一坨 fetch 設定。
 */

import type {
  Article,
  ErrorCode,
  GenerateInput,
  Outline,
  PublishResult,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/**
 * 帶著錯誤碼的例外。
 *
 * 元件只要 catch 到 ApiError 就能拿到 code，據此決定要顯示什麼提示、
 * 要不要給「重試」按鈕，而不是去比對錯誤訊息的字串。
 */
export class ApiError extends Error {
  readonly code: ErrorCode
  readonly status: number

  constructor(code: ErrorCode, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

/** 使用者主動中止（例如重新送出）造成的取消，不是真的錯誤。 */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

async function post<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (error) {
    // fetch 只有在「連線層級」失敗時才會 reject：後端沒啟動、網路斷線、被 CORS 擋下。
    // 注意 HTTP 400/500 不會走到這裡——那些對 fetch 來說是「成功收到回應」。
    if (isAbortError(error)) throw error
    throw new ApiError(
      'NETWORK_ERROR',
      '無法連線至後端服務，請確認後端是否已在 http://localhost:8000 啟動',
      0,
    )
  }

  if (!response.ok) {
    // 後端保證錯誤形狀一律是 { error: { code, message } }，
    // 但仍用 catch(() => null) 兜底——萬一回的不是 JSON（例如 proxy 吐出的 HTML 錯誤頁），
    // 也不能讓解析失敗把整個流程炸掉。
    const payload = await response.json().catch(() => null)
    const detail = payload?.error
    throw new ApiError(
      detail?.code ?? 'INTERNAL_ERROR',
      detail?.message ?? `伺服器回應異常（HTTP ${response.status}）`,
      response.status,
    )
  }

  return (await response.json()) as T
}

// ── 三支端點 ───────────────────────────────────────

/** Step 1：規劃大綱。 */
export function createOutline(
  input: GenerateInput,
  signal?: AbortSignal,
): Promise<Outline> {
  return post<Outline>('/api/outline', input, signal)
}

/**
 * Step 2：依大綱撰寫內文。
 *
 * 注意 outline 是從前端帶回去的——後端不存資料（題目要求 No DB），
 * 所以 Step 1 的產出由前端保管，第二次呼叫時一起送出。
 */
export function createContent(
  input: GenerateInput & { outline: Outline },
  signal?: AbortSignal,
): Promise<Article> {
  return post<Article>('/api/content', input, signal)
}

/** 發布到 WordPress，狀態固定為草稿。 */
export function publishArticle(
  article: { title: string; html: string },
  signal?: AbortSignal,
): Promise<PublishResult> {
  return post<PublishResult>(
    '/api/publish',
    { title: article.title, html: article.html, status: 'draft' },
    signal,
  )
}
