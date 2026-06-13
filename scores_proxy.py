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
from html import unescape

PORT = int(os.environ.get("PORT", 8765))
BIND = "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1"
HTML_DIR = os.path.dirname(os.path.abspath(__file__))
BAIDU_API = "https://tiyu.baidu.com/api/na/subscribe?subscribeID=69&appKey=NA_matchschedule"

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

            # Fallback: scrape al/match page for today's completed matches
            # that the subscribe API hasn't indexed yet
            try:
                page_matches = fetch_today_page_scores()
                # Merge: today-page completed results override subscribe data
                # Match by team names (Chinese)
                merged = []
                page_keys = {(m["home"], m["away"]) for m in page_matches}
                for m in matches:
                    key = (m["home"], m["away"])
                    if key in page_keys:
                        # Replace with fresher data from today's page
                        for pm in page_matches:
                            if pm["home"] == m["home"] and pm["away"] == m["away"]:
                                merged.append(pm)
                                break
                    else:
                        merged.append(m)
                # Add page matches not in subscribe at all
                sub_keys = {(m["home"], m["away"]) for m in matches}
                for pm in page_matches:
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
            home_score = scores[0].strip()
            away_score = scores[1].strip()

            score_data = None
            if home_score.isdigit() and away_score.isdigit():
                score_data = {"home": int(home_score), "away": int(away_score)}

            matches.append({
                "home": home_name,
                "away": away_name,
                "score": score_data,
                "status": status,
                "round": round_text,
                "time": match_time
            })

    return matches


def fetch_today_page_scores():
    """Fallback: scrape al/match page for today's completed matches
    that subscribe API hasn't indexed yet. Uses tag-stripped text extraction."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    url = f"https://tiyu.baidu.com/al/match?match=%E4%B8%96%E7%95%8C%E6%9D%AF&date_time={today}&tab=%E8%B5%9B%E7%A8%8B&from=baidu_aladdin"
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
    patterns = [
        # Done: 03:00 小组赛B组第1轮 加拿大 1 波黑 1 已结束
        re.compile(r'(\d{2}:\d{2})\s+(.+?)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+已结束'),
        # Alternative: no space between round and team: 03:00小组赛B组第1轮加拿大1波黑1已结束
        re.compile(r'(\d{2}:\d{2})[\s]*([^0-9]+?)[\s]*(\S+)[\s]+(\d+)[\s]+(\S+)[\s]+(\d+)[\s]+已结束'),
    ]

    results = []
    seen = set()
    for pat in patterns:
        for m in pat.finditer(text):
            match_time = m.group(1)
            round_text = m.group(2).strip()
            home_name = m.group(3).strip()
            home_score = m.group(4)
            away_name = m.group(5).strip()
            away_score = m.group(6)

            key = (home_name, away_name, home_score, away_score)
            if key in seen:
                continue
            seen.add(key)

            # Only World Cup matches
            if "小组赛" not in round_text and "世界杯" not in round_text.lower():
                continue

            results.append({
                "home": home_name,
                "away": away_name,
                "score": {"home": int(home_score), "away": int(away_score)},
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
