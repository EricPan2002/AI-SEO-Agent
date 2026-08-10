/**
 * Agent 狀態可視化：即時呈現後端 pipeline 跑到哪一步。
 *
 * 這個元件本身沒有任何 state——它只是把傳進來的 steps 畫出來。
 * 步驟的狀態全部由 generationMachine 的 selectSteps() 從 state 算出來，
 * 所以不可能出現「畫面顯示 Step 1 進行中，但實際上已經在跑 Step 2」的不同步。
 */

import type { StepStatus, StepView } from '../state/generationMachine'

interface Props {
  steps: StepView[]
  isComplete: boolean
}

const STATUS_ICON: Record<StepStatus, string> = {
  pending: '○',
  running: '◐',
  done: '✓',
  failed: '✕',
}

const STATUS_TEXT: Record<StepStatus, string> = {
  pending: '等待中',
  running: '進行中',
  done: '完成',
  failed: '失敗',
}

export function StepTracker({ steps, isComplete }: Props) {
  return (
    <div className="card tracker">
      <h2 className="card-title">Agent 執行進度</h2>

      <ol className="steps">
        {steps.map((step, index) => (
          <li key={step.id} className={`step step-${step.status}`}>
            <span className="step-icon" aria-hidden="true">
              {STATUS_ICON[step.status]}
            </span>
            <span className="step-body">
              <span className="step-label">
                [Step {index + 1}] {step.label}
                {step.status === 'running' && '…'}
              </span>
              <span className="step-status">{STATUS_TEXT[step.status]}</span>
            </span>
          </li>
        ))}

        <li className={`step ${isComplete ? 'step-done' : 'step-pending'}`}>
          <span className="step-icon" aria-hidden="true">
            {isComplete ? '✓' : '○'}
          </span>
          <span className="step-body">
            <span className="step-label">[完成]</span>
            <span className="step-status">
              {isComplete ? '文章已生成' : '等待中'}
            </span>
          </span>
        </li>
      </ol>
    </div>
  )
}
