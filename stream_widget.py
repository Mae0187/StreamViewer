import logging
import os
import sys
import requests
import mpv
import streamlink
import webbrowser
import time
import traceback
import subprocess  
import signal
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, 
                               QLabel, QFrame, QSizePolicy, QMessageBox, QComboBox, 
                               QApplication, QStackedWidget)
from PySide6.QtCore import Qt, Signal, QThread, QEvent, QObject, QMimeData, QPoint, QTimer
from PySide6.QtGui import QCursor, QDrag, QFont
from cookie_manager import CookieManager

# [背景清理執行緒]
class CleanupThread(QThread):
    def __init__(self, mpv_instance, rec_process=None):
        super().__init__()
        self.mpv = mpv_instance
        self.rec_pid = None
        if rec_process and hasattr(rec_process, 'pid'):
            self.rec_pid = rec_process.pid
        self.daemon = True # [Fix] 設為守護執行緒，防止程式退出時卡住
        self.daemon = True # [Fix] 設為守護執行緒，防止程式退出時卡住

    def run(self):
        # 1. 強制清理錄影程序 (使用預先存下的 PID)
        if self.rec_pid:
            try:
                logging.info(f"CleanupThread: Terminating recorder PID {self.rec_pid}")
                subprocess.run(f"taskkill /F /T /PID {self.rec_pid}", shell=True, capture_output=True)
            except Exception as e:
                logging.error(f"Cleanup record process error: {e}")

        # 2. 清理 MPV
        if self.mpv:
            try:
                self.mpv.stop()
                self.mpv.terminate()
            except Exception as e:
                logging.error(f"Background cleanup error: {e}")

