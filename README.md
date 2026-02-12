# AI News Helper

本專案可自動抓取新聞並透過 **Gemini AI** 摘要後寫入 Google 試算表。提供兩種實作方式，請依需求選擇：

---

## 選擇版本

| 版本 | 說明 | 適合情境 |
|------|------|----------|
| **[Google Apps Script 版](google_apps_script/)** | 在試算表內選單執行，只需 Gemini API Key，無需本機環境 | 不想裝 Python、不想設定服務帳戶，快速在試算表內使用 |
| **[Python GUI 版](python_gui/)** | 本機 Tkinter 介面，需 Google 服務帳戶 + 試算表 URL + Gemini API Key | 本機排程、多試算表、需要完整 GUI 與設定檔 |

兩版皆使用 **Gemini + Google Search** 抓新聞並寫入試算表，輸出欄位一致（標題、來源、發佈日期、連結、AI 摘要）。

---

### 想用試算表內直接執行？（推薦入門）

→ 請見 **[google_apps_script/README.md](google_apps_script/README.md)**：安裝教學、設定 API Key、使用方式。

---

### 想在本機用 Python 執行？

→ 請見 **python_gui/** 資料夾：內含 `news_gui.py`、`requirements.txt`、`settings.example.json`。  
需先完成 Google Cloud 服務帳戶與試算表共用設定，再執行 `python news_gui.py`（請在 `python_gui` 目錄下執行）。

---

## 目錄結構

```
├── README.md                 ← 本檔案（總說明，引導選擇版本）
├── python_gui/               ← Python 版
│   ├── news_gui.py
│   ├── requirements.txt
│   ├── settings.example.json
│   └── (settings.json、credentials.json 請勿上傳，已列入 .gitignore)
└── google_apps_script/       ← GAS 版
    ├── Code.gs
    ├── appsscript.json
    └── README.md             ← GAS 版安裝教學
```
