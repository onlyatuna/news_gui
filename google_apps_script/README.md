# AI News Helper - Google Apps Script 版 (2026)

在 Google 試算表內直接執行：用 **Gemini API + Google Search** 抓取指定關鍵字的最新新聞，並寫入同一份試算表。無需本機 Python、無需 `credentials.json`，只需試算表與 Gemini API Key。

---

## 1. 前置需求

- Google 帳號
- [Google AI Studio](https://aistudio.google.com/app/apikey) 取得的 **Gemini API Key**（免費額度即可）

---

## 2. 安裝步驟

### 2.1 建立試算表並開啟 Apps Script

1. 新增一份 [Google 試算表](https://sheets.google.com)。
2. 選單：**擴充功能** → **Apps Script**。
3. 若出現「未命名專案」，可將專案命名為「AI News Helper」。

### 2.2 貼上程式碼

1. 在 Apps Script 編輯器中，刪除預設的 `function myFunction() { ... }`。
2. 將本資料夾中的 **`Code.gs`** 全部內容複製貼上並儲存（Ctrl+S）。

### 2.3 設定 API Key

任選一種方式：

- **方式 A（推薦）**  
  在試算表中：**AI 新聞** → **設定 API Key** → 貼上一或多個 Gemini API Key（**一行一個**，或逗號分隔）→ 確定。  
  多個 Key 會**輪替使用**，每個 Key 各自遵守 RPM 配額（2.5 Flash 每 Key 每分鐘 10 次），可提高每日可用次數。

- **方式 B**  
  Apps Script 左側：**專案設定**（齒輪）→ **指令碼內容** → **新增指令碼內容**：  
  - 單一 Key：屬性 `GEMINI_API_KEY`，值：你的 API Key。  
  - 多個 Key：屬性 `GEMINI_API_KEYS`，值：多行字串（一行一個 Key）。

### 2.4 首次授權

1. 回到試算表，重新整理頁面（F5）。
2. 選單會出現 **AI 新聞**。
3. 點選 **AI 新聞** → **執行新聞抓取**。
4. 若出現權限說明，點「檢閱權限」→ 選擇你的帳號 → 「允許」。

---

## 3. 使用方式

| 選單項目 | 說明 |
|---------|------|
| **執行新聞抓取** | 依目前關鍵字呼叫 Gemini（Google Search）抓新聞並寫入工作表 |
| **設定 API Key** | 設定一或多個 Gemini API Key（一行一個），多 Key 輪替並各自遵守配額 |
| **設定關鍵字** | 設定監控關鍵字（預設：NVIDIA） |

- 輸出會寫入名為 **「新聞」** 的工作表；若沒有該工作表，會寫入**第一個工作表**。
- 欄位：**標題、來源、發佈日期、連結、AI 摘要**。

---

## 4. 可選：用 Config 工作表設定關鍵字

若希望用試算表管理關鍵字，可新增一名為 **Config** 的工作表，前兩欄為：

| 設定項 | 值   |
|--------|------|
| KEYWORD | 台積電 |

程式會優先讀取此處的 **KEYWORD**，沒有 Config 或 KEYWORD 時才用選單設定的關鍵字。

---

## 5. 技術說明（2026 適用）

- **執行環境**：Google Apps Script（V8）。
- **Gemini**：`gemini-2.5-flash`，透過 REST `generateContent` 呼叫。
- **Google Search**：請求中加上 `tools: [{ "google_search": {} }]`，使用官方 [Grounding with Google Search](https://ai.google.dev/gemini-api/docs/grounding)。
- **輸出**：要求模型回傳 JSON 陣列，並以 `responseMimeType: "application/json"` 提高穩定性。
- **權限**：僅需目前試算表的讀寫與指令碼內容的讀寫，無需硬碟或其它試算表。
- **限頻**：每個 API Key 各自有「距上次使用至少 7 秒」的冷卻，符合 Gemini 2.5 Flash 單 Key RPM=10。多個 Key 會輪替使用，可提高總吞吐與 RPD。
- **配額參考**（供選模型與除錯用）：

| 模型名稱 | 每分鐘請求 (RPM) | 每日請求 (RPD) | 每分鐘 Token (TPM) | 備註 |
|----------|------------------|----------------|---------------------|------|
| Gemini 2.5 Pro | 5 | 100 | 250,000 | 適合複雜推理，配額最為稀缺 |
| **Gemini 2.5 Flash** | **10** | **250** | **250,000** | **本程式預設**，平衡性能與速率 |
| Gemini 2.5 Flash-Lite | 15 | 1,000 | 250,000 | 高吞吐量場景，RPD 較充裕 |
| Gemini 3 Pro (Preview) | 10–50* | 100+* | 250,000 | *依帳號權限與地區動態調整 |
| Gemini Embeddings | 100 | 1,000 | — | 向量嵌入專用 |

---

## 6. 常見問題

- **「請先設定 Gemini API Key」**  
  請用 **AI 新聞** → **設定 API Key** 或專案設定中的 `GEMINI_API_KEY` 設定金鑰。

- **API 錯誤 400 / 403 / 過期**  
  請到 [Google AI Studio](https://aistudio.google.com/app/apikey) 檢查 API Key 是否有效、未過期，必要時重新建立並在程式中更新。

- **「未取得任何新聞」**  
  可換關鍵字或稍後再試；若錯誤訊息提到配額或計費，請確認 AI Studio 專案與計費設定。

- **想改輸出工作表**  
  在 `Code.gs` 頂端 `CONFIG.OUTPUT_SHEET_NAME` 改成你要的工作表名稱即可。

---

## 7. 與 Python 版的差異

| 項目 | Python 版 (news_gui.py) | Apps Script 版 |
|------|-------------------------|----------------|
| 執行環境 | 本機 + credentials.json + 試算表 URL | 僅試算表內，無需本機與 JSON 金鑰 |
| 設定方式 | GUI 或 settings.json | 試算表選單 + 指令碼內容 / Config 工作表 |
| 試算表 | 需指定 Sheet URL + 服務帳戶共用 | 直接寫入「目前這份」試算表 |
| API | google-genai SDK | UrlFetchApp + REST generateContent |
| 適用情境 | 本機排程、多試算表 | 雲端、單一試算表、快速設定 |

兩版皆使用 **Gemini + Google Search** 抓新聞並寫入試算表，輸出欄位一致。