# [串流載入器]
class StreamLoader(QThread):
    stream_found = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, url, quality_preference="best"):
        super().__init__()
        self.url = url
        self.quality = quality_preference
        self._is_running = True

    def _check_yt_fast(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
            res = requests.get(url, headers=headers, timeout=10)
            if '"isLiveNow":true' in res.text or 'hqdefault_live.jpg' in res.text:
                return True
            return False
        except:
            return False

    def run(self):
        # YouTube 專用通道
        if "youtube.com" in self.url or "youtu.be" in self.url:
            if not self._check_yt_fast(self.url):
                self.error_occurred.emit("Stream Offline (YouTube Check)")
                return
            logging.info(f"YouTube detected ({self.url}) -> 啟動 MPV 直連模式")
            self.stream_found.emit(self.url)
            return

        try:
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
            
            is_soop = "sooplive" in self.url or "afreecatv" in self.url
            is_twitch = "twitch.tv" in self.url

            if is_soop:
                headers["Referer"] = "https://www.sooplive.co.kr/"
                headers["Origin"] = "https://www.sooplive.co.kr"
            
            session.set_option("http-headers", headers)
            
            if is_soop:
                cookies = CookieManager.get_cookies_for_streamlink()
                if cookies:
                    session.http.cookies.update(cookies)
                    for name, value in cookies.items():
                        session.http.cookies.set(name, value, domain=".afreecatv.com")
                        session.http.cookies.set(name, value, domain=".sooplive.co.kr")
                        session.http.cookies.set(name, value, domain="play.sooplive.co.kr")
            
            session.set_option("http-timeout", 20.0)
            session.set_option("stream-segment-timeout", 20.0)
            session.set_option("stream-timeout", 20.0)

            if not self._is_running: return

            try:
                streams = session.streams(self.url)
            except streamlink.exceptions.NoPluginError:
                self.stream_found.emit(self.url)
                return
            except Exception as pe:
                err_str = str(pe).lower()
                if "404" in err_str and is_twitch:
                    self.error_occurred.emit("Stream Offline (Twitch 404)")
                    return
                fallback_keywords = ["login", "age", "adult", "verification", "19+", "premium"]
                if any(k in err_str for k in fallback_keywords):
                    self.stream_found.emit(self.url)
                    return
                raise pe

            if not streams:
                if is_twitch or is_soop:
                    self.error_occurred.emit("Stream Offline (No streams found)")
                else:
                    self.stream_found.emit(self.url)
                return

            if not self._is_running: return

            stream_url = ""
            priority = []
            if self.quality == "1080p": priority = ["1080p60", "1080p", "best"]
            elif self.quality == "720p": priority = ["720p60", "720p", "best"]
            elif self.quality == "480p": priority = ["480p", "360p", "worst"]
            elif self.quality == "audio": priority = ["audio_only", "audio", "worst"]
            else: priority = ["best"]

            for q in priority:
                if q in streams:
                    stream_url = streams[q].url
                    break
            
            if not stream_url and 'best' in streams:
                stream_url = streams['best'].url
            
            if stream_url:
                self.stream_found.emit(stream_url)
            else:
                key = list(streams.keys())[0]
                self.stream_found.emit(streams[key].url)

        except Exception as e:
            if self._is_running:
                logging.error(f"Critical Stream Error: {traceback.format_exc()}")
                self.error_occurred.emit(str(e))

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()

class StreamWidget(QFrame):
    request_removal = Signal(QWidget)
    fullscreen_toggled = Signal() 
    clicked = Signal(object) 
    mpv_state_change = Signal(str, bool) 
    on_player_eof = Signal() 
    playing_state_changed = Signal(bool) 

    def __init__(self, url: str):
        super().__init__()
        self.setObjectName("StreamCard")
        self.original_stream_url = url
        self.current_play_url = None 
        self.mpv_player = None
        self.loader = None
        self.cleanup_worker = None
        self.is_fullscreen = False
        
        self.is_recording = False
        self.rec_process = None 
        
        self.is_closing = False
        self.is_highlighted = False 
        
        self.is_switching_stream = False
        self.is_stream_ended = False 
        
        self.retry_count = 0 
        self.max_retries = 999 
        self.consecutive_stuck_count = 0 
        
        self.last_time_pos = None
        self.startup_wait_count = 0
        self.stable_playback_count = 0 
        
        self.play_start_time = 0
        self.short_session_count = 0
        self.offline_check_count = 0 
        
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.setInterval(600) 
        self.watchdog_timer.timeout.connect(self._watchdog_check)
        
        self.drag_start_pos = QPoint()
        self.is_right_pressed = False
        
        self.record_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "recordings"))
        if not os.path.exists(self.record_path): os.makedirs(self.record_path)
        
        self.setStyleSheet("#StreamCard { border: 4px solid transparent; background-color: #000; }")

        self.on_player_eof.connect(self._handle_eof_detection)
        self.mpv_state_change.connect(self._handle_mpv_state)

        self._init_ui()
        self._start_stream_loading("best")
        
        self.video_container.installEventFilter(self)
        self.end_screen.installEventFilter(self)

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.stack_widget = QStackedWidget()
        
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: black; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        self.video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_container.setAttribute(Qt.WA_NativeWindow)
        self.video_container.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.video_container.mouseDoubleClickEvent = self._toggle_fullscreen
        
        self.end_screen = QWidget()
        self.end_screen.setStyleSheet("background-color: #222222; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        end_layout = QVBoxLayout(self.end_screen)
        end_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.setSpacing(15)
        
        self.end_label = QLabel("直播已結束")
        self.end_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-family: 'Microsoft JhengHei'; font-size: 28px;")
        
        self.retry_btn = QPushButton(" ⟳ 點擊重試 ")
        self.retry_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.retry_btn.setStyleSheet("QPushButton { background-color: #444; color: white; border: 1px solid #666; padding: 10px 20px; border-radius: 6px; font-size: 16px; font-weight: bold; } QPushButton:hover { background-color: #555; border-color: #888; }")
        self.retry_btn.clicked.connect(self._manual_reload)
        
        end_layout.addWidget(self.end_label)
        end_layout.addWidget(self.retry_btn)
        
        self.stack_widget.addWidget(self.video_container) 
        self.stack_widget.addWidget(self.end_screen)      
        
        self.control_bar = QWidget()
        self.control_bar.setFixedHeight(45)
        self.control_bar.setObjectName("ControlBar")
        
        control_layout = QHBoxLayout(self.control_bar)
        control_layout.setContentsMargins(5, 0, 5, 0)
        control_layout.setSpacing(5)
        
        vol_label = QLabel("🔊")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(50)
        self.vol_slider.setFixedWidth(60)
        self.vol_slider.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.vol_slider.valueChanged.connect(self._on_manual_volume_change)
        
        self.quality_combo = QComboBox()
        self.quality_combo.setFixedWidth(70)
        self.quality_combo.addItems(["最佳", "1080p", "720p", "480p", "純音訊"])
        self.quality_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)

        self.snap_btn = QPushButton("📷")
        self.snap_btn.setFixedSize(28, 28)
        self.snap_btn.setToolTip("截圖")
        self.snap_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.snap_btn.clicked.connect(self._take_snapshot)

        self.rec_btn = QPushButton("🔴")
        self.rec_btn.setFixedSize(28, 28)
        self.rec_btn.setToolTip("開始錄影")
        self.rec_btn.setObjectName("RecordBtn")
        self.rec_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rec_btn.clicked.connect(self._toggle_recording)

        self.chat_btn = QPushButton("📺")
        self.chat_btn.setFixedSize(28, 28)
        self.chat_btn.setToolTip("開啟直播原網址")
        self.chat_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.chat_btn.clicked.connect(self._open_chat)

        self.reload_btn = QPushButton("🔄")
        self.reload_btn.setFixedSize(28, 28)
        self.reload_btn.setToolTip("重新載入 (Hard Reset)")
        self.reload_btn.setObjectName("ReloadBtn")
        self.reload_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reload_btn.clicked.connect(self._manual_reload)

        self.status_label = QLabel("準備中...")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_btn.clicked.connect(self.safe_close)
        
        control_layout.addWidget(vol_label)
        control_layout.addWidget(self.vol_slider)
        control_layout.addWidget(self.quality_combo)
        control_layout.addWidget(self.snap_btn)
        control_layout.addWidget(self.rec_btn)
        control_layout.addWidget(self.chat_btn)
        control_layout.addWidget(self.reload_btn)
        control_layout.addWidget(self.status_label)
        control_layout.addStretch()
        control_layout.addWidget(self.close_btn)
        
        self.main_layout.addWidget(self.stack_widget)
        self.main_layout.addWidget(self.control_bar)

    def _init_mpv(self):
        try:
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            if base_path not in os.environ["PATH"]:
                os.environ["PATH"] += os.pathsep + base_path

            is_youtube = "youtube.com" in self.original_stream_url or "youtu.be" in self.original_stream_url
            
            mpv_kwargs = {
                'wid': str(int(self.video_container.winId())),
                'input_default_bindings': True,
                'input_vo_keyboard': True,
                'ytdl': True,
                'hwdec': 'auto',
                'vo': 'gpu',
                'gpu_context': 'd3d11',
                'keep_open': 'yes',
            }

            if is_youtube:
                logging.info("MPV Profile: YouTube Stability Mode (Buffering Enabled)")
                mpv_kwargs['profile'] = 'gpu-hq'
                self.mpv_player = mpv.MPV(**mpv_kwargs)
                self.mpv_player['cache'] = 'yes'
                self.mpv_player['cache-secs'] = 45 
                self.mpv_player['demuxer-readahead-secs'] = 30
            else:
                logging.info("MPV Profile: Low Latency Mode")
                mpv_kwargs['profile'] = 'low-latency'
                self.mpv_player = mpv.MPV(**mpv_kwargs)
                self.mpv_player['network-timeout'] = 30  
                self.mpv_player['stream-buffer-size'] = '10MiB' 
                self.mpv_player['demuxer-max-bytes'] = '100MiB'
            
            cookie_path = os.path.join(base_path, "cookies.json")
            if os.path.exists(cookie_path):
                # 只有 SOOP 和 AfreecaTV 需要注入 Cookie，YouTube 恢復為直連模式以避免讀取失敗
                if "sooplive.co.kr" in self.original_stream_url or "afreecatv.com" in self.original_stream_url:
                    self.mpv_player['ytdl-raw-options'] = f"cookies={cookie_path}"
                    logging.info(f"MPV: applied cookies for SOOP/AfreecaTV from {cookie_path}")
                else:
                    # YouTube 及其它平台不使用 Cookie
                    self.mpv_player['ytdl-raw-options'] = ""
            
            @self.mpv_player.property_observer('eof-reached')
            def eof_observer(_name, value):
                if value:
                    QTimer.singleShot(0, self.on_player_eof.emit)

        except Exception as e:
            self.status_label.setText("MPV 錯誤")
            logging.error(f"MPV Init Error: {e}")

    def _handle_mpv_state(self, msg, is_idle):
        if self.is_closing: return
        self.status_label.setText(msg)

    def _watchdog_check(self):
        if self.is_closing or self.is_switching_stream or self.is_stream_ended: return
        if self.stack_widget.currentIndex() == 1: return
        if not self.mpv_player: return

        is_youtube = "youtube.com" in self.original_stream_url or "youtu.be" in self.original_stream_url
        startup_threshold = 60 if is_youtube else 25 # YouTube 需要更長時間啟動

        try:
            if self.mpv_player.eof_reached:
                self._handle_eof_detection()
                return
        except: pass

        try:
            current_pos = self.mpv_player.time_pos
            is_paused = self.mpv_player.pause
            core_idle = self.mpv_player.core_idle
            idle_active = getattr(self.mpv_player, 'idle_active', False)
        except: return

        if current_pos is None:
            # 如果還在載入中 (core_idle 或 idle_active 為 True 表示尚未有數據流)
            if core_idle or idle_active: 
                self.startup_wait_count += 1
            else: 
                self.startup_wait_count = 0
            
            if self.startup_wait_count > startup_threshold:
                logging.warning(f"Watchdog: Startup timeout reached for {self.original_stream_url} (Count: {self.startup_wait_count})")
                self._trigger_retry_logic()
            return

        self.startup_wait_count = 0
        
        if current_pos == self.last_time_pos and not is_paused:
            self.consecutive_stuck_count += 1
            # 增加寬限期，避免網絡短暫波動導致重啟
            if self.consecutive_stuck_count > 15: 
                logging.warning(f"Watchdog: Playback stuck at {current_pos} for {self.original_stream_url}")
                self._trigger_retry_logic()
        else:
            if self.consecutive_stuck_count > 0: self.status_label.setText("直播中")
            self.consecutive_stuck_count = 0
            self.last_time_pos = current_pos
            self.stable_playback_count += 1
            if self.stable_playback_count > 10:
                self.retry_count = 0
                self.short_session_count = 0 

    def _trigger_retry_logic(self):
        if self.is_switching_stream: return
        
        # 增加判斷閾值至 60 秒，以應對 YouTube 較慢的啟動過程
        session_duration = time.time() - self.play_start_time
        if session_duration < 60 and self.play_start_time > 0:
            self.short_session_count += 1
            logging.info(f"Short session detected ({session_duration:.1f}s). Count: {self.short_session_count}/5")
        
        if self.short_session_count >= 5:
            logging.info(f"Too many short sessions for {self.original_stream_url}, stopping.")
            self._show_end_screen()
            return
        
        self.retry_count += 1
        if self.retry_count <= self.max_retries:
            self.status_label.setText(f"重連 ({self.retry_count})...")
            self.consecutive_stuck_count = 0
            self.startup_wait_count = 0
            
            force_reinit = (self.retry_count > 1)
            QTimer.singleShot(1000, lambda: self._start_stream_loading(self._get_current_quality_code(), force_reinit=force_reinit))
        else:
            logging.info(f"Max retries ({self.max_retries}) reached for {self.original_stream_url}")
            self._show_end_screen()

    def force_reload_stream(self):
        self._manual_reload()

    def _manual_reload(self):
        logging.info(f"Manual Reload triggered for {self.original_stream_url}")
        self.retry_count = 0
        self.consecutive_stuck_count = 0
        self.startup_wait_count = 0
        self.offline_check_count = 0
        self._start_stream_loading(self._get_current_quality_code(), force_reinit=True)

    def _handle_eof_detection(self):
        if self.is_closing or self.is_switching_stream: return
        
        live_duration = time.time() - self.play_start_time
        # 如果播放時間極短，直接進重試邏輯（會增加 short_session_count）
        if live_duration < 10 and self.play_start_time > 0:
             self._trigger_retry_logic()
             return
             
        # 若是正常播放後結束，嘗試重連，但也要增加 retry_count 避免無限循環
        self.retry_count += 1
        if self.retry_count > 20: # 給予正常結束較寬鬆的重試機會
            self._show_end_screen()
            return

        self.status_label.setText("確認直播狀態...")
        QTimer.singleShot(2000, lambda: self._start_stream_loading(self._get_current_quality_code()))

    def _show_end_screen(self):
        if self.is_switching_stream or self.is_stream_ended: return
        if self.is_closing: return
        self.is_stream_ended = True
        self.playing_state_changed.emit(False)
        self.watchdog_timer.stop() 
        if self.mpv_player:
            try: self.mpv_player.stop()
            except: pass
        self.video_container.hide()
        self.stack_widget.setCurrentIndex(1)
        self.end_screen.show()
        self.status_label.setText("直播已結束")

    def _apply_headers_based_on_url(self):
        if not self.mpv_player: return
        try:
            if "sooplive.co.kr" in self.original_stream_url or "afreecatv.com" in self.original_stream_url:
                headers = [
                    "Referer: https://www.sooplive.co.kr/",
                    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ]
                self.mpv_player['http-header-fields'] = headers
            else:
                self.mpv_player['http-header-fields'] = []
        except Exception as e:
            logging.error(f"Failed to apply headers: {e}")

    def _on_stream_found(self, stream_url):
        self.is_switching_stream = False
        if self.is_closing: return
        self.status_label.setText("連接中...")
        self.current_play_url = stream_url
        self.play_start_time = time.time()
        self.offline_check_count = 0 
        self.stable_playback_count = 0 
        self.playing_state_changed.emit(True)
        if self.mpv_player:
            try:
                self._apply_headers_based_on_url()
                self.mpv_player.play(stream_url)
                self.mpv_player.volume = self.vol_slider.value()
            except: pass

    def _on_stream_error(self, error_msg):
        self.is_switching_stream = False
        if self.is_closing: return
        if "Stream Offline" in error_msg or "No streams found" in error_msg:
             if self.offline_check_count >= 3:
                 self._show_end_screen()
             else:
                 self.offline_check_count += 1
                 self.status_label.setText(f"確認訊號中 ({self.offline_check_count}/3)...")
                 self._trigger_retry_logic() 
             return
        self.offline_check_count = 0
        self.status_label.setText("錯誤")
        self._trigger_retry_logic()

    def _open_chat(self):
        try: webbrowser.open(self.original_stream_url)
        except Exception as e: logging.error(f"開啟網頁失敗: {e}")

    def safe_close(self):
        self.is_closing = True
        self.watchdog_timer.stop() 
        if self.loader:
            if self.loader.isRunning(): self.loader.stop()
            self.loader.deleteLater()
            self.loader = None
        if self.mpv_player:
            try: self.mpv_player.wid = None
            except: pass
            self.cleanup_worker = CleanupThread(self.mpv_player, self.rec_process)
            self.cleanup_worker.finished.connect(self.cleanup_worker.deleteLater)
            self.cleanup_worker.start()
            self.mpv_player = None
        self.request_removal.emit(self)

    def closeEvent(self, event):
        self.safe_close()
        super().closeEvent(event)
    
    # [關鍵修正]: 攔截 video_container 的右鍵以觸發拖曳
    def eventFilter(self, source, event):
        if source == self.video_container or source == self.end_screen:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.clicked.emit(self)
                    return True
                elif event.button() == Qt.RightButton:
                    self.is_right_pressed = True
                    self.drag_start_pos = event.pos()
                    return True # [Fix]: 必須 return True，否則事件會被 MPV 搶走
            elif event.type() == QEvent.MouseMove:
                if self.is_right_pressed and (event.buttons() & Qt.RightButton):
                    if (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                        self._start_drag()
                        self.is_right_pressed = False
                        return True
            elif event.type() == QEvent.MouseButtonRelease:
                self.is_right_pressed = False
        return super().eventFilter(source, event)
    
    def _start_drag(self):
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.original_stream_url) 
        mime_data.setData("application/x-stream-url", self.original_stream_url.encode('utf-8'))
        drag.setMimeData(mime_data)
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaled(200, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.setHotSpot(QPoint(100, 75))
        drag.exec_(Qt.MoveAction)

    # [關鍵修正]: 補上 Frame 層級的事件處理，讓操作列也能拖曳
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        elif event.button() == Qt.RightButton:
            self.is_right_pressed = True
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_right_pressed and (event.buttons() & Qt.RightButton):
            if (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                self._start_drag()
                self.is_right_pressed = False
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_right_pressed = False
        super().mouseReleaseEvent(event)
        
    def set_highlight(self, enable: bool):
        self.is_highlighted = enable
        border_color = "#ff0000" if enable else "transparent"
        self.setStyleSheet(f"#StreamCard {{ border: 4px solid {border_color}; background-color: #000; }}")

    def set_volume_slot(self, value):
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(value)
        self.vol_slider.blockSignals(False)
        if self.mpv_player:
            try: self.mpv_player.volume = value
            except: pass

    def _on_manual_volume_change(self, value):
        if self.mpv_player:
            try: self.mpv_player.volume = value
            except: pass

    def _toggle_fullscreen(self, event=None):
        if not self.is_fullscreen:
            self.setWindowFlags(Qt.Window)
            self.showFullScreen()
            self.control_bar.hide()
            self.is_fullscreen = True
        else:
            self.setWindowFlags(Qt.Widget)
            self.showNormal()
            self.control_bar.show()
            self.is_fullscreen = False
            self.fullscreen_toggled.emit()
        if self.mpv_player:
            try: self.mpv_player.wid = str(int(self.video_container.winId()))
            except: pass

    def _take_snapshot(self):
        if not self.mpv_player: return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snap_{timestamp}.jpg"
        filepath = os.path.join(self.record_path, filename)
        try:
            self.mpv_player.screenshot_to_file(filepath)
            self.status_label.setText("已截圖")
            QThread.msleep(100)
        except Exception as e:
            logging.error(f"Snapshot error: {e}")

    def _toggle_recording(self):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        if self.is_recording:
            if self.rec_process:
                self.status_label.setText("存檔中...")
                try:
                    pid = self.rec_process.pid
                    logging.info(f"Stopping recording by killing PID: {pid}")
                    subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    logging.error(f"Error killing recorder: {e}")
                self.rec_process = None
            
            self.is_recording = False
            self.rec_btn.setStyleSheet("")
            self.status_label.setText("錄影完成")
            QMessageBox.information(self, "錄影完成", "檔案已儲存。")
            return

        record_url = self.current_play_url
        if not record_url:
            QMessageBox.warning(self, "錯誤", "尚未獲取到串流，無法錄影。")
            return
            
        try:
            self.record_path.encode('ascii')
        except UnicodeEncodeError:
            if QMessageBox.warning(self, "警告", "路徑含中文可能導致錄影失敗，建議移至純英文路徑。\n繼續？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
                return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rec_{timestamp}.mkv"
        filepath = os.path.join(self.record_path, filename)
        
        cmd = []
        is_youtube = "youtube.com" in record_url or "youtu.be" in record_url
        
        if is_youtube:
            yt_dlp_path = os.path.join(base_path, "yt-dlp.exe")
            if not os.path.exists(yt_dlp_path):
                yt_dlp_path = "yt-dlp" 
            
            logging.info(f"Starting YT-DLP recording (No Cookie Mode) for: {self.original_stream_url}")
            
            cmd = [
                yt_dlp_path,
                "--no-part",       
                "--no-keep-video", 
                "-f", "bestvideo+bestaudio/best",
                "-o", filepath,
                self.original_stream_url 
            ]
            self.status_label.setText("錄影中(yt-dlp)...")
            
        else:
            ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                QMessageBox.critical(self, "錯誤", "找不到 ffmpeg.exe")
                return
                
            cmd = [
                ffmpeg_path,
                "-y", "-hide_banner", "-loglevel", "error",
                "-i", record_url,
                "-c", "copy",
                "-f", "matroska",
                filepath
            ]
            self.status_label.setText("錄影中(FFmpeg)...")

        try:
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = subprocess.SW_HIDE
            
            self.rec_process = subprocess.Popen(
                cmd,
                startupinfo=startup_info,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.is_recording = True
            self.rec_btn.setStyleSheet("background-color: #ff3333; border: 2px solid white;")
            
        except Exception as e:
            logging.error(f"Record start error: {e}")
            self.status_label.setText("錄影啟動失敗")
            QMessageBox.critical(self, "錄影錯誤", f"無法啟動錄影程序: {e}")

    def _get_current_quality_code(self):
        txt = self.quality_combo.currentText()
        map_code = { "最佳": "best", "1080p": "1080p", "720p": "720p", "480p": "480p", "純音訊": "audio" }
        return map_code.get(txt, "best")

    def _on_quality_changed(self):
        self.retry_count = 0
        quality = self._get_current_quality_code()
        self._start_stream_loading(quality)

    def _start_stream_loading(self, quality="best", force_reinit=False):
        self.is_switching_stream = True
        self.is_stream_ended = False
        
        self.consecutive_stuck_count = 0
        self.startup_wait_count = 0
        self.last_time_pos = None
        self.watchdog_timer.start() 
        
        self.video_container.setVisible(True)
        self.end_screen.setVisible(False)
        self.stack_widget.setCurrentIndex(0)
        
        if force_reinit and self.mpv_player:
            logging.info("Forcing MPV Re-initialization...")
            try:
                self.mpv_player.stop()
                self.mpv_player.terminate()
            except: pass
            self.mpv_player = None

        if self.mpv_player is None: self._init_mpv()
        if self.loader and self.loader.isRunning(): self.loader.stop()
        
        self.status_label.setText(f"解析 {quality}...")
        
        if self.mpv_player:
            try: self.mpv_player.stop()
            except: pass
        
        self.loader = StreamLoader(self.original_stream_url, quality)
        self.loader.stream_found.connect(self._on_stream_found)
        self.loader.error_occurred.connect(self._on_stream_error)
        self.loader.start()
