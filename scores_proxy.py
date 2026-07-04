"""
World Cup live score proxy server.
Serves worldcup.html on localhost + proxies ESPN & Baidu APIs for live scores.

Sources (in order of preference):
  1. ESPN API (primary, official, free, no CORS)
  2. Baidu Sports (fallback)

Usage: python3 scores_proxy.py
Then open http://localhost:8765 in browser.

Deploy: Render.com (free tier, auto-deploy from GitHub)
"""
import http.server
import urllib.request
import json
import re
import os
import datetime
import time as _time
from html import unescape

PORT = int(os.environ.get("PORT", 8765))
BIND = "0.0.0.0"
HTML_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== ESPN API ==========
# Request yesterday + today + tomorrow to handle timezone differences

def build_espn_url(date_str):
    """Build ESPN scoreboard URL for a specific date (YYYYMMDD format)."""
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?limit=100&dates={date_str}"

# English (ESPN) / Chinese (frontend) team name mapping
# Keys: lower-case English name or ESPN abbreviation
TEAM_EN_TO_CN = {
    # A
    "mexico": "墨西哥", "mex": "墨西哥",
    "south africa": "南非", "bafana": "南非", "rsa": "南非",
    # B
    "canada": "加拿大", "can": "加拿大",
    "bosnia": "波黑", "bosnia and herzegovina": "波黑", "bih": "波黑",
    # C
    "brazil": "巴西", "bra": "巴西",
    "morocco": "摩洛哥", "mar": "摩洛哥",
    "haiti": "海地", "hai": "海地",
    "scotland": "苏格兰", "sco": "苏格兰",
    # D
    "usa": "美国", "united states": "美国", "usmnt": "美国",
    "paraguay": "巴拉圭", "par": "巴拉圭",
    "australia": "澳大利亚", "aus": "澳大利亚",
    "turkey": "土耳其", "tur": "土耳其",
    # E
    "germany": "德国", "ger": "德国",
    "curacao": "库拉索", "cuw": "库拉索",
    "ivory coast": "科特迪瓦", "cote d'ivoire": "科特迪瓦", "civ": "科特迪瓦",
    "ecuador": "厄瓜多尔", "ecu": "厄瓜多尔",
    # F
    "netherlands": "荷兰", "ned": "荷兰",
    "japan": "日本", "jpn": "日本",
    "sweden": "瑞典", "swe": "瑞典",
    "tunisia": "突尼斯", "tun": "突尼斯",
    # G
    "spain": "西班牙", "esp": "西班牙",
    "cape verde": "佛得角", "cpv": "佛得角",
    "saudi arabia": "沙特", "korea saudi": "沙特", "ksa": "沙特",
    "uruguay": "乌拉圭", "uru": "乌拉圭",
    # H
    "belgium": "比利时", "bel": "比利时",
    "egypt": "埃及", "egy": "埃及",
    "iran": "伊朗", "irn": "伊朗",
    "new zealand": "新西兰", "nzl": "新西兰",
    # I
    "france": "法国", "fra": "法国",
    "senegal": "塞内加尔", "sen": "塞内加尔",
    "iraq": "伊拉克", "irq": "伊拉克",
    "norway": "挪威", "nor": "挪威",
    # J
    "argentina": "阿根廷", "arg": "阿根廷",
    "algeria": "阿尔及利亚", "alg": "阿尔及利亚",
    "austria": "奥地利", "aut": "奥地利",
    "jordan": "约旦", "jor": "约旦",
    # K
    "portugal": "葡萄牙", "por": "葡萄牙",
    "dr congo": "刚果民主共和国", "congo dr": "刚果民主共和国", "cod": "刚果民主共和国",
    "uzbekistan": "乌兹别克斯坦", "uzb": "乌兹别克斯坦",
    "colombia": "哥伦比亚", "col": "哥伦比亚",
    # L
    "england": "英格兰", "eng": "英格兰",
    "croatia": "克罗地亚", "cro": "克罗地亚",
    "ghana": "加纳", "gha": "加纳",
    "panama": "巴拿马", "pan": "巴拿马",
    # others
    "korea": "韩国", "korea republic": "韩国", "kor": "韩国",
    "czech": "捷克", "czech republic": "捷克", "cze": "捷克",
    "qatar": "卡塔尔", "qat": "卡塔尔",
    "switzerland": "瑞士", "sui": "瑞士",
    "poland": "波兰", "pol": "波兰",
    "denmark": "丹麦", "den": "丹麦",
    "serbia": "塞尔维亚", "srb": "塞尔维亚",
    "nigeria": "尼日利亚", "nga": "尼日利亚",
    "cameroon": "喀麦隆", "cmr": "喀麦隆",
}

