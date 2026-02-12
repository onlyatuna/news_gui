"""AI News Helper - Gemini + Sheet 新聞抓取 GUI。"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tkinter import font as tkfont
import threading
import json
import os
import re
import random
import time
import platform
import sys
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from google import genai
from google.genai import types


class PlatformConfig:
    """依 OS 設定字型、DPI、按鈕。"""
    def __init__(self):
        self.os_name = platform.system()
        self.is_mac = (self.os_name == "Darwin")
        self.is_windows = (self.os_name == "Windows")
        
        if self.is_windows:
            self.FONT_MAIN = "Segoe UI"
            self.FONT_MONO = "Consolas"
        elif self.is_mac:
            self.FONT_MAIN = "San Francisco"
            self.FONT_MONO = "Menlo"
        else:
            self.FONT_MAIN = "DejaVu Sans"
            self.FONT_MONO = "Ubuntu Mono"

    def setup_dpi_awareness(self):
        """Windows 高 DPI 修正。"""
        if self.is_windows:
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    import ctypes
                    ctypes.windll.user32.SetProcessDPIAware()
                except:
                    pass

    def get_button_config(self, primary_color):
        """依平台回傳按鈕樣式。"""
        if self.is_mac:
            return {
                "bg": "#FFFFFF",
                "fg": primary_color,
                "highlightbackground": "#FFFFFF",
                "relief": "flat"
            }
        else:
            return {
                "bg": primary_color,
                "fg": "white",
                "relief": "flat"
            }

OS_CONFIG = PlatformConfig()
OS_CONFIG.setup_dpi_awareness()

def clean_json_string(text):
    """剝 markdown、擷取 JSON 陣列。"""
    try:
        text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1:
            return text[start : end+1]
        return text.strip()
    except Exception:
        return text.strip()

CONFIG_FILE = "settings.json"
CREDENTIALS_FILE = "credentials.json"
MIN_REQUEST_INTERVAL = 7  # 秒，限頻

COLORS = {
    "bg_main": "#F3F4F6",
    "bg_card": "#FFFFFF",
    "primary": "#3B82F6",
    "primary_hover": "#2563EB",
    "text_dark": "#111827",
    "text_gray": "#6B7280",
    "console_bg": "#1F2937",
    "console_fg": "#10B981",
    "border": "#E5E7EB",
    "success": "#10B981",
    "error": "#EF4444"
}

class ModernNewsBotGUI:
    """主視窗：左設定、右主控台。"""
    def __init__(self, root):
        self.root = root
        self.root.title("AI News Helper v2.4")
        self.root.geometry("1000x750")
        self.root.configure(bg=COLORS["bg_main"])
        
        self.last_request_time = 0
        self.stats = {"success": 0, "fail": 0}
        
        self.default_settings = {
            "sheet_url": "",
            "api_keys": "",
            "keyword": "NVIDIA"
        }
        self.settings = self.load_settings()

        self.setup_styles()
        
        self.create_layout()
        
        if not os.path.exists(CREDENTIALS_FILE):
            self.log_to_console("❌ 警告：找不到 credentials.json！", "error")

    def load_settings(self):
        """讀取 settings.json，相容舊 api_key。"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "api_key" in data and "api_keys" not in data:
                        data["api_keys"] = data["api_key"]
                    return data
            except: pass
        return self.default_settings

    def save_settings(self):
        """寫入 settings.json。"""
        settings = {
            "sheet_url": self.entry_sheet.get().strip(),
            "api_keys": self._api_keys_full,
            "keyword": self.entry_keyword.get().strip()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)

    def setup_styles(self):
        """ttk 主題、字型、顏色。"""
        style = ttk.Style()
        style.theme_use('clam')
        
        base_font = OS_CONFIG.FONT_MAIN
        
        style.configure("Main.TFrame", background=COLORS["bg_main"])
        style.configure("Card.TFrame", background=COLORS["bg_card"], relief="flat")
        
        style.configure("H1.TLabel", font=(base_font, 16, "bold"), background=COLORS["bg_main"], foreground=COLORS["text_dark"])
        style.configure("H2.TLabel", font=(base_font, 12, "bold"), background=COLORS["bg_card"], foreground=COLORS["text_dark"])
        style.configure("FieldLabel.TLabel", font=(base_font, 10), background=COLORS["bg_card"], foreground=COLORS["text_dark"])
        style.configure("Status.TLabel", font=(base_font, 10, "bold"), background=COLORS["bg_card"], foreground=COLORS["primary"])
        
        style.configure("TEntry", fieldbackground="white", bordercolor=COLORS["border"], lightcolor=COLORS["border"], darkcolor=COLORS["border"])
        style.configure("TProgressbar", thickness=10, background=COLORS["primary"], troughcolor=COLORS["bg_main"])

    def create_layout(self):
        """組裝標題、左卡、右卡。"""
        header_frame = ttk.Frame(self.root, style="Main.TFrame")
        header_frame.pack(fill="x", padx=32, pady=(24, 12))
        
        lbl_title = ttk.Label(header_frame, text="AI News Helper v2.4", style="H1.TLabel")
        lbl_title.pack(side="left")

        main_container = ttk.Frame(self.root, style="Main.TFrame")
        main_container.pack(fill="both", expand=True, padx=32, pady=(0, 32))
        
        main_container.columnconfigure(0, weight=4)
        main_container.columnconfigure(1, weight=6)
        main_container.rowconfigure(0, weight=1)

        left_card = ttk.Frame(main_container, style="Card.TFrame", padding=24)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        
        ttk.Label(left_card, text="1. CONFIGURATION", style="H2.TLabel").pack(anchor="w", pady=(0, 20))

        ttk.Label(left_card, text="📋 資料來源 (Google Sheet URL)", style="FieldLabel.TLabel").pack(anchor="w", pady=(0, 6))
        sheet_frame = ttk.Frame(left_card, style="Card.TFrame")
        sheet_frame.pack(fill="x", pady=(0, 20))
        self.entry_sheet = ttk.Entry(sheet_frame, font=(OS_CONFIG.FONT_MAIN, 10))
        self.entry_sheet.pack(side="left", fill="both", expand=True, ipady=4)
        self.entry_sheet.insert(0, self.settings.get("sheet_url", ""))
        btn_open_sheet = ttk.Button(sheet_frame, text="🔗 開啟", command=self.open_sheet_link, width=8)
        btn_open_sheet.pack(side="right", padx=(6, 0))

        ttk.Label(left_card, text="🔑 Gemini API Keys (一行一組)", style="FieldLabel.TLabel").pack(anchor="w", pady=(0, 6))
        self._api_keys_full = self.settings.get("api_keys", "")
        api_frame = tk.Frame(left_card, bg=COLORS["border"], padx=1, pady=1)
        api_frame.pack(fill="both", expand=True, pady=(0, 20))
        self.txt_api_keys = tk.Text(api_frame, height=5, font=(OS_CONFIG.FONT_MONO, 10), bd=0, padx=5, pady=5)
        self.txt_api_keys.pack(fill="both", expand=True)
        masked_keys = self._get_masked_keys(self._api_keys_full)
        self.txt_api_keys.insert(tk.END, masked_keys)
        self.txt_api_keys.bind("<FocusIn>", self._on_api_keys_focus_in)
        self.txt_api_keys.bind("<FocusOut>", self._on_api_keys_focus_out)

        ttk.Label(left_card, text="🔍 監控關鍵字", style="FieldLabel.TLabel").pack(anchor="w", pady=(0, 6))
        self.entry_keyword = ttk.Entry(left_card, font=(OS_CONFIG.FONT_MAIN, 10))
        self.entry_keyword.pack(fill="x", ipady=4, pady=(0, 24))
        self.entry_keyword.insert(0, self.settings.get("keyword", "NVIDIA"))

        btn_params = OS_CONFIG.get_button_config(COLORS["primary"])
        self.btn_run = tk.Button(left_card, text="🚀 開始執行任務", 
                                 font=(OS_CONFIG.FONT_MAIN, 12, "bold"), 
                                 cursor="hand2",
                                 disabledforeground="#E5E7EB", 
                                 activebackground=COLORS["primary_hover"], activeforeground="white",
                                 command=self.start_thread,
                                 **btn_params)
        self.btn_run.pack(fill="x", ipady=8, side="bottom")

        right_card = ttk.Frame(main_container, style="Card.TFrame", padding=24)
        right_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        top_status_frame = ttk.Frame(right_card, style="Card.TFrame")
        top_status_frame.pack(fill="x", pady=(0, 16), side="top")
        
        ttk.Label(top_status_frame, text="2. LIVE CONSOLE", style="H2.TLabel").pack(side="left")
        self.lbl_status_text = ttk.Label(top_status_frame, text="🟢 系統就緒", style="Status.TLabel", foreground=COLORS["success"])
        self.lbl_status_text.pack(side="right")

        self.progress = ttk.Progressbar(right_card, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=(0, 20), side="top")

        stats_frame = ttk.Frame(right_card, style="Card.TFrame")
        stats_frame.pack(fill="x", side="bottom", pady=(20, 0))
        
        def create_stat_box(parent, label, var_name, color):
            """單一統計區塊。"""
            f = tk.Frame(parent, bg=COLORS["bg_main"], padx=10, pady=5)
            f.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(f, text=label, bg=COLORS["bg_main"], fg=COLORS["text_gray"], font=(OS_CONFIG.FONT_MAIN, 9)).pack(anchor="w")
            lbl_val = tk.Label(f, text="0", bg=COLORS["bg_main"], fg=color, font=(OS_CONFIG.FONT_MAIN, 14, "bold"))
            lbl_val.pack(anchor="e")
            setattr(self, var_name, lbl_val)

        create_stat_box(stats_frame, "成功擷取", "lbl_stat_success", COLORS["success"])
        create_stat_box(stats_frame, "失敗/略過", "lbl_stat_fail", COLORS["error"])

        console_container = tk.Frame(right_card, bg=COLORS["console_bg"])
        console_container.pack(fill="both", expand=True, side="top")
        
        self.txt_console = tk.Text(console_container, bg=COLORS["console_bg"], fg="#D1D5DB", 
                                   font=(OS_CONFIG.FONT_MONO, 10), state="disabled", padx=10, pady=10, bd=0)
        self.txt_console.pack(side="left", fill="both", expand=True)
        
        sb = ttk.Scrollbar(console_container, command=self.txt_console.yview, orient="vertical")
        sb.pack(side="right", fill="y")
        self.txt_console.config(yscrollcommand=sb.set)
        
        self.txt_console.tag_config("INFO", foreground="#10B981")
        self.txt_console.tag_config("WARN", foreground="#FBBF24")
        self.txt_console.tag_config("ERROR", foreground="#EF4444")
        self.txt_console.tag_config("CMD", foreground="white", background="#374151")

        self.log_to_console("System initialized...", "INFO")
        self.log_to_console("Waiting for command.", "INFO")

    def log_to_console(self, message, level="INFO"):
        """主控台附加日誌。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_console.config(state='normal')
        
        self.txt_console.insert(tk.END, f"[{timestamp}] ", "text_gray")
        self.txt_console.insert(tk.END, "> ", "CMD")
        self.txt_console.insert(tk.END, f"{message}\n", level)
        
        self.txt_console.see(tk.END)
        self.txt_console.config(state='disabled')

    def update_ui_state(self, status_text, progress_val, is_running=True):
        """更新狀態、進度、按鈕鎖定。"""
        self.lbl_status_text.config(text=status_text)
        self.progress["value"] = progress_val
        
        if is_running:
            self.btn_run.config(
                bg="#9CA3AF",
                fg="white",
                state="normal",
                cursor="arrow",
                command=lambda: None
            )
        else:
            self.btn_run.config(
                bg=COLORS["primary"],
                fg="white",
                state="normal",
                cursor="hand2",
                command=self.start_thread
            )
        
        self.root.update_idletasks()

    def update_stats(self):
        """同步成功/失敗計數。"""
        self.lbl_stat_success.config(text=str(self.stats["success"]))
        self.lbl_stat_fail.config(text=str(self.stats["fail"]))

    def open_sheet_link(self):
        """瀏覽器開啟 Sheet URL。"""
        url = self.entry_sheet.get().strip()
        if not url:
            messagebox.showwarning("提示", "請先輸入 Google Sheet URL")
            return
        
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟鏈接: {str(e)}")

    def _get_masked_keys(self, full_keys):
        """API Key 遮罩（前5+後3）。"""
        if not full_keys:
            return ""
        
        lines = full_keys.strip().split("\n")
        masked_lines = []
        for key in lines:
            if len(key) > 10:
                masked = key[:5] + "." * 32 + key[-3:]
                masked_lines.append(masked)
            else:
                masked_lines.append(key)
        return "\n".join(masked_lines)

    def _on_api_keys_focus_in(self, event):
        """焦點進入：顯示完整 Key。"""
        self.txt_api_keys.config(state="normal")
        self.txt_api_keys.delete("1.0", tk.END)
        self.txt_api_keys.insert(tk.END, self._api_keys_full)

    def _on_api_keys_focus_out(self, event):
        """焦點離開：儲存並遮罩。"""
        self._api_keys_full = self.txt_api_keys.get("1.0", tk.END).strip()
        masked_keys = self._get_masked_keys(self._api_keys_full)
        self.txt_api_keys.delete("1.0", tk.END)
        self.txt_api_keys.insert(tk.END, masked_keys)

    def start_thread(self):
        """儲存、重置、背景執行。"""
        self.save_settings()
        self.stats = {"success": 0, "fail": 0}
        self.update_stats()
        
        thread = threading.Thread(target=self.run_process)
        thread.daemon = True
        thread.start()

    def run_process(self):
        """主流程：驗證→Sheet→冷卻→Gemini→寫入。"""
        try:
            self.update_ui_state("🚀 正在初始化...", 5, True)
            
            sheet_url = self.entry_sheet.get().strip()
            raw_keys = self._api_keys_full.strip()
            keyword = self.entry_keyword.get().strip()
            
            self.log_to_console(f"任務啟動: 搜尋 '{keyword}'", "INFO")

            api_key_list = [k.strip() for k in re.split(r'[,\n]', raw_keys) if k.strip()]
            if not sheet_url or not api_key_list:
                self.log_to_console("缺少必要設定 (URL 或 API Key)", "ERROR")
                self.update_ui_state("❌ 設定錯誤", 0, False)
                return

            self.update_ui_state("☁️ 連線 Google Sheet...", 20, True)
            self.log_to_console("Connecting to Google Sheets...", "INFO")
            
            try:
                scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
                client_gs = gspread.authorize(creds)
                sheet = client_gs.open_by_url(sheet_url).sheet1
            except Exception as e:
                self.log_to_console(f"Sheet 連線失敗: {e}", "ERROR")
                raise e
            
            self.log_to_console("Sheet 連線成功", "INFO")

            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < MIN_REQUEST_INTERVAL:
                wait_time = MIN_REQUEST_INTERVAL - elapsed
                self.log_to_console(f"冷卻中 (RPM 保護)... 等待 {int(wait_time)}s", "WARN")
                time.sleep(wait_time)

            self.update_ui_state("🧠 AI 正在思考...", 40, True)
            available_keys = list(api_key_list)
            news_data = None
            
            while available_keys:
                current_key = random.choice(available_keys)
                masked_key = current_key[:5] + "." * 32 + current_key[-3:]
                self.log_to_console(f"使用 Key: {masked_key}", "INFO")

                try:
                    client_ai = genai.Client(api_key=current_key)
                    google_search_tool = types.Tool(google_search=types.GoogleSearch())
                    today = datetime.now().strftime("%Y-%m-%d")
                    
                    prompt = f"""
                    請透過 Google 搜尋關於「{keyword}」的最新新聞。
                    今天是 {today}。
                    發佈日期請盡量在最近 7 天內。
                    請找出 10 則不同的新聞事件。
                    回傳 JSON 列表，包含：title, source, date, link, summary (50-100字繁體中文)。
                    """
                    
                    self.update_ui_state("🔍 Google Search & GenAI...", 60, True)
                    
                    config = types.GenerateContentConfig(
                        tools=[google_search_tool],
                        response_modalities=["TEXT"],
                        temperature=0.3
                    )

                    response = client_ai.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=config
                    )

                    self.update_ui_state("📥 解析資料中...", 80, True)
                    
                    final_json_text = clean_json_string(response.text)
                    news_data = json.loads(final_json_text)
                    
                    self.last_request_time = time.time()
                    self.log_to_console(f"成功獲取 {len(news_data)} 筆資料", "INFO")
                    
                    self.stats["success"] += len(news_data)
                    self.update_stats()
                    break 

                except Exception as e:
                    error_msg = str(e)
                    self.log_to_console(f"API Error: {error_msg}", "WARN")
                    available_keys.remove(current_key)
                    self.stats["fail"] += 1
                    self.update_stats()
                    time.sleep(1)
            
            if not news_data:
                self.log_to_console("所有 API Key 皆失敗或無資料", "ERROR")
                self.update_ui_state("❌ 任務失敗", 0, False)
                return

            self.update_ui_state("💾 寫入資料庫...", 90, True)
            sheet.clear()
            header = ["標題", "來源", "發佈日期", "連結", "AI 摘要"]
            sheet.append_row(header)

            rows_to_add = []
            for item in news_data:
                rows_to_add.append([
                    item.get("title", ""),
                    item.get("source", ""),
                    item.get("date", ""),
                    item.get("link", ""),
                    item.get("summary", "")
                ])
            
            sheet.append_rows(rows_to_add)
            
            self.log_to_console("任務全部完成！", "INFO")
            self.update_ui_state("🟢 系統就緒", 100, False)
            messagebox.showinfo("完成", f"成功更新 {len(rows_to_add)} 則新聞！")

        except Exception as e:
            self.log_to_console(f"System Critical: {str(e)}", "ERROR")
            self.update_ui_state("❌ 發生錯誤", 0, False)
            messagebox.showerror("錯誤", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernNewsBotGUI(root)
    root.mainloop()
