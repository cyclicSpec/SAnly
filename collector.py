import re
import requests


SINA_URL = "https://hq.sinajs.cn/list={codes}"
HEADERS = {"Referer": "https://finance.sina.com.cn"}

FIELD_MAP = {
    "name": 0, "open": 1, "yclose": 2, "price": 3,
    "high": 4, "low": 5, "volume": 8, "amount": 9,
    "date": 30, "time": 31,
}


def _sina_code(code):
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def fetch_realtime(watchlist):
    codes = [_sina_code(c) for c in watchlist]
    url = SINA_URL.format(codes=",".join(codes))
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = "gbk"
        return _parse(resp.text, watchlist)
    except requests.RequestException as e:
        print(f"[collector] HTTP 请求失败: {e}")
        return {}


def _parse(text, watchlist):
    results = {}
    code_map = {_sina_code(k): k for k in watchlist}

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'var hq_str_(\w+)="(.*)"', line)
        if not m:
            continue
        sina_code = m.group(1)
        raw = m.group(2)
        if not raw:
            continue
        fields = raw.split(",")
        if len(fields) < 32:
            continue

        key = code_map.get(sina_code)
        if not key:
            continue

        try:
            results[key] = {
                "name": fields[FIELD_MAP["name"]],
                "open": float(fields[FIELD_MAP["open"]] or 0),
                "yclose": float(fields[FIELD_MAP["yclose"]] or 0),
                "price": float(fields[FIELD_MAP["price"]] or 0),
                "high": float(fields[FIELD_MAP["high"]] or 0),
                "low": float(fields[FIELD_MAP["low"]] or 0),
                "volume": float(fields[FIELD_MAP["volume"]] or 0) * 100,
                "amount": float(fields[FIELD_MAP["amount"]] or 0) * 10000,
                "date": fields[FIELD_MAP["date"]],
                "time": fields[FIELD_MAP["time"]],
            }
        except (ValueError, IndexError):
            continue

    return results
