本程式可自動抓取新聞並透過 Gemini AI 摘要後寫入 Google 試算表。

## 1. 環境準備
1. 安裝 [Python 3.10+](https://www.python.org/downloads/)。
2. 開啟終端機安裝套件：
   ```bash
   pip install -r requirements.txt
   ```

## 2. Google Cloud 設定 (關鍵步驟)
1. **啟用 API**：在 Google Cloud Console 建立專案，啟用 `Google Sheets API` 與 `Google Drive API`。
2. **取得金鑰**：建立「服務帳戶 (Service Account)」，下載 JSON 金鑰並改名為 `credentials.json`，放入本資料夾。
3. **授權試算表**：
   - 開啟 `credentials.json` 複製 `client_email` (通常結尾為 `@...iam.gserviceaccount.com`)。
   - 到你的 Google 試算表點擊「共用」，將權限開放給該 Email (設為編輯者)。

## 3. Gemini API 設定
前往 [Google AI Studio](https://aistudio.google.com/) 申請 API Key。

## 4. 執行程式
```bash
python news_gui.py
```
啟動後請在介面輸入：
1. **Google Sheet URL**: 你的試算表網址。
2. **Gemini API Key**: 剛剛申請的 AI 金鑰。
3. **關鍵字**: 想監控的新聞主題 (如: NVIDIA)。

## 常見問題
- **無法寫入試算表**：請確認是否已將試算表「共用」給 `credentials.json` 內的 Email。
- **API Error**：請確認 Google Cloud 專案已啟用 Sheets/Drive API。
