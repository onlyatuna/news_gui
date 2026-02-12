/**
 * AI News Helper - Google Apps Script 版 (2026)
 * 使用 Gemini API + Google Search 抓取新聞並寫入本試算表。
 * 修正重點：維持 gemini-2.5-flash，但增加對 Google Search 回傳結構的相容性解析。
 */

// --- 全域設定（模型、試算表名稱、請求間隔等）---
const CONFIG = {
  /** 本程式使用 Gemini 2.5 Flash：RPM=10、RPD=250。改模型請同步查 README 配額表。 */
  GEMINI_MODEL: 'gemini-2.5-flash',
  GEMINI_BASE: 'https://generativelanguage.googleapis.com/v1beta/models',
  DEFAULT_KEYWORD: 'NVIDIA',
  OUTPUT_SHEET_NAME: '新聞',
  CONFIG_SHEET_NAME: 'Config',
  /** HTTP 請求逾時（秒） */
  REQUEST_TIMEOUT: 120,
  /** 兩次執行之間最少間隔（秒）。2.5 Flash RPM=10 → 至少 6s；設 7 與 Python 版一致。 */
  MIN_REQUEST_INTERVAL: 7
};

// --- 選單：試算表開啟時建立「AI 新聞」選單 ---
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('AI 新聞')
    .addItem('執行新聞抓取', 'runNewsFetch')
    .addSeparator()
    .addItem('設定 API Key', 'showSetApiKeyDialog')
    .addItem('設定關鍵字', 'showSetKeywordDialog')
    .addToUi();
}

// 從 Script Properties 讀取 API Key 陣列（支援 GEMINI_API_KEYS 多個 / 舊版 GEMINI_API_KEY 單一）
function getApiKeysArray(props) {
  var raw = props.getProperty('GEMINI_API_KEYS');
  if (raw) {
    return raw.split(/[\n,]/).map(function (s) { return s.trim(); }).filter(function (s) { return s.length > 0; });
  }
  var single = props.getProperty('GEMINI_API_KEY');
  if (single && single.trim()) return [single.trim()];
  return [];
}

// 取得執行設定：API Key 陣列 + 關鍵字（關鍵字優先讀 Config 工作表，否則 Properties）
function getConfig() {
  const props = PropertiesService.getScriptProperties();
  const apiKeys = getApiKeysArray(props);
  let keyword = props.getProperty('KEYWORD') || CONFIG.DEFAULT_KEYWORD;

  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const configSheet = ss.getSheetByName(CONFIG.CONFIG_SHEET_NAME);
    if (configSheet && configSheet.getLastRow() >= 1) {
      const data = configSheet.getDataRange().getValues();
      for (let i = 0; i < data.length; i++) {
        if (String(data[i][0]).trim().toUpperCase() === 'KEYWORD' && data[i][1]) {
          keyword = String(data[i][1]).trim();
          break;
        }
      }
    }
  } catch (e) {}

  return { apiKeys: apiKeys, keyword: keyword };
}

