/**
 * 把「狀態機」和「API 呼叫」接起來的 hook。
 *
 * 元件只會看到 state 和四個動作（generate / publish / retry / reset），
 * 完全不需要知道背後有幾支 API、順序是什麼。
 */

import { useCallback, useEffect, useReducer, useRef } from 'react'

import * as api from '../api/client'
import { ApiError, isAbortError } from '../api/client'
import {
  generationReducer,
  initialState,
  selectArticle,
  type Stage,
} from '../state/generationMachine'
import type { Article, GenerateInput, Outline } from '../types'

/** 把任何丟出來的東西統一成 ApiError，這樣後面取 code 永遠安全。 */
function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  return new ApiError(
    'INTERNAL_ERROR',
    error instanceof Error ? error.message : '發生未預期的錯誤',
    0,
  )
}

export function useGeneration() {
  const [state, dispatch] = useReducer(generationReducer, initialState)

  /**
   * 每次啟動新流程就 +1。回應回來時比對編號，不符代表這是「過期的回應」，
   * 直接丟棄不 dispatch。
   *
   * 為什麼需要？使用者連點兩次生成、或第一次還在跑就改主題重送時，
   * 會有兩條 async 鏈同時在飛。如果慢的那條後回來，就會把新的結果蓋掉。
   */
  const runIdRef = useRef(0)

  /** 真正去中止還在飛的 fetch，省下沒有意義的網路流量。 */
  const abortRef = useRef<AbortController | null>(null)

  /** 記住最後一次的輸入，讓「重試」不必要求使用者重打一遍。 */
  const lastInputRef = useRef<GenerateInput | null>(null)

  /** 開始一段新流程：中止舊的、拿新編號、給一個檢查是否過期的函式。 */
  const startRun = useCallback(() => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const runId = ++runIdRef.current
    return {
      signal: controller.signal,
      isStale: () => runId !== runIdRef.current,
    }
  }, [])

  const failWith = useCallback((stage: Stage, error: unknown) => {
    const apiError = toApiError(error)
    dispatch({
      type: 'FAIL',
      failedAt: stage,
      code: apiError.code,
      message: apiError.message,
    })
  }, [])

  // 元件被移除時（例如使用者離開頁面）中止還在飛的請求
  useEffect(() => () => abortRef.current?.abort(), [])

  // ── Step 2 單獨執行（generate 與 retry 共用）────────
  const writeContent = useCallback(
    async (
      input: GenerateInput,
      outline: Outline,
      run: { signal: AbortSignal; isStale: () => boolean },
    ) => {
      const article = await api.createContent({ ...input, outline }, run.signal)
      if (run.isStale()) return
      dispatch({ type: 'CONTENT_OK', article })
    },
    [],
  )

  // ── 發布（publish 與 retry 共用）────────────────────
  const runPublish = useCallback(
    async (article: Article) => {
      const run = startRun()
      try {
        const post = await api.publishArticle(article, run.signal)
        if (run.isStale()) return
        dispatch({ type: 'PUBLISH_OK', post })
      } catch (error) {
        if (run.isStale() || isAbortError(error)) return
        failWith('publish', error)
      }
    },
    [startRun, failWith],
  )

  // ── 對外的四個動作 ──────────────────────────────────

  /**
   * 完整跑一次 Step 1 → Step 2。
   *
   * 這裡就是「方案 A」的具體實作：兩次 await 之間 dispatch 一次，
   * 所以畫面切到 Step 2 的時機，是 Step 1 的請求「真的回來了」，
   * 不是用計時器假裝的。
   */
  const generate = useCallback(
    async (input: GenerateInput) => {
      lastInputRef.current = input
      const run = startRun()
      dispatch({ type: 'SUBMIT' })

      // 記錄目前跑到哪一步，失敗時才知道要標記哪個步驟為 failed
      let stage: Stage = 'outline'
      try {
        const outline = await api.createOutline(input, run.signal)
        if (run.isStale()) return
        dispatch({ type: 'OUTLINE_OK', outline })

        stage = 'content'
        await writeContent(input, outline, run)
      } catch (error) {
        if (run.isStale() || isAbortError(error)) return
        failWith(stage, error)
      }
    },
    [startRun, writeContent, failWith],
  )

  /** 發布目前預覽中的文章。 */
  const publish = useCallback(async () => {
    const article = selectArticle(state)
    if (!article) return
    dispatch({ type: 'PUBLISH_START' })
    await runPublish(article)
  }, [state, runPublish])

  /** 從失敗的那一步重跑，不必重來整條流程。 */
  const retry = useCallback(async () => {
    if (state.phase !== 'error') return
    const input = lastInputRef.current
    const { failedAt, outline, article } = state

    dispatch({ type: 'RETRY' })

    if (failedAt === 'publish' && article) {
      await runPublish(article)
      return
    }

    if (!input) return

    if (failedAt === 'content' && outline) {
      // 大綱還在手上，只要重跑 Step 2，不用再燒一次 Gemini 額度規劃大綱
      const run = startRun()
      try {
        await writeContent(input, outline, run)
      } catch (error) {
        if (run.isStale() || isAbortError(error)) return
        failWith('content', error)
      }
      return
    }

    await generate(input)
  }, [state, runPublish, startRun, writeContent, failWith, generate])

  /** 清空回到初始畫面。 */
  const reset = useCallback(() => {
    abortRef.current?.abort()
    runIdRef.current += 1 // 讓還在飛的回應變成過期，不會再影響畫面
    dispatch({ type: 'RESET' })
  }, [])

  return { state, generate, publish, retry, reset }
}