# Baidu API (fallback)
BAIDU_API = "https://tiyu.baidu.com/api/na/subscribe?subscribeID=69&appKey=NA_matchschedule"

# World Cup start date for historical data scraping
WC_START = datetime.date(2026, 6, 11)

# Server-side cache
_history_cache = {}
_cache_full_ts = 0.0
CACHE_TTL = 600  # refresh full history every 10 minutes


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HTML_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/scores":
            self.serve_scores()
        elif self.path == "/" or self.path == "/index.html":
            self.path = "/worldcup.html"
            super().do_GET()
        elif self.path.startswith("/.git") or self.path.startswith("/.venv"):
            self.send_error(403, "Forbidden")
        else:
            super().do_GET()

    def serve_scores(self):
        """Try ESPN first, fall back to Baidu."""
        errors = []

        # --- Try ESPN ---
        try:
            espn_matches = fetch_espn_scores()
            if espn_matches:
                self.send_json({
                    "matches": espn_matches,
                    "updated": datetime.datetime.now().isoformat(),
                    "source": "espn.com"
                })
                return
        except Exception as e:
            errors.append(f"ESPN: {e}")

        # --- Fallback: Baidu ---
        try:
            req = urllib.request.Request(BAIDU_API, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://tiyu.baidu.com/"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8")

            matches = parse_baidu_scores(html)

            # Merge with historical scores (cached server-side)
            try:
                today = datetime.date.today()
                recent = []
                for offset in (0, 1):
                    date_str = (today - datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
                    recent.extend(fetch_page_scores(date_str))

                global _history_cache, _cache_full_ts
                if _time.time() - _cache_full_ts > CACHE_TTL:
                    print(f"[{datetime.datetime.now():%H:%M:%S}] 刷新完整历史比分缓存...", flush=True)
                    new_cache = {}
                    delta = (today - WC_START).days
                    fetched_dates = 0
                    for offset in range(delta + 1):
                        date_str = (today - datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
                        if offset <= 1:
                            continue
                        page_matches = fetch_page_scores(date_str)
                        if page_matches:
                            new_cache[date_str] = page_matches
                            fetched_dates += 1
                    _history_cache = new_cache
                    _cache_full_ts = _time.time()
                    print(f"[{datetime.datetime.now():%H:%M:%S}] 缓存了 {fetched_dates} 天历史数据", flush=True)

                all_page_matches = list(recent)
                for date_str, page_matches in _history_cache.items():
                    all_page_matches.extend(page_matches)

                deduped = {}
                for m in all_page_matches:
                    k = (m["home"], m["away"])
                    if k not in deduped:
                        deduped[k] = m
                all_page_matches = list(deduped.values())

                merged = []
                page_keys = {(m["home"], m["away"]) for m in all_page_matches}
                for m in matches:
                    key = (m["home"], m["away"])
                    if key in page_keys:
                        for pm in all_page_matches:
                            if pm["home"] == m["home"] and pm["away"] == m["away"]:
                                merged.append(pm)
                                break
                    else:
                        merged.append(m)
                sub_keys = {(m["home"], m["away"]) for m in matches}
                for pm in all_page_matches:
                    if (pm["home"], pm["away"]) not in sub_keys:
                        merged.append(pm)
                matches = merged
            except Exception as e:
                print(f"[{datetime.datetime.now():%H:%M:%S}] Baidu page fallback failed: {e}", flush=True)

            self.send_json({
                "matches": matches,
                "updated": datetime.datetime.now().isoformat(),
                "source": "tiyu.baidu.com"
            })
            return

        except Exception as e:
            errors.append(f"Baidu: {e}")
            self.send_json({
                "error": "; ".join(errors),
                "updated": datetime.datetime.now().isoformat(),
                "matches": []
            }, status=500)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        if "/api/scores" in str(args):
            print(f"[{datetime.datetime.now():%H:%M:%S}] /api/scores", flush=True)


# ========== ESPN API ==========

def fetch_espn_scores():
    """Fetch live/completed scores from ESPN API.
    Requests yesterday + today + tomorrow to handle timezone differences.
    Returns list of {home, away, score, status} dicts with CHINESE team names.
    """
    all_matches = []
    seen_ids = set()

    # Get yesterday, today, tomorrow dates in YYYYMMDD format
    today = datetime.date.today()
    dates = []
    for offset in (-1, 0, 1):
        d = today + datetime.timedelta(days=offset)
        dates.append(d.strftime("%Y%m%d"))

    for date_str in dates:
        url = build_espn_url(date_str)
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.espn.com/",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            for event in data.get("events", []):
                # Deduplicate by event id
                event_id = event.get("id")
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)

                matches = parse_espn_event(event)
                if matches:
                    all_matches.extend(matches)
        except Exception as e:
            print(f"[ESPN] Failed to fetch {date_str}: {e}", flush=True)
            continue

    print(f"[ESPN] Fetched {len(all_matches)} matches from {len(dates)} dates", flush=True)
    return all_matches


def parse_espn_event(event):
    """Parse a single ESPN event into match dict. Returns list of matches."""
    competitions = event.get("competitions", [])
    if not competitions:
        return []
    comp = competitions[0]

    competitors = comp.get("competitors", [])
    if len(competitors) < 2:
        return []

    # Find home/away
    home_c = None
    away_c = None
    for c in competitors:
        if c.get("homeAway") == "home":
            home_c = c
        elif c.get("homeAway") == "away":
            away_c = c

    if not home_c or not away_c:
        home_c = competitors[0]
        away_c = competitors[1]

    # Get English team names
    home_en = home_c.get("team", {}).get("displayName", "")
    away_en = away_c.get("team", {}).get("displayName", "")
    home_abbr = home_c.get("team", {}).get("abbreviation", "").lower()
    away_abbr = away_c.get("team", {}).get("abbreviation", "").lower()

    # Convert to Chinese
    home_cn = _en_to_cn(home_en, home_abbr)
    away_cn = _en_to_cn(away_en, away_abbr)
    if not home_cn or not away_cn:
        return []

    # Get scores (ESPN: competitors[].scores.value)
    home_score = home_c.get("scores", {}).get("value")
    away_score = away_c.get("scores", {}).get("value")
    if home_score is not None:
        home_score = int(home_score)
    if away_score is not None:
        away_score = int(away_score)

    # Get status
    status_info = comp.get("status", {})
    type_info = status_info.get("type", {})
    status_type_id = str(type_info.get("id", ""))
    status_completed = type_info.get("completed", False)
    status_display = type_info.get("detail", "")

    # Determine our status
    if status_completed:
        status = "done"
    elif status_type_id == "1":  # Scheduled
        status = "upcoming"
    else:
        status = "live"

    # Check for penalty shootout
    home_pen = home_c.get("shootoutScores", {}).get("value")
    away_pen = away_c.get("shootoutScores", {}).get("value")
    if home_pen is not None:
        home_pen = int(home_pen)
    if away_pen is not None:
        away_pen = int(away_pen)

    score_data = None
    if home_score is not None and away_score is not None:
        score_data = {"home": home_score, "away": away_score}
        if home_pen is not None and away_pen is not None:
            score_data["homePen"] = home_pen
            score_data["awayPen"] = away_pen

    return [{
        "home": home_cn,
        "away": away_cn,
        "score": score_data,
        "status": status,
        "round": comp.get("stage", {}).get("name", ""),
        "time": status_display,
    }]


def _en_to_cn(en_name, abbr=""):
    """Convert English team name to Chinese using mapping dict."""
    if not en_name and not abbr:
        return None
    key = (en_name or "").strip().lower()
    if key in TEAM_EN_TO_CN:
        return TEAM_EN_TO_CN[key]
    if abbr and abbr in TEAM_EN_TO_CN:
        return TEAM_EN_TO_CN[abbr]
    # Try partial match
    for k, v in TEAM_EN_TO_CN.items():
        if k in key or key in k:
            return v
    return en_name  # fallback: return English name as-is


# ========== Baidu API (fallback) ==========

def parse_baidu_scores(html):
    """Parse Baidu Sports HTML into match data."""
    html = unescape(html)
    matches = []

    items = re.split(r'<a[^>]*wa-tiyu-schedule-item[^>]*>', html)
    if items:
        items = items[1:]

    for item in items:
        names = re.findall(r'<span[^>]*c-line-clamp1[^>]*>\s*(.+?)\s*</span>', item, re.DOTALL)
        scores = re.findall(r'<div[^>]*team-row-score[^>]*>\s*<span[^>]*>\s*(\S+?)\s*</span>', item, re.DOTALL)
        status_match = re.search(r'<div[^>]*status-text[^>]*>\s*(.+?)\s*</div>', item, re.DOTALL)
        round_match = re.search(r'<p[^>]*c-line-clamp2[^>]*>\s*(.+?)\s*</p>', item, re.DOTALL)
        time_match = re.search(r'<p[^>]*>\s*(\d{2}:\d{2})\s*</p>', item, re.DOTALL)

        if len(names) >= 2 and len(scores) >= 2:
            status_text = status_match.group(1).strip() if status_match else "未知"
            round_text = round_match.group(1).strip() if round_match else ""
            match_time = time_match.group(1) if time_match else ""

            status = "upcoming"
            if "已结束" in status_text or "完赛" in status_text:
                status = "done"
            elif "进行中" in status_text or "中场" in status_text:
                status = "live"
            elif "未开赛" in status_text:
                status = "upcoming"
            elif "取消" in status_text or "推迟" in status_text or "中止" in status_text:
                continue

            if not ("决赛" in round_text or "小组" in round_text):
                continue

            home_name = names[0].strip()
            away_name = names[1].strip()
            home_score_raw = scores[0].strip()
            away_score_raw = scores[1].strip()

            score_data = None
            hm = re.match(r'^(\d+)(?:\[(\d+)\])?$', home_score_raw)
            am = re.match(r'^(\d+)(?:\[(\d+)\])?$', away_score_raw)
            if hm and am:
                score_data = {"home": int(hm.group(1)), "away": int(am.group(1))}
                if hm.group(2) or am.group(2):
                    score_data["homePen"] = int(hm.group(2) or 0)
                    score_data["awayPen"] = int(am.group(2) or 0)

            matches.append({
                "home": home_name,
                "away": away_name,
                "score": score_data,
                "status": status,
                "round": round_text,
                "time": match_time
            })

    return matches


def fetch_page_scores(date_str):
    """Scrape al/match page for completed matches on a given date."""
    url = (f"https://tiyu.baidu.com/al/match"
            f"?match=%E4%B8%96%E7%95%8C%E6%9D%AF&date_time={date_str}"
            f"&tab=%E8%B5%9B%E7%A8%8B&from=baidu_aladdin")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://tiyu.baidu.com/"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    text = re.sub(r'<[^>]+>', ' ', raw)
    text = unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)

    pat_main = re.compile(
        r'(\d{2}:\d{2})\s+'
        r'([^0-9]+?)\s+'
        r'(\S+?)\s+'
        r'(\d+)\s*(?:\[(\d+)\])?'
        r'\s+'
        r'(\S+?)\s+'
        r'(\d+)\s*(?:\[(\d+)\])?'
        r'\s+已结束'
    )

    results = []
    seen = set()
    for m in pat_main.finditer(text):
        match_time = m.group(1)
        round_text = m.group(2).strip()
        home_name = m.group(3).strip()
        home_score = m.group(4)
        home_pen = m.group(5)
        away_name = m.group(6).strip()
        away_score = m.group(7)
        away_pen = m.group(8)

        key = (home_name, away_name, home_score, away_score)
        if key in seen:
            continue
        seen.add(key)

        if "小组赛" not in round_text and "世界杯" not in round_text.lower():
            continue

        sd = {"home": int(home_score), "away": int(away_score)}
        if home_pen or away_pen:
            sd["homePen"] = int(home_pen) if home_pen else 0
            sd["awayPen"] = int(away_pen) if away_pen else 0
        results.append({
            "home": home_name,
            "away": away_name,
            "score": sd,
            "status": "done",
            "round": round_text,
            "time": match_time
        })

    return results


if __name__ == "__main__":
    print(f"[{datetime.datetime.now():%H:%M:%S}] 世界杯比分代理服务启动 (ESPN + Baidu)", flush=True)
    print(f"  页面: http://localhost:{PORT}", flush=True)
    print(f"  比分接口: http://localhost:{PORT}/api/scores", flush=True)
    print(flush=True)

    server = http.server.ThreadingHTTPServer((BIND, PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()
