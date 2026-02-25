import sys
import os
import logging
import traceback
import json
import streamlink
import time
import re
import ctypes
import unicodedata
from urllib.parse import unquote, urlparse

# ---------------------------------------------------------
# [VibeCoding 標準起手式 V2.0]
# ---------------------------------------------------------

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    internal_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    internal_path = application_path

try:
    myappid = 'vibecoding.multistream.viewer.v3.9.3.smartload' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

os.environ["PATH"] += os.pathsep + internal_path
if hasattr(os, 'add_dll_directory'):
    try: os.add_dll_directory(internal_path)
    except: pass

current_dir = internal_path
data_dir = application_path

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLineEdit, QPushButton, QGridLayout, 
                               QListWidget, QLabel, QSlider, QFrame,
                               QListWidgetItem, QMessageBox, QInputDialog, QSizePolicy,
                               QCheckBox, QAbstractItemView, QComboBox, QFileDialog, QMenu,
                               QDialog, QTextBrowser, QDialogButtonBox)
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QCursor, QColor, QIcon, QPixmap, QAction, QDrag, QFont
from stream_widget import StreamWidget
from cookie_manager import CookieManager

log_path = os.path.join(data_dir, "debug.log")
logging.basicConfig(filename=log_path, filemode='w', level=logging.INFO, encoding='utf-8')

# --- 樣式表區域 ---
LIGHT_STYLE = """
    QMainWindow { background-color: #f0f0f0; }
    QWidget { font-family: 'Microsoft JhengHei', sans-serif; font-size: 16px; color: #000000; }
    QLineEdit { padding: 10px; border: 2px solid #aaa; border-radius: 6px; background: #fff; color: #000; font-weight: bold; }
    #ControlBar QPushButton { font-size: 20px; height: 32px; width: 32px; padding: 2px; }
    #ControlBar QLabel { font-size: 26px; font-weight: bold; color: #0056b3; }
    #StreamCard { background-color: #ffffff; border: 1px solid #ccc; border-radius: 8px; }
    #ControlBar { background-color: #f8f8f8; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; border-top: 1px solid #e0e0e0; }
    #Sidebar { background-color: #ffffff; border-left: 2px solid #aaa; }
    QPushButton { background-color: #e0e0e0; color: #000; border: 1px solid #999; border-radius: 6px; font-weight: bold; padding: 8px; }
    QPushButton:hover { background-color: #d0d0d0; }
    QPushButton#RefreshBtn { padding: 0px; font-size: 20px; background-color: #fff; }
    QPushButton#HelpBtn { background-color: #fff; border: 1px solid #aaa; font-size: 18px; color: #333; font-weight: bold; border-radius: 6px; padding: 0 10px; }
    QPushButton#HelpBtn:hover { background-color: #e0e0e0; color: #000; border: 1px solid #888; }
    QPushButton#AccentBtn:hover { background-color: #6CB4EE; }
    QPushButton#DangerBtn { background-color: #F88379; color: #000; border: 1px solid #a71d2a; }
    QPushButton#SuccessBtn { background-color: #98FB98; color: #000; border: 1px solid #28a745; }
    QPushButton#MuteBtn { background-color: transparent; border: none; font-size: 20px; padding: 0px; color: #fff; }
    QListWidget { background-color: #fff; border: 2px solid #aaa; border-radius: 6px; color: #000; }
    QListWidget::item:selected { background-color: #cce5ff; color: #000; border: 1px solid #007bff; }
    QLabel#PanelTitle { font-size: 18px; font-weight: 900; color: #0056b3; margin-bottom: 5px; }
    QComboBox { background-color: #ffffff; color: #000000; border: 1px solid #999; border-radius: 4px; padding: 5px; }
    QComboBox QAbstractItemView { background-color: #ffffff; color: #000000; selection-background-color: #cce5ff; selection-color: #000000; }
"""

DARK_STYLE = """
    QMainWindow { background-color: #1e1e1e; }
    QWidget { font-family: 'Microsoft JhengHei', sans-serif; font-size: 16px; color: #e0e0e0; }
    QLineEdit { padding: 10px; border: 2px solid #555; border-radius: 6px; background: #333; color: #fff; font-weight: bold; }
    #ControlBar QPushButton { font-size: 24px; height: 32px; width: 32px; padding: 2px; }
    #ControlBar QLabel { font-size: 26px; font-weight: bold; color: #ffffff; }
    #StreamCard { background-color: #2d2d2d; border: 1px solid #444; border-radius: 8px; }
    #ControlBar { background-color: #333; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; border-top: 1px solid #444; }
    #Sidebar { background-color: #252525; border-left: 2px solid #444; }
    QPushButton { background-color: #444; color: #fff; border: 1px solid #666; border-radius: 6px; font-weight: bold; padding: 8px; }
    QPushButton:hover { background-color: #555; }
    QPushButton#RefreshBtn { padding: 0px; font-size: 20px; background-color: #333; }
    QPushButton#HelpBtn { background-color: #444; border: 1px solid #666; font-size: 18; color: #ddd; font-weight: bold; border-radius: 6px; padding: 0 10px; }
    QPushButton#HelpBtn:hover { background-color: #555; color: #fff; border: 1px solid #888; }
    QPushButton#AccentBtn { background-color: #007bff; color: #fff; border: 1px solid #0056b3; }
    QPushButton#DangerBtn { background-color: #dc3545; color: #fff; border: 1px solid #a71d2a; }
    QPushButton#SuccessBtn { background-color: #28a745; color: #fff; border: 1px solid #1e7e34; }
    QPushButton#MuteBtn { background-color: transparent; border: none; font-size: 20px; padding: 0px; color: #fff; }
    QListWidget { background-color: #333; border: 2px solid #555; border-radius: 6px; color: #fff; }
    QListWidget::item:selected { background-color: #007bff; color: #fff; }
    QLabel#PanelTitle { font-size: 18px; font-weight: 900; color: #4dabf7; margin-bottom: 5px; }
    QComboBox { background-color: #333; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 5px; }
    QComboBox QAbstractItemView { background-color: #333; color: #fff; selection-background-color: #007bff; selection-color: #fff; }
"""

class HelpWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用說明")
        self.resize(1024, 800)
        
        layout = QVBoxLayout(self)
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        
        readme_path = os.path.join(internal_path, "README.md")
        content = ""
        if os.path.exists(readme_path):
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"# 錯誤\n無法讀取說明檔: {e}"
        else:
            content = "# VibeCoding Multi-Stream Viewer\n\n說明檔 (README.md) 遺失。"
            
        self.text_browser.setMarkdown(content)
        self.text_browser.setStyleSheet("font-size: 28px;")

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        
        layout.addWidget(self.text_browser)
        layout.addWidget(btn_box)

class 狀態檢查器(QThread):
    status_updated = Signal(int, bool)
    def __init__(self, items):
        super().__init__()
        self.items = items
        self.is_running = True

    def run(self):
        session = streamlink.Streamlink()
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
        if os.path.exists(ffmpeg_path):
            session.set_option("ffmpeg-ffmpeg", ffmpeg_path)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        session.set_option("http-headers", headers)

        cookies = CookieManager.get_cookies_for_streamlink()
        if cookies: 
            session.http.cookies.update(cookies)
            for name, value in cookies.items():
                session.http.cookies.set(name, value, domain=".afreecatv.com")
                session.http.cookies.set(name, value, domain=".sooplive.co.kr")
                session.http.cookies.set(name, value, domain="play.sooplive.co.kr")
        
        for i, item in enumerate(self.items):
            if not self.is_running: break
            url = item.get('url', '')
            if not url: continue
            
            if "sooplive" in url or "afreecatv" in url:
                session.set_option("http-headers", {
                    "Referer": "https://www.sooplive.co.kr/",
                    "Origin": "https://www.sooplive.co.kr"
                })

            try:
                streams = session.streams(url)
                self.status_updated.emit(i, len(streams) > 0)
            except:
                self.status_updated.emit(i, False)
            
            time.sleep(1.0)

    def stop(self): 
        self.is_running = False
        self.wait()

