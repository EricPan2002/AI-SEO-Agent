# AI SEO 文章 Agent 自動化發布系統

輸入行銷主題與關鍵字，透過 **2 階段 AI Skill Pipeline** 自動完成大綱規劃與文章撰寫，
在前端即時呈現 Agent 執行進度與 HTML 預覽，最後一鍵發布為本機 WordPress 站台的草稿。

---

## 系統架構

```
┌──────────────────────────────┐
│  React SPA  (localhost:5173) │
│                              │
│  InputForm ─► 狀態機 (useReducer)
│                 ├─ StepTracker  即時顯示 Step 1 / Step 2
│                 ├─ PreviewCard  渲染 HTML 預覽
│                 └─ PublishButton
└──────────────┬───────────────┘
               │  HTTP + JSON（CORS 白名單只開在這一段）
┌──────────────▼───────────────┐
│  FastAPI  (localhost:8000)   │
│                              │
│  POST /api/outline  ─► Skill 1  OutlinePlanner ─► Gemini ─► JSON
│  POST /api/content  ─► Skill 2  ContentWriter  ─► Gemini ─► HTML
│  POST /api/publish  ─► WordPressClient
└──────────────┬───────────────┘
               │  Server-to-Server（不經瀏覽器，因此沒有 CORS 問題）
┌──────────────▼───────────────┐
│  WordPress  (ai-seo.local)   │
│  POST /wp-json/wp/v2/posts   │
│       { title, content, status: "draft" }
└──────────────────────────────┘
```

## 技術選型

| 層 | 技術 | 選擇理由 |
|---|---|---|
| 前端 | React 19 + TypeScript + Vite | 題目限定 React 生態系；TS 讓前後端資料結構有型別保證 |
| 後端 | Python FastAPI | Pydantic 可直接把 API 契約寫成型別並自動驗證 |
| LLM | Google Gemini (`gemini-3.6-flash`) | 支援 `responseSchema` 結構化輸出，Step 1 的 JSON 由 API 層級強制保證 |
| WordPress | Local by Flywheel + Application Passwords | 題目指定；走 HTTP Basic Auth |

---

## 本機啟動說明

### 前置需求

- Node.js 20+
- Python 3.11+
- [Local by Flywheel](https://localwp.com)
- [Gemini API Key](https://aistudio.google.com/apikey)

### 1. 架設 WordPress

1. 用 Local 建立站台，站台名稱 `ai-seo`（網址為 `http://ai-seo.local`）。
2. 開啟站台目錄下的 `app/public/wp-config.php`，在
   `/* That's all, stop editing! */` 之前加入一行：

   ```php
   define( 'WP_ENVIRONMENT_TYPE', 'local' );
   ```

   > WordPress 預設只在 HTTPS 站台顯示「應用程式密碼」。宣告環境類型為 `local`
   > 可在維持 HTTP 的情況下啟用該功能，避免後端還要處理自簽憑證。

3. 進入 WP 後台 › **使用者 › 個人資料 › 應用程式密碼**，新增一組並複製產生的密碼。

### 2. 啟動後端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # Windows: copy .env.example .env
# 編輯 .env，填入 GEMINI_API_KEY 與 WP_APP_PASSWORD

uvicorn app.main:app --reload --port 8000
```

API 文件：http://localhost:8000/docs

### 3. 啟動前端

```bash
cd frontend
npm install
npm run dev
```

開啟 http://localhost:5173

---

## API

| Method | Path | 說明 |
|---|---|---|
| `POST` | `/api/outline` | Skill 1：依主題與關鍵字產生大綱 JSON |
| `POST` | `/api/content` | Skill 2：依大綱撰寫 HTML 文章 |
| `POST` | `/api/publish` | 將文章寫入 WordPress，狀態為 `draft` |
| `GET`  | `/api/health` | 健康檢查 |

所有錯誤回應統一為：

```jsonc
{ "error": { "code": "WP_AUTH_FAILED", "message": "WordPress 認證失敗，請確認應用程式密碼" } }
```

前端依 `code` 分流處理，不依賴訊息字串比對。

---

## 設計決策

（實作完成後補上）
