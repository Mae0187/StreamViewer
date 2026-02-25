import json
import logging
import os
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtCore import QDateTime, QUrl

class CookieManager:
    """
    Cookie 管理器：負責載入 cookies.json 並轉換格式供 Streamlink 使用。
    """
    
    _cached_cookies_dict = {}

    @staticmethod
    def load_cookies(file_path: str, profile: QWebEngineProfile):
        if not os.path.exists(file_path):
            logging.warning(f"Cookie 檔案不存在: {file_path}")
            return

        try:
            logging.info(f"正在載入 Cookie: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)

            cookie_store = profile.cookieStore()
            count = 0
            CookieManager._cached_cookies_dict = {}

            for item in cookie_data:
                name = item.get('name', '')
                value = item.get('value', '')
                domain = item.get('domain', '')
                
                if not name: continue

                # 1. 注入到 QtWebEngine (保留給登入視窗使用)
                q_cookie = QNetworkCookie(name.encode(), value.encode())
                if domain: q_cookie.setDomain(domain)
                q_cookie.setPath(item.get('path', '/'))
                q_cookie.setSecure(item.get('secure', False))
                q_cookie.setHttpOnly(item.get('httpOnly', False))
                if item.get('expirationDate'):
                    q_cookie.setExpirationDate(QDateTime.fromSecsSinceEpoch(int(item.get('expirationDate'))))
                
                cookie_store.setCookie(q_cookie, QUrl(f"https://{domain.lstrip('.')}"))
                
                # 2. 快取給 Streamlink 使用
                CookieManager._cached_cookies_dict[name] = value
                count += 1

            logging.info(f"成功注入 {count} 個 Cookie。")
            
        except json.JSONDecodeError:
            logging.error("Cookie 檔案格式錯誤，請確認是否為有效的 JSON。")
        except Exception as e:
            logging.error(f"載入 Cookie 時發生錯誤: {e}", exc_info=True)

    @staticmethod
    def get_cookies_for_streamlink():
        """
        回傳 Python 字典格式的 Cookies，供 Streamlink 使用。
        """
        return CookieManager._cached_cookies_dict