// 主流程：檢查 Key → 選 Key（冷卻最久）→ 呼叫 API → 解析 → 寫入試算表
function runNewsFetch() {
  const ui = SpreadsheetApp.getUi();
  const { apiKeys, keyword } = getConfig();

  if (!apiKeys || apiKeys.length === 0) {
    ui.alert('請先設定 Gemini API Key', '請使用選單「AI 新聞」→「設定 API Key」（可輸入多個，一行一個）。', ui.ButtonSet.OK);
    return;
  }

  ui.alert('開始執行', '正在透過 ' + CONFIG.GEMINI_MODEL + ' (Google Search) 抓取「' + keyword + '」相關新聞，共 ' + apiKeys.length + ' 個 Key 可用，請稍候…', ui.ButtonSet.OK);

  var props = PropertiesService.getScriptProperties();
  var now = Date.now();

  // 挑選「距上次使用最久」的 Key，符合每個 Key 的 RPM 配額
  var bestIdx = 0;
  var bestElapsed = -1;
  for (var i = 0; i < apiKeys.length; i++) {
    var last = parseInt(props.getProperty('LAST_KEY_' + i + '_MS') || '0', 10);
    var elapsedSec = last === 0 ? 999999 : (now - last) / 1000;
    if (elapsedSec > bestElapsed) { bestElapsed = elapsedSec; bestIdx = i; }
  }
  // 若該 Key 冷卻未滿，先等待
  var lastUsed = parseInt(props.getProperty('LAST_KEY_' + bestIdx + '_MS') || '0', 10);
  var elapsedSec = lastUsed === 0 ? 0 : (now - lastUsed) / 1000;
  if (lastUsed > 0 && elapsedSec < CONFIG.MIN_REQUEST_INTERVAL) {
    var waitSec = Math.ceil(CONFIG.MIN_REQUEST_INTERVAL - elapsedSec);
    Utilities.sleep(waitSec * 1000);
  }

  // 依序嘗試各 Key（從 bestIdx 開始），任一個成功即寫入
  var newsData = null;
  var usedIdx = -1;
  for (var round = 0; round < apiKeys.length; round++) {
    var idx = (bestIdx + round) % apiKeys.length;
    try {
      var raw = callGemini(keyword, apiKeys[idx]);
      props.setProperty('LAST_KEY_' + idx + '_MS', String(Date.now()));
      usedIdx = idx;
      newsData = parseNewsJson(raw);
      break;
    } catch (e) {
      console.error('API Key #' + (idx + 1) + ' 失敗:', e.message);
    }
  }

  if (!newsData || newsData.length === 0) {
    ui.alert('無資料或全部失敗', '未取得任何新聞，或所有 API Key 皆失敗，請檢查關鍵字與 Key（詳見執行紀錄）。', ui.ButtonSet.OK);
    return;
  }

  try {
    writeToSheet(newsData);
    ui.alert('完成', '已寫入 ' + newsData.length + ' 則新聞。' + (apiKeys.length > 1 && usedIdx >= 0 ? '（本次使用 Key #' + (usedIdx + 1) + '）' : ''), ui.ButtonSet.OK);
  } catch (e) {
    ui.alert('寫入失敗', e.message, ui.ButtonSet.OK);
  }
}

// 呼叫 Gemini API（Google Search），組 prompt + 送 request，回傳純文字；支援多重 parts 解析
function callGemini(keyword, apiKey) {
  const today = Utilities.formatDate(new Date(), Session.getScriptTimeZone() || 'Asia/Taipei', 'yyyy-MM-dd');
  const prompt = [
    '請透過 Google 搜尋關於「' + keyword + '」的最新新聞。',
    '今天是 ' + today + '。',
    '發佈日期請盡量在最近 7 天內。',
    '請找出約 10 則不同的新聞事件。',
    '回傳「僅一個」JSON 陣列，每筆物件欄位：title（標題）、source（來源）、date（發佈日期）、link（連結）、summary（50–100 字繁體中文摘要）。',
    '不要回傳 markdown 程式碼區塊，只回傳純 JSON 陣列。'
  ].join('\n');

  const url = CONFIG.GEMINI_BASE + '/' + CONFIG.GEMINI_MODEL + ':generateContent';

  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
    tools: [{ google_search: {} }],  // 啟用 Google Search
    generationConfig: {
      temperature: 0.3
    }
  };

  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: { 'x-goog-api-key': apiKey },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(url, options);
  const code = response.getResponseCode();
  const body = response.getContentText();

  // 1. HTTP 非 200 則拋錯
  if (code !== 200) {
    let errMsg = body;
    try {
      const err = JSON.parse(body);
      if (err.error && err.error.message) errMsg = err.error.message;
    } catch (_) {}
    throw new Error('API Error ' + code + ': ' + errMsg);
  }

  // 2. 解析回應 JSON
  let data;
  try {
    data = JSON.parse(body);
  } catch (e) {
    throw new Error('API 回傳非 JSON 格式');
  }

  // 3. 檢查是否有候選回應 (candidates[0])
  const candidate = data.candidates && data.candidates[0];
  if (!candidate) {
    const feedback = data.promptFeedback || {};
    const reason = feedback.blockReason || 'UNKNOWN';
    console.error('無候選回應 (No Candidate)，完整 Body:', body);
    throw new Error('API 無回應 (BlockReason: ' + reason + ')');
  }

  // 4. 檢查 content.parts 存在
  const content = candidate.content;
  if (!content || !content.parts || content.parts.length === 0) {
    const reason = candidate.finishReason || 'UNKNOWN';
    console.error('無內容 (No Content Parts)，完整 Body:', body);
    throw new Error('API 回傳無內容 (FinishReason: ' + reason + ')');
  }

  // 5. 遍歷所有 parts，取第一個有 part.text 的作為回傳（相容 Google Search 多 part）
  for (var i = 0; i < content.parts.length; i++) {
    var part = content.parts[i];
    if (part && part.text && part.text.trim().length > 0) {
      return part.text.trim();
    }
  }

  // 無任何 part 含文字時拋錯
  const finishReason = candidate.finishReason || 'STOP';
  console.error('有 Parts 但無文字 (可能被安全過濾或僅回傳 Metadata)，完整 Body:', body);
  throw new Error('API 回傳無有效文字 (FinishReason: ' + finishReason + ')');
}

