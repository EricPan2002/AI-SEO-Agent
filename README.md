# AI SEO 文章 Agent 自動化發布系統

輸入行銷主題與關鍵字，透過 **2 階段 AI Skill Pipeline** 自動完成大綱規劃與文章撰寫，
在前端即時呈現 Agent 執行進度與 HTML 預覽，最後一鍵發布為本機 WordPress 站台的草稿。

```
輸入主題 + 關鍵字
      ↓
[Step 1] 規劃文章大綱  ──►  Gemini（responseSchema 強制 JSON 結構）
      ↓
[Step 2] 撰寫 HTML 內文 ──►  Gemini（白名單過濾後輸出）
      ↓
   預覽文章
      ↓
發布到 WordPress（status: draft）
```

---

## 系統架構

```
┌──────────────────────────────────────┐
│  React SPA        localhost:5173     │
│                                       │
│  InputForm ──► useGeneration          │
│                 └─ useReducer 狀態機   │
│                     ├─ StepTracker    │
│                     ├─ PreviewCard    │
│                     └─ Toast          │
└───────────────┬──────────────────────┘
                │  HTTP + JSON
                │  （CORS 白名單只開在這一段）
┌───────────────▼──────────────────────┐
│  FastAPI          localhost:8000     │
│                                       │
│  POST /api/outline ─► OutlinePlanner  │──► Gemini
│  POST /api/content ─► ContentWriter   │──► Gemini
│  POST /api/publish ─► WordPressClient │
└───────────────┬──────────────────────┘
                │  Server-to-Server
                │  （不經瀏覽器，無 CORS 問題）
┌───────────────▼──────────────────────┐
│  WordPress        ai-seo.local       │
│  POST /wp-json/wp/v2/posts           │
│       { title, content, status }     │
└──────────────────────────────────────┘
```

## 技術選型

| 層 | 技術 | 選擇理由 |
|---|---|---|
| 前端 | React 19 + TypeScript + Vite | 題目限定 React 生態系；TypeScript 讓前後端資料結構有型別保證 |
| 狀態管理 | `useReducer` + 判別式聯集 | 單一狀態來源，讓矛盾狀態在型別層面就無法表達 |
| 後端 | Python FastAPI | Pydantic 可直接把 API 契約寫成型別並自動驗證 |
| LLM | Google Gemini `gemini-3.6-flash` | 支援 `responseSchema`，Step 1 的 JSON 由 API 層級強制保證 |
| HTML 淨化 | bleach | 白名單過濾 LLM 輸出，前端才能安全渲染 |
| WordPress | Local by Flywheel + Application Passwords | 題目指定；走 HTTP Basic Auth |

無資料庫（題目要求 No DB）。Step 1 的大綱由前端保管，於 Step 2 隨請求帶回後端。

---

## 本機啟動說明

### 前置需求

