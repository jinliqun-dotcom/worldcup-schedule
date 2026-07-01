"""
Baidu Sports live score proxy server.
Serves worldcup.html on localhost + proxies Baidu API for live scores.
Zero quota usage - uses Baidu's free match data.

Usage: python3 scores_proxy.py
Then open http://localhost:8765 in browser.
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
BAIDU_API = "https://tiyu.baidu.com/api/na/subscribe?subscribeID=69&appKey=NA_matchschedule"

# World Cup start date for historical data scraping
WC_START = datetime.date(2026, 6, 11)

# Server-side cache: {date_str: [matches], ...}
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
        try:
            req = urllib.request.Request(BAIDU_API, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://tiyu.baidu.com/"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8")

            matches = parse_scores(html)

            # Merge with historical scores (cached server-side)
            try:
                today = datetime.date.today()
                # Always refresh today + yesterday from page (live data)
                recent = []
                for offset in (0, 1):
                    date_str = (today - datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
                    recent.extend(fetch_page_scores(date_str))

                # Full history: fetch all WC dates if cache expired
                global _history_cache, _cache_full_ts
                if _time.time() - _cache_full_ts > CACHE_TTL:
                    print(f"[{datetime.datetime.now():%H:%M:%S}] 刷新完整历史比分缓存...", flush=True)
                    new_cache = {}
                    delta = (today - WC_START).days
                    fetched_dates = 0
                    for offset in range(delta + 1):
                        date_str = (today - datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
                        # Skip today+yesterday (already fetched fresh above)
                        if offset <= 1:
                            continue
                        page_matches = fetch_page_scores(date_str)
                        if page_matches:
                            new_cache[date_str] = page_matches
                            fetched_dates += 1
                    _history_cache = new_cache
                    _cache_full_ts = _time.time()
                    print(f"[{datetime.datetime.now():%H:%M:%S}] 缓存了 {fetched_dates} 天历史数据", flush=True)

                # Collect: recent (fresh) + history cache
                all_page_matches = list(recent)
                for date_str, page_matches in _history_cache.items():
                    all_page_matches.extend(page_matches)

                # Deduplicate page matches by (home, away) key
                deduped = {}
                for m in all_page_matches:
                    k = (m["home"], m["away"])
                    if k not in deduped:
                        deduped[k] = m
                all_page_matches = list(deduped.values())

                # Merge: page results override subscribe data
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
                # Add page matches not in subscribe at all
                sub_keys = {(m["home"], m["away"]) for m in matches}
                for pm in all_page_matches:
                    if (pm["home"], pm["away"]) not in sub_keys:
                        merged.append(pm)
                matches = merged
            except Exception as e:
                print(f"[{datetime.datetime.now():%H:%M:%S}] page fallback failed: {e}", flush=True)

            self.send_json({
                "matches": matches,
                "updated": datetime.datetime.now().isoformat(),
                "source": "tiyu.baidu.com"
            })
        except Exception as e:
            self.send_json({"error": str(e), "updated": datetime.datetime.now().isoformat()}, status=500)

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
            print(f"[{datetime.datetime.now():%H:%M:%S}] /api/scores")


def parse_scores(html):
    """Parse Baidu Sports HTML into match data."""
    html = unescape(html)
    matches = []

    # Each match is in <a class="c-blocka wa-tiyu-schedule-item">
    # Split by schedule items
    items = re.split(r'<a[^>]*wa-tiyu-schedule-item[^>]*>', html)
    # Remove anything before first item (header)
    if items:
        items = items[1:]

    for item in items:
        # Extract name, score, status from each match item
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

            home_name = names[0].strip()
            away_name = names[1].strip()
            home_score_raw = scores[0].strip()
            away_score_raw = scores[1].strip()

            # Parse penalty scores: "2", "1[3]", "[4]" etc.
            score_data = None
            homePen = None
            awayPen = None
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
    """Scrape al/match page for completed matches on a given date.
    date_str: YYYY-MM-DD format."""
    url = f"https://tiyu.baidu.com/al/match?match=%E4%B8%96%E7%95%8C%E6%9D%AF&date_time={date_str}&tab=%E8%B5%9B%E7%A8%8B&from=baidu_aladdin"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://tiyu.baidu.com/"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # Strip all HTML tags to get plain text
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = unescape(text)
    # Collapse whitespace but keep line breaks for structure
    text = re.sub(r'[ \t]+', ' ', text)

    # Match completed matches: HH:MM round_text team1 score1 team2 score2 已结束
    # Also match: HH:MM round_text team1 - team2 - 未开赛 (to avoid false matches)
    # Match done: time round team score [pen] team score [pen] 已结束
    # e.g. 德国 1 [3] 巴拉圭 1 [4] 已结束
    pat_main = re.compile(
        r'(\d{2}:\d{2})\s+'   # time
        r'([^0-9]+?)\s+'       # round text
        r'(\S+?)\s+'           # home team
        r'(\d+)\s*(?:\[(\d+)\])?'  # home score + optional [pen]
        r'\s+'
        r'(\S+?)\s+'           # away team
        r'(\d+)\s*(?:\[(\d+)\])?'  # away score + optional [pen]
        r'\s+已结束'
    )

    results = []
    seen = set()
    for m in pat_main.finditer(text):
        match_time = m.group(1)
        round_text = m.group(2).strip()
        home_name = m.group(3).strip()
        home_score = m.group(4)
        home_pen = m.group(5)  # may be None
        away_name = m.group(6).strip()
        away_score = m.group(7)
        away_pen = m.group(8)  # may be None

            key = (home_name, away_name, home_score, away_score)
            if key in seen:
                continue
            seen.add(key)

            # Only World Cup matches
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
    import sys
    print(f"[{datetime.datetime.now():%H:%M:%S}] 世界杯比分代理服务启动", flush=True)
    print(f"  页面: http://localhost:{PORT}", flush=True)
    print(f"  比分接口: http://localhost:{PORT}/api/scores", flush=True)
    print(flush=True)

    server = http.server.ThreadingHTTPServer((BIND, PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()
