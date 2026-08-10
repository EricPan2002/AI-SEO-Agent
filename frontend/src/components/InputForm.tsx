/**
 * 輸入表單：文章主題 + 多筆關鍵字。
 *
 * 關鍵字用「標籤」的方式輸入——打字後按 Enter 或逗號就變成一個標籤。
 * 比起用逗號分隔的單一文字框，使用者能清楚看到自己輸入了幾筆、可個別刪除。
 */

import { useState, type FormEvent, type KeyboardEvent } from 'react'

import type { GenerateInput } from '../types'

interface Props {
  disabled: boolean
  onSubmit: (input: GenerateInput) => void
}

interface FieldErrors {
  topic?: string
  keywords?: string
}

const MAX_KEYWORDS = 10

export function InputForm({ disabled, onSubmit }: Props) {
  const [topic, setTopic] = useState('')
  const [keywords, setKeywords] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})

  function addKeyword(raw: string): string[] {
    const value = raw.trim()
    // 空字串、重複、超過上限都不加
    if (!value || keywords.includes(value) || keywords.length >= MAX_KEYWORDS) {
      return keywords
    }
    const next = [...keywords, value]
    setKeywords(next)
    return next
  }

  function handleKeywordKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      // 在表單裡按 Enter 預設會送出表單，這裡要攔下來改成「新增標籤」
      event.preventDefault()
      addKeyword(draft)
      setDraft('')
      return
    }
    // 輸入框已清空時按倒退鍵，刪掉最後一個標籤——這是標籤輸入的慣例操作
    if (event.key === 'Backspace' && draft === '' && keywords.length > 0) {
      setKeywords(keywords.slice(0, -1))
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()

    // 使用者可能打完字沒按 Enter 就直接送出，這裡幫他補上
    const finalKeywords = draft.trim() ? addKeyword(draft) : keywords
    setDraft('')

    const nextErrors: FieldErrors = {}
    if (!topic.trim()) nextErrors.topic = '請輸入文章主題'
    if (finalKeywords.length === 0) nextErrors.keywords = '請至少輸入一個關鍵字'

    setErrors(nextErrors)
    // 有任何一項不通過就不送出。這是前端驗證——它的價值是「立刻」給回饋，
    // 不用等一趟網路來回。但真正的防線在後端，因為前端驗證可以被繞過。
    if (Object.keys(nextErrors).length > 0) return

    onSubmit({ topic: topic.trim(), keywords: finalKeywords })
  }

  return (
    <form className="card form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="topic">文章主題</label>
        <input
          id="topic"
          type="text"
          value={topic}
          disabled={disabled}
          placeholder="例如：居家手沖咖啡入門"
          maxLength={100}
          aria-invalid={Boolean(errors.topic)}
          onChange={(event) => {
            setTopic(event.target.value)
            if (errors.topic) setErrors({ ...errors, topic: undefined })
          }}
        />
        {errors.topic && <p className="field-error">{errors.topic}</p>}
      </div>

      <div className="field">
        <label htmlFor="keywords">
          關鍵字
          <span className="hint">
            按 Enter 或逗號新增（{keywords.length}/{MAX_KEYWORDS}）
          </span>
        </label>

        <div className={`tag-input ${errors.keywords ? 'has-error' : ''}`}>
          {keywords.map((keyword) => (
            <span className="tag" key={keyword}>
              {keyword}
              <button
                type="button"
                aria-label={`移除 ${keyword}`}
                disabled={disabled}
                onClick={() =>
                  setKeywords(keywords.filter((k) => k !== keyword))
                }
              >
                ×
              </button>
            </span>
          ))}
          <input
            id="keywords"
            type="text"
            value={draft}
            disabled={disabled || keywords.length >= MAX_KEYWORDS}
            placeholder={keywords.length === 0 ? '例如：手沖咖啡' : ''}
            onKeyDown={handleKeywordKeyDown}
            onChange={(event) => {
              setDraft(event.target.value)
              if (errors.keywords) setErrors({ ...errors, keywords: undefined })
            }}
          />
        </div>
        {errors.keywords && <p className="field-error">{errors.keywords}</p>}
      </div>

      {/* disabled 由父層傳進來的 state 推導，不另外開一個 state 來記 */}
      <button type="submit" className="btn btn-primary" disabled={disabled}>
        {disabled ? '生成中…' : '開始生成'}
      </button>
    </form>
  )
}
