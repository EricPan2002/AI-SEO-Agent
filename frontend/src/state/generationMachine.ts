/**
 * 生成流程的狀態機。
 *
 * ── 為什麼不用一堆 useState？────────────────────────────
 * 常見寫法會開六個獨立的 state：
 *   isLoading / step / outline / article / isPublishing / error
 * 六個獨立變數 = 2^6 種組合，但其中絕大多數是無意義的：
 *   · isLoading 和 error 同時為真時，畫面該顯示什麼？
 *   · isPublishing 為真但 article 是 null——正在發布一篇不存在的文章。
 * 這些矛盾狀態在型別上都是合法的，所以 bug 一定會從那裡長出來。
 *
 * ── 這裡的做法 ─────────────────────────────────────────
 * 用「判別式聯集」(discriminated union)：一個 phase 欄位決定現在在哪一格，
 * 而每一格各自帶著「那一格才會有」的資料。
 * 於是 TypeScript 會保證：只有進到 writing 之後才拿得到 outline、
 * 只有進到 preview 之後才拿得到 article。
 * 「發布一篇不存在的文章」變成編譯錯誤，而不是執行時的 bug。
 */

import type { Article, ErrorCode, Outline, PublishResult } from '../types'

/** 三個可能失敗的階段。用來決定「重試」要從哪裡重跑。 */
export type Stage = 'outline' | 'content' | 'publish'

export type GenerationState =
  | { phase: 'idle' }
  | { phase: 'planning' }
  | { phase: 'writing'; outline: Outline }
  | { phase: 'preview'; outline: Outline; article: Article }
  | { phase: 'publishing'; outline: Outline; article: Article }
  | {
      phase: 'published'
      outline: Outline
      article: Article
      post: PublishResult
    }
  | {
      phase: 'error'
      failedAt: Stage
      code: ErrorCode
      message: string
      // 失敗時把已經拿到的成果保留下來，這樣重試可以從失敗的那一步繼續，
      // 不必重跑前面的步驟（也就不用再燒一次 Gemini 額度）。
      outline?: Outline
      article?: Article
    }

export type GenerationAction =
  | { type: 'SUBMIT' }
  | { type: 'OUTLINE_OK'; outline: Outline }
  | { type: 'CONTENT_OK'; article: Article }
  | { type: 'PUBLISH_START' }
  | { type: 'PUBLISH_OK'; post: PublishResult }
  | { type: 'FAIL'; failedAt: Stage; code: ErrorCode; message: string }
  | { type: 'RETRY' }
  | { type: 'RESET' }

export const initialState: GenerationState = { phase: 'idle' }

/**
 * 所有狀態轉移都集中在這一個函式裡。
 *
 * 注意每個 case 都先檢查「目前在哪一格」才決定要不要轉移。
 * 不合法的轉移直接回傳原本的 state（等於忽略）。
 * 這道防線擋掉了「過期的回應晚一步回來，把新的狀態覆蓋掉」的情況。
 */
export function generationReducer(
  state: GenerationState,
  action: GenerationAction,
): GenerationState {
  switch (action.type) {
    case 'SUBMIT':
      // 從任何一格都可以重新送出（重來一次）
      return { phase: 'planning' }

    case 'OUTLINE_OK':
      if (state.phase !== 'planning') return state
      return { phase: 'writing', outline: action.outline }

    case 'CONTENT_OK':
      if (state.phase !== 'writing') return state
      return {
        phase: 'preview',
        outline: state.outline,
        article: action.article,
      }

    case 'PUBLISH_START':
      if (state.phase !== 'preview') return state
      return {
        phase: 'publishing',
        outline: state.outline,
        article: state.article,
      }

    case 'PUBLISH_OK':
      if (state.phase !== 'publishing') return state
      return {
        phase: 'published',
        outline: state.outline,
        article: state.article,
        post: action.post,
      }

    case 'FAIL':
      return {
        phase: 'error',
        failedAt: action.failedAt,
        code: action.code,
        message: action.message,
        // 'outline' in state 是 TypeScript 的型別守衛：
        // 只有帶著 outline 的那幾格才會通過，所以這裡取值是安全的。
        outline: 'outline' in state ? state.outline : undefined,
        article: 'article' in state ? state.article : undefined,
      }

    case 'RETRY': {
      if (state.phase !== 'error') return state
      switch (state.failedAt) {
        case 'outline':
          return { phase: 'planning' }
        case 'content':
          // 大綱還在手上就從 Step 2 重跑；不在的話只能整條重來
          return state.outline
            ? { phase: 'writing', outline: state.outline }
            : { phase: 'planning' }
        case 'publish':
          return state.outline && state.article
            ? {
                phase: 'publishing',
                outline: state.outline,
                article: state.article,
              }
            : initialState
      }
    }

    case 'RESET':
      return initialState
  }
}

// ─────────────────────────────────────────────────────────
// 衍生值 (selector)
//
// 這些全部由 state 「算出來」，而不是另外存成 state。
// 任何能被推導的東西都不該獨立存放——存了就要記得同步，遲早會忘。
// ─────────────────────────────────────────────────────────

export type StepStatus = 'pending' | 'running' | 'done' | 'failed'

export interface StepView {
  id: Stage
  label: string
  status: StepStatus
}

/** 給 StepTracker 用：兩個步驟各自現在是什麼狀態。 */
export function selectSteps(state: GenerationState): StepView[] {
  const outlineStatus = ((): StepStatus => {
    switch (state.phase) {
      case 'idle':
        return 'pending'
      case 'planning':
        return 'running'
      case 'error':
        return state.failedAt === 'outline' ? 'failed' : 'done'
      default:
        return 'done'
    }
  })()

  const contentStatus = ((): StepStatus => {
    switch (state.phase) {
      case 'idle':
      case 'planning':
        return 'pending'
      case 'writing':
        return 'running'
      case 'error':
        if (state.failedAt === 'outline') return 'pending'
        return state.failedAt === 'content' ? 'failed' : 'done'
      default:
        return 'done'
    }
  })()

  return [
    { id: 'outline', label: '規劃文章大綱', status: outlineStatus },
    { id: 'content', label: '撰寫 HTML 內文', status: contentStatus },
  ]
}

/** 是否正在等待某個 API——用來決定按鈕要不要變灰。 */
export function selectIsBusy(state: GenerationState): boolean {
  return (
    state.phase === 'planning' ||
    state.phase === 'writing' ||
    state.phase === 'publishing'
  )
}

/** 目前有沒有可以預覽的文章。 */
export function selectArticle(state: GenerationState): Article | undefined {
  return 'article' in state ? state.article : undefined
}

/** 整條流程是否已完成（兩個步驟都跑完）。 */
export function selectIsComplete(state: GenerationState): boolean {
  return (
    state.phase === 'preview' ||
    state.phase === 'publishing' ||
    state.phase === 'published'
  )
}