class 主視窗(QMainWindow):
    訊號_廣播音量 = Signal(int)

    def __init__(self):
        super().__init__()
        logging.info("System Initialized (VibeCoding V3.9.3 SmartLoad)...")
        self.setWindowTitle("Multi-Stream Viewer")
        self.resize(1700, 1200)
        
        self.players = []
        self.favorites_file = os.path.join(data_dir, "favorites.json")
        self.checker_thread = None
        self.sidebar_visible = True
        self.is_muted = False
        self.last_volume = 50
        self.is_dark_mode = False
        self.layout_mode = "grid"
        self.current_group_filter = "All"
        self.cached_fav_data = [] 
        self.is_closing_app = False # [Fix] 防止關閉時UI刷新衝突

        # [V3.9.3] 直播狀態緩存
        self.live_status_cache = {} 
        
        # 智慧型載入佇列初始化
        self.load_queue = []
        self.load_timer = QTimer(self)
        self.load_timer.setSingleShot(True) 
        self.load_timer.timeout.connect(self._處理下一個載入請求)
        self.loading_batch_count = 0 

        self._初始化介面()
        self._從磁碟讀取收藏資料() 
        self._渲染收藏列表() 
        self._套用主題()
        
        self.setAcceptDrops(True)

    def _初始化介面(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.video_area = QWidget()
        video_layout = QVBoxLayout(self.video_area)
        video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_grid = QGridLayout()
        self.video_grid.setSpacing(2) 
        self.video_grid.setContentsMargins(0, 0, 0, 0)
        video_layout.addLayout(self.video_grid)
        
        self.toggle_sidebar_btn = QPushButton("▶") 
        self.toggle_sidebar_btn.setObjectName("ToggleBtn")
        self.toggle_sidebar_btn.setFixedWidth(20)
        self.toggle_sidebar_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.toggle_sidebar_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_sidebar_btn.clicked.connect(self._切換側邊欄)
        
        # [Fix] 明確指定 parent 避免關閉時 orphaned
        self.sidebar = QFrame(main_widget)
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(350)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)
        sidebar_layout.setSpacing(15)
        
        # --- 新增串流區塊 ---
        add_layout = QVBoxLayout()
        add_header_layout = QHBoxLayout()
        title_add = QLabel("➕ 新增串流")
        title_add.setObjectName("PanelTitle")
        
        self.btn_help = QPushButton("📖使用說明")
        self.btn_help.setObjectName("HelpBtn")
        self.btn_help.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_help.setToolTip("查看使用說明")
        self.btn_help.setFixedHeight(35)
        self.btn_help.setFixedWidth(120)
        self.btn_help.clicked.connect(self._顯示說明)

        add_header_layout.addWidget(title_add)
        add_header_layout.addStretch()
        add_header_layout.addWidget(self.btn_help)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("貼上網址 (YT/TWITCH/SOOP)...")
        self.url_input.returnPressed.connect(lambda: self._新增串流(self.url_input.text()))
        self.add_btn = QPushButton("加入播放")
        self.add_btn.setObjectName("AccentBtn") 
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.setFixedHeight(40)
        self.add_btn.clicked.connect(lambda: self._新增串流(self.url_input.text()))
        
        add_layout.addLayout(add_header_layout)
        add_layout.addWidget(self.url_input)
        add_layout.addWidget(self.add_btn)
        
        # --- 收藏區塊 ---
        fav_layout = QVBoxLayout()
        fav_header = QHBoxLayout()
        title_fav = QLabel("⭐ 收藏頻道")
        title_fav.setObjectName("PanelTitle")
        
        self.cb_auto_sort = QCheckBox("開台置頂")
        self.cb_auto_sort.setToolTip("若手動拖曳排序，此選項將自動關閉")
        self.cb_auto_sort.setChecked(True)
        
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setObjectName("RefreshBtn")
        self.btn_refresh.setFixedSize(30, 30)
        self.btn_refresh.clicked.connect(self._檢查直播狀態)
        fav_header.addWidget(title_fav)
        fav_header.addStretch()
        fav_header.addWidget(self.cb_auto_sort)
        fav_header.addSpacing(5)
        fav_header.addWidget(self.btn_refresh)
        
        group_filter_layout = QHBoxLayout()
        self.group_combo = QComboBox()
        self.group_combo.addItem("All")
        self.group_combo.currentTextChanged.connect(self._當群組過濾變更時)
        self.btn_load_group = QPushButton("載入群組")
        self.btn_load_group.clicked.connect(self._載入當前群組串流)
        group_filter_layout.addWidget(QLabel("群組:"))
        group_filter_layout.addWidget(self.group_combo)
        group_filter_layout.addWidget(self.btn_load_group)

        self.fav_list = QListWidget()
        self.fav_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.fav_list.setDefaultDropAction(Qt.MoveAction)
        self.fav_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.fav_list.model().rowsMoved.connect(self._拖曳後儲存順序)
        self.fav_list.itemDoubleClicked.connect(self._載入收藏串流)
        self.fav_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fav_list.customContextMenuRequested.connect(self._顯示收藏右鍵選單)
        self.fav_list.itemClicked.connect(self._同步選取狀態_右對左)
        
        row1 = QHBoxLayout()
        self.btn_save = QPushButton("收藏當前")
        self.btn_save.clicked.connect(self._將當前輸入存為收藏)
        self.btn_edit = QPushButton("改名")
        self.btn_edit.clicked.connect(self._編輯收藏名稱)
        self.btn_del = QPushButton("刪除")
        self.btn_del.clicked.connect(self._刪除收藏)
        row1.addWidget(self.btn_save)
        row1.addWidget(self.btn_edit)
        row1.addWidget(self.btn_del)
        
        group_manage_row = QHBoxLayout()
        self.btn_new_group = QPushButton("新增群組")
        self.btn_new_group.clicked.connect(self._批量新增群組)
        self.btn_join_group = QPushButton("加入群組")
        self.btn_join_group.clicked.connect(self._批量移動至群組)
        self.btn_manage_group = QPushButton("管理群組")
        self.btn_manage_group.clicked.connect(self._管理群組對話框)
        group_manage_row.addWidget(self.btn_new_group)
        group_manage_row.addWidget(self.btn_join_group)
        group_manage_row.addWidget(self.btn_manage_group)

        row2 = QHBoxLayout()
        self.btn_open_sel = QPushButton("📂 開啟選取")
        self.btn_open_sel.setObjectName("AccentBtn")
        self.btn_open_sel.clicked.connect(self._開啟選取的收藏)
        self.btn_open_live = QPushButton("📺 開啟直播中")
        self.btn_open_live.setObjectName("SuccessBtn")
        self.btn_open_live.clicked.connect(self._開啟直播中收藏)
        row2.addWidget(self.btn_open_sel)
        row2.addWidget(self.btn_open_live)
        
        fav_layout.addLayout(fav_header)
        fav_layout.addLayout(group_filter_layout)
        fav_layout.addWidget(self.fav_list)
        fav_layout.addLayout(row1)
        fav_layout.addLayout(group_manage_row)
        fav_layout.addLayout(row2)

        global_layout = QVBoxLayout()
        title_global = QLabel("🎛️ 系統控制")
        title_global.setObjectName("PanelTitle")
        
        vol_row = QHBoxLayout()
        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setObjectName("MuteBtn")
        self.btn_mute.setFixedSize(32, 32)
        self.btn_mute.clicked.connect(self._切換全局靜音)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self._設定全局音量)
        vol_row.addWidget(self.btn_mute)
        vol_row.addWidget(self.slider)
        
        settings_row = QHBoxLayout()
        self.btn_layout_toggle = QPushButton("⊞ 網格")
        self.btn_layout_toggle.clicked.connect(self._切換佈局模式)
        self.btn_theme_toggle = QPushButton("🌙")
        self.btn_theme_toggle.clicked.connect(self._切換主題)
        settings_row.addWidget(self.btn_layout_toggle)
        settings_row.addWidget(self.btn_theme_toggle)

        self.btn_reload_all = QPushButton("🔄 全部重整")
        self.btn_reload_all.setObjectName("SuccessBtn")
        self.btn_reload_all.clicked.connect(self._重整所有串流)
        
        io_row = QHBoxLayout()
        self.btn_export = QPushButton("📤 匯出收藏")
        self.btn_export.setObjectName("IOBtn")
        self.btn_export.clicked.connect(self._匯出收藏)
        self.btn_import = QPushButton("📥 匯入收藏")
        self.btn_import.setObjectName("IOBtn")
        self.btn_import.clicked.connect(self._匯入收藏)
        io_row.addWidget(self.btn_export)
        io_row.addWidget(self.btn_import)

        self.btn_clear = QPushButton("清空畫面")
        self.btn_clear.setObjectName("DangerBtn")
        self.btn_clear.clicked.connect(self._清空所有串流)
        
        global_layout.addWidget(title_global)
        global_layout.addLayout(vol_row)
        global_layout.addLayout(settings_row)
        global_layout.addSpacing(5)
        global_layout.addWidget(self.btn_reload_all)
        global_layout.addLayout(io_row)
        global_layout.addWidget(self.btn_clear)

        sidebar_layout.addLayout(add_layout)
        sidebar_layout.addSpacing(30)
        sidebar_layout.addLayout(fav_layout)
        sidebar_layout.addSpacing(30)
        sidebar_layout.addLayout(global_layout)
       
        about_label = QLabel("VibeCoding Player v3.9.3 (SmartLoad)")
        about_label.setStyleSheet("color: #888; font-size: 12px;")
        about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(about_label)

        main_layout.addWidget(self.video_area, stretch=1)
        main_layout.addWidget(self.toggle_sidebar_btn)
        main_layout.addWidget(self.sidebar)

    # --- 拖曳事件處理 ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-stream-url"):
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-stream-url"):
            event.ignore()
            return
            
        source_url = event.mimeData().text()
        
        source_player = None
        source_index = -1
        norm_source = self._標準化URL(source_url)
        for i, p in enumerate(self.players):
            if self._標準化URL(p.original_stream_url) == norm_source:
                source_player = p
                source_index = i
                break
        
        if not source_player: return
        
        target_index = -1
        drop_pos = event.position().toPoint()
        
        for i, p in enumerate(self.players):
            player_geo = p.mapTo(self, p.rect().topLeft())
            player_rect = p.rect()
            player_rect.moveTo(player_geo)
            
            if player_rect.contains(drop_pos):
                target_index = i
                break
        
        if target_index == -1:
            if source_index != -1:
                p = self.players.pop(source_index)
                self.players.append(p)
                self._重新整理佈局()
                self._同步側邊欄順序() 
        else:
            if source_index != -1 and source_index != target_index:
                self.players[source_index], self.players[target_index] = self.players[target_index], self.players[source_index]
                self._重新整理佈局()
                self._同步側邊欄順序()
            
        event.accept()

    def _同步側邊欄順序(self):
        if self.cb_auto_sort.isChecked():
            self.cb_auto_sort.setChecked(False)

        url_order = {self._標準化URL(p.original_stream_url): i for i, p in enumerate(self.players)}
        
        active_items = []
        inactive_items = []
        
        for fav in self.cached_fav_data:
            url = self._標準化URL(fav['url'])
            if url in url_order:
                fav['_sort_order'] = url_order[url]
                active_items.append(fav)
            else:
                inactive_items.append(fav)
        
        active_items.sort(key=lambda x: x['_sort_order'])
        for item in active_items: 
            if '_sort_order' in item: del item['_sort_order']
            
        self.cached_fav_data = active_items + inactive_items
        self._儲存收藏至磁碟(self.cached_fav_data)
        self._渲染收藏列表(check_status=False)

    def _顯示說明(self):
        help_window = HelpWindow(self)
        help_window.exec()
    
    def _標準化URL(self, url):
        if not url: return ""
        try:
            u = unquote(url.strip())
            u = unicodedata.normalize('NFC', u)
            u = u.replace("https://", "").replace("http://", "").replace("www.", "")
            return u.rstrip('/')
        except:
            return str(url).strip()
            
    def _優化YT連結(self, url):
        if not url: return ""
        if "youtube.com" not in url and "youtu.be" not in url: return url
        if "watch?v=" in url: return url
        
        for suffix in ['/streams', '/featured', '/videos', '/shorts', '/live']:
            if suffix in url: url = url.split(suffix)[0]
            
        return url.rstrip('/') + "/live"

    def _從磁碟讀取收藏資料(self):
        self.cached_fav_data = []
        if not os.path.exists(self.favorites_file): return
        try:
            with open(self.favorites_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                
            valid_data = []
            seen_urls = set()
            
            for item in raw_data:
                url = item.get('url')
                if not url or not str(url).strip(): continue
                if item.get('_temp'): continue
                
                norm_url = self._標準化URL(url)
                if norm_url in seen_urls: continue
                
                seen_urls.add(norm_url)
                valid_data.append(item)
            
            self.cached_fav_data = valid_data
            if len(raw_data) != len(valid_data):
                self._儲存收藏至磁碟(valid_data)
                
            self._更新群組下拉選單資料()
        except:
            self.cached_fav_data = []

    def _更新群組下拉選單資料(self):
        current = self.group_combo.currentText()
        groups = set(["Default"])
        for fav in self.cached_fav_data:
            groups.add(fav.get('group', 'Default'))
        
        sorted_groups = sorted(list(groups))
        
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("All")
        self.group_combo.addItems(sorted_groups)
        
        index = self.group_combo.findText(current)
        if index >= 0: self.group_combo.setCurrentIndex(index)
        else: self.group_combo.setCurrentIndex(0)
        self.group_combo.blockSignals(False)

    def _當群組過濾變更時(self, text):
        self.current_group_filter = text
        self._渲染收藏列表(check_status=False)

    def _檢測是否播放中(self, url):
        target_norm = self._標準化URL(self._優化YT連結(url))
        for p in self.players:
            if self._標準化URL(p.original_stream_url) == target_norm:
                if p.is_stream_ended:
                    return False
                return True
        return False

    def _渲染收藏列表(self, check_status=True):
            if self.is_closing_app: return # [Fix] 關閉中不渲染

            self.fav_list.clear()
            
            bold_font = QFont()
            bold_font.setBold(True)
            normal_font = QFont()
            normal_font.setBold(False)

            for fav in self.cached_fav_data:
                group = fav.get('group', 'Default')
                is_temp = fav.get('_temp', False)
                url = fav['url']
                
                if self.current_group_filter == "All" or group == self.current_group_filter:
                    display_name = fav['name']
                    is_playing = self._檢測是否播放中(url)
                    
                    is_live = self.live_status_cache.get(url, False)

                    display_text = ""
                    state_code = 0
                    fore_color = QColor("#000000")
                    font = normal_font

                    if is_playing:
                        display_text = f"▶ {display_name}"
                        state_code = 2
                        fore_color = QColor("#00cc00")
                        font = bold_font
                    elif is_live:
                        prefix = "📺" if is_temp else "🟢"
                        suffix = " (未收藏)" if is_temp else ""
                        display_text = f"{prefix} {display_name}{suffix}"
                        state_code = 1
                        fore_color = QColor("#4dabf7") if self.is_dark_mode else QColor("#007bff")
                        font = normal_font
                    else: # Offline
                        prefix = "📺" if is_temp else "⚫"
                        suffix = " (未收藏)" if is_temp else ""
                        display_text = f"{prefix} {display_name}{suffix}"
                        state_code = 0
                        fore_color = QColor("#666666") if is_temp else (QColor("#aaaaaa") if self.is_dark_mode else QColor("#000000"))
                        font = normal_font

                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, unquote(url))
                    item.setData(Qt.UserRole + 1, fav['name'])
                    item.setData(Qt.UserRole + 2, group)
                    item.setData(Qt.UserRole + 3, state_code) 
                    item.setData(Qt.UserRole + 4, is_temp)

                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    item.setCheckState(Qt.Unchecked)
                    
                    item.setFont(font)
                    item.setForeground(fore_color)
                    
                    self.fav_list.addItem(item)
            
            if check_status:
                self._檢查直播狀態()

    def _自動排序收藏(self):
        if not self.cb_auto_sort.isChecked(): return
        
        items = []
        while self.fav_list.count() > 0:
            items.append(self.fav_list.takeItem(0))
        items.sort(key=lambda x: x.data(Qt.UserRole + 3), reverse=True)
        for item in items: self.fav_list.addItem(item)
        
        self._同步播放器順序()

    def _檢查直播狀態(self):
        if self.is_closing_app: return

        items_to_check = []
        for i in range(self.fav_list.count()):
            item = self.fav_list.item(i)
            items_to_check.append({'url': item.data(Qt.UserRole)})
            
            url = item.data(Qt.UserRole)
            if not self._檢測是否播放中(url):
                base_name = item.data(Qt.UserRole + 1)
                is_temp = item.data(Qt.UserRole + 4)
                
                is_live_cache = self.live_status_cache.get(url, False)
                if is_live_cache:
                    prefix = "📺" if is_temp else "🟢"
                else:
                    prefix = "📺" if is_temp else "🔄" 
                
                suffix = " (未收藏)" if is_temp else ""
                item.setText(f"{prefix} {base_name}{suffix}")
        
        if self.checker_thread and self.checker_thread.isRunning():
            self.checker_thread.stop()
        
        self.checker_thread = 狀態檢查器(items_to_check)
        self.checker_thread.status_updated.connect(self._更新項目狀態)
        self.checker_thread.finished.connect(self._當檢查結束時)
        self.checker_thread.start()

    def _更新項目狀態(self, index, is_live):
            if self.is_closing_app: return

            if index < self.fav_list.count():
                item = self.fav_list.item(index)
                url = item.data(Qt.UserRole)
                name = item.data(Qt.UserRole + 1)
                is_temp = item.data(Qt.UserRole + 4)
                is_playing = self._檢測是否播放中(url)
                
                self.live_status_cache[url] = is_live

                if is_playing:
                    item.setData(Qt.UserRole + 3, 2)
                    item.setText(f"▶ {name}")
                    bold_font = QFont()
                    bold_font.setBold(True)
                    item.setFont(bold_font)
                    item.setForeground(QColor("#00cc00"))
                    return

                item.setData(Qt.UserRole + 3, 1 if is_live else 0)
                suffix = " (未收藏)" if is_temp else ""
                normal_font = QFont()
                item.setFont(normal_font)
                
                if is_live:
                    prefix = "📺" if is_temp else "🟢"
                    item.setText(f"{prefix} {name}{suffix}")
                    item.setForeground(QColor("#4dabf7") if self.is_dark_mode else QColor("#007bff"))
                else:
                    prefix = "📺" if is_temp else "⚫"
                    item.setText(f"{prefix} {name}{suffix}")
                    if is_temp:
                         item.setForeground(QColor("#666666"))
                    else:
                        item.setForeground(QColor("#aaaaaa") if self.is_dark_mode else QColor("#000000"))

    def _當檢查結束時(self):
        if self.cb_auto_sort.isChecked():
            self._自動排序收藏()

    def _新增串流(self, url_text):
            raw_url = self._優化YT連結(url_text.strip())
            if not raw_url: return
            
            norm_new = self._標準化URL(raw_url)
            for p in self.players:
                if self._標準化URL(p.original_stream_url) == norm_new:
                    return
            
            decoded_url = unquote(raw_url) 
            is_known = False
            for fav in self.cached_fav_data:
                if self._標準化URL(fav['url']) == norm_new:
                    is_known = True
                    break
            
            if not is_known:
                temp_name = decoded_url.split('/')[-1] or "Unknown"
                if temp_name == "live":
                    temp_name = decoded_url.split('/')[-2]
                
                new_temp_item = {
                    "name": temp_name,
                    "url": decoded_url,
                    "group": "Default",
                    "_temp": True
                }
                self.cached_fav_data.append(new_temp_item)
                self._渲染收藏列表(check_status=True)
                self._更新群組下拉選單資料()

            try:
                new_player = StreamWidget(decoded_url)
                new_player.request_removal.connect(self._移除串流)
                new_player.fullscreen_toggled.connect(self._當全螢幕切換時)
                new_player.clicked.connect(self._當播放器被點擊_左對右)
                new_player.playing_state_changed.connect(self._當播放狀態改變時)
                
                self.訊號_廣播音量.connect(new_player.set_volume_slot)
                
                if self.is_muted: new_player.set_volume_slot(0)
                else: new_player.set_volume_slot(self.slider.value())
                
                self.players.append(new_player)
                
                self.url_input.clear()
                self._重新整理佈局()
                self._渲染收藏列表(check_status=False)

            except Exception as e: 
                logging.error(f"Error adding stream: {e}")
                if not is_known:
                    self.cached_fav_data.pop()
                    self._渲染收藏列表(check_status=False)
    
    def _當播放狀態改變時(self, is_playing):
        if self.is_closing_app: return
        self._渲染收藏列表(check_status=False)
        if self.cb_auto_sort.isChecked():
            self._自動排序收藏()

    def _當播放器被點擊_左對右(self, target_player):
        should_highlight = not target_player.is_highlighted
        target_norm = self._標準化URL(target_player.original_stream_url)
        
        for p in self.players:
            if p == target_player:
                p.set_highlight(should_highlight)
            else:
                p.set_highlight(False)
        
        self.fav_list.blockSignals(True) 
        
        if should_highlight:
            self.fav_list.clearSelection()
            for i in range(self.fav_list.count()):
                item = self.fav_list.item(i)
                if self._標準化URL(item.data(Qt.UserRole)) == target_norm:
                    item.setSelected(True)
                    self.fav_list.scrollToItem(item)
                    break
            if self.layout_mode == "focus":
                self._重新整理佈局()
        else:
            self.fav_list.clearSelection()
            
        self.fav_list.blockSignals(False)

    def _同步選取狀態_右對左(self, item):
        target_norm = self._標準化URL(item.data(Qt.UserRole))
        target_player = None
        for p in self.players:
            if self._標準化URL(p.original_stream_url) == target_norm:
                target_player = p
                break
        
        if not target_player: return

        should_highlight = not target_player.is_highlighted
        for p in self.players:
            if p == target_player:
                p.set_highlight(should_highlight)
            else:
                p.set_highlight(False)

        if not should_highlight:
            self.fav_list.blockSignals(True)
            self.fav_list.clearSelection()
            self.fav_list.blockSignals(False)
        
        if should_highlight and self.layout_mode == "focus":
            self._重新整理佈局()

    def _清空所有串流(self):
        # [Fix] 如果正在關閉程式，只做必要的銷毀，不做UI更新
        self.load_queue.clear()
        self.load_timer.stop()
        self.loading_batch_count = 0
        
        for p in self.players[:]:
            if p: p.safe_close()
        self.players.clear()
        
        if not self.is_closing_app:
            self._重新整理佈局()
            self.cached_fav_data = [f for f in self.cached_fav_data if not f.get('_temp')]
            self._渲染收藏列表(check_status=False)

    def _移除串流(self, target_player):
        if target_player in self.players:
            target_norm = self._標準化URL(target_player.original_stream_url)
            try: self.訊號_廣播音量.disconnect(target_player.set_volume_slot)
            except: pass
            
            self.players.remove(target_player)
            self._重新整理佈局()
            
            self.cached_fav_data = [
                f for f in self.cached_fav_data 
                if not (self._標準化URL(f['url']) == target_norm and f.get('_temp') is True)
            ]
            self._渲染收藏列表(check_status=False)

            if self.cb_auto_sort.isChecked():
                self._自動排序收藏()

    def _重新整理佈局(self):
        if self.is_closing_app: return

        current_grid_widgets = []
        while self.video_grid.count(): 
            item = self.video_grid.takeAt(0)
            widget = item.widget()
            if widget:
                current_grid_widgets.append(widget)
        
        for r in range(12): self.video_grid.setRowStretch(r, 0)
        for c in range(12): self.video_grid.setColumnStretch(c, 0)
        
        count = len(self.players)
        
        if count == 0: 
            for w in current_grid_widgets:
                w.hide()
            return

        if self.layout_mode == "grid":
            import math
            cols = math.ceil(math.sqrt(count))
            for index, player in enumerate(self.players):
                row = index // cols
                col = index % cols
                if not player.is_fullscreen:
                    self.video_grid.addWidget(player, row, col)
                    player.show() 
                self.video_grid.setRowStretch(row, 1)
                self.video_grid.setColumnStretch(col, 1)
        
        elif self.layout_mode == "focus":
            primary_player = None
            secondary_players = []
            
            for p in self.players:
                if p.is_highlighted:
                    primary_player = p
                    break
            
            if not primary_player:
                primary_player = self.players[0]
            
            secondary_players = [p for p in self.players if p != primary_player]
            
            if not primary_player.is_fullscreen:
                self.video_grid.addWidget(primary_player, 0, 0, max(1, len(secondary_players)), 1)
                primary_player.show()
            
            for i, p in enumerate(secondary_players):
                if not p.is_fullscreen:
                    self.video_grid.addWidget(p, i, 1, 1, 1)
                    p.show()
                self.video_grid.setRowStretch(i, 1)
                
            self.video_grid.setColumnStretch(0, 3) 
            self.video_grid.setColumnStretch(1, 1)

        for w in current_grid_widgets:
            if w not in self.players:
                w.hide()

    def _當全螢幕切換時(self):
        self._重新整理佈局()

    def _設定全局音量(self, value):
        self.last_volume = value
        if value > 0 and self.is_muted:
            self.is_muted = False
            self.btn_mute.setText("🔊")
        self.訊號_廣播音量.emit(value)

    def _切換全局靜音(self):
        if self.is_muted:
            self.is_muted = False
            self.btn_mute.setText("🔊")
            self.slider.setValue(self.last_volume)
        else:
            self.is_muted = True
            self.last_volume = self.slider.value()
            self.btn_mute.setText("🔇")
            self.slider.setValue(0)
    
    def _取得勾選項目(self):
        items = []
        for i in range(self.fav_list.count()):
            item = self.fav_list.item(i)
            if item.checkState() == Qt.Checked:
                items.append(item)
        return items

    def _批量新增群組(self):
        items = self._取得勾選項目()
        if not items:
            QMessageBox.warning(self, "提示", "請先勾選頻道")
            return
        group_name, ok = QInputDialog.getText(self, "新增群組", "群組名稱:")
        if ok and group_name.strip():
            self._批量更新磁碟群組(items, group_name.strip())

    def _批量移動至群組(self):
        items = self._取得勾選項目()
        if not items:
            QMessageBox.warning(self, "提示", "請先勾選頻道")
            return
        groups = set(["Default"])
        for f in self.cached_fav_data: groups.add(f.get('group', 'Default'))
        
        group_name, ok = QInputDialog.getItem(self, "加入群組", "選擇群組:", sorted(list(groups)), 0, False)
        if ok and group_name:
            self._批量更新磁碟群組(items, group_name)

    def _批量更新磁碟群組(self, items, new_group):
        target_names = [item.data(Qt.UserRole + 1) for item in items]
        modified = False
        for fav in self.cached_fav_data:
            if fav['name'] in target_names:
                fav['group'] = new_group
                if '_temp' in fav: del fav['_temp']
                modified = True
        
        if modified:
            self._儲存收藏至磁碟(self.cached_fav_data)
            self._渲染收藏列表(check_status=False)
            self._更新群組下拉選單資料()
            QMessageBox.information(self, "成功", f"已更新 {len(target_names)} 個頻道的群組")

    def _管理群組對話框(self):
        groups = set()
        for f in self.cached_fav_data: groups.add(f.get('group', 'Default'))
        if "Default" in groups: groups.remove("Default")
        
        if not groups:
            QMessageBox.information(self, "提示", "沒有自定義群組")
            return
            
        group_name, ok = QInputDialog.getItem(self, "刪除群組", "選擇要刪除的群組 (內容將回到 Default):", sorted(list(groups)), 0, False)
        if ok and group_name:
            for fav in self.cached_fav_data:
                if fav.get('group') == group_name:
                    fav['group'] = 'Default'
            self._儲存收藏至磁碟(self.cached_fav_data)
            self._渲染收藏列表(check_status=False)
            self._更新群組下拉選單資料()

    # 智慧型載入佇列處理
    def _處理下一個載入請求(self):
        if not self.load_queue:
            self.loading_batch_count = 0 
            return
        
        url = self.load_queue.pop(0)
        self._新增串流(url)
        
        is_youtube = "youtube.com" in url or "youtu.be" in url
        
        if is_youtube:
            logging.info("YouTube detected, using serial loading (3s delay)...")
            next_delay = 3000 
        else:
            self.loading_batch_count += 1
            next_delay = 1000
            if self.loading_batch_count % 4 == 0:
                next_delay = 3000
        
        self.load_timer.start(next_delay)

    def _載入當前群組串流(self):
        self.load_queue.clear()
        self.loading_batch_count = 0
        count = 0
        for i in range(self.fav_list.count()):
            item = self.fav_list.item(i)
            self.load_queue.append(item.data(Qt.UserRole))
            count += 1
        
        if count == 0:
            QMessageBox.information(self, "提示", "當前列表無頻道")
        else:
            self._處理下一個載入請求() 

    def _載入收藏串流(self, item):
        self._新增串流(item.data(Qt.UserRole))

    def _將當前輸入存為收藏(self):
        url = self._優化YT連結(self.url_input.text().strip())
        
        if not url: return
        
        target_norm = self._標準化URL(url)
        target_fav = None
        for fav in self.cached_fav_data:
            if self._標準化URL(fav['url']) == target_norm:
                target_fav = fav
                break
        
        default_name = target_fav['name'] if target_fav else "New Channel"
        name, ok = QInputDialog.getText(self, "加入收藏", "名稱:", text=default_name)
        if ok and name:
            if target_fav:
                target_fav['name'] = name
                if '_temp' in target_fav: del target_fav['_temp']
            else:
                new_fav = {"name": name, "url": unquote(url), "group": "Default"}
                self.cached_fav_data.append(new_fav)
            
            self._儲存收藏至磁碟(self.cached_fav_data)
            self._渲染收藏列表(check_status=True)
            self._更新群組下拉選單資料()

    def _編輯收藏名稱(self):
        row = self.fav_list.currentRow()
        if row < 0: return
        item = self.fav_list.item(row)
        old_name = item.data(Qt.UserRole + 1)
        new_name, ok = QInputDialog.getText(self, "改名", "新名稱:", text=old_name)
        if ok and new_name:
            for fav in self.cached_fav_data:
                if fav['name'] == old_name:
                    fav['name'] = new_name
                    if '_temp' in fav: del fav['_temp']
                    break
            self._儲存收藏至磁碟(self.cached_fav_data)
            self._渲染收藏列表(check_status=False)

    def _刪除收藏(self):
        row = self.fav_list.currentRow()
        if row < 0: return
        item = self.fav_list.item(row)
        
        target_norm = self._標準化URL(item.data(Qt.UserRole))
        
        new_list = []
        for f in self.cached_fav_data:
            if self._標準化URL(f.get('url')) == target_norm:
                continue 
            new_list.append(f)
            
        self.cached_fav_data = new_list
        self._儲存收藏至磁碟(self.cached_fav_data)
        self._渲染收藏列表(check_status=False)

    def _儲存收藏至磁碟(self, data):
        clean_data = [f for f in data if not f.get('_temp')]
        with open(self.favorites_file, 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, indent=4, ensure_ascii=False)

    def _拖曳後儲存順序(self):
        if self.cb_auto_sort.isChecked():
            self.cb_auto_sort.setChecked(False)
            
        visual_names = set()
        new_visual_order = []
        
        for i in range(self.fav_list.count()):
            item = self.fav_list.item(i)
            name = item.data(Qt.UserRole + 1)
            visual_names.add(name)
            
            for f in self.cached_fav_data:
                if f['name'] == name:
                    new_visual_order.append(f)
                    break
        
        hidden_items = [f for f in self.cached_fav_data if f['name'] not in visual_names]
        self.cached_fav_data = new_visual_order + hidden_items
        self._儲存收藏至磁碟(self.cached_fav_data)
        self._同步播放器順序()

    def _同步播放器順序(self):
        if not self.players: return
        
        url_order_map = {}
        for i in range(self.fav_list.count()):
            item = self.fav_list.item(i)
            url = self._標準化URL(item.data(Qt.UserRole))
            url_order_map[url] = i
        
        def sort_key(player):
            p_url = self._標準化URL(player.original_stream_url)
            return url_order_map.get(p_url, 9999)

        self.players.sort(key=sort_key)
        self._重新整理佈局()

    def _開啟選取的收藏(self):
        self.load_queue.clear()
        self.loading_batch_count = 0
        items = self._取得勾選項目()
        for item in items:
            self.load_queue.append(item.data(Qt.UserRole))
            item.setCheckState(Qt.Unchecked)
        
        if self.load_queue:
            self._處理下一個載入請求()

    def _開啟直播中收藏(self):
        self.load_queue.clear()
        self.loading_batch_count = 0
        count = 0
        for i in range(self.fav_list.count()):
            item = self.fav_list.item(i)
            if item.data(Qt.UserRole + 3) == 1:
                self.load_queue.append(item.data(Qt.UserRole))
                count += 1
        if count == 0: QMessageBox.information(self, "提示", "無直播中頻道")
        else: self._處理下一個載入請求()

    def _匯出收藏(self):
        fp, _ = QFileDialog.getSaveFileName(self, "匯出收藏", "favs.json", "JSON (*.json)")
        if fp:
            clean_data = [f for f in self.cached_fav_data if not f.get('_temp')]
            with open(fp, 'w', encoding='utf-8') as f: json.dump(clean_data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "OK", "匯出成功")

    def _匯入收藏(self):
        fp, _ = QFileDialog.getOpenFileName(self, "匯入收藏", "", "JSON (*.json)")
        if fp:
            try:
                with open(fp, 'r', encoding='utf-8') as f: d = json.load(f)
                if isinstance(d, list):
                    self.cached_fav_data = d
                    self._儲存收藏至磁碟(d)
                    self._渲染收藏列表(check_status=True)
                    self._更新群組下拉選單資料()
                    QMessageBox.information(self, "OK", "匯入成功")
            except: QMessageBox.warning(self, "Err", "匯入失敗")

    def _切換主題(self):
        self.is_dark_mode = not self.is_dark_mode
        self._套用主題()

    def _套用主題(self):
        if self.is_dark_mode:
            self.setStyleSheet(DARK_STYLE)
            self.video_area.setStyleSheet("background-color: #121212;")
            self.btn_theme_toggle.setText("☀️")
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self.video_area.setStyleSheet("background-color: #dcdcdc;")
            self.btn_theme_toggle.setText("🌙")

    def _切換佈局模式(self):
        self.layout_mode = "focus" if self.layout_mode == "grid" else "grid"
        self.btn_layout_toggle.setText("▣ 焦點" if self.layout_mode == "grid" else "⊞ 網格")
        self._重新整理佈局()

    def _切換側邊欄(self):
        self.sidebar_visible = not self.sidebar_visible
        self.sidebar.setVisible(self.sidebar_visible)
        self.toggle_sidebar_btn.setText("▶" if self.sidebar_visible else "◀")

    def _重整所有串流(self):
        logging.info("Global Reload Triggered: Staggering reload requests...")
        widgets = [p for p in self.players if hasattr(p, 'force_reload_stream')]
        if widgets:
            self._分批重整遞迴(widgets, 0)
        else:
            logging.warning("Legacy reload fallback (No force_reload_stream found)")
            for p in self.players:
                p._start_stream_loading(p._get_current_quality_code())

    def _分批重整遞迴(self, widgets, index):
        if index >= len(widgets):
            logging.info("Global Reload Complete.")
            return

        widget = widgets[index]
        try:
            widget.force_reload_stream()
        except Exception as e:
            logging.error(f"Error reloading widget {index}: {e}")

        QTimer.singleShot(300, lambda: self._分批重整遞迴(widgets, index + 1))
    
    def _顯示收藏右鍵選單(self, pos):
        item = self.fav_list.itemAt(pos)
        if not item: return
        menu = QMenu(self)
        
        current_g = item.data(Qt.UserRole + 2)
        label_action = QAction(f"當前群組: {current_g}", self)
        label_action.setEnabled(False)
        menu.addAction(label_action)
        menu.addSeparator()

        move_menu = menu.addMenu("移動到群組...")
        groups = set(["Default"])
        for f in self.cached_fav_data: groups.add(f.get('group', 'Default'))
        
        for g in sorted(list(groups)):
            action = QAction(g, self)
            action.triggered.connect(lambda checked, g=g: self._批量更新磁碟群組([item], g))
            move_menu.addAction(action)
            
        new_group_action = QAction("➕ 新增群組...", self)
        new_group_action.triggered.connect(lambda: self._批量新增群組())
        move_menu.addAction(new_group_action)
        menu.exec_(self.fav_list.mapToGlobal(pos))

    # [Fix] 關閉程式時強制結束所有執行緒
    def closeEvent(self, event):
        self.is_closing_app = True # 鎖定UI
        self._清空所有串流()
        super().closeEvent(event)
        # 強制自殺，防止背景執行緒卡死黑窗
        QTimer.singleShot(100, lambda: sys.exit(0))

def main():
    os.environ["QT_FONT_DPI"] = "96"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --no-sandbox"
    app = QApplication(sys.argv)
    
    default_profile = QWebEngineProfile.defaultProfile()
    storage_path = os.path.abspath(os.path.join(data_dir, "browser_data"))
    if not os.path.exists(storage_path): os.makedirs(storage_path)
    default_profile.setPersistentStoragePath(storage_path)
    cookie_file = os.path.join(data_dir, "cookies.json")
    if os.path.exists(cookie_file):
        CookieManager.load_cookies(cookie_file, default_profile)
        
    window = 主視窗()
    icon_path = os.path.join(internal_path, "01.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        window.setWindowIcon(QIcon(icon_path))
        
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()