// 將 API 回傳文字轉成新聞陣列：清掉 markdown 外殼、擷取 [...]、解析為 { title, source, date, link, summary }
function parseNewsJson(text) {
  if (!text || typeof text !== 'string') return [];
  let jsonStr = text.trim();
  
  // 移除 ```json ... ```
  jsonStr = jsonStr.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/, '');
  
  // 擷取第一個 [...] 區段
  const start = jsonStr.indexOf('[');
  const end = jsonStr.lastIndexOf(']');
  if (start !== -1 && end !== -1 && end > start) {
    jsonStr = jsonStr.substring(start, end + 1);
  }

  try {
    const arr = JSON.parse(jsonStr);
    if (!Array.isArray(arr)) return [];
    
    return arr.map(function (item) {
      return {
        title: item.title ? String(item.title) : '',
        source: item.source ? String(item.source) : '',
        date: item.date ? String(item.date) : '',
        link: item.link ? String(item.link) : '',
        summary: item.summary ? String(item.summary) : ''
      };  // 統一欄位並轉字串
    });
  } catch (e) {
    console.error('JSON 解析失敗，原始文字:', text);
    throw new Error('無法解析新聞 JSON，請檢查格式。');
  }
}

// 寫入「新聞」工作表：清空 → 第 1 列標題 → 第 2 列起資料 → 自動欄寬
function writeToSheet(newsData) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(CONFIG.OUTPUT_SHEET_NAME);
  if (!sheet) {
    sheet = ss.getSheets()[0];
  }

  const headers = ['標題', '來源', '發佈日期', '連結', 'AI 摘要'];
  const rows = newsData.map(function (item) {
    return [item.title, item.source, item.date, item.link, item.summary];
  });

  sheet.clear();
  
  // 第 1 列：標題列
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');

  // 第 2 列起：資料列
  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  }
  
  sheet.autoResizeColumns(1, headers.length);
}

// UI：設定 API Key（多個可一行一個或逗號分隔，存 GEMINI_API_KEYS）
function showSetApiKeyDialog() {
  const ui = SpreadsheetApp.getUi();
  const props = PropertiesService.getScriptProperties();
  const result = ui.prompt('設定 Gemini API Key（可多個）', '請輸入一或多個 API Key，一行一個（或逗號分隔）：', ui.ButtonSet.OK_CANCEL);
  if (result.getSelectedButton() === ui.Button.OK) {
    const value = result.getResponseText().trim();
    if (value) {
      props.setProperty('GEMINI_API_KEYS', value);
      var keys = getApiKeysArray(props);
      ui.alert('已儲存 ' + keys.length + ' 個 API Key。多 Key 會輪替使用並各自遵守 RPM 配額。');
    }
  }
}

// UI：設定監控關鍵字（存 Script Properties KEYWORD）
function showSetKeywordDialog() {
  const ui = SpreadsheetApp.getUi();
  const result = ui.prompt('設定監控關鍵字', '請輸入新聞關鍵字：', ui.ButtonSet.OK_CANCEL);
  if (result.getSelectedButton() === ui.Button.OK) {
    const value = result.getResponseText().trim();
    if (value) {
      PropertiesService.getScriptProperties().setProperty('KEYWORD', value);
      ui.alert('關鍵字已更新為：' + value);
    }
  }
}
