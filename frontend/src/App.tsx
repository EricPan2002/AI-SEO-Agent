import { InputForm } from './components/InputForm'
import { PreviewCard } from './components/PreviewCard'
import { StepTracker } from './components/StepTracker'
import { Toast } from './components/Toast'
import { useGeneration } from './hooks/useGeneration'
import {
  selectIsBusy,
  selectIsComplete,
  selectSteps,
} from './state/generationMachine'

export default function App() {
  const { state, generate, publish, retry, reset } = useGeneration()

  // 以下四個值全部是「算出來的」，不是額外存的 state。
  // 只要 state 變了它們就一定跟著對，不可能不同步。
  const steps = selectSteps(state)
  const isBusy = selectIsBusy(state)
  const isComplete = selectIsComplete(state)

  // TypeScript 的 in 型別守衛：只有帶著這些欄位的狀態才取得到值
  const outline = 'outline' in state ? state.outline : undefined
  const article = 'article' in state ? state.article : undefined
  const post = state.phase === 'published' ? state.post : undefined

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI SEO 文章 Agent</h1>
        <p>輸入主題與關鍵字，兩階段 Skill Pipeline 自動產出文章並發布為草稿</p>
      </header>

      <main className="layout">
        <section className="column">
          <InputForm disabled={isBusy} onSubmit={generate} />
          <StepTracker steps={steps} isComplete={isComplete} />

          {state.phase !== 'idle' && !isBusy && (
            <button type="button" className="btn btn-ghost" onClick={reset}>
              重新開始
            </button>
          )}
        </section>

        <section className="column column-wide">
          {outline && article ? (
            <PreviewCard
              outline={outline}
              article={article}
              isPublishing={state.phase === 'publishing'}
              post={post}
              onPublish={publish}
            />
          ) : (
            <div className="card placeholder">
              <p>
                {isBusy
                  ? '文章生成中，請稍候…'
                  : '生成完成後，文章預覽會顯示在這裡'}
              </p>
            </div>
          )}
        </section>
      </main>

      {/*
        錯誤只是狀態機的一格，不是特例。
        畫面其他部分照常渲染，只是多掛一個提示——這就是「不會整站 Crash」。
      */}
      {state.phase === 'error' && (
        <Toast
          code={state.code}
          message={state.message}
          onRetry={retry}
          onDismiss={reset}
        />
      )}
    </div>
  )
}