- Node.js 20+
- Python 3.12+
- [Local by Flywheel](https://localwp.com)
- [Gemini API Key](https://aistudio.google.com/apikey)

### 1. 架設 WordPress

1. 用 Local 建立站台，名稱 `ai-seo`（網址為 `http://ai-seo.local`），並啟動站台。

2. 開啟站台目錄下的 `app/public/wp-config.php`，在
   `/* That's all, stop editing! */` 之前加入：

   ```php
   define( 'WP_ENVIRONMENT_TYPE', 'local' );
   ```

   > WordPress 預設只在 HTTPS 站台顯示「應用程式密碼」功能。宣告環境類型為
   > `local` 可在維持 HTTP 的情況下啟用它，避免後端還要處理自簽憑證。

3. 進入 WP 後台 › **使用者 › 個人資料 › 應用程式密碼**，新增一組並複製產生的密碼
   （只會顯示一次）。

### 2. 啟動後端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env            # macOS / Linux: cp .env.example .env
# 編輯 .env，填入 GEMINI_API_KEY 與 WP_APP_PASSWORD

uvicorn app.main:app --reload --port 8000
```

- API 文件：http://localhost:8000/docs
- 健康檢查：http://localhost:8000/api/health （會一併回報 WordPress 連線狀態）

### 3. 啟動前端

```bash
cd frontend
npm install
npm run dev
```

開啟 http://localhost:5173

> 三個服務都要啟動：Local 的 WordPress 站台、後端（8000）、前端（5173）。
> WordPress 站台不會自動啟動，需先在 Local 中按下 Start。

---

## API

| Method | Path | 說明 |
|---|---|---|
| `POST` | `/api/outline` | Step 1：依主題與關鍵字產生大綱 JSON |
| `POST` | `/api/content` | Step 2：依大綱撰寫 HTML 文章 |
| `POST` | `/api/generate` | 一次跑完兩階段（整合測試用，前端不走這支） |
| `POST` | `/api/publish` | 寫入 WordPress，狀態為 `draft` |
| `GET`  | `/api/health` | 健康檢查 |

### 統一錯誤格式

所有端點失敗時都回傳相同形狀：

```jsonc
{
  "error": {
    "code": "WP_AUTH_FAILED",
    "message": "WordPress 認證失敗，請確認使用者名稱與應用程式密碼是否正確"
  }
}
```

| code | 情境 |
|---|---|
| `VALIDATION_ERROR` | 輸入不合法（空白主題、無有效關鍵字） |
| `LLM_UNAVAILABLE` | Gemini 叫不動：金鑰無效、額度用盡、逾時、上游 503 |
| `LLM_INVALID_JSON` | Gemini 回應無法解析或結構不完整 |
| `WP_UNREACHABLE` | WordPress 站台未啟動或未正常回應 |
| `WP_AUTH_FAILED` | 應用程式密碼錯誤 |
| `WP_REJECTED` | WordPress 拒絕該篇文章 |
| `INTERNAL_ERROR` | 未預期的伺服器錯誤 |

前端依 `code` 分流處理，不依賴訊息字串比對。

---

## 專案結構

```
backend/app/
├── main.py             FastAPI 進入點：CORS、例外處理器、路由
├── config.py           集中管理憑證與參數（從 .env 讀取）
├── deps.py             共用元件單例（共享 httpx 連線池）
├── schemas.py          API 契約（Pydantic）
├── errors.py           錯誤碼、自訂例外、三層全域例外處理器
├── schema_bridge.py    Pydantic 模型 → Gemini responseSchema
├── gemini.py           Gemini 客戶端：重試、指數退避、錯誤翻譯
├── sanitize.py         HTML 白名單過濾
├── wordpress.py        WordPress REST API 客戶端（Basic Auth）
└── skills/
    ├── base.py             Skill 抽象
    ├── outline_planner.py  Step 1
    ├── content_writer.py   Step 2
    └── pipeline.py         兩階段串接

frontend/src/
├── types.ts                    前後端契約的 TypeScript 版本
├── api/client.ts               所有 fetch 的唯一出入口
├── state/generationMachine.ts  狀態機：state / action / reducer / selector
├── hooks/useGeneration.ts      串接兩次呼叫、競態處理、重試
└── components/
    ├── InputForm.tsx       主題與多筆關鍵字輸入 + 前端驗證
    ├── StepTracker.tsx     Agent 執行進度
    ├── PreviewCard.tsx     HTML 預覽 + 發布
    └── Toast.tsx           錯誤提示 + 重試
```

---

## 設計決策

### 1. 前端用兩次 API 呼叫串接，而非單一請求

`/api/outline` 回來後，前端才把畫面切到 Step 2，再帶著大綱呼叫 `/api/content`。

**理由**：狀態轉移由真實的請求邊界驅動，進度是真的，不是用計時器模擬的。
若改成單一請求跑完兩階段，前端在整段等待期間無從得知後端進度。

**取捨**：更細緻的即時進度需要 SSE 讓後端主動推送事件。此處未採用，因為兩階段
各自產出完整的結構化物件，用請求邊界當轉移點語意最清楚，錯誤處理也可直接沿用
HTTP 狀態碼；SSE 連線一旦建立即為 200，之後的失敗需另外設計協定。

### 2. WordPress 由後端呼叫，不由前端直接呼叫

**憑證安全**：應用程式密碼等同帳號權限，放在前端等於公開。

**沒有 CORS 問題**：瀏覽器的同源政策只約束網頁發出的請求。後端對 WordPress 是
server-to-server，不經瀏覽器。若讓前端直接呼叫，WordPress 預設不會回應跨來源的
preflight，請求會被瀏覽器擋下（常見的錯誤解法是裝外掛全開 CORS，等同拆掉防線）。

CORS 只需設定在「前端 ↔ 本後端」這一段，並使用明確白名單而非 `*`。

### 3. Step 1 的 JSON 由 API 層級強制，而非在 prompt 裡要求

使用 Gemini 的 `responseSchema`，模型在生成時就被限制只能產出符合結構的內容，
不可能加開場白或 ` ```json ` 圍欄。

分工原則：**格式正確交給機制，內容品質才交給 prompt**（語氣、段落數、關鍵字分布）。

### 4. Gemini 的 schema 由 Pydantic 模型自動推導

`schema_bridge.py` 把 `Outline` 模型轉成 Gemini 的 `responseSchema`，因此
「後端期待的結構」與「要求模型產出的結構」是同一份定義，不可能不同步。

### 5. Step 2 的 HTML 採兩道防線

- **prompt**：明確列出允許的標籤與禁止事項，讓模型大多數時候直接寫對。
- **程式**：`sanitize.py` 以白名單過濾，剝除所有不允許的標籤與**全部屬性**。

只靠 prompt 等於沒有防線——prompt 是機率不是保證，而前端使用
`dangerouslySetInnerHTML` 渲染，LLM 輸出必須視為不可信輸入。

### 6. 發布時移除文章開頭的 `<h1>`

WordPress 將標題與內文分為兩個欄位，佈景主題會自行把標題渲染成 `<h1>`。
內文若再帶一個 `<h1>` 會導致標題重複顯示。

前端預覽保留 `<h1>`（那是一份獨立的 HTML 文件，題目也要求文章包含 `<h1>`），
僅在送往 WordPress 時移除——差異來自兩邊對「標題」的定義不同。

### 7. 前端用狀態機，而非多個獨立的 boolean

```ts
type GenerationState =
  | { phase: 'idle' }
  | { phase: 'planning' }
  | { phase: 'writing';    outline: Outline }
  | { phase: 'preview';    outline: Outline; article: Article }
  | { phase: 'publishing'; outline: Outline; article: Article }
  | { phase: 'published';  outline: Outline; article: Article; post: PublishResult }
  | { phase: 'error';      failedAt: Stage; code: ErrorCode; message: string; … }
```

用 `isLoading / step / outline / article / isPublishing / error` 六個獨立變數，
會產生大量無意義的組合（例如 `isPublishing` 為真但 `article` 為 null）。
判別式聯集讓 TypeScript 保證每一格只帶得到該格才有的資料。

按鈕的 disabled、步驟狀態等皆由 selector 從 state 推導，不另存 state——
能被算出來的值就不該獨立存放。

### 8. 競態處理

每次啟動流程遞增 `runId` 並建立新的 `AbortController`。回應返回時比對編號，
過期的回應直接丟棄。使用者連點或中途改輸入重送時，慢的請求不會覆蓋新的結果。

API 請求寫在事件處理器而非 `useEffect`，因此不受 React StrictMode 在開發模式下
重複執行 effect 的影響。

### 9. 錯誤處理

後端註冊三層全域例外處理器（自訂 `AppError`、輸入驗證錯誤、兜底的未預期錯誤），
使前端收到的錯誤永遠是同一種形狀。未預期錯誤的完整堆疊只記錄於伺服器端，
不回傳給前端。

前端將錯誤視為狀態機的一格（`phase: 'error'`），畫面其餘部分照常渲染，
只額外顯示 Toast——因此不會整站崩潰。重試會從失敗的那一步繼續，
例如 Step 2 失敗時大綱仍保留在 state 中，不需重新規劃大綱。
