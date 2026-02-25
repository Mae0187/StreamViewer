import re

class UrlParser:
    @staticmethod
    def parse_stream_url(original_url: str) -> str:
        url = original_url.strip()
        if "sooplive.co.kr" in url or "afreecatv.com" in url:
            if "/play/" in url: return url
            try:
                match = re.search(r"(?:sooplive\.co\.kr|afreecatv\.com)/([^/?]+)", url)
                if match: return f"https://play.sooplive.co.kr/{match.group(1)}"
            except: pass
        if "twitch.tv" in url:
            try: return f"https://player.twitch.tv/?channel={url.split('/')[-1]}&parent=localhost"
            except: pass
        if "youtube.com" in url or "youtu.be" in url:
            try:
                vid = url.split('v=')[1].split('&')[0] if "v=" in url else url.split('/')[-1]
                if vid: return f"https://www.youtube.com/embed/{vid}?autoplay=1"
            except: pass
        return